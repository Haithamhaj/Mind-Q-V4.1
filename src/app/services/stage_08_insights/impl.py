from __future__ import annotations

import json
import math
import shutil
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import importlib.metadata as importlib_metadata
import numpy as np
import polars as pl  # type: ignore
import jsonschema  # type: ignore
import yaml  # type: ignore
from zoneinfo import ZoneInfo

from shared.logging import setup_logger, write_jsonl  # type: ignore
from .settings import Stage08Settings

FORBIDDEN_WORDS = {"cause", "causal", "impact", "affect"}
EMAIL_RE = __import__("re").compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", __import__("re").IGNORECASE)
PHONE_RE = __import__("re").compile(r"(?:(?:\+?[\d]{1,3})?[\s\-]?\d[\d\-\s]{5,}\d)")
IBAN_RE = __import__("re").compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{10,30}$", __import__("re").IGNORECASE)
TOKEN_MAXLEN = 40
EPS = 1e-12
DEFAULT_KPI_NAMES: Tuple[str, ...] = ("cod_amount", "sla_achieved", "rto_rate", "rto_flag")
BACKEND_ROOT = Path(__file__).resolve().parents[4]
KPI_CONTRACT_PATH = BACKEND_ROOT / "contracts" / "kpis.yml"
DEFAULT_GEO_COLUMN_HINTS = {"latitude", "lat", "longitude", "lon", "lng"}
DEFAULT_GEO_WARN_THRESHOLD = 0.6
DEFAULT_GEO_STOP_THRESHOLD = 0.95
ADVANCED_PAYLOAD_MAX_BYTES = 750_000  # ~0.75 MB cap per derived JSON field


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _load_policy(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return float(value)
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_ratio(numerator: Any, denominator: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Robust division helper that tolerates strings, numpy scalars, and None.
    Returns `default` when the division cannot be performed or denominator is zero.
    """
    try:
        num = float(numerator)
        den = float(denominator)
        if den == 0:
            return default
        return num / den
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def _z_score(series: pl.Series) -> pl.Series:
    if series.is_empty():
        return series
    mean = float(series.mean())
    std = float(series.std())
    if std <= 0 or math.isnan(std):
        return pl.Series(series.name, [math.nan] * series.len(), dtype=pl.Float64)
    return (series - mean) / std


def _anomalies(
    df: pl.DataFrame,
    by: Sequence[str],
    column: str,
    *,
    sigma: float = 3.0,
    min_n: int = 300,
) -> pl.DataFrame:
    if column not in df.columns:
        return pl.DataFrame()
    group_cols = [col for col in by if col in df.columns]
    if not group_cols:
        return pl.DataFrame()
    grouped = (
        df.group_by(group_cols)
        .agg(
            [
                pl.col(column).count().alias("_n"),
                pl.col(column).mean().alias("_m"),
                pl.col(column).std().alias("_s"),
            ]
        )
        .filter(pl.col("_n") >= min_n)
    )
    if grouped.is_empty():
        return grouped
    z_series = _z_score(grouped["_m"])
    grouped = grouped.with_columns(pl.Series("z_score", z_series))
    return grouped.filter(pl.col("z_score").abs() > sigma)


def _mask_token(token: str) -> str:
    if not token:
        return token
    if EMAIL_RE.search(token) or PHONE_RE.fullmatch(token) or IBAN_RE.fullmatch(token):
        return "[PII]"
    digits = __import__("re").sub(r"\D", "", token)
    if len(digits) >= 7:
        return "[PII]"
    if len(token) > TOKEN_MAXLEN:
        return token[: TOKEN_MAXLEN - 3] + "..."
    return token


def _sanitize_language(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in FORBIDDEN_WORDS):
        raise ValueError("Forbidden causal wording detected in generated text")
    return text


def _coalesce_datetime(value: Any, tz: ZoneInfo) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=tz)
        return value.astimezone(tz)
    return None


def _human_window(start: Optional[datetime], end: Optional[datetime]) -> Optional[str]:
    if not start or not end:
        return None
    return f"{start.date().isoformat()} -> {end.date().isoformat()}"


def _load_kpi_names() -> List[str]:
    if KPI_CONTRACT_PATH.exists():
        try:
            payload = yaml.safe_load(KPI_CONTRACT_PATH.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover - defensive
            payload = None
        candidates: Set[str] = set()

        def _collect(value: Any) -> None:
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    candidates.add(stripped)
            elif isinstance(value, dict):
                for key, val in value.items():
                    if isinstance(val, str) and key.lower() in {"name", "kpi", "id", "field", "metric"}:
                        stripped = val.strip()
                        if stripped:
                            candidates.add(stripped)
                    _collect(val)
            elif isinstance(value, list):
                for item in value:
                    _collect(item)

        if payload:
            _collect(payload)
        if candidates:
            return sorted(candidates)
    return list(DEFAULT_KPI_NAMES)


def _normalize_correlations(
    entries: Sequence[Mapping[str, Any]], kpi_names: Sequence[str]
) -> Tuple[List[Dict[str, Any]], bool]:
    if not entries:
        return [], False
    if all(isinstance(entry, Mapping) and "kpi" in entry and "feature" in entry for entry in entries):
        return [dict(entry) for entry in entries], False
    kpi_lookup = {name.lower() for name in kpi_names}
    normalized: List[Dict[str, Any]] = []
    fallback_used = False
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        f1 = entry.get("f1")
        f2 = entry.get("f2")
        r_value = entry.get("r")
        n_value = entry.get("n")
        if not isinstance(f1, str) or not isinstance(f2, str):
            continue
        f1_l = f1.lower()
        f2_l = f2.lower()
        if f1_l in kpi_lookup and f2_l not in kpi_lookup:
            normalized.append({"kpi": f1, "feature": f2, "r": r_value, "n": n_value})
            fallback_used = True
        elif f2_l in kpi_lookup and f1_l not in kpi_lookup:
            normalized.append({"kpi": f2, "feature": f1, "r": r_value, "n": n_value})
            fallback_used = True
    return normalized, fallback_used


def _direction_from_value(value: float) -> str:
    if math.isnan(value):
        return "unknown"
    if value > 0.05:
        return "positive"
    if value < -0.05:
        return "negative"
    return "mixed"


def _ensure_numeric(series: pl.Series) -> pl.Series:
    if series.dtype.is_numeric() or series.dtype == pl.Boolean:
        return series.cast(pl.Float64)
    try:
        return series.cast(pl.Float64, strict=False)
    except (pl.exceptions.ComputeError, TypeError, ValueError):
        try:
            return series.to_physical().cast(pl.Float64, strict=False)
        except Exception:
            return pl.Series(series.name or "value", [None] * series.len(), dtype=pl.Float64)


def _is_binary(series: pl.Series) -> bool:
    non_null = series.drop_nulls()
    unique = non_null.n_unique()
    if unique == 0:
        return False
    if series.dtype == pl.Boolean:
        return True
    if series.dtype.is_integer() and unique <= 2:
        values = set(non_null.unique().to_list())
        return values <= {0, 1} or values <= {-1, 0, 1} or len(values) <= 2
    return False


def _is_categorical(series: pl.Series) -> bool:
    return series.dtype in {pl.Utf8, pl.Categorical} or (series.dtype.is_integer() and series.n_unique() <= 25)


def _maybe_binary_to_float(series: pl.Series) -> pl.Series:
    if _is_binary(series):
        return series.cast(pl.Float64)
    return series


def _string_blank_count(series: pl.Series) -> int:
    try:
        stripped = series.cast(pl.Utf8, strict=False).str.strip_chars()
        return int((stripped == "").sum())
    except Exception:
        return 0


def _screen_columns(df: pl.DataFrame, settings: Stage08Settings) -> tuple[pl.DataFrame, Dict[str, Any]]:
    threshold = _clamp(settings.missing_ratio_threshold, 0.0, 1.0)
    total_rows = df.height
    if total_rows == 0:
        return df, {
            "threshold": threshold,
            "rows": 0,
            "total_columns": len(df.columns),
            "kept": [],
            "dropped": [],
        }
    protected = set(filter(None, [settings.timestamp_col]))
    coverage_entries: List[Dict[str, Any]] = []
    keep_columns: List[str] = []
    for column in df.columns:
        series = df[column]
        nulls = int(series.null_count())
        blanks = _string_blank_count(series) if series.dtype in {pl.Utf8, pl.Categorical} else 0
        missing_ratio = _safe_ratio(nulls + blanks, total_rows, default=1.0) or 0.0
        entry = {
            "column": column,
            "dtype": str(series.dtype),
            "missing": nulls + blanks,
            "missing_ratio": missing_ratio,
            "protected": column in protected,
        }
        drop = missing_ratio >= threshold and column not in protected
        entry["dropped"] = drop
        coverage_entries.append(entry)
        if not drop:
            keep_columns.append(column)
    filtered_df = df.select(keep_columns) if keep_columns else df
    summary = {
        "threshold": threshold,
        "rows": total_rows,
        "total_columns": len(df.columns),
        "kept": [
            {
                "column": item["column"],
                "missing": item["missing"],
                "missing_ratio": item["missing_ratio"],
                "dtype": item["dtype"],
            }
            for item in coverage_entries
            if not item["dropped"]
        ],
        "dropped": [
            {
                "column": item["column"],
                "missing": item["missing"],
                "missing_ratio": item["missing_ratio"],
                "dtype": item["dtype"],
            }
            for item in coverage_entries
            if item["dropped"]
        ],
    }
    return filtered_df, summary


def _rankdata(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return np.array([], dtype=float)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        # average rank for ties (1-based)
        avg_rank = (i + j) / 2.0 + 1.0
        ranks[order[i : j + 1]] = avg_rank
        i = j + 1
    return ranks


@dataclass
class ScopeWindow:
    label: str
    start: Optional[datetime]
    end: Optional[datetime]


@dataclass
class StabilityComponents:
    time_score: Optional[float] = None
    segment_score: Optional[float] = None
    holdout_score: Optional[float] = None

    def aggregate(self) -> float:
        values = [value for value in (self.time_score, self.segment_score, self.holdout_score) if value is not None]
        if not values:
            return 0.5
        return float(sum(values) / len(values))


@dataclass
class CandidateFlags:
    small_n: bool = False
    simpson: bool = False
    may_conflict_with: Optional[str] = None


@dataclass
class CandidateRecord:
    kpi: str
    feature: str
    metric: str
    effect: float
    strength: float
    direction: str
    n: int
    coverage: float
    confidence: float
    bucket: str
    stability: StabilityComponents
    stability_score: float
    redundancy: Optional[float]
    signal_score: float
    segment: Optional[str] = None
    window: Optional[str] = None
    source: str = "numeric"
    notes: List[str] = field(default_factory=list)
    flags: CandidateFlags = field(default_factory=CandidateFlags)
    evidence: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    low_signal: bool = False
    nzv_override: bool = False

    def to_official_payload(self) -> Dict[str, Any]:
        payload = {
            "kpi": self.kpi,
            "relation": f"{self.feature} <-> {self.kpi}",
            "direction": self.direction,
            "strength": round(self.strength, 4),
            "confidence": round(self.confidence, 4),
            "coverage": round(_clamp(self.coverage, 0.0, 1.0), 4),
            "stability_score": round(self.stability_score, 4),
            "n": self.n,
            "bucket": self.bucket,
            "evidence": self.evidence,
            "source": self.source,
        }
        payload["segment"] = self.segment
        payload["window"] = self.window
        if self.nzv_override:
            payload["nzv_override"] = True
        if self.low_signal:
            payload["low_signal"] = True
        if self.notes:
            payload["notes"] = "; ".join(self.notes)
        return payload

    def to_candidate_payload(self) -> Dict[str, Any]:
        return {
            "kpi": self.kpi,
            "feature": self.feature,
            "metric": self.metric,
            "effect": self.effect,
            "strength": self.strength,
            "direction": self.direction,
            "n": self.n,
            "coverage": self.coverage,
            "confidence": self.confidence,
            "bucket": self.bucket,
            "stability_score": self.stability_score,
            "stability": {
                "time": self.stability.time_score,
                "segment": self.stability.segment_score,
                "holdout": self.stability.holdout_score,
            },
            "redundancy": self.redundancy,
            "signal_score": self.signal_score,
            "segment": self.segment,
            "window": self.window,
            "source": self.source,
            "notes": self.notes,
            "low_signal": self.low_signal,
            "nzv_override": self.nzv_override,
            "flags": {
                "small_n": self.flags.small_n,
                "simpson": self.flags.simpson,
                "may_conflict_with": self.flags.may_conflict_with,
            },
            "evidence": self.evidence,
            "diagnostics": self.diagnostics,
        }


OFFICIAL_REQUIRED_FIELDS = {"kpi", "relation", "direction", "strength", "confidence", "coverage", "stability_score", "n", "evidence"}
OFFICIAL_ALLOWED_FIELDS = OFFICIAL_REQUIRED_FIELDS | {"segment", "window", "bucket", "notes", "source", "low_signal", "nzv_override"}

CANDIDATE_REQUIRED_FIELDS = {
    "kpi",
    "feature",
    "metric",
    "effect",
    "strength",
    "direction",
    "n",
    "coverage",
    "confidence",
    "bucket",
    "stability_score",
    "stability",
    "redundancy",
    "signal_score",
    "segment",
    "window",
    "source",
    "notes",
    "flags",
    "evidence",
    "diagnostics",
}
CANDIDATE_ALLOWED_FIELDS = CANDIDATE_REQUIRED_FIELDS | {"strength", "low_signal", "nzv_override"}


def _validate_records(records: Sequence[Dict[str, Any]], required: set[str], allowed: set[str], label: str) -> None:
    for idx, record in enumerate(records):
        keys = set(record.keys())
        missing = required - keys
        extra = keys - allowed
        if missing or extra:
            raise ValueError(f"{label}[{idx}] schema mismatch. Missing={sorted(missing)} Extra={sorted(extra)}")
        if "evidence" in record and not isinstance(record["evidence"], list):
            raise ValueError(f"{label}[{idx}] evidence must be a list.")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_inputs(run_id: str, settings: Stage08Settings) -> Dict[str, Path]:
    base = Path(settings.artifacts_root) / run_id
    corr_dir = base / "stage_07_correlations"
    readiness_dir = base / "stage_07_readiness"
    feature_report_dir = base / "stage_07_5_feature_report"
    knime_base = base / "phase_07_knime"
    knime_profile_dir = knime_base / "profile"
    knime_outputs_dir = knime_base / "outputs"
    analytics_base = base / "phase_07_analytics"
    analytics_profile_dir = analytics_base / "profile"
    analytics_outputs_dir = analytics_base / "outputs"

    correlations_kpi = corr_dir / "correlations_kpi.json"
    if not correlations_kpi.exists():
        alt_kpi = readiness_dir / "correlations_kpi.json"
        if alt_kpi.exists():
            correlations_kpi = alt_kpi
    correlations_legacy = corr_dir / "correlations.json"

    def _resolve_optional(candidates: Sequence[Path], default: Path) -> Path:
        for candidate in candidates:
            if candidate and candidate.exists():
                return candidate
        return default

    def _resolve_forecast_source() -> Path:
        forecast_candidates: List[Path] = []
        for pattern in ("orders_forecast*.parquet", "forecast*.parquet"):
            forecast_candidates.extend(sorted(analytics_outputs_dir.glob(pattern)))
            forecast_candidates.extend(sorted(knime_outputs_dir.glob(pattern)))
        for directory in (
            analytics_base / "transforms" / "forecast",
            knime_base / "transforms" / "forecast",
        ):
            if directory.exists():
                forecast_candidates.extend(sorted(directory.glob("*.parquet")))
        for candidate in forecast_candidates:
            if candidate.exists():
                return candidate
        if analytics_outputs_dir.exists():
            return analytics_outputs_dir / "forecast.parquet"
        return knime_outputs_dir / "orders_forecast.parquet"

    paths = {
        "features": base / "stage_06_feature_eng" / "features.parquet",
        "correlations": correlations_kpi if correlations_kpi.exists() else correlations_legacy,
        "correlations_source": correlations_legacy,
        "redundancy": corr_dir / "redundancy.json",
        "text_profile": base / "stage_03_5_textops" / "text_profile.json",
        "sentiment": base / "stage_03_5_textops" / "sentiment_features.parquet",
        "text_findings": base / "stage_03_5_textops" / "quality_findings.json",
        "layer2_variance": feature_report_dir / "variance_analysis.json",
        "layer2_compare": feature_report_dir / "comparative_summary.json",
        "layer2_heatmap": feature_report_dir / "heatmap_matrix.json",
        "layer2_candidate": _resolve_optional(
            [
                analytics_profile_dir / "layer2_candidate.json",
                knime_profile_dir / "layer2_candidate.json",
            ],
            analytics_profile_dir / "layer2_candidate.json",
        ),
    }

    paths["cluster_summary"] = _resolve_optional(
        [
            analytics_outputs_dir / "cluster_summary.json",
            analytics_profile_dir / "cluster_summary.json",
            knime_outputs_dir / "cluster_summary.json",
            knime_profile_dir / "cluster_summary.json",
        ],
        analytics_outputs_dir / "cluster_summary.json",
    )
    paths["anomalies"] = _resolve_optional(
        [
            analytics_outputs_dir / "anomalies.json",
            analytics_profile_dir / "anomalies.json",
            knime_outputs_dir / "anomalies.json",
            knime_profile_dir / "anomalies.json",
        ],
        analytics_outputs_dir / "anomalies.json",
    )
    paths["correlation_matrix"] = _resolve_optional(
        [
            analytics_outputs_dir / "correlation_matrix.json",
            analytics_profile_dir / "correlation_matrix.json",
            knime_outputs_dir / "correlation_matrix.json",
            knime_profile_dir / "correlation_matrix.json",
        ],
        analytics_outputs_dir / "correlation_matrix.json",
    )
    paths["forecast"] = _resolve_forecast_source()
    paths["analytics_dq_summary"] = analytics_outputs_dir / "dq_summary.json"
    paths["analytics_forecast_summary"] = analytics_outputs_dir / "forecast_summary.json"
    paths["readiness_decision_manifest"] = readiness_dir / "decision_manifest.json"
    paths["readiness_diagnostics"] = readiness_dir / "diagnostics.json"
    paths["layer1_catalog"] = readiness_dir / "layer1_catalog.json"
    paths["layer1_preview"] = readiness_dir / "layer1_preview.json"
    paths["layer1_dataset"] = readiness_dir / "layer1_dataset.parquet"
    paths["llm_summary_metrics"] = base / "stage_07_6_llm_summary" / "metrics.json"

    missing = [name for name, path in paths.items() if name in {"features", "correlations", "redundancy"} and not path.exists()]
    if missing:
        raise FileNotFoundError(f"Stage 08 inputs missing for run_id={run_id}: {', '.join(missing)}")
    return paths


def _summarize_readiness(
    manifest: Optional[Mapping[str, Any]],
    diagnostics: Optional[Mapping[str, Any]],
    layer1_catalog: Optional[Mapping[str, Any]],
    layer1_preview_path: Path,
    layer1_dataset_path: Path,
) -> Dict[str, Any]:
    overlay: Dict[str, Any] = {
        "gate_status": (diagnostics or {}).get("gate_status"),
        "gate_reasons": (diagnostics or {}).get("gate_reasons") or (manifest or {}).get("reasons"),
        "actions": [],
        "layer1": {},
    }
    entries = []
    if manifest:
        raw_entries = manifest.get("entries") or []
        for entry in raw_entries[:10]:
            if isinstance(entry, Mapping):
                entries.append(
                    {
                        "action": entry.get("action"),
                        "reason": entry.get("reason"),
                        "features": entry.get("features"),
                    }
                )
    overlay["actions"] = entries
    if layer1_catalog:
        overlay["layer1"] = {
            "field_count": layer1_catalog.get("field_count"),
            "row_count": layer1_catalog.get("row_count"),
        }
    if layer1_preview_path.exists():
        overlay["layer1"]["preview"] = layer1_preview_path.as_posix()
    if layer1_dataset_path.exists():
        overlay["layer1"]["dataset"] = layer1_dataset_path.as_posix()
    return overlay


def _summarize_textops(
    text_profile: Optional[Mapping[str, Any]],
    findings: Optional[Mapping[str, Any]],
    sentiment_df: Optional[pl.DataFrame],
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "warnings": (findings or {}).get("warnings", []),
        "errors": (findings or {}).get("errors", []),
    }
    if sentiment_df is not None and not sentiment_df.is_empty():
        total = sentiment_df.height or 1
        negative = sentiment_df.filter(pl.col("sentiment_score") < -0.2).height
        summary["sentiment"] = {
            "negative_pct": round(negative / total, 4),
            "observations": total,
        }
    if text_profile:
        columns = text_profile.get("columns") or {}
        tokens: List[Dict[str, Any]] = []
        for column, info in columns.items():
            top_tokens = info.get("top_tokens") or []
            for token in top_tokens[:3]:
                if isinstance(token, Mapping):
                    tokens.append(
                        {
                            "column": column,
                            "token": token.get("t"),
                            "count": token.get("c"),
                        }
                    )
        summary["top_tokens"] = tokens[:5]
    return summary


def _summarize_analytics(
    dq_summary: Optional[Mapping[str, Any]],
    forecast_summary: Optional[Mapping[str, Any]],
    forecast_path: Path,
) -> Dict[str, Any]:
    overlay: Dict[str, Any] = {}
    if dq_summary:
        overlay["dq"] = {
            "total_rules": dq_summary.get("total_rules"),
            "failed": dq_summary.get("failed"),
            "critical_failures": dq_summary.get("critical_failures"),
        }
    if forecast_summary:
        overlay["forecast"] = {
            "horizon_days": forecast_summary.get("horizon_days"),
            "historical_days": forecast_summary.get("historical_days"),
        }
        if forecast_path.exists():
            overlay["forecast"]["dataset"] = forecast_path.as_posix()
    return overlay


def _summarize_llm(metrics: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not metrics:
        return {}
    return {
        "provider": metrics.get("provider"),
        "model": metrics.get("model"),
        "cache_hit": metrics.get("cache_hit"),
        "fallback_chain": metrics.get("fallback_chain", []),
    }


def _build_readiness_cards(readiness_overlay: Mapping[str, Any]) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    actions = readiness_overlay.get("actions") or []
    for entry in actions[:2]:
        if not isinstance(entry, Mapping):
            continue
        feature_list = entry.get("features") or []
        feature_text = ", ".join(feature_list) if isinstance(feature_list, list) else str(feature_list)
        cards.append(
            {
                "title": "Readiness guardrail",
                "what_we_see": entry.get("reason") or "Review readiness actions",
                "where": feature_text or "Data quality",
                "action_now": [entry.get("action") or "Review readiness decision."],
                "expected_effect": "Removes blockers before KNIME/BI",
                "priority": "High",
                "kpi": "data_quality",
                "window": "Pre-analytics",
                "n": None,
            }
        )
    return cards


def _build_dq_cards(analytics_overlay: Mapping[str, Any]) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    dq = analytics_overlay.get("dq") if isinstance(analytics_overlay, Mapping) else None
    if dq and dq.get("critical_failures"):
        cards.append(
            {
                "title": "Data quality risks",
                "what_we_see": f"{dq.get('critical_failures')} critical rule failures in Stage 07 analytics.",
                "where": "Analytics",
                "action_now": ["Address critical DQ failures highlighted in Stage 07 analytics."],
                "expected_effect": "Prevents misleading correlations",
                "priority": "High",
                "kpi": "data_quality",
                "window": "Validation",
                "n": None,
            }
        )
    return cards


def _build_textops_cards(textops_overlay: Mapping[str, Any], *, limit: int) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    top_tokens = textops_overlay.get("top_tokens") or []
    warnings = textops_overlay.get("warnings") or []
    sentiment = textops_overlay.get("sentiment") or {}
    if warnings:
        cards.append(
            {
                "title": "Customer sentiment flags",
                "what_we_see": warnings[0],
                "where": "TextOps",
                "action_now": ["Review SLA/TextOps findings and route to ops owner."],
                "expected_effect": "Proactive mitigation of customer pain points",
                "priority": "Medium",
                "kpi": "csat",
                "window": "TextOps",
                "n": None,
            }
        )
    if top_tokens:
        for token in top_tokens[:limit]:
            cards.append(
                {
                    "title": f"Feedback hotspot: {token.get('token')}",
                    "what_we_see": f"Appears in {token.get('column')} ({token.get('count')} mentions)",
                    "where": "TextOps",
                    "action_now": ["Trace impacted orders and respond to customers."],
                    "expected_effect": "Reduce repeated complaints",
                    "priority": "Medium",
                    "kpi": "csat",
                    "window": "TextOps",
                    "n": token.get("count"),
                }
            )
    if sentiment and sentiment.get("negative_pct", 0) > 0.25:
        cards.append(
            {
                "title": "High negative sentiment",
                "what_we_see": f"Negative tone detected in {sentiment.get('negative_pct'):.0%} of feedback",
                "where": "Customer feedback",
                "action_now": ["Escalate to customer success and adjust SOPs."],
                "expected_effect": "Protect NPS",
                "priority": "High",
                "kpi": "csat",
                "window": "TextOps",
                "n": sentiment.get("observations"),
            }
        )
    return cards


def _build_supplemental_cards(
    readiness_overlay: Mapping[str, Any],
    analytics_overlay: Mapping[str, Any],
    textops_overlay: Mapping[str, Any],
    llm_overlay: Mapping[str, Any],
    settings: Stage08Settings,
) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    if readiness_overlay:
        cards.extend(_build_readiness_cards(readiness_overlay))
    if analytics_overlay:
        cards.extend(_build_dq_cards(analytics_overlay))
    if textops_overlay:
        cards.extend(_build_textops_cards(textops_overlay, limit=getattr(settings, "textops_card_limit", 3)))
    if llm_overlay.get("provider") == "heuristic":
        cards.append(
            {
                "title": "LLM summary fallback",
                "what_we_see": "LLM provider unavailable; heuristics used instead.",
                "where": "LLM Summary",
                "action_now": ["Provide LLM credentials or re-run Stage 07.6."],
                "expected_effect": "Restores executive narratives",
                "priority": "Low",
                "kpi": "insights_completeness",
                "window": "Narratives",
                "n": None,
            }
        )
    return cards


def _apply_external_warnings(
    gate_status: str,
    gate_reasons: List[str],
    readiness_overlay: Mapping[str, Any],
    analytics_overlay: Mapping[str, Any],
    llm_overlay: Mapping[str, Any],
    *,
    enforce_readiness: bool,
) -> Tuple[str, List[str]]:
    status = gate_status
    reasons = list(gate_reasons)
    readiness_gate = readiness_overlay.get("gate_status") if isinstance(readiness_overlay, Mapping) else None
    if enforce_readiness and readiness_gate in {"WARN", "STOP"}:
        reasons.append(f"Stage 07 readiness reported {readiness_gate} status.")
        if readiness_gate == "STOP" and status == "PASS":
            status = "WARN"
    dq = analytics_overlay.get("dq") if isinstance(analytics_overlay, Mapping) else None
    if dq and dq.get("critical_failures"):
        reasons.append("Stage 07 analytics detected critical data quality failures.")
        if status == "PASS":
            status = "WARN"
    if llm_overlay.get("provider") == "heuristic":
        reasons.append("LLM summary fell back to heuristics; narratives may be conservative.")
    return status, reasons

def _infer_stage07_origin(path: Path) -> str:
    path_str = path.as_posix().lower()
    if "phase_07_analytics" in path_str:
        return "python_analytics"
    if "phase_07_knime" in path_str:
        return "knime"
    return "external"


def _apply_sampling(df: pl.DataFrame, settings: Stage08Settings, logger: Any) -> tuple[pl.DataFrame, Optional[Dict[str, Any]]]:
    population = df.height
    if population > settings.sampling_threshold_rows and settings.enable_sampling_over_5m:
        fraction = _clamp(settings.sample_fraction, 0.05, 1.0)
        sampled = df.sample(fraction=fraction, with_replacement=False, seed=settings.seed)
        info = {"enabled": True, "fraction": fraction, "population_rows": population, "sampled_rows": sampled.height}
        logger.info(json.dumps({"event": "sampling", **info}))
        return sampled, info
    return df, {"enabled": False, "population_rows": population}


def _run_profile(df: pl.DataFrame, timestamp_col: Optional[str], tz: ZoneInfo) -> Dict[str, Any]:
    profile: Dict[str, Any] = {"n_rows": df.height}
    if not timestamp_col or timestamp_col not in df.columns:
        return profile
    ts_series = df[timestamp_col].drop_nulls()
    if ts_series.len() == 0:
        return profile
    if not ts_series.dtype.is_temporal():
        return profile
    converted = ts_series.dt.convert_time_zone(str(tz))
    profile["window_start"] = _coalesce_datetime(converted.min(), tz).isoformat() if converted.len() else None
    profile["window_end"] = _coalesce_datetime(converted.max(), tz).isoformat() if converted.len() else None
    if profile["window_start"] and profile["window_end"]:
        start = datetime.fromisoformat(profile["window_start"])
        end = datetime.fromisoformat(profile["window_end"])
        profile["window_days"] = max((end - start).days, 0)
    return profile


def _missing_ratio(df: pl.DataFrame, columns: Sequence[str]) -> Dict[str, float]:
    ratios: Dict[str, float] = {}
    for column in columns:
        if column not in df.columns:
            ratios[column] = 1.0
            continue
        total = df.height
        if total == 0:
            ratios[column] = 1.0
            continue
        missing = df[column].null_count()
        ratio_value = _safe_ratio(missing, total, default=1.0)
        ratios[column] = 1.0 if ratio_value is None else float(ratio_value)
    return ratios


def _preflight_checks(
    df: pl.DataFrame,
    correlations: Sequence[Mapping[str, Any]],
    settings: Stage08Settings,
    tz: ZoneInfo,
    geo_policy: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    kpi_features = {(entry["kpi"], entry["feature"]) for entry in correlations if "kpi" in entry and "feature" in entry}
    critical_columns = sorted({column for pair in kpi_features for column in pair})
    if settings.timestamp_col:
        critical_columns.append(settings.timestamp_col)
    ratios = _missing_ratio(df, critical_columns)
    geo_policy = geo_policy or {}
    geo_columns_config = [str(col) for col in (geo_policy.get("columns") or [])]
    has_geo_config = bool(geo_columns_config) or any(
        key in geo_policy for key in ("missing_warn_threshold", "missing_stop_threshold")
    )
    geo_columns_lower = {col.lower() for col in geo_columns_config if isinstance(col, str)}
    geo_warn_threshold = float(geo_policy.get("missing_warn_threshold", settings.critical_missing_warn))
    geo_stop_threshold = float(geo_policy.get("missing_stop_threshold", settings.critical_missing_stop))
    allowed_geo_high = {
        str(col).lower()
        for col in (geo_policy.get("allow_high_missing_columns") or [])
        if isinstance(col, str) and col.strip()
    }
    if not has_geo_config:
        geo_columns_lower = set(DEFAULT_GEO_COLUMN_HINTS)
        allowed_geo_high = set(DEFAULT_GEO_COLUMN_HINTS)
        geo_warn_threshold = max(geo_warn_threshold, DEFAULT_GEO_WARN_THRESHOLD)
        geo_stop_threshold = max(geo_stop_threshold, DEFAULT_GEO_STOP_THRESHOLD)
    default_warn_threshold = settings.critical_missing_warn
    default_stop_threshold = settings.critical_missing_stop

    missing_blockers: Dict[str, float] = {}
    warning_columns: Dict[str, Tuple[float, float]] = {}

    future_dates = False
    future_rows = 0
    now = datetime.now(tz)
    if settings.timestamp_col and settings.timestamp_col in df.columns:
        ts_series = df[settings.timestamp_col].drop_nulls()
        if ts_series.len() > 0 and ts_series.dtype.is_temporal():
            converted = ts_series.dt.convert_time_zone(str(tz))
            future_mask = converted > now
            future_rows = int(future_mask.sum())
            future_dates = future_rows > 0

    profile = _run_profile(df, settings.timestamp_col, tz)
    status = "PASS"
    reasons: List[str] = []
    warning_messages: List[str] = []

    for column, ratio in ratios.items():
        normalized = column.lower()
        if normalized in geo_columns_lower:
            warn_threshold = geo_warn_threshold
            stop_threshold = geo_stop_threshold
            if normalized in allowed_geo_high:
                stop_threshold = 1.0
                warn_threshold = max(warn_threshold, DEFAULT_GEO_WARN_THRESHOLD)
        else:
            warn_threshold = default_warn_threshold
            stop_threshold = default_stop_threshold

        if ratio >= stop_threshold:
            missing_blockers[column] = ratio
            reasons.append(
                f"Critical column '{column}' missing ratio {ratio:.2%} exceeds {stop_threshold:.0%} threshold."
            )
        elif ratio >= warn_threshold:
            warning_columns[column] = (ratio, warn_threshold)
            warning_messages.append(
                f"Critical column '{column}' missing ratio {ratio:.2%} exceeds {warn_threshold:.0%} warning threshold."
            )

    if missing_blockers:
        status = "STOP"
    if future_dates:
        status = "STOP"
        reasons.append(f"Detected {future_rows} records with future timestamps in '{settings.timestamp_col}'.")

    return {
        "status": status,
        "reasons": reasons,
        "warnings": warning_messages,
        "profile": profile,
        "critical_missing": missing_blockers,
        "warning_columns": warning_columns,
        "future_rows": future_rows,
        "thresholds": {
            "geo_warn": geo_warn_threshold,
            "geo_stop": geo_stop_threshold,
            "default_warn": default_warn_threshold,
            "default_stop": default_stop_threshold,
        },
        "geo_columns": geo_columns_config,
    }


def _categorise_columns(df: pl.DataFrame, hints: Sequence[str]) -> Dict[str, str]:
    categories: Dict[str, str] = {}
    for column in df.columns:
        series = df[column]
        if column in hints or series.dtype.is_float():
            categories[column] = "numeric"
        elif _is_binary(series):
            categories[column] = "binary"
        elif _is_categorical(series):
            categories[column] = "categorical"
        elif series.dtype.is_numeric():
            categories[column] = "numeric"
        else:
            categories[column] = "other"
    return categories


def _phi_coefficient(a: float, b: float, c: float, d: float) -> float:
    denominator = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    if denominator == 0:
        return 0.0
    return ((a * d) - (b * c)) / denominator


def _risk_diff(a: float, b: float, c: float, d: float) -> float:
    p1 = a / (a + b) if (a + b) > 0 else 0.0
    p0 = c / (c + d) if (c + d) > 0 else 0.0
    return p1 - p0


def _odds_ratio(a: float, b: float, c: float, d: float) -> float:
    return ((a + EPS) * (d + EPS)) / ((b + EPS) * (c + EPS))


def _lift(a: float, b: float, c: float, d: float) -> float:
    p1 = a / (a + b) if (a + b) > 0 else 0.0
    p0 = c / (c + d) if (c + d) > 0 else 0.0
    if p0 == 0:
        return float("inf") if p1 > 0 else 0.0
    return p1 / p0


def _point_biserial(binary: pl.Series, numeric: pl.Series) -> float:
    num = _ensure_numeric(numeric).drop_nulls()
    bin_series = _maybe_binary_to_float(binary).drop_nulls().cast(pl.Float64)
    if num.len() == 0 or bin_series.len() == 0:
        return 0.0
    merged = pl.DataFrame({"bin": bin_series, "num": num}).drop_nulls()
    if merged.height < 3:
        return 0.0
    arr_bin = merged["bin"].to_numpy()
    arr_num = merged["num"].to_numpy()
    if arr_bin.std(ddof=0) == 0 or arr_num.std(ddof=0) == 0:
        return 0.0
    corr = float(np.corrcoef(arr_bin, arr_num)[0, 1])
    if math.isnan(corr):
        return 0.0
    return corr


def _cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    if len(group1) < 2 or len(group2) < 2:
        return 0.0
    mean1 = float(group1.mean())
    mean2 = float(group2.mean())
    var1 = float(group1.var(ddof=1))
    var2 = float(group2.var(ddof=1))
    pooled_std = math.sqrt(((len(group1) - 1) * var1 + (len(group2) - 1) * var2) / (len(group1) + len(group2) - 2))
    if pooled_std == 0:
        return 0.0
    return (mean1 - mean2) / pooled_std


def _cohens_d_ci(d_value: float, n1: int, n2: int, alpha: float = 0.05) -> Tuple[float, float]:
    if n1 < 2 or n2 < 2:
        return (d_value, d_value)
    se = math.sqrt((n1 + n2) / (n1 * n2) + (d_value**2) / (2 * (n1 + n2)))
    z = 1.96 if alpha == 0.05 else statistics.NormalDist().inv_cdf(1 - alpha / 2)  # type: ignore[attr-defined]
    return d_value - z * se, d_value + z * se


def _cramers_v(contingency: np.ndarray) -> float:
    if contingency.size == 0:
        return 0.0
    total = contingency.sum()
    if total == 0:
        return 0.0
    expected = np.outer(contingency.sum(axis=1), contingency.sum(axis=0)) / total
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = np.nansum(((contingency - expected) ** 2) / np.where(expected == 0, np.nan, expected))
    n = contingency.sum()
    if n == 0:
        return 0.0
    min_dim = min(contingency.shape) - 1
    if min_dim <= 0:
        return 0.0
    return math.sqrt((chi2 / n) / min_dim)


def _pearson_spearman(df: pl.DataFrame, x: str, y: str) -> Tuple[float, float]:
    if df.height < 3:
        return 0.0, 0.0
    arr_x = df[x].to_numpy()
    arr_y = df[y].to_numpy()
    pearson = 0.0
    if np.std(arr_x, ddof=0) > 0 and np.std(arr_y, ddof=0) > 0:
        pearson = float(np.corrcoef(arr_x, arr_y)[0, 1])
        if math.isnan(pearson):
            pearson = 0.0
    ranks_x = _rankdata(arr_x)
    ranks_y = _rankdata(arr_y)
    spearman = 0.0
    if np.std(ranks_x, ddof=0) > 0 and np.std(ranks_y, ddof=0) > 0:
        spearman = float(np.corrcoef(ranks_x, ranks_y)[0, 1])
        if math.isnan(spearman):
            spearman = 0.0
    return pearson, spearman


def _window_filters(df: pl.DataFrame, timestamp_col: Optional[str], tz: ZoneInfo, splits: Tuple[int, int]) -> Dict[str, ScopeWindow]:
    if not timestamp_col or timestamp_col not in df.columns:
        return {}
    ts_series = df[timestamp_col].drop_nulls()
    if ts_series.len() == 0 or not ts_series.dtype.is_temporal():
        return {}
    target_tz = str(tz)
    source_tz = getattr(ts_series.dtype, "time_zone", None)
    source_is_naive = source_tz in (None, "")
    try:
        if source_is_naive:
            converted = ts_series.dt.replace_time_zone(target_tz)
        else:
            converted = ts_series.dt.convert_time_zone(target_tz)
    except Exception:
        converted = ts_series
        source_is_naive = getattr(ts_series.dtype, "time_zone", None) in (None, "")
    end = converted.max()
    if end is None:
        return {}
    end_dt = _coalesce_datetime(end, tz)
    if not end_dt:
        return {}
    t1_end = end_dt
    t1_start = t1_end - timedelta(days=splits[1])
    t2_end = t1_start
    t2_start = t2_end - timedelta(days=splits[0])
    if source_is_naive:
        def _strip_tz(value: Optional[datetime]) -> Optional[datetime]:
            if value is None:
                return None
            return value.astimezone(tz).replace(tzinfo=None)

        t1_end = _strip_tz(t1_end)
        t1_start = _strip_tz(t1_start)
        t2_end = _strip_tz(t2_end)
        t2_start = _strip_tz(t2_start)
    return {
        "T2": ScopeWindow("T2", t2_start, t2_end),
        "T1": ScopeWindow("T1", t1_start, t1_end),
    }


def _filter_df(df: pl.DataFrame, mask: Optional[pl.Expr]) -> pl.DataFrame:
    if mask is None:
        return df
    return df.filter(mask)


def _compute_binary_binary(df: pl.DataFrame, feature: str, kpi: str) -> Dict[str, Any]:
    subset = df.select([feature, kpi]).drop_nulls()
    if subset.height == 0:
        return {"metric": "phi", "effect": 0.0, "strength": 0.0, "direction": "unknown", "n": 0, "details": {}}
    ones_feature = subset[feature] > 0
    ones_kpi = subset[kpi] > 0
    a = float((ones_feature & ones_kpi).sum())
    b = float((ones_feature & (~ones_kpi)).sum())
    c = float(((~ones_feature) & ones_kpi).sum())
    d = float(((~ones_feature) & (~ones_kpi)).sum())
    total = int(a + b + c + d)
    phi = _phi_coefficient(a, b, c, d)
    risk_diff = _risk_diff(a, b, c, d)
    odds_ratio = _odds_ratio(a, b, c, d)
    lift = _lift(a, b, c, d)
    strength = min(1.0, abs(phi))
    direction = _direction_from_value(risk_diff if not math.isnan(risk_diff) else phi)
    return {
        "metric": "phi",
        "effect": phi,
        "strength": strength,
        "direction": direction,
        "n": total,
        "details": {
            "risk_diff": risk_diff,
            "odds_ratio": odds_ratio,
            "lift": lift,
            "table": {"tp": a, "fp": b, "fn": c, "tn": d},
        },
    }


def _compute_binary_numeric(df: pl.DataFrame, binary_col: str, numeric_col: str) -> Dict[str, Any]:
    subset = df.select([binary_col, numeric_col]).drop_nulls()
    if subset.height < 3:
        return {"metric": "point_biserial_r", "effect": 0.0, "strength": 0.0, "direction": "unknown", "n": subset.height, "details": {}}
    pb = _point_biserial(subset[binary_col], subset[numeric_col])
    group1 = subset.filter(subset[binary_col] > 0)[numeric_col].to_numpy()
    group0 = subset.filter(subset[binary_col] <= 0)[numeric_col].to_numpy()
    d_value = _cohens_d(group1, group0)
    ci_low, ci_high = _cohens_d_ci(d_value, len(group1), len(group0))
    strength = min(1.0, abs(pb))
    direction = _direction_from_value(pb)
    return {
        "metric": "point_biserial_r",
        "effect": pb,
        "strength": strength,
        "direction": direction,
        "n": subset.height,
        "details": {
            "cohens_d": d_value,
            "cohens_d_ci95": [ci_low, ci_high],
            "mean_1": float(group1.mean()) if len(group1) else None,
            "mean_0": float(group0.mean()) if len(group0) else None,
        },
    }


def _compute_categorical_binary(df: pl.DataFrame, categorical: str, binary: str) -> Dict[str, Any]:
    subset = df.select([categorical, binary]).drop_nulls()
    if subset.height == 0:
        return {"metric": "cramers_v", "effect": 0.0, "strength": 0.0, "direction": "unknown", "n": 0, "details": {}}
    categories = subset[categorical].unique().to_list()
    binary_values = subset[binary].unique().to_list()
    contingency = np.zeros((len(categories), len(binary_values)))
    rates: Dict[str, Any] = {}
    for i, category in enumerate(categories):
        cat_slice = subset.filter(subset[categorical] == category)
        total = cat_slice.height
        if total == 0:
            continue
        positive = cat_slice.filter(cat_slice[binary] > 0).height
        rates[str(category)] = {"n": total, "positive_rate": _safe_ratio(positive, total)}
        for j, b_value in enumerate(binary_values):
            contingency[i, j] = cat_slice.filter(cat_slice[binary] == b_value).height
    cramers = _cramers_v(contingency)
    pos_rates = [info["positive_rate"] for info in rates.values() if info["positive_rate"] is not None]
    direction = "mixed"
    if pos_rates:
        diff = max(pos_rates) - min(pos_rates)
        direction = _direction_from_value(diff)
    return {
        "metric": "cramers_v",
        "effect": cramers,
        "strength": min(1.0, cramers),
        "direction": direction,
        "n": subset.height,
        "details": {"rates": rates, "categories": categories},
    }


def _compute_numeric_numeric(df: pl.DataFrame, feature: str, kpi: str) -> Dict[str, Any]:
    feature_series = _ensure_numeric(df[feature]).alias(feature)
    kpi_series = _ensure_numeric(df[kpi]).alias(kpi)
    subset = pl.DataFrame({feature: feature_series, kpi: kpi_series}).drop_nulls()
    if subset.height < 3:
        return {"metric": "pearson_r", "effect": 0.0, "strength": 0.0, "direction": "unknown", "n": subset.height, "details": {}}
    pearson, spearman = _pearson_spearman(subset, feature, kpi)
    strength = min(1.0, abs(pearson))
    direction = _direction_from_value(pearson)
    return {
        "metric": "pearson_r",
        "effect": pearson,
        "strength": strength,
        "direction": direction,
        "n": subset.height,
        "details": {"spearman_rho": spearman},
    }


def _primary_metric(df: pl.DataFrame, feature: str, kpi: str, column_types: Mapping[str, str]) -> Dict[str, Any]:
    feature_type = column_types.get(feature, "other")
    kpi_type = column_types.get(kpi, "other")
    if feature_type == "binary" and kpi_type == "binary":
        return _compute_binary_binary(df, feature, kpi)
    if feature_type == "binary" and kpi_type == "numeric":
        return _compute_binary_numeric(df, feature, kpi)
    if feature_type == "numeric" and kpi_type == "binary":
        return _compute_binary_numeric(df, kpi, feature)
    if feature_type == "categorical" and kpi_type == "binary":
        return _compute_categorical_binary(df, feature, kpi)
    if feature_type == "binary" and kpi_type == "categorical":
        return _compute_categorical_binary(df, kpi, feature)
    if feature_type == "numeric" and kpi_type == "numeric":
        return _compute_numeric_numeric(df, feature, kpi)
    return _compute_numeric_numeric(df, feature, kpi)


def _compute_holdout_score(df: pl.DataFrame, feature: str, kpi: str, column_types: Mapping[str, str], settings: Stage08Settings) -> Tuple[Optional[float], Optional[float]]:
    if df.height < max(50, settings.n_min_per_segment * 2):
        return None, None
    rng = np.random.default_rng(seed=settings.seed)
    mask = rng.random(df.height) < 0.8
    train = df.filter(mask)
    holdout = df.filter(~mask)
    if train.height < 5 or holdout.height < 5:
        return None, None
    base = _primary_metric(train, feature, kpi, column_types)
    hold = _primary_metric(holdout, feature, kpi, column_types)
    delta = abs(base["effect"] - hold["effect"])
    score = _clamp(1.0 - min(1.0, delta))
    return score, delta


def _compute_time_stability(
    df: pl.DataFrame,
    feature: str,
    kpi: str,
    column_types: Mapping[str, str],
    timestamp_col: Optional[str],
    tz: ZoneInfo,
    splits: Tuple[int, int],
) -> Tuple[Optional[float], Dict[str, Any]]:
    windows = _window_filters(df, timestamp_col, tz, splits)
    if not windows:
        return None, {}
    timestamp_expr: Optional[pl.Expr] = None
    col_tz: Optional[str] = None
    if timestamp_col:
        timestamp_expr = pl.col(timestamp_col)
        dtype = df.schema.get(timestamp_col)
        col_tz = getattr(dtype, "time_zone", None) if dtype is not None else None
        if col_tz and col_tz != str(tz):
            timestamp_expr = timestamp_expr.dt.convert_time_zone(str(tz))
    metrics: Dict[str, Any] = {}
    directions: Dict[str, str] = {}
    effects: Dict[str, float] = {}
    for key, window in windows.items():
        if not window.start or not window.end:
            continue
        mask: Optional[pl.Expr]
        if timestamp_col:
            base_expr = timestamp_expr if timestamp_expr is not None else pl.col(timestamp_col)
            mask = (base_expr >= window.start) & (base_expr < window.end)
        else:
            mask = None
        scoped = _filter_df(df, mask)
        if scoped.height < 5:
            continue
        metric = _primary_metric(scoped, feature, kpi, column_types)
        metrics[key] = metric
        directions[key] = metric["direction"]
        effects[key] = metric["effect"]
    if len(metrics) < 2:
        return None, {"windows": metrics}
    valid_directions = {direction for direction in directions.values() if direction != "unknown"}
    stable_direction = len(valid_directions) <= 1
    abs_diff = abs(effects.get("T1", 0.0) - effects.get("T2", 0.0))
    score = _clamp(1.0 - min(1.0, abs_diff))
    base = 1.0 if stable_direction else 0.0
    time_score = _clamp((base + score) / 2.0)
    return time_score, {"windows": metrics, "abs_diff": abs_diff}


def _segment_masks(df: pl.DataFrame, segments: Sequence[str], max_segments: int, settings: Stage08Settings) -> Dict[str, pl.Expr]:
    masks: Dict[str, pl.Expr] = {}
    total = 0
    for column in segments:
        if column not in df.columns:
            continue
        counts = df[column].drop_nulls().value_counts(sort=True)
        for value, count in counts.iter_rows():
            if value is None:
                continue
            label = f"{column}={value}"
            masks[label] = pl.col(column) == value
            total += 1
            if total >= max_segments:
                return masks
    return masks


def _compute_segment_metrics(
    df: pl.DataFrame,
    feature: str,
    kpi: str,
    column_types: Mapping[str, str],
    segments: Mapping[str, pl.Expr],
) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    for label, mask in segments.items():
        scoped = _filter_df(df, mask)
        if scoped.height < 5:
            continue
        metric = _primary_metric(scoped, feature, kpi, column_types)
        metric["n"] = scoped.height
        results[label] = metric
    return results


def _segment_stability(global_direction: str, segment_metrics: Mapping[str, Mapping[str, Any]]) -> Optional[float]:
    if not segment_metrics:
        return None
    total = 0
    aligned = 0
    for metric in segment_metrics.values():
        direction = metric.get("direction", "unknown")
        n = metric.get("n", 0)
        if direction == "unknown" or n == 0:
            continue
        total += 1
        if direction == global_direction:
            aligned += 1
    if total == 0:
        return None
    return aligned / total


def _confidence_bucket(confidence: float, settings: Stage08Settings) -> str:
    high_threshold = max(settings.high_bucket, settings.emit_threshold)
    if confidence >= high_threshold:
        return "HIGH"
    if confidence >= settings.emit_threshold:
        return "MEDIUM"
    return "LOW"


def _compute_candidate_records(
    df: pl.DataFrame,
    correlations: Sequence[Mapping[str, Any]],
    redundancy: Mapping[str, Any],
    settings: Stage08Settings,
    tz: ZoneInfo,
) -> Tuple[List[CandidateRecord], Dict[str, Any]]:
    column_types = _categorise_columns(df, settings.numeric_hints)
    segments = _segment_masks(df, settings.segments, settings.max_segments, settings)
    total_rows = df.height or 1

    records: List[CandidateRecord] = []
    diagnostics: Dict[str, Any] = {"segments_used": list(segments.keys()), "column_types": column_types}

    for entry in correlations[: settings.max_features]:
        kpi = entry.get("kpi")
        feature = entry.get("feature")
        rel_key = entry.get("rel_key") or (f"{kpi}|{feature}" if kpi and feature else None)
        if not isinstance(kpi, str) or not isinstance(feature, str):
            continue
        if kpi not in df.columns or feature not in df.columns:
            continue

        base_metric = _primary_metric(df, feature, kpi, column_types)
        segment_metrics = _compute_segment_metrics(df, feature, kpi, column_types, segments)
        time_score, time_diag = _compute_time_stability(df, feature, kpi, column_types, settings.timestamp_col, tz, settings.split_windows)
        holdout_score, holdout_delta = _compute_holdout_score(df, feature, kpi, column_types, settings)
        segment_score = _segment_stability(base_metric["direction"], segment_metrics)

        stability = StabilityComponents(time_score=time_score, segment_score=segment_score, holdout_score=holdout_score)
        stability_score = stability.aggregate()

        coverage_ratio = _safe_ratio(base_metric["n"], total_rows, default=0.0)
        coverage = _clamp(coverage_ratio or 0.0)
        strength = min(1.0, abs(base_metric["effect"]))
        weights = settings.confidence_weights
        confidence = _clamp(weights[0] * strength + weights[1] * stability_score + weights[2] * coverage)
        bucket = _confidence_bucket(confidence, settings)

        redundancy_score: Optional[float] = None
        if rel_key and rel_key in redundancy:
            redundancy_score = _safe_float(redundancy.get(rel_key, {}).get("redundancy_score"))

        signal_score = (
            0.45 * strength
            + 0.30 * stability_score
            + 0.15 * coverage
            + 0.10 * (1 - _clamp(redundancy_score if redundancy_score is not None else 0.0))
        )

        entry_source_raw = entry.get("source")
        entry_source = entry_source_raw if isinstance(entry_source_raw, str) and entry_source_raw else "stage07_correlations"
        low_signal_entry = bool(entry.get("low_signal"))
        nzv_override_entry = bool(entry.get("nzv_override"))
        entry_note_value = entry.get("note")
        entry_note = entry_note_value.strip() if isinstance(entry_note_value, str) else ""
        corr_method = entry.get("method")

        flags = CandidateFlags(
            small_n=base_metric["n"] < settings.n_min_per_segment,
            simpson=False,
        )

        evidence = [
            "artifacts/{run_id}/stage_07_correlations/correlations_kpi.json",
            "artifacts/{run_id}/stage_07_correlations/correlations.json",
            "artifacts/{run_id}/stage_07_correlations/redundancy.json",
        ]
        evidence.append(f"stage07_source:{entry_source}")
        if corr_method:
            evidence.append(f"corr_method:{corr_method}")
        if low_signal_entry:
            evidence.append("low_signal:true")
        if nzv_override_entry:
            evidence.append("nzv_override:true")
        notes: List[str] = []
        if entry_note:
            notes.append(entry_note)
        if low_signal_entry and not entry_note:
            notes.append("Generated via low-signal KPI fallback.")

        base_record = CandidateRecord(
            kpi=kpi,
            feature=feature,
            metric=base_metric["metric"],
            effect=base_metric["effect"],
            strength=strength,
            direction=base_metric["direction"],
            n=base_metric["n"],
            coverage=coverage,
            confidence=confidence,
            bucket=bucket,
            stability=stability,
            stability_score=stability_score,
            redundancy=redundancy_score,
            signal_score=signal_score,
            segment=None,
            window=None,
            source=entry_source,
            notes=notes,
            flags=flags,
            evidence=evidence,
            diagnostics={
                "time": time_diag,
                "holdout_delta": holdout_delta,
                "segment_metrics": segment_metrics,
                "correlation_entry": {
                    "source": entry_source,
                    "low_signal": low_signal_entry,
                    "nzv_override": nzv_override_entry,
                    "note": entry_note,
                    "method": corr_method,
                    "r": entry.get("r"),
                },
            },
            low_signal=low_signal_entry,
            nzv_override=nzv_override_entry,
        )
        records.append(base_record)

        for label, metric in segment_metrics.items():
            seg_strength = min(1.0, abs(metric["effect"]))
            seg_ratio = _safe_ratio(metric["n"], total_rows, default=0.0)
            seg_coverage = _clamp(seg_ratio or 0.0)
            seg_confidence = _clamp(weights[0] * seg_strength + weights[1] * stability_score + weights[2] * seg_coverage)
            seg_bucket = _confidence_bucket(seg_confidence, settings)
            seg_flags = CandidateFlags(
                small_n=metric["n"] < settings.n_min_per_segment,
                simpson=False,
            )
            seg_record = CandidateRecord(
                kpi=kpi,
                feature=feature,
                metric=metric["metric"],
                effect=metric["effect"],
                strength=seg_strength,
                direction=metric["direction"],
                n=metric["n"],
                coverage=seg_coverage,
                confidence=seg_confidence,
                bucket=seg_bucket,
                stability=stability,
                stability_score=stability_score,
                redundancy=redundancy_score,
                signal_score=signal_score,
                segment=label,
                window=None,
                source="numeric",
                notes=[],
                flags=seg_flags,
                evidence=evidence,
                diagnostics={"time": time_diag, "holdout_delta": holdout_delta},
            )
            records.append(seg_record)

    return records, diagnostics


def _post_process_coverage(records: List[CandidateRecord]) -> None:
    per_kpi_max: Dict[str, int] = {}
    for record in records:
        per_kpi_max[record.kpi] = max(per_kpi_max.get(record.kpi, 0), record.n)
    for record in records:
        max_n = per_kpi_max.get(record.kpi, record.n)
        record.coverage = _clamp(record.n / max_n) if max_n else 0.0


def _partition_candidates(records: List[CandidateRecord], settings: Stage08Settings) -> Tuple[List[CandidateRecord], List[CandidateRecord]]:
    official: List[CandidateRecord] = []
    exploratory: List[CandidateRecord] = []
    for record in records:
        if record.flags.small_n or record.flags.simpson or record.low_signal:
            exploratory.append(record)
            continue
        if record.confidence >= settings.emit_threshold:
            official.append(record)
        exploratory.append(record)
    return official, exploratory


def _gate_status(
    official: List[CandidateRecord],
    has_low_signal: bool,
    has_candidates: bool,
    has_blockers: bool,
    settings: Stage08Settings,
) -> Tuple[str, List[str]]:
    if not official:
        if has_low_signal:
            return "WARN", ["Only low-signal fallback candidates were available; treat insights as exploratory."]
        if not has_candidates:
            return "WARN", ["No correlation signals met the emission criteria; downstream stages may continue without official insights."]
        if has_blockers:
            return "STOP", ["Candidate insights were blocked by guardrails (e.g. small sample size or Simpson effects)."]
        return "STOP", ["No official insights met the emission criteria."]
    high_threshold = max(settings.high_bucket, settings.emit_threshold)
    if any(record.confidence < high_threshold for record in official):
        return "WARN", ["Some official insights fall below the PASS threshold (0.70)."]
    return "PASS", []


def _story_cards(official: List[CandidateRecord], coverage_summary: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    if coverage_summary:
        dropped = coverage_summary.get("dropped", [])
        threshold = coverage_summary.get("threshold")
        dropped_count = len(dropped)
        if dropped_count:
            top_dropped = sorted(dropped, key=lambda item: item["missing_ratio"], reverse=True)[:5]
            top_names = ", ".join(entry["column"] for entry in top_dropped)
            pct_text = f"{int(round((threshold or 0.0) * 100))}%" if threshold is not None else "the set threshold"
            cards.append(
                {
                    "title": "Improve data completeness for richer signals",
                    "what_we_see": f"{dropped_count} fields were excluded because more than {pct_text} of their values are missing (examples: {top_names}).",
                    "where": "Data quality",
                    "action_now": [
                        "Review capture processes for the excluded fields and ensure source systems populate them.",
                        "Schedule a data refresh once key fields reach acceptable coverage so new insights can surface.",
                    ],
                    "expected_effect": "Better insight coverage once these fields exceed the completeness threshold",
                    "priority": "High",
                    "kpi": "Data completeness",
                    "window": "Data quality",
                    "n": coverage_summary.get("rows", 0),
                }
            )
    for record in official:
        segment = record.segment or "Global"
        direction_text = "higher" if record.direction == "positive" else "lower" if record.direction == "negative" else "different"
        headline = _sanitize_language(f"{record.feature} linked with {record.kpi} ({segment})")
        what = _sanitize_language(f"We observe {direction_text} {record.kpi.replace('_', ' ').lower()} when {record.feature.replace('_', ' ').lower()} shifts in {segment}.")
        action_now = [
            _sanitize_language(f"Review operational levers tied to {record.feature} within {segment}."),
            _sanitize_language(f"Pilot an intervention on {record.feature} and monitor {record.kpi}."),
        ]
        duration = "2-4 weeks" if record.bucket == "HIGH" else "4-6 weeks"
        cards.append(
            {
                "title": headline,
                "what_we_see": what,
                "where": segment,
                "action_now": action_now,
                "expected_effect": f"Measurable change within {duration}",
                "priority": "High" if record.bucket == "HIGH" else "Medium",
                "kpi": record.kpi,
                "window": record.window or "Recent window",
                "n": record.n,
            }
        )
    return cards


def _basic_stats(df: pl.DataFrame) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"numeric": {}, "freq_topk": {}, "counts": {"rows": df.height}}
    numeric_cols = [col for col in df.columns if df[col].dtype.is_numeric()]
    for column in numeric_cols:
        series = df[column].drop_nulls()
        if series.len() == 0:
            continue
        payload["numeric"][column] = {
            "mean": float(series.mean()),
            "p50": float(series.quantile(0.5)),
            "p90": float(series.quantile(0.9)),
            "std": float(series.std()),
            "n": int(series.len()),
        }
    categorical_cols = [col for col in df.columns if _is_categorical(df[col])]
    for column in categorical_cols:
        counts = df[column].drop_nulls().value_counts(sort=True).head(5)
        payload["freq_topk"][column] = [{"value": value, "count": int(count)} for value, count in counts.iter_rows()]
    return payload


def _segment_stats_frame(df: pl.DataFrame, settings: Stage08Settings) -> pl.DataFrame:
    rows: List[Dict[str, Any]] = []
    total_rows = df.height or 1
    for column in settings.segments:
        if column not in df.columns:
            continue
        counts = (
            df.select(column)
            .drop_nulls()
            .group_by(column)
            .len()
            .rename({"len": "n"})
            .sort("n", descending=True)
        )
        for value, count in counts.iter_rows():
            try:
                count_int = int(count)
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "segment": column,
                    "segment_value": value,
                    "n": count_int,
                    "share": float(_safe_ratio(count_int, total_rows, default=0.0) or 0.0),
                }
            )
    if not rows:
        return pl.DataFrame(
            {
                "segment": pl.Series("segment", [], dtype=pl.Utf8),
                "segment_value": pl.Series("segment_value", [], dtype=pl.Utf8),
                "n": pl.Series("n", [], dtype=pl.Int64),
                "share": pl.Series("share", [], dtype=pl.Float64),
            }
        )
    return pl.DataFrame(rows)


def _time_stats_frame(df: pl.DataFrame, timestamp_col: Optional[str], tz: ZoneInfo) -> pl.DataFrame:
    if not timestamp_col or timestamp_col not in df.columns:
        return pl.DataFrame(
            {
                "time_bucket": pl.Series("time_bucket", [], dtype=pl.Utf8),
                "n": pl.Series("n", [], dtype=pl.Int64),
                "share": pl.Series("share", [], dtype=pl.Float64),
            }
        )
    series = df[timestamp_col].drop_nulls()
    if series.len() == 0 or not series.dtype.is_temporal():
        return pl.DataFrame(
            {
                "time_bucket": pl.Series("time_bucket", [], dtype=pl.Utf8),
                "n": pl.Series("n", [], dtype=pl.Int64),
                "share": pl.Series("share", [], dtype=pl.Float64),
            }
        )
    converted = (
        df.select(pl.col(timestamp_col).dt.convert_time_zone(str(tz)).dt.date().alias("time_bucket"))
        .drop_nulls()
        .group_by("time_bucket")
        .len()
        .rename({"len": "n"})
        .sort("time_bucket")
    )
    total_rows = df.height or 1
    rows = []
    for bucket, count in converted.iter_rows():
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "time_bucket": bucket.isoformat() if bucket is not None else None,
                "n": count_int,
                "share": float(_safe_ratio(count_int, total_rows, default=0.0) or 0.0),
            }
        )
    return pl.DataFrame(rows)


def _keyphrases_payload(run_id: str, text_profile: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    keyphrases: List[Dict[str, Any]] = []
    top_tokens: List[Dict[str, Any]] = []
    if text_profile:
        for column_info in text_profile.get("columns", {}).values():
            for phrase in column_info.get("top_tokens", []) or []:
                token = str(phrase.get("t", ""))
                masked = _mask_token(token)
                entry = {"token": masked, "count": phrase.get("c", 0)}
                if entry not in top_tokens:
                    top_tokens.append(entry)
                if token and entry not in keyphrases:
                    keyphrases.append({"phrase": masked, "count": phrase.get("c", 0)})
    return {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "keyphrases": keyphrases,
        "top_tokens": top_tokens,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _materialise_layer2_artifacts(
    run_id: str,
    tz: ZoneInfo,
    paths: Mapping[str, Path],
    out_dir: Path,
) -> Dict[str, Path]:
    candidates: Dict[str, Path] = {
        name: path
        for name, path in (
            ("layer2_variance", paths.get("layer2_variance")),
            ("layer2_compare", paths.get("layer2_compare")),
            ("layer2_heatmap", paths.get("layer2_heatmap")),
        )
        if path and path.exists()
    }
    candidate_src = paths.get("layer2_candidate")
    if candidate_src and candidate_src.exists():
        candidates["layer2_candidate"] = candidate_src
    if not candidates:
        return {}
    layer2_dir = out_dir / "layer2"
    layer2_dir.mkdir(parents=True, exist_ok=True)
    summary: Dict[str, Any] = {
        "run_id": run_id,
        "generated_at": datetime.now(tz).isoformat(),
        "sources": {},
    }
    exported: Dict[str, Path] = {}
    for key, src in candidates.items():
        dest = layer2_dir / src.name
        try:
            shutil.copyfile(src, dest)
        except Exception as exc:  # pragma: no cover - defensive
            summary.setdefault("errors", []).append({key: str(exc)})
            continue
        exported[key] = dest
        summary["sources"][key] = dest.as_posix()
        try:
            summary[key.replace("layer2_", "")] = _load_json(dest)
        except Exception as exc:  # pragma: no cover - defensive
            summary.setdefault("errors", []).append({key: str(exc)})
    if not exported:
        return {}
    snapshot_path = layer2_dir / "layer2_snapshot.json"
    _write_json(snapshot_path, summary)
    exported["layer2_snapshot"] = snapshot_path
    return exported


def _text_stats(run_id: str, text_profile: Optional[Mapping[str, Any]], tz: ZoneInfo) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "run_id": run_id,
        "generated_at": datetime.now(tz).isoformat(),
        "columns": {},
        "global": {},
    }
    if not text_profile:
        return payload
    columns: Dict[str, Any] = {}
    for column, info in text_profile.get("columns", {}).items():
        tokens = info.get("top_tokens", [])
        masked = [{"token": _mask_token(str(item.get("t", ""))), "count": item.get("c", 0)} for item in tokens[:20]]
        columns[column] = {
            "counts": info.get("counts") or {},
            "top_tokens": masked,
        }
    payload["columns"] = columns
    payload["global"] = text_profile.get("global", {})
    return payload


def run(run_id: str, context: Mapping[str, Any], config: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    settings = Stage08Settings.from_config(config)
    tz = ZoneInfo(settings.timezone)
    start_time = time.time()
    paths = _load_inputs(run_id, settings)
    logger = setup_logger(f"stage_08_{run_id}")

    policy_path = Path(settings.policy_path)
    if not policy_path.is_absolute():
        policy_path = BACKEND_ROOT / policy_path
    policy_payload = _load_policy(policy_path)
    geo_policy = policy_payload.get("geo") or {}
    geo_columns_cfg = [str(col) for col in (geo_policy.get("columns") or []) if str(col)]
    geo_warn_threshold = float(geo_policy.get("missing_warn_threshold", settings.critical_missing_warn))
    geo_stop_threshold = float(geo_policy.get("missing_stop_threshold", settings.critical_missing_stop))
    policy_event = {
        "event": "policy",
        "path": str(policy_path),
        "loaded": bool(policy_payload),
        "geo_columns": geo_columns_cfg,
        "geo_warn_threshold": geo_warn_threshold,
        "geo_stop_threshold": geo_stop_threshold,
        "default_warn_threshold": settings.critical_missing_warn,
        "default_stop_threshold": settings.critical_missing_stop,
    }
    if not policy_payload:
        logger.warning("Stage 08 policy file not found at %s; using defaults.", policy_path)

    features_df = pl.read_parquet(paths["features"].as_posix())
    features_df, sampling_info = _apply_sampling(features_df, settings, logger)
    features_df, coverage_summary = _screen_columns(features_df, settings)
    raw_correlations = _load_json(paths["correlations"])
    kpi_names = _load_kpi_names()
    correlations, correlations_converted = _normalize_correlations(raw_correlations, kpi_names)
    redundancy = _load_json(paths["redundancy"])
    text_profile = _load_json(paths["text_profile"]) if paths["text_profile"].exists() else None
    sentiment_df = pl.read_parquet(paths["sentiment"].as_posix()) if paths["sentiment"].exists() else None
    text_findings = _load_optional_json(paths["text_findings"])
    readiness_manifest = _load_optional_json(paths["readiness_decision_manifest"])
    readiness_diag = _load_optional_json(paths["readiness_diagnostics"])
    layer1_catalog = _load_optional_json(paths["layer1_catalog"])
    dq_summary = _load_optional_json(paths["analytics_dq_summary"])
    forecast_summary = _load_optional_json(paths["analytics_forecast_summary"])
    llm_metrics = _load_optional_json(paths["llm_summary_metrics"])

    readiness_overlay = _summarize_readiness(
        readiness_manifest,
        readiness_diag,
        layer1_catalog,
        paths["layer1_preview"],
        paths["layer1_dataset"],
    )
    textops_overlay = _summarize_textops(text_profile, text_findings, sentiment_df)
    analytics_overlay = _summarize_analytics(dq_summary, forecast_summary, paths["forecast"])
    llm_overlay = _summarize_llm(llm_metrics)

    preflight = _preflight_checks(features_df, correlations, settings, tz, geo_policy)

    logs: List[Dict[str, Any]] = [
        {
            "event": "phase_start",
            "timestamp": datetime.now(tz).isoformat(),
            "run_id": run_id,
            "inputs": {name: path.as_posix() for name, path in paths.items() if path.exists()},
        },
        {
            "event": "env_info",
            "python": context.get("python_version") or sys.version,
            "packages": {
                "numpy": np.__version__,
                "polars": pl.__version__,
                "jsonschema": importlib_metadata.version("jsonschema"),
            },
        },
        policy_event,
        {
            "event": "column_screen",
            "threshold": coverage_summary["threshold"],
            "dropped": len(coverage_summary["dropped"]),
            "kept": len(coverage_summary["kept"]),
            "dropped_columns": [entry["column"] for entry in coverage_summary["dropped"]],
        },
        {"event": "preflight", **preflight},
    ]

    corr_source_name = paths["correlations"].name
    corr_origin = "kpi_file" if corr_source_name == "correlations_kpi.json" else "legacy"
    if correlations_converted:
        corr_origin = "legacy_fallback"
    logs.append(
        {
            "event": "correlations_format",
            "origin": corr_origin,
            "count": len(correlations),
            "path": paths["correlations"].as_posix(),
        }
    )

    anomaly_metric = "COD_AMOUNT"
    anomaly_records: List[Dict[str, Any]] = []
    anomalies_df = _anomalies(features_df, settings.segments, anomaly_metric, sigma=3.0, min_n=300)
    if not anomalies_df.is_empty():
        selected_cols = [col for col in anomalies_df.columns if not col.startswith("_")] + ["_n", "_m", "_s", "z_score"]
        ordered_cols: List[str] = []
        seen: Set[str] = set()
        for col in selected_cols:
            if col in anomalies_df.columns and col not in seen:
                ordered_cols.append(col)
                seen.add(col)
        anomaly_records = anomalies_df.select(ordered_cols).to_dicts()
        logs.append(
            {
                "event": "anomaly_detection",
                "metric": anomaly_metric,
                "count": len(anomaly_records),
                "sigma": 3.0,
                "min_n": 300,
            }
        )

    out_dir = Path(settings.artifacts_root) / run_id / "stage_08_insights"
    out_dir.mkdir(parents=True, exist_ok=True)
    coverage_path = out_dir / "column_coverage.json"
    _write_json(coverage_path, coverage_summary)
    quality_report_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(tz).isoformat(),
        "threshold": coverage_summary.get("threshold"),
        "rows": coverage_summary.get("rows"),
        "excluded_columns": [
            {
                "name": entry.get("column"),
                "missing": entry.get("missing"),
                "missing_ratio": entry.get("missing_ratio"),
                "dtype": entry.get("dtype"),
            }
            for entry in coverage_summary.get("dropped", [])
        ],
    }
    _write_json(out_dir / "quality_report.json", quality_report_payload)

    layer2_exports = _materialise_layer2_artifacts(run_id, tz, paths, out_dir)
    if layer2_exports:
        logs.append(
            {
                "event": "layer2_ingest",
                "artifacts": {key: path.as_posix() for key, path in layer2_exports.items()},
            }
        )

    if preflight["status"] == "STOP":
        gate_payload = {
            "status": "STOP",
            "counts": {"all": 0, "emitted": 0},
            "reasons": preflight["reasons"],
            "policy": {
                "path": str(policy_path),
                "geo_warn_threshold": geo_warn_threshold,
                "geo_stop_threshold": geo_stop_threshold,
                "geo_columns": geo_columns_cfg,
            },
            "diag": {"preflight": preflight},
        }
        _write_json(out_dir / "gate.json", gate_payload)
        diagnostics_payload = {
            "run_id": run_id,
            "time_window_days": settings.time_window_days,
            "counts": {"features": 0, "segments_used": 0, "pairs_tested": 0},
            "coverage": {},
            "effect": {},
            "confidence": {},
            "stability": {},
            "flags": {},
            "warnings": preflight["reasons"] + preflight.get("warnings", []),
            "sampling": sampling_info,
            "notes": ["Preflight STOP triggered."],
            "coverage_report": coverage_summary,
            "policy": gate_payload["policy"],
            "thresholds": preflight.get("thresholds"),
        }
        _write_json(out_dir / "diagnostics.json", diagnostics_payload)
        logs.append({"event": "gate", **gate_payload})
        logs.append({"event": "phase_end", "duration_sec": round(time.time() - start_time, 4)})
        write_jsonl(logs, (out_dir / "logs.jsonl").as_posix())
        outputs = {
            "gate": (out_dir / "gate.json").as_posix(),
            "diagnostics": (out_dir / "diagnostics.json").as_posix(),
            "logs": (out_dir / "logs.jsonl").as_posix(),
            "column_coverage": coverage_path.as_posix(),
        }
        if layer2_exports:
            outputs.update({key: path.as_posix() for key, path in layer2_exports.items()})
        return {
            "run_id": run_id,
            "status": "STOP",
            "outputs": outputs,
            "logs_uri": (out_dir / "logs.jsonl").as_posix(),
        }

    records, meta = _compute_candidate_records(features_df, correlations, redundancy, settings, tz)
    _post_process_coverage(records)
    official, exploratory = _partition_candidates(records, settings)
    gate_status, gate_reasons = _gate_status(
        official,
        any(record.low_signal for record in records),
        bool(records),
        any(record.flags.small_n or record.flags.simpson for record in records),
        settings,
    )
    gate_status, gate_reasons = _apply_external_warnings(
        gate_status,
        gate_reasons,
        readiness_overlay,
        analytics_overlay,
        llm_overlay,
        enforce_readiness=settings.enforce_readiness_gates,
    )

    official_payloads = [record.to_official_payload() for record in official]
    candidate_payloads = [record.to_candidate_payload() for record in exploratory]

    _validate_records(official_payloads, OFFICIAL_REQUIRED_FIELDS, OFFICIAL_ALLOWED_FIELDS, "official_insights")
    _validate_records(candidate_payloads, CANDIDATE_REQUIRED_FIELDS, CANDIDATE_ALLOWED_FIELDS, "insight_candidates")

    story_context = {
        "readiness": readiness_overlay,
        "analytics": analytics_overlay,
        "text_ops": textops_overlay,
        "llm_summary": llm_overlay,
    }

    insights_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(tz).isoformat(),
        "timezone": settings.timezone,
        "summary": {
            "official_count": len(official),
            "exploratory_count": len(exploratory),
            "n_rows": features_df.height,
            "max_strength": max((record.strength for record in official), default=None),
            "max_confidence": max((record.confidence for record in official), default=None),
            "median_confidence": statistics.median([record.confidence for record in official]) if official else None,
        },
        "source": {
            "features": paths["features"].as_posix(),
            "correlations": paths["correlations"].as_posix(),
            "redundancy": paths["redundancy"].as_posix(),
            "text_profile": paths["text_profile"].as_posix() if text_profile else None,
            "sentiment": paths["sentiment"].as_posix() if sentiment_df is not None else None,
        },
        "insights": official_payloads,
        "context": story_context,
    }
    _write_json(out_dir / "insights_report.json", insights_payload)

    if settings.candidates_enable:
        candidates_payload = {
            "run_id": run_id,
            "generated_at": datetime.now(tz).isoformat(),
            "candidates": candidate_payloads,
        }
        _write_json(out_dir / "insights_candidates.json", candidates_payload)

    low_signal_count = sum(1 for record in records if record.low_signal)
    nzv_override_count = sum(1 for record in records if record.nzv_override)
    warnings = list(preflight.get("warnings", []))
    if low_signal_count:
        warnings.append("Low-signal fallback candidates present; treat as exploratory signals.")
    if readiness_overlay.get("gate_status") in {"WARN", "STOP"}:
        warnings.append("Stage 07 readiness reported gating blockers.")
    dq_overlay = analytics_overlay.get("dq") if isinstance(analytics_overlay, Mapping) else None
    if dq_overlay and dq_overlay.get("critical_failures"):
        warnings.append("Stage 07 analytics detected critical data-quality failures.")
    if llm_overlay.get("provider") == "heuristic":
        warnings.append("LLM summary fell back to heuristics; narratives are advisory.")
    notes = ["All signals are associative, not causal."]
    if low_signal_count:
        notes.append(f"{low_signal_count} candidate(s) generated via low-signal KPI fallback.")
    diagnostics_payload = {
        "run_id": run_id,
        "time_window_days": settings.time_window_days,
        "counts": {
            "features": len({record.feature for record in records}),
            "segments_used": len(meta.get("segments_used", [])),
            "pairs_tested": len(records),
            "low_signal": low_signal_count,
            "nzv_override": nzv_override_count,
        },
        "coverage": {
            "median": statistics.median([record.coverage for record in records]) if records else None,
            "p90": float(np.quantile([record.coverage for record in records], 0.9)) if records else None,
        },
        "effect": {
            "max_abs": max((abs(record.effect) for record in records), default=None),
            "median_abs": statistics.median([abs(record.effect) for record in records]) if records else None,
        },
        "confidence": {
            "max": max((record.confidence for record in records), default=None),
            "p50": statistics.median([record.confidence for record in records]) if records else None,
        },
        "stability": {
            "time_stable_pct": (sum(1 for record in records if record.stability.time_score and record.stability.time_score >= 0.5) / len(records) * 100) if records else 0,
            "segment_stable_pct": (sum(1 for record in records if record.stability.segment_score and record.stability.segment_score >= 0.5) / len(records) * 100) if records else 0,
        },
        "flags": {
            "simpson": sum(1 for record in records if record.flags.simpson),
            "small_n": sum(1 for record in records if record.flags.small_n),
        },
        "warnings": warnings,
        "sampling": sampling_info,
        "disabled_features": {
            "segment_time_grid": not settings.enable_seg_time,
            "permutation_tests": settings.enable_permutation is False,
            "bh_fdr": settings.enable_bh_fdr is False,
            "contrast_sets": settings.enable_contrast_sets is False,
            "simpson_detector": settings.enable_simpson_detect is False,
        },
        "coverage_report": coverage_summary,
        "notes": notes,
        "readiness": readiness_overlay,
        "analytics": analytics_overlay,
        "textops": textops_overlay,
        "llm_summary": llm_overlay,
        "policy": {
            "path": str(policy_path),
            "geo_warn_threshold": geo_warn_threshold,
            "geo_stop_threshold": geo_stop_threshold,
            "geo_columns": geo_columns_cfg,
        },
        "thresholds": preflight.get("thresholds"),
        "anomalies": {
            "metric": anomaly_metric,
            "sigma": 3.0,
            "min_n": 300,
            "records": anomaly_records,
        },
    }
    _write_json(out_dir / "diagnostics.json", diagnostics_payload)

    low_signal_count = sum(1 for record in records if record.low_signal)
    gate_payload = {
        "status": gate_status,
        "counts": {"all": len(records), "emitted": len(official)},
        "reasons": gate_reasons,
        "diag": {"preflight": preflight},
        "low_signal_candidates": low_signal_count,
        "policy": {
            "path": str(policy_path),
            "geo_warn_threshold": geo_warn_threshold,
            "geo_stop_threshold": geo_stop_threshold,
            "geo_columns": geo_columns_cfg,
        },
    }
    _write_json(out_dir / "gate.json", gate_payload)

    supplemental_cards = _build_supplemental_cards(
        readiness_overlay,
        analytics_overlay,
        textops_overlay,
        llm_overlay,
        settings,
    )
    core_story_items = _story_cards(official, coverage_summary)
    story_payload = {
        "run_id": run_id,
        "confidence_note": "Confidence = f(strength, stability, coverage). Non-causal.",
        "items": core_story_items,
        "supplemental": supplemental_cards,
        "context": story_context,
    }
    _write_json(out_dir / "story_ops.json", story_payload)

    # Generate cards.json (extract cards from story_ops)
    cards_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(tz).isoformat(),
        "count": len(core_story_items),
        "cards": core_story_items,
    }
    _write_json(out_dir / "cards.json", cards_payload)
    
    # Generate narratives.json (bilingual narratives for each insight)
    narratives_items = []
    for record in official:
        kpi_name = record.kpi or "unknown"
        feature_name = record.feature or "unknown"
        direction_text = "إيجابية" if record.direction == "positive" else "سلبية" if record.direction == "negative" else "مختلطة"
        direction_en = record.direction.capitalize()
        
        # Arabic narrative
        narrative_ar = (
            f"العلاقة بين {feature_name} و{kpi_name} تُظهر ارتباطاً {direction_text} "
            f"بقوة {record.strength:.2f} وثقة {record.confidence:.2f}. "
            f"هذه العلاقة تغطي {record.coverage:.1%} من البيانات وتستند إلى {record.n} ملاحظة."
        )
        
        # English narrative
        narrative_en = (
            f"The relationship between {feature_name} and {kpi_name} shows a {direction_en} association "
            f"with strength {record.strength:.2f} and confidence {record.confidence:.2f}. "
            f"This relationship covers {record.coverage:.1%} of the data and is based on {record.n} observations."
        )
        
        narratives_items.append({
            "id": f"{kpi_name}_{feature_name}",
            "kpi": kpi_name,
            "feature": feature_name,
            "narrative_ar": narrative_ar,
            "narrative_en": narrative_en,
            "direction": record.direction,
            "strength": record.strength,
            "confidence": record.confidence,
            "coverage": record.coverage,
            "n": record.n,
        })
    
    narratives_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(tz).isoformat(),
        "count": len(narratives_items),
        "narratives": narratives_items,
    }
    _write_json(out_dir / "narratives.json", narratives_payload)
    
    # Generate dashboard_data.parquet (combined data for ECharts dashboards)
    # Include key metrics and features for dashboard visualization
    dashboard_cols = []
    for col in features_df.columns:
        if col in ["cod_amount", "COD_AMOUNT", "amount", "AMOUNT", "sla_achieved", "SLA_ACHIEVED", 
                   "rto_rate", "RTO_RATE", "rto_flag", "RTO_FLAG"] or col in [r.kpi for r in official if r.kpi]:
            dashboard_cols.append(col)
        elif col in [r.feature for r in official if r.feature]:
            dashboard_cols.append(col)
    
    # Also include segment and time columns if available
    segment_cols = [col for col in features_df.columns if "segment" in col.lower() or "region" in col.lower() or "destination" in col.lower()]
    time_cols = [col for col in features_df.columns if "date" in col.lower() or "time" in col.lower()]
    if settings.timestamp_col and settings.timestamp_col in features_df.columns:
        time_cols.append(settings.timestamp_col)
    
    all_dashboard_cols = list(set(dashboard_cols + segment_cols[:3] + time_cols[:2]))  # Limit to avoid too many cols
    valid_cols = [col for col in all_dashboard_cols if col in features_df.columns]
    
    # Generate dashboard_data.parquet
    if valid_cols:
        dashboard_df = features_df.select(valid_cols)
    else:
        # Fallback: use first 10 numeric columns or all columns if fewer
        numeric_cols = [col for col in features_df.columns if features_df[col].dtype.is_numeric()][:10]
        dashboard_df = features_df.select(numeric_cols if numeric_cols else features_df.columns[:10])
    
    # Add run_id column
    dashboard_df = dashboard_df.with_columns(pl.lit(run_id).alias("run_id"))
    dashboard_df.write_parquet((out_dir / "dashboard_data.parquet").as_posix())

    basic_stats_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(tz).isoformat(),
        **_basic_stats(features_df),
    }
    _write_json(out_dir / "basic_stats.json", basic_stats_payload)

    segment_df = _segment_stats_frame(features_df, settings).with_columns(pl.lit(run_id).alias("run_id"))
    segment_df.write_parquet((out_dir / "segment_stats.parquet").as_posix())

    time_df = _time_stats_frame(features_df, settings.timestamp_col, tz).with_columns(pl.lit(run_id).alias("run_id"))
    time_df.write_parquet((out_dir / "time_stats.parquet").as_posix())

    _write_json(out_dir / "text_stats.json", _text_stats(run_id, text_profile, tz))
    _write_json(out_dir / "keyphrases_topk.json", _keyphrases_payload(run_id, text_profile))

    if low_signal_count:
        logs.append({"event": "low_signal_fallback", "count": low_signal_count})

    logs.append(
        {
            "event": "measure_summary",
            "candidates": len(records),
            "official": len(official),
            "gate_status": gate_status,
        }
    )
    logs.append({"event": "gate", **gate_payload})
    logs.append({"event": "phase_end", "duration_sec": round(time.time() - start_time, 4)})
    write_jsonl(logs, (out_dir / "logs.jsonl").as_posix())
    logger.info(json.dumps({"gate_status": gate_status, "duration_sec": round(time.time() - start_time, 4)}))


    advanced_dir = out_dir / "advanced"
    advanced_dir.mkdir(parents=True, exist_ok=True)
    knime_outputs_dir = Path(settings.artifacts_root) / run_id / "phase_07_knime" / "outputs"
    advanced_truncations: List[Dict[str, Any]] = []

    def _record_truncation(filename: str, size: Optional[int], origin: Optional[Path]) -> None:
        entry = {
            "event": "advanced_payload_truncated",
            "file": filename,
            "size_bytes": size,
            "origin": origin.as_posix() if origin else None,
        }
        logs.append(entry)
        advanced_truncations.append(entry)

    def _truncate_payload(filename: str, payload: Dict[str, Any], size: Optional[int], origin: Optional[Path]) -> Dict[str, Any]:
        truncated = {
            "run_id": payload.get("run_id", run_id),
            "generated_at": payload.get("generated_at", datetime.now(tz).isoformat()),
            "source": payload.get("source", "truncated"),
            "notes": list(payload.get("notes") or []),
            "truncated": True,
        }
        truncated["notes"].append(
            f"{filename} limited to {ADVANCED_PAYLOAD_MAX_BYTES} bytes (original {size or 'unknown'})."
        )
        if origin:
            truncated["origin"] = origin.as_posix()
        if size is not None:
            truncated["size_bytes"] = size
        _record_truncation(filename, size, origin)
        return truncated

    def _copy_or_build_json(source: Path, filename: str, builder) -> tuple[str, str]:
        dest = advanced_dir / filename
        if source.exists():
            size = source.stat().st_size
            if size > ADVANCED_PAYLOAD_MAX_BYTES:
                payload = _truncate_payload(filename, {}, size, source)
                _write_json(dest, payload)
                return dest.as_posix(), "truncated"
            shutil.copy2(source, dest)
            label = "knime" if "phase_07_knime" in source.as_posix() else "analytics"
            return dest.as_posix(), label
        payload = builder()
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(encoded) > ADVANCED_PAYLOAD_MAX_BYTES:
            payload = _truncate_payload(filename, payload, len(encoded), None)
        _write_json(dest, payload)
        label = str(payload.get("source", "fallback"))
        return dest.as_posix(), label

    def _fallback_cluster() -> Dict[str, Any]:
        top_segment = "GLOBAL"
        if "REGION" in features_df.columns and not features_df.is_empty():
            region_series = features_df["REGION"].drop_nulls()
            if region_series.is_empty():
                top_segment = "GLOBAL"
            else:
                top_segment = str(region_series.head(1).item())
        cluster_payload: Dict[str, Any] = {
            "run_id": run_id,
            "generated_at": datetime.now(tz).isoformat(),
            "source": "fallback",
            "clusters": [
                {
                    "id": top_segment,
                    "count": int(features_df.height),
                    "mean_cod": float(features_df["COD_AMOUNT"].mean()) if "COD_AMOUNT" in features_df.columns else None,
                }
            ],
        }
        return cluster_payload

    def _fallback_anomalies() -> Dict[str, Any]:
        return {
            "run_id": run_id,
            "generated_at": datetime.now(tz).isoformat(),
            "source": "fallback",
            "records": [],
        }

    def _fallback_correlation() -> Dict[str, Any]:
        matrix: Dict[str, Dict[str, float]] = {}
        if "DELIVERED" in features_df.columns and "IS_COD" in features_df.columns:
            try:
                value = float(features_df.select(pl.corr("DELIVERED", "IS_COD")).item())
            except Exception:
                value = 0.0
            matrix = {"DELIVERED": {"IS_COD": value}}
        return {
            "run_id": run_id,
            "generated_at": datetime.now(tz).isoformat(),
            "source": "fallback",
            "matrix": matrix,
        }

    cluster_path, cluster_source = _copy_or_build_json(paths["cluster_summary"], "cluster_summary.json", _fallback_cluster)
    anomalies_path, anomalies_source = _copy_or_build_json(paths["anomalies"], "anomalies.json", _fallback_anomalies)
    corr_path, _ = _copy_or_build_json(paths["correlation_matrix"], "correlation_matrix.json", _fallback_correlation)

    forecast_dest = advanced_dir / "orders_forecast.parquet"
    if paths["forecast"].exists():
        shutil.copy2(paths["forecast"], forecast_dest)
        forecast_source = "knime" if "phase_07_knime" in paths["forecast"].as_posix() else "analytics"
    else:
        future_dates = [datetime.now(tz) + timedelta(days=idx) for idx in range(1, 6)]
        baseline = float(features_df["COD_AMOUNT"].mean()) if "COD_AMOUNT" in features_df.columns else 0.0
        forecast_df = pl.DataFrame(
            {
                "forecast_date": future_dates,
                "forecast": [baseline for _ in future_dates],
                "step": list(range(1, len(future_dates) + 1)),
                "metric": ["COD_AMOUNT"] * len(future_dates),
                "method": ["fallback"] * len(future_dates),
            }
        )
        forecast_df.write_parquet(forecast_dest.as_posix())
        forecast_source = "fallback"

    summary_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(tz).isoformat(),
        "sources": {
            "cluster_summary": {"source": cluster_source},
            "anomalies": {"source": anomalies_source},
            "orders_forecast": {"source": forecast_source},
        },
        "truncations": advanced_truncations,
    }
    summary_path = advanced_dir / "summary.json"
    _write_json(summary_path, summary_payload)

    outputs = {
        "insights_report": (out_dir / "insights_report.json").as_posix(),
        "story_ops": (out_dir / "story_ops.json").as_posix(),
        "cards": (out_dir / "cards.json").as_posix(),
        "narratives": (out_dir / "narratives.json").as_posix(),
        "dashboard_data": (out_dir / "dashboard_data.parquet").as_posix(),
        "gate": (out_dir / "gate.json").as_posix(),
        "diagnostics": (out_dir / "diagnostics.json").as_posix(),
        "logs": (out_dir / "logs.jsonl").as_posix(),
        "basic_stats": (out_dir / "basic_stats.json").as_posix(),
        "text_stats": (out_dir / "text_stats.json").as_posix(),
        "segment_stats": (out_dir / "segment_stats.parquet").as_posix(),
        "time_stats": (out_dir / "time_stats.parquet").as_posix(),
        "keyphrases_topk": (out_dir / "keyphrases_topk.json").as_posix(),
        "column_coverage": coverage_path.as_posix(),
        "quality_report": (out_dir / "quality_report.json").as_posix(),
    }
    outputs.update(
        {
            "cluster_summary": cluster_path,
            "anomalies": anomalies_path,
            "correlation_matrix": corr_path,
            "orders_forecast": forecast_dest.as_posix(),
            "advanced_summary": summary_path.as_posix(),
        }
    )
    if settings.candidates_enable:
        outputs["insights_candidates"] = (out_dir / "insights_candidates.json").as_posix()
    if layer2_exports:
        outputs.update({key: path.as_posix() for key, path in layer2_exports.items()})

    return {
        "run_id": run_id,
        "status": gate_status,
        "outputs": outputs,
        "metrics": {
            "n_rows": features_df.height,
            "insights_emitted": len(official),
            "gate_status": gate_status,
        },
        "logs_uri": (out_dir / "logs.jsonl").as_posix(),
    }


__all__ = ["run"]
