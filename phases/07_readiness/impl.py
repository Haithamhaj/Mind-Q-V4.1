from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np  # type: ignore
import yaml  # type: ignore
from scipy import stats  # type: ignore

try:
    import pandas as pd  # type: ignore
    from pandas.api import types as ptypes  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("pandas is required for phase 07 readiness") from exc

from backend.src.app.services import nzv_policy
from shared import baseline as baseline_utils  # type: ignore
from shared.terminology_loader import TerminologyRepository  # type: ignore
from shared.kpi_selector import select_kpi_candidates  # type: ignore
from shared.correlation_semantics import (  # type: ignore
    CorrelationHistoryTracker,
    ShippingCorrelationEnricher,
)

READINESS_RANDOM_SEED = 42
PSI_WARN_THRESHOLD = 0.2
PSI_STOP_THRESHOLD = 0.3
CORR_THRESHOLD = 0.98
NZV_DOMINANT_THRESHOLD = 0.999
NZV_UNIQUE_RATIO_THRESHOLD = 0.001
AFTER_EVENT_RATIO_THRESHOLD = 0.01
DEFAULT_KPI_NAMES: Tuple[str, ...] = ("cod_amount", "sla_achieved", "rto_rate", "rto_flag")
LOW_SIGNAL_CORR_THRESHOLD = 0.15
BACKEND_ROOT = Path(__file__).resolve().parents[2]
KPI_CONTRACT_PATH = BACKEND_ROOT / "contracts" / "kpis.yml"
CRITICAL_COLUMNS_PATH = BACKEND_ROOT / "contracts" / "kpis" / "critical_columns.yml"
ID_PATTERN = re.compile(r"(?:^|_)(?:id|guid|uuid|hash|md5|sha(?:1|256|512)?)$", re.IGNORECASE)
ID_STRICT_NAMES: Set[str] = {
    "id",
    "guid",
    "uuid",
    "hash",
    "md5",
    "sha",
    "sha1",
    "sha256",
    "sha512",
    "order_id",
    "shipment_id",
    "customer_id",
    "invoice_id",
}


def _id_like_reason(name: str) -> Optional[str]:
    n = str(name).strip().lower()
    if not n:
        return None
    if ID_PATTERN.search(n):
        return "pattern"
    if n.endswith("_id"):
        return "suffix"
    if n in ID_STRICT_NAMES:
        return "whitelist"
    return None


def is_id_like(name: str) -> bool:
    return _id_like_reason(name) is not None


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _normalize_string_list(payload: Any) -> List[str]:
    if payload is None:
        return []
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, Mapping):
        results: List[str] = []
        for value in payload.values():
            results.extend(_normalize_string_list(value))
        return results
    if isinstance(payload, Iterable) and not isinstance(payload, (bytes, bytearray)):
        results: List[str] = []
        for item in payload:
            results.extend(_normalize_string_list(item))
        return results
    return [str(payload)]


def _load_critical_columns(path: Optional[Path] = None) -> Tuple[List[str], Optional[Path]]:
    target_path = path or CRITICAL_COLUMNS_PATH
    if not target_path.exists():
        return [], None
    try:
        payload = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return [], target_path

    if isinstance(payload, Mapping):
        candidates = payload.get("critical_columns") or payload.get("columns") or payload.get("fields") or payload
    else:
        candidates = payload

    columns = [entry.strip() for entry in _normalize_string_list(candidates) if isinstance(entry, str) and entry.strip()]
    return columns, target_path


def _extract_nzv_columns_from_report(report_payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    columns_payload = report_payload.get("columns")
    if isinstance(columns_payload, Mapping):
        for standardized, meta in columns_payload.items():
            if not isinstance(meta, Mapping):
                continue
            entry = dict(meta)
            entry.setdefault("standardized_name", standardized)
            entry.setdefault("name", standardized)
            result.append(entry)
    elif isinstance(columns_payload, list):
        result.extend([entry for entry in columns_payload if isinstance(entry, Mapping)])
    return result


def _load_nzv_context(
    artifacts_root: Path,
    run_id: str,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], Optional[Path]]:
    stage05_dir = artifacts_root / run_id / "stage_05_missing"
    summary_path = stage05_dir / "summary.json"
    details_path = stage05_dir / "nzv_summaries.json"

    summary_payload = _load_json(summary_path)
    if isinstance(summary_payload, Mapping) and "nzv_summary" in summary_payload:
        nested_summary = summary_payload.get("nzv_summary")
        summary_payload = nested_summary if isinstance(nested_summary, Mapping) else None
    elif not isinstance(summary_payload, Mapping):
        summary_payload = None

    details_payload = _load_json(details_path)
    columns: List[Dict[str, Any]] = []
    if isinstance(details_payload, Mapping):
        raw_columns = details_payload.get("columns")
    else:
        raw_columns = details_payload
    if isinstance(raw_columns, list):
        columns = [dict(entry) for entry in raw_columns if isinstance(entry, Mapping)]

    if summary_payload or columns:
        return summary_payload, columns, (details_path if columns else summary_path if summary_payload else None)

    stage06_report_path = artifacts_root / run_id / "stage_06_standardize" / "standardize_report.json"
    report_payload = _load_json(stage06_report_path)
    if isinstance(report_payload, Mapping):
        summary = report_payload.get("nzv_summary")
        if not isinstance(summary, Mapping):
            summary = None
        report_columns = _extract_nzv_columns_from_report(report_payload)
        if summary or report_columns:
            return summary, report_columns, stage06_report_path

    return None, [], None


def _is_nzv_entry(entry: Mapping[str, Any]) -> bool:
    category = (entry.get("nzv_category") or "").strip().lower()
    if category in {"constant_like", "near_zero_variance"}:
        return True
    return bool(entry.get("is_nzv"))


def _nzv_name_variants(entry: Mapping[str, Any]) -> Set[str]:
    names: Set[str] = set()
    for key in ("name", "standardized_name", "original_name"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            names.add(value)
    return names


def _build_nzv_details_from_columns(columns: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    for entry in columns:
        if not _is_nzv_entry(entry):
            continue
        names = _nzv_name_variants(entry)
        feature_name = next(iter(names)) if names else entry.get("name")
        if not feature_name:
            continue
        details.append(
            {
                "feature": str(feature_name),
                "nzv_category": entry.get("nzv_category"),
                "nzv_reason": entry.get("nzv_reason") or entry.get("reason"),
                "dominant_value": entry.get("dominant_value"),
                "dominant_pct": entry.get("dominant_pct"),
                "unique_count": entry.get("unique_count"),
                "is_nzv": bool(entry.get("is_nzv", True)),
            }
        )
    return details


def _infer_semantic_role(series: "pd.Series") -> str:
    if ptypes.is_bool_dtype(series):
        return "flag"
    if ptypes.is_datetime64_any_dtype(series):
        return "temporal"
    if ptypes.is_numeric_dtype(series):
        return "metric"
    return "dimension"


def _format_dtype(series: "pd.Series") -> str:
    if ptypes.is_datetime64_any_dtype(series):
        return "datetime"
    if ptypes.is_bool_dtype(series):
        return "boolean"
    if ptypes.is_integer_dtype(series):
        return "int"
    if ptypes.is_float_dtype(series):
        return "float"
    return str(series.dtype)


def _sample_column_values(series: "pd.Series", limit: int = 8) -> List[Any]:
    try:
        cleaned = series.dropna()
    except Exception:
        return []
    if cleaned.empty:
        return []
    head = cleaned.head(limit)
    samples: List[Any] = []
    for value in head.tolist():
        if isinstance(value, (pd.Timestamp, datetime)):
            samples.append(value.isoformat())
        else:
            samples.append(value if isinstance(value, (str, int, float)) else str(value))
    return samples


def _serialize_preview_records(frame: "pd.DataFrame", limit: int = 50) -> List[Dict[str, Any]]:
    preview = frame.head(limit).copy()
    for column in preview.columns:
        series = preview[column]
        if ptypes.is_datetime64_any_dtype(series):
            preview[column] = series.dt.strftime("%Y-%m-%dT%H:%M:%S").where(~series.isna(), None)
        elif ptypes.is_bool_dtype(series):
            coerced = series.astype("boolean")
            preview[column] = coerced.astype(object).where(~coerced.isna(), None)
        elif ptypes.is_numeric_dtype(series):
            preview[column] = series.where(~series.isna(), None)
        else:
            preview[column] = series.astype("string").where(~series.isna(), None)
    return preview.replace({pd.NA: None}).to_dict(orient="records")


def _build_layer1_catalog(layer1_path: Path, schema_path: Path, run_id: str) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
    if not layer1_path.exists():
        return None
    try:
        frame = pd.read_parquet(layer1_path)
    except Exception:
        return None

    schema_payload: Dict[str, Any] = {}
    if schema_path.exists():
        try:
            schema_payload = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            schema_payload = {}
    column_lookup = {
        str(entry.get("name")): entry
        for entry in schema_payload.get("columns", [])
        if isinstance(entry, Mapping) and entry.get("name")
    }

    columns_meta: List[Dict[str, Any]] = []
    role_counts: Dict[str, int] = {}
    for column in frame.columns:
        series = frame[column]
        base_meta = column_lookup.get(column, {})
        role = base_meta.get("role") or _infer_semantic_role(series)
        dtype_repr = base_meta.get("dtype") or _format_dtype(series)
        label_payload = base_meta.get("label")
        if isinstance(label_payload, Mapping):
            label_en = label_payload.get("en") or column.replace("_", " ").title()
            label_ar = label_payload.get("ar") or label_en
        else:
            label_en = column.replace("_", " ").title()
            label_ar = label_en
        description_payload = base_meta.get("description")
        if isinstance(description_payload, Mapping):
            description_en = description_payload.get("en") or label_en
            description_ar = description_payload.get("ar") or description_en
        elif isinstance(description_payload, str):
            description_en = description_payload
            description_ar = description_payload
        else:
            description_en = label_en
            description_ar = label_ar

        null_fraction = float(series.isna().mean()) if len(series) else 0.0
        sample_values = _sample_column_values(series)
        unique_count = None
        try:
            unique_count = int(series.dropna().nunique())
        except Exception:
            unique_count = None

        column_entry = {
            "name": column,
            "role": role,
            "dtype": dtype_repr,
            "label": {"en": label_en, "ar": label_ar},
            "description": {"en": description_en, "ar": description_ar},
            "nullable": bool(series.isna().any()),
            "null_fraction": null_fraction,
            "sample_values": sample_values,
            "unique_values": unique_count,
        }
        if isinstance(base_meta.get("source_columns"), list):
            column_entry["source_columns"] = base_meta["source_columns"]
        columns_meta.append(column_entry)
        role_counts[role] = role_counts.get(role, 0) + 1

    catalog = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "row_count": int(frame.shape[0]),
        "field_count": int(frame.shape[1]),
        "role_counts": role_counts,
        "columns": columns_meta,
    }
    preview_rows = _serialize_preview_records(frame)
    return catalog, preview_rows


def _schema_hash(columns: Sequence[str]) -> str:
    import hashlib

    ordered = "\n".join(sorted(columns))
    return hashlib.sha256(ordered.encode("utf-8")).hexdigest()


def _write_logs(out_dir: Path, records: Iterable[Dict[str, Any]]) -> None:
    log_path = out_dir / "logs.jsonl"
    with log_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _normalize_name(value: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(value).strip()).lower()


def _load_kpi_synonyms() -> Dict[str, List[str]]:
    if KPI_CONTRACT_PATH.exists():
        try:
            payload = yaml.safe_load(KPI_CONTRACT_PATH.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover - defensive
            payload = None
        if isinstance(payload, Mapping):
            raw = payload.get("kpis")
            if isinstance(raw, Mapping):
                synonyms: Dict[str, List[str]] = {}
                for canonical, values in raw.items():
                    entries: List[str] = []
                    if isinstance(values, str):
                        entries.append(values)
                    elif isinstance(values, (list, tuple, set)):
                        entries.extend(str(item) for item in values if isinstance(item, str))
                    if not entries:
                        continue
                    canonical_str = str(canonical)
                    merged = [canonical_str] + entries
                    synonyms[canonical_str] = merged
                if synonyms:
                    return synonyms
    return {name: [name] for name in DEFAULT_KPI_NAMES}


def _derive_keep_features(decision_entries: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> List[str]:
    excluded: Set[str] = set()
    for entry in decision_entries:
        features = entry.get("features")
        if isinstance(features, list):
            excluded.update(str(item) for item in features if isinstance(item, str))
        for key in ("stop_features", "warn_features"):
            vals = entry.get(key)
            if isinstance(vals, list):
                excluded.update(str(item) for item in vals if isinstance(item, str))
    return [col for col in columns if col not in excluded]


def _kpi_fallback(
    out_dir: Path,
    df: pd.DataFrame,
    decision_entries: Sequence[Mapping[str, Any]],
    redundancy_payload: Mapping[str, Any],
    leakage_after_event: Sequence[Mapping[str, Any]],
    logs: List[Dict[str, Any]],
) -> None:
    corr_kpi_path = out_dir / "correlations_kpi.json"
    try:
        existing = json.loads(corr_kpi_path.read_text(encoding="utf-8"))
    except Exception:
        existing = []
    if not isinstance(existing, list):
        existing = []
    if existing:
        logs.append({"event": "kpi_fallback", "added": 0, "message": "skipped_non_empty"})
        return

    synonyms_map = _load_kpi_synonyms()
    normalized_lookup = {_normalize_name(col): str(col) for col in df.columns}
    kpi_actual_map: Dict[str, List[str]] = {}
    for canonical, synonym_list in synonyms_map.items():
        matches: List[str] = []
        for synonym in synonym_list:
            norm = _normalize_name(synonym)
            if norm in normalized_lookup:
                matches.append(normalized_lookup[norm])
        if matches:
            kpi_actual_map[str(canonical)] = sorted(set(matches))

    if not kpi_actual_map:
        logs.append({"event": "kpi_fallback", "severity": "WARN", "message": "no_kpi_columns_found"})
        corr_kpi_path.write_text("[]", encoding="utf-8")
        return

    kpi_columns: Set[str] = {actual for actuals in kpi_actual_map.values() for actual in actuals}
    keep_features = _derive_keep_features(decision_entries, [str(col) for col in df.columns])
    numeric_columns = set(df.select_dtypes(include=[np.number, "bool"]).columns.astype(str))
    nzv_features = {
        str(item.get("feature"))
        for item in redundancy_payload.get("near_zero_variance", []) or []
        if isinstance(item, Mapping) and item.get("feature")
    }
    after_event_features = {
        str(item.get("feature"))
        for item in leakage_after_event or []
        if isinstance(item, Mapping) and item.get("feature")
    }
    nzv_override_features: Set[str] = set()
    for pair in redundancy_payload.get("high_corr_pairs", []) or []:
        if not isinstance(pair, Mapping):
            continue
        f1 = pair.get("f1")
        f2 = pair.get("f2")
        if isinstance(f1, str) and f1 in kpi_columns and isinstance(f2, str):
            nzv_override_features.add(f2)
        if isinstance(f2, str) and f2 in kpi_columns and isinstance(f1, str):
            nzv_override_features.add(f1)

    candidate_pool: List[str] = []
    nzv_overrides_applied: Dict[str, bool] = {}
    for col in keep_features:
        if col not in numeric_columns:
            continue
        if col.endswith("_is_missing"):
            continue
        if col in after_event_features:
            continue
        if col in nzv_features and col not in nzv_override_features:
            continue
        reason = _id_like_reason(col)
        if reason:
            logs.append({"event": "id_like_filter", "column": col, "reason": reason})
            continue
        if col in nzv_override_features:
            nzv_overrides_applied[col] = True
        candidate_pool.append(col)

    results: List[Dict[str, Any]] = []
    total_added = 0
    low_signal_cache: Dict[str, List[Dict[str, Any]]] = {}
    for canonical, actual_columns in kpi_actual_map.items():
        for actual_col in actual_columns:
            if actual_col not in df.columns:
                continue
            series = pd.to_numeric(df[actual_col], errors="coerce")
            valid_series = series.dropna()
            if valid_series.empty:
                logs.append({"event": "kpi_fallback", "kpi": actual_col, "candidates": 0, "added": 0})
                continue
            nunique = valid_series.nunique(dropna=True)
            method = "pearson" if len(valid_series) >= 1000 and nunique >= 20 else "spearman"

            candidate_results: List[Dict[str, Any]] = []
            for feature in candidate_pool:
                if feature == actual_col:
                    continue
                feature_series = pd.to_numeric(df[feature], errors="coerce")
                mask = feature_series.notna() & series.notna()
                n_valid = int(mask.sum())
                if n_valid < 3:
                    continue
                try:
                    r_value = series[mask].corr(feature_series[mask], method=method)
                except Exception:
                    continue
                if r_value is None or not isinstance(r_value, (int, float)):
                    continue
                if not math.isfinite(r_value):
                    continue
                base_record: Dict[str, Any] = {
                    "kpi": actual_col,
                    "feature": feature,
                    "r": float(r_value),
                    "n": n_valid,
                    "method": method,
                }
                if feature in nzv_overrides_applied:
                    base_record["nzv_override"] = True

                if abs(r_value) >= LOW_SIGNAL_CORR_THRESHOLD:
                    strong_record = dict(base_record)
                    strong_record.update({"source": "kpi_fallback", "low_signal": False})
                    candidate_results.append(strong_record)
                else:
                    weak_record = dict(base_record)
                    low_signal_cache.setdefault(actual_col, []).append(weak_record)

            candidate_results.sort(key=lambda item: abs(item["r"]), reverse=True)
            top_candidates = candidate_results[:10]
            results.extend(top_candidates)
            total_added += len(top_candidates)
            logs.append(
                {
                    "event": "kpi_fallback",
                    "kpi": actual_col,
                    "candidates": len(candidate_pool),
                    "added": len(top_candidates),
                    "method": method,
                }
            )

    if total_added == 0:
        fallback_low_signal: List[Dict[str, Any]] = []
        for actual_col, entries in low_signal_cache.items():
            if not entries:
                continue
            entries.sort(key=lambda item: abs(item["r"]), reverse=True)
            selected = entries[:10]
            max_abs = max(abs(item["r"]) for item in selected) if selected else None
            for entry in selected:
                record = dict(entry)
                record.update(
                    {
                        "source": "kpi_fallback_low_signal",
                        "low_signal": True,
                        "note": f"abs(r)={abs(record['r']):.3f} below threshold {LOW_SIGNAL_CORR_THRESHOLD}",
                    }
                )
                fallback_low_signal.append(record)
            logs.append(
                {
                    "event": "kpi_fallback",
                    "kpi": actual_col,
                    "candidates": len(candidate_pool),
                    "added": len(selected),
                    "method": selected[0]["method"] if selected else None,
                    "low_signal": True,
                    "threshold": LOW_SIGNAL_CORR_THRESHOLD,
                    "max_abs_r": max_abs,
                }
            )

        if fallback_low_signal:
            corr_kpi_path.write_text(json.dumps(fallback_low_signal, ensure_ascii=False, indent=2), encoding="utf-8")
            return

        logs.append({"event": "kpi_fallback", "severity": "WARN", "message": "no_kpi_correlations_added"})
        corr_kpi_path.write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
        return

    corr_kpi_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def _generate_kpi_candidates(
    df: "pd.DataFrame",
    run_id: str,
    artifacts_root: Path,
    out_dir: Path,
    config: Mapping[str, Any],
    logs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    kpi_cfg = config.get("kpi_selector") if isinstance(config, Mapping) else {}
    if kpi_cfg is None:
        kpi_cfg = {}
    if not bool(kpi_cfg.get("enabled", True)):
        logs.append({"event": "kpi_selector_llm", "status": "disabled"})
        return None

    repo = TerminologyRepository(artifacts_root, run_id)
    min_confidence = float(kpi_cfg.get("confidence_threshold", 0.65))
    max_columns = int(kpi_cfg.get("max_columns", 120))
    provider = kpi_cfg.get("provider")
    model = kpi_cfg.get("model")
    temperature = float(kpi_cfg.get("temperature", 0.1))
    max_tokens = int(kpi_cfg.get("max_tokens", 900))

    entries: List[Mapping[str, Any]] = []
    for entry in repo.get_columns():
        column_id = str(entry.get("column_id") or "").strip()
        if not column_id or column_id not in df.columns:
            continue
        series = df[column_id]
        if not (pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series)):
            continue
        sample_values = (
            series.dropna()
            .astype(str)
            .map(lambda x: x.strip())
            .replace("", pd.NA)
            .dropna()
            .head(int(kpi_cfg.get("sample_values", 12)))
            .tolist()
        )
        profile = repo.get_profile(column_id) or {}
        entries.append(
            {
                "column_id": column_id,
                "display": entry.get("display"),
                "description": entry.get("description"),
                "dtype": str(series.dtype),
                "units": entry.get("units"),
                "tags": entry.get("tags", []),
                "is_kpi_hint": bool(entry.get("is_kpi", False)),
                "sample_values": [str(val) for val in sample_values],
                "profile": profile,
            }
        )
    if not entries:
        logs.append({"event": "kpi_selector_llm", "status": "skipped_no_entries"})
        return None

    entries = entries[:max_columns]
    result = select_kpi_candidates(
        entries,
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    candidates = result.get("candidates", [])
    selected = [
        item
        for item in candidates
        if isinstance(item, Mapping)
        and item.get("is_kpi")
        and float(item.get("confidence", 0)) >= min_confidence
    ]

    semantic_dir = out_dir / "semantic"
    semantic_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "provider": result.get("provider"),
        "model": result.get("model"),
        "confidence_threshold": min_confidence,
        "total_candidates": len(candidates),
        "selected_count": len(selected),
        "selected": selected,
        "candidates": candidates,
    }
    path = semantic_dir / "kpi_candidates.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logs.append(
        {
            "event": "kpi_selector_llm",
            "provider": result.get("provider"),
            "model": result.get("model"),
            "total": len(candidates),
            "selected": len(selected),
        }
    )
    return {"path": path.as_posix(), "selected": len(selected), "total": len(candidates), "threshold": min_confidence}
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


def _write_correlations_kpi(out_dir: Path, corr_pairs: Sequence[Dict[str, Any]], logs: List[Dict[str, Any]]) -> None:
    correlations_kpi_path = out_dir / "correlations_kpi.json"
    try:
        kpi_names = _load_kpi_names()
        kpi_lookup = {name.lower() for name in kpi_names}
        records: List[Dict[str, Any]] = []
        unique_kpis: Set[str] = set()
        for entry in corr_pairs:
            f1 = entry.get("f1")
            f2 = entry.get("f2")
            r_value = entry.get("r")
            n_value = entry.get("n")
            if not isinstance(f1, str) or not isinstance(f2, str):
                continue
            f1_l = f1.lower()
            f2_l = f2.lower()
            if f1_l in kpi_lookup and f2_l not in kpi_lookup:
                records.append({"kpi": f1, "feature": f2, "r": r_value, "n": n_value})
                unique_kpis.add(f1)
            elif f2_l in kpi_lookup and f1_l not in kpi_lookup:
                records.append({"kpi": f2, "feature": f1, "r": r_value, "n": n_value})
                unique_kpis.add(f2)
        correlations_kpi_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        logs.append(
            {
                "rule": "correlations_kpi",
                "count": len(records),
                "kpis_detected": sorted(unique_kpis),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        correlations_kpi_path.write_text("[]", encoding="utf-8")
        logs.append({"rule": "correlations_kpi", "severity": "WARN", "error": str(exc)})


def _near_zero_variance(df: pd.DataFrame) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    n_rows = float(len(df)) if len(df) else 1.0
    for col in df.columns:
        if str(col).endswith("_is_missing"):
            continue
        series = df[col]
        non_null = series.dropna()
        if non_null.empty:
            dominant_ratio = 0.0
            unique_ratio = 0.0
            std = 0.0
        else:
            counts = non_null.value_counts(normalize=True)
            dominant_ratio = float(counts.iloc[0]) if not counts.empty else 0.0
            unique_ratio = float(non_null.nunique()) / n_rows
            std = float(non_null.astype(float).std()) if ptypes.is_numeric_dtype(non_null.dtype) else 0.0
        is_nzv = (
            (ptypes.is_numeric_dtype(series.dtype) and math.isclose(std, 0.0, abs_tol=1e-12))
            or dominant_ratio >= NZV_DOMINANT_THRESHOLD
            or unique_ratio <= NZV_UNIQUE_RATIO_THRESHOLD
        )
        if is_nzv:
            results.append(
                {
                    "feature": str(col),
                    "std": std,
                    "dominant_ratio": dominant_ratio,
                    "unique_ratio": unique_ratio,
                }
            )
    return results


def _prepare_numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    numeric_df = df.select_dtypes(include=["number", "bool"]).copy()
    for col in numeric_df.columns:
        if ptypes.is_bool_dtype(numeric_df[col].dtype):
            numeric_df[col] = numeric_df[col].astype(float)
    return numeric_df


def _prepare_datetime_numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    datetime_cols: List[str] = [
        col
        for col in df.columns
        if ptypes.is_datetime64_any_dtype(df[col].dtype) or ptypes.is_datetime64tz_dtype(df[col].dtype)
    ]
    if not datetime_cols:
        return pd.DataFrame(index=df.index)

    converted: Dict[str, pd.Series] = {}
    for col in datetime_cols:
        series = df[col]
        if not ptypes.is_datetime64_any_dtype(series.dtype) and not ptypes.is_datetime64tz_dtype(series.dtype):
            continue
        temp = series
        if ptypes.is_datetime64tz_dtype(temp.dtype):
            temp = temp.dt.tz_convert("UTC").dt.tz_localize(None)
        numeric_ready = temp.astype("datetime64[ns]")
        values = numeric_ready.to_numpy(dtype="datetime64[ns]")
        int_values = values.astype("datetime64[ns]").astype("int64").astype(float)
        int_values /= 1e9
        mask = np.isnat(values)
        if mask.any():
            int_values[mask] = np.nan
        converted[col] = pd.Series(int_values, index=series.index, name=str(col))

    if not converted:
        return pd.DataFrame(index=df.index)
    return pd.DataFrame(converted)


def _numeric_stats_map(numeric_df: "pd.DataFrame") -> Dict[str, Dict[str, float]]:
    stats_map: Dict[str, Dict[str, float]] = {}
    for column in numeric_df.columns:
        series = numeric_df[column].dropna()
        if series.empty:
            continue
        try:
            mean = float(series.mean())
        except Exception:
            mean = 0.0
        try:
            std = float(series.std())
        except Exception:
            std = 0.0
        stats_map[str(column)] = {"mean": mean, "std": std}
    return stats_map


def _compute_correlations_from_numeric_df(
    numeric_df: pd.DataFrame,
    *,
    enricher: Optional[ShippingCorrelationEnricher] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]:
    numeric_cols = list(numeric_df.columns)
    if len(numeric_cols) < 2:
        return [], [], 0.0

    sampled_df = numeric_df
    if len(numeric_cols) > 70:
        sample_size = min(500000, len(numeric_df))
        sampled_df = numeric_df.sample(n=sample_size, random_state=READINESS_RANDOM_SEED)
    elif len(numeric_cols) > 50:
        if len(numeric_df) > 100000:
            sampled_df = numeric_df.sample(n=100000, random_state=READINESS_RANDOM_SEED)

    flagged_pairs: List[Dict[str, Any]] = []
    top_pairs: List[Dict[str, Any]] = []
    total_pairs = len(numeric_cols) * (len(numeric_cols) - 1) / 2

    for c1, c2 in combinations(numeric_cols, 2):
        pair_df = sampled_df[[c1, c2]].dropna()
        n = int(pair_df.shape[0])
        if n < 10:
            continue
        try:
            r_value, p_value = stats.pearsonr(pair_df[c1], pair_df[c2])
        except Exception:
            continue
        if r_value is None or not isinstance(r_value, (int, float)):
            continue
        if not math.isfinite(float(r_value)):
            continue
        abs_r = abs(float(r_value))
        record: Dict[str, Any] = {
            "f1": c1,
            "f2": c2,
            "feature_a": c1,
            "feature_b": c2,
            "r": float(r_value),
            "correlation": float(r_value),
            "abs_r": abs_r,
            "abs_correlation": abs_r,
            "n": n,
            "sample_size": n,
            "method": "pearson",
        }
        if isinstance(p_value, (int, float)) and math.isfinite(float(p_value)):
            record["p_value"] = float(p_value)
        if enricher is not None:
            record.update(
                enricher.enrich_pair(
                    c1,
                    c2,
                    float(r_value),
                    n,
                    method="pearson",
                )
            )
        top_pairs.append(record)
        if abs_r > CORR_THRESHOLD:
            flagged_pairs.append(dict(record))

    top_pairs_sorted = sorted(top_pairs, key=lambda x: x["abs_correlation"], reverse=True)[:50]
    ratio = len(flagged_pairs) / total_pairs if total_pairs else 0.0
    return flagged_pairs, top_pairs_sorted, ratio


def _compute_correlations(
    df: pd.DataFrame,
    enricher: Optional[ShippingCorrelationEnricher] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]:
    numeric_df = _prepare_numeric_df(df)
    if enricher is not None:
        enricher.set_numeric_stats(_numeric_stats_map(numeric_df))
    flagged_pairs, top_pairs_sorted, ratio = _compute_correlations_from_numeric_df(numeric_df, enricher=enricher)
    return flagged_pairs, top_pairs_sorted, ratio


def _compute_datetime_correlations(
    df: pd.DataFrame,
    enricher: Optional[ShippingCorrelationEnricher] = None,
) -> List[Dict[str, Any]]:
    datetime_numeric_df = _prepare_datetime_numeric_df(df)
    if datetime_numeric_df.empty or len(datetime_numeric_df.columns) < 2:
        return []

    _, top_pairs, _ = _compute_correlations_from_numeric_df(datetime_numeric_df, enricher=enricher)
    return top_pairs


def _load_feature_spec(feature_dir: Path) -> Dict[str, Any]:
    spec_path = feature_dir / "feature_spec.json"
    if not spec_path.exists():
        return {}
    try:
        return json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _identify_id_like(columns: Sequence[str]) -> List[str]:
    pattern = re.compile(r"(?:^|_)(?:id|hash|guid|uuid)$|hash|md5|sha", re.IGNORECASE)
    return sorted(col for col in columns if pattern.search(str(col)))


def _convert_datetime(series: pd.Series) -> pd.Series:
    if ptypes.is_datetime64_any_dtype(series):
        return series
    return pd.to_datetime(series, errors="coerce", utc=False)


def _detect_after_event(
    df: pd.DataFrame, spec: Dict[str, Any], main_ts_col: Optional[str]
) -> List[Dict[str, Any]]:
    if not main_ts_col or main_ts_col not in df.columns:
        return []

    main_ts = _convert_datetime(df[main_ts_col])
    if main_ts.isna().all():
        return []

    baseline = main_ts
    results: List[Dict[str, Any]] = []

    comparison_columns: Set[str] = set()
    for key in ("business_event_ts", "target"):
        val = spec.get(key)
        if isinstance(val, str) and val in df.columns:
            comparison_columns.add(val)
    comparison_columns |= {col for col in df.columns if ptypes.is_datetime64_any_dtype(df[col].dtype)}

    for col in sorted(comparison_columns):
        if col == main_ts_col:
            continue
        candidate = _convert_datetime(df[col])
        mask = candidate.notna() & baseline.notna()
        if not mask.any():
            continue
        after_ratio = float((candidate[mask] > baseline[mask]).sum()) / float(mask.sum())
        if after_ratio > AFTER_EVENT_RATIO_THRESHOLD:
            results.append({"feature": col, "pct_after_event": after_ratio})
    return results


def _psi_bins(values: np.ndarray, num_bins: int) -> np.ndarray:
    unique_vals = np.unique(values)
    if unique_vals.size <= num_bins:
        bins = np.linspace(values.min(), values.max(), unique_vals.size + 1)
    else:
        quantiles = np.linspace(0, 1, num_bins + 1)
        bins = np.unique(np.quantile(values, quantiles))
    if bins.size < 2:
        bins = np.array([values.min(), values.max() + 1e-9])
    return bins


def _calc_psi(base_vals: np.ndarray, comp_vals: np.ndarray, bins: np.ndarray) -> float:
    base_counts, _ = np.histogram(base_vals, bins=bins)
    comp_counts, _ = np.histogram(comp_vals, bins=bins)
    base_dist = base_counts / base_counts.sum() if base_counts.sum() else np.zeros_like(base_counts, dtype=float)
    comp_dist = comp_counts / comp_counts.sum() if comp_counts.sum() else np.zeros_like(comp_counts, dtype=float)
    eps = 1e-6
    base_adj = np.where(base_dist == 0, eps, base_dist)
    comp_adj = np.where(comp_dist == 0, eps, comp_dist)
    psi = np.sum((base_adj - comp_adj) * np.log(base_adj / comp_adj))
    return float(psi)


def _psi_analysis(
    df: pd.DataFrame,
    main_ts_col: Optional[str],
    candidates: Sequence[str],
) -> Tuple[Dict[str, Any], int, List[str], List[str]]:
    if not main_ts_col or main_ts_col not in df.columns:
        return {"status": "missing_ts", "psi": []}, 0, [], []

    main_ts_series = _convert_datetime(df[main_ts_col])
    if main_ts_series.isna().all():
        return {"status": "missing_ts", "psi": []}, 0, [], []

    month_series = main_ts_series.dt.to_period("M")
    valid_mask = month_series.notna()
    months_index = month_series[valid_mask].unique()
    if isinstance(months_index, pd.Index):
        months_list = list(months_index.sort_values())
    else:
        months_list = sorted(list(months_index))

    col_lookup = {str(col).lower(): str(col) for col in df.columns}

    if len(months_list) < 2:
        psi_entries: List[Dict[str, Any]] = []
        evaluated = 0
        warn_features: List[str] = []
        stop_features: List[str] = []
        for candidate in candidates:
            col_name = col_lookup.get(candidate.lower())
            if not col_name:
                continue
            series = df[col_name]
            if not pd.api.types.is_numeric_dtype(series):
                continue
            numeric_series = pd.to_numeric(series, errors="coerce")
            combined = pd.DataFrame({"ts": main_ts_series, "value": numeric_series}).dropna()
            if combined.shape[0] < 2:
                continue
            combined = combined.sort_values("ts")
            split_index = combined.shape[0] // 2
            if split_index == 0 or split_index == combined.shape[0]:
                continue
            baseline_values = combined["value"].iloc[:split_index]
            comp_values = combined["value"].iloc[split_index:]
            if comp_values.empty or baseline_values.empty:
                continue
            bins = _psi_bins(baseline_values.to_numpy(), min(10, len(baseline_values)))
            psi_val = _calc_psi(baseline_values.to_numpy(), comp_values.to_numpy(), bins)
            if psi_val > PSI_STOP_THRESHOLD:
                status = "STOP"
                stop_features.append(col_name)
            elif psi_val > PSI_WARN_THRESHOLD:
                status = "WARN"
                warn_features.append(col_name)
            else:
                status = "OK"
            psi_entries.append(
                {
                    "feature": col_name,
                    "status": status,
                    "psi": psi_val,
                    "method": "temporal_half_split",
                    "baseline_size": int(len(baseline_values)),
                    "comparison_size": int(len(comp_values)),
                    "bins": len(bins) - 1,
                }
            )
            evaluated += 1
        overall_status = "fallback_split" if evaluated else "insufficient_history"
        return {"status": overall_status, "psi": psi_entries}, evaluated, warn_features, stop_features

    baseline_month = months_list[0]
    baseline_mask = month_series == baseline_month

    psi_entries: List[Dict[str, Any]] = []
    warn_features: List[str] = []
    stop_features: List[str] = []
    evaluated = 0

    for candidate in candidates:
        col_name = col_lookup.get(candidate.lower())
        if not col_name:
            continue
        series = df[col_name]
        if not ptypes.is_numeric_dtype(series):
            continue
        combined_mask = series.notna() & month_series.notna()
        if combined_mask.sum() < 10:
            psi_entries.append(
                {
                    "feature": col_name,
                    "status": "insufficient_data",
                    "psi": None,
                    "baseline_month": str(baseline_month),
                    "comparison_month": None,
                    "bins": None,
                }
            )
            continue
        values = series[combined_mask].astype(float)
        months_filtered = month_series[combined_mask]
        baseline_values = values[months_filtered == baseline_month]
        if baseline_values.empty:
            psi_entries.append(
                {
                    "feature": col_name,
                    "status": "insufficient_baseline",
                    "psi": None,
                    "baseline_month": str(baseline_month),
                    "comparison_month": None,
                    "bins": None,
                }
            )
            continue

        num_bins = 10 if len(values) >= 1000 else 5
        bins = _psi_bins(baseline_values.to_numpy(), num_bins)

        max_psi = 0.0
        worst_month = None
        evaluated_months = 0
        for month in months_list[1:]:
            month_mask = months_filtered == month
            comp_values = values[month_mask]
            if comp_values.empty:
                continue
            psi_val = _calc_psi(baseline_values.to_numpy(), comp_values.to_numpy(), bins)
            evaluated_months += 1
            if psi_val > max_psi:
                max_psi = psi_val
                worst_month = month

        if evaluated_months == 0:
            psi_entries.append(
                {
                    "feature": col_name,
                    "status": "insufficient_comparison",
                    "psi": None,
                    "baseline_month": str(baseline_month),
                    "comparison_month": None,
                    "bins": num_bins,
                }
            )
            continue

        evaluated += 1
        if max_psi > PSI_STOP_THRESHOLD:
            status = "STOP"
            stop_features.append(col_name)
        elif max_psi > PSI_WARN_THRESHOLD:
            status = "WARN"
            warn_features.append(col_name)
        else:
            status = "OK"

        psi_entries.append(
            {
                "feature": col_name,
                "status": status,
                "psi": max_psi,
                "baseline_month": str(baseline_month),
                "comparison_month": str(worst_month) if worst_month is not None else None,
                "bins": num_bins,
            }
        )

    stability_payload = {
        "status": "evaluated",
        "psi": psi_entries,
    }
    return stability_payload, evaluated, warn_features, stop_features


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[override]
    artifacts_root = Path((config or {}).get("artifacts_root", "artifacts"))
    out_dir = artifacts_root / run_id / "stage_07_readiness"
    _ensure_dir(out_dir)

    raw_uri = (inputs or {}).get("raw") or (inputs or {}).get("raw_uri")
    if not isinstance(raw_uri, str):
        raise ValueError("Stage 07 readiness expects inputs['raw'] with feature dataset path")
    raw_path = Path(raw_uri).expanduser().resolve()
    if not raw_path.exists():
        raise FileNotFoundError(f"readiness dataset not found: {raw_path}")

    df = pd.read_parquet(raw_path)
    n_rows = int(len(df))
    n_cols = int(len(df.columns))
    columns = [str(col) for col in df.columns]

    policy = nzv_policy.load_policy()
    nzv_summary_payload, nzv_columns_payload, nzv_source_path = _load_nzv_context(artifacts_root, run_id)
    critical_columns, critical_path = _load_critical_columns()

    baseline = baseline_utils.load(artifacts_root, run_id)
    expected_rows = int(baseline.get("n_rows", 0)) if baseline else None
    baseline_utils.enforce_row_guard(expected=expected_rows, actual=n_rows, phase="07", out_dir=out_dir)

    logs: List[Dict[str, Any]] = [{"rule": "dimensions", "n_rows": n_rows, "n_cols": n_cols}]
    logs.append(
        {
            "rule": "nzv_summary_source",
            "path": nzv_source_path.as_posix() if nzv_source_path else None,
            "summary_loaded": bool(nzv_summary_payload),
            "columns_loaded": bool(nzv_columns_payload),
        }
    )
    if critical_path is None:
        logs.append({"rule": "critical_columns_missing", "path": CRITICAL_COLUMNS_PATH.as_posix()})
    else:
        logs.append({"rule": "critical_columns_loaded", "path": critical_path.as_posix(), "count": len(critical_columns)})

    if n_cols == 0:
        payload = {
            "run_id": run_id,
            "gate": {"status": "STOP", "reasons": ["no_features"]},
            "key_stats": {"n_rows": n_rows, "n_cols": n_cols},
            "source": raw_path.as_posix(),
        }
        (out_dir / "readiness_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_logs(out_dir, logs + [{"rule": "no_features"}])
        (out_dir / "row_meta.json").write_text(
            json.dumps({"phase": "07", "n_rows": n_rows, "source": raw_path.as_posix(), "n_cols": n_cols}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise SystemExit(1)

    missing_cells = int(df.isna().sum().sum())
    total_cells = n_rows * n_cols if n_rows and n_cols else 0
    missing_ratio = float(missing_cells) / float(total_cells) if total_cells else 0.0
    schema_hash = _schema_hash(columns)

    use_nzv_entries = any(_is_nzv_entry(entry) for entry in nzv_columns_payload)
    if use_nzv_entries:
        nzv_details = _build_nzv_details_from_columns(nzv_columns_payload)
    else:
        nzv_details = _near_zero_variance(df)
        nzv_columns_payload = []

    if not isinstance(nzv_summary_payload, Mapping):
        nzv_summary_payload = None

    if nzv_summary_payload is None:
        n_constant_like = sum(1 for item in nzv_details if str(item.get("nzv_category")).lower() == "constant_like")
        nzv_summary_payload = {
            "n_nzv_columns": len(nzv_details),
            "n_constant_like": n_constant_like,
            "n_high_imbalance": 0,
            "n_total_columns": n_cols,
            "nzv_ratio": float(len(nzv_details)) / float(n_cols) if n_cols else 0.0,
        }

    nzv_count = int(nzv_summary_payload.get("n_nzv_columns", len(nzv_details)))
    total_cols_for_ratio = int(nzv_summary_payload.get("n_total_columns") or n_cols)
    if total_cols_for_ratio:
        nzv_ratio = float(nzv_summary_payload.get("nzv_ratio", nzv_count / total_cols_for_ratio))
    else:
        nzv_ratio = 0.0

    nzv_flagged_names: Set[str] = set()
    if nzv_columns_payload:
        for entry in nzv_columns_payload:
            if not isinstance(entry, Mapping):
                continue
            if not _is_nzv_entry(entry):
                continue
            for variant in _nzv_name_variants(entry):
                nzv_flagged_names.add(variant.lower())
    else:
        for detail in nzv_details:
            feature_name = detail.get("feature")
            if isinstance(feature_name, str):
                nzv_flagged_names.add(feature_name.lower())

    critical_hits = sorted(
        {col for col in critical_columns if isinstance(col, str) and col.strip().lower() in nzv_flagged_names}
    )
    logs.append({"rule": "critical_nzv_hits", "columns": critical_hits})

    kpi_synonyms = _load_kpi_synonyms()
    terminology_repo = TerminologyRepository(artifacts_root, run_id)
    enricher = ShippingCorrelationEnricher(
        artifacts_root,
        run_id,
        repo=terminology_repo,
        kpi_synonyms=kpi_synonyms,
    )
    history_tracker = CorrelationHistoryTracker(artifacts_root)

    corr_flagged, corr_top, corr_ratio = _compute_correlations(df, enricher=enricher)
    corr_time_top = _compute_datetime_correlations(df, enricher=enricher)
    history_tracker.mark_and_update(run_id, corr_top)
    history_tracker.mark_and_update(run_id, corr_flagged)
    history_tracker.mark_and_update(run_id, corr_time_top)
    corr_count = len(corr_flagged)

    feature_dir = artifacts_root / run_id / "stage_06_feature_eng"
    layer1_dataset_path = feature_dir / "layer1_dataset.parquet"
    layer1_schema_path = feature_dir / "layer1_schema.json"
    layer1_catalog_payload = _build_layer1_catalog(layer1_dataset_path, layer1_schema_path, run_id)
    layer1_catalog_paths: Dict[str, str] = {}
    layer1_field_count: Optional[int] = None
    layer1_row_count: Optional[int] = None
    if layer1_catalog_payload:
        catalog_payload, preview_rows = layer1_catalog_payload
        catalog_path = out_dir / "layer1_catalog.json"
        catalog_path.write_text(json.dumps(catalog_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        preview_path = out_dir / "layer1_preview.json"
        preview_payload = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rows": preview_rows,
            "count": len(preview_rows),
        }
        preview_path.write_text(json.dumps(preview_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        layer1_catalog_paths = {
            "layer1_catalog": catalog_path.as_posix(),
            "layer1_preview": preview_path.as_posix(),
            "layer1_dataset": layer1_dataset_path.as_posix(),
            "layer1_schema": layer1_schema_path.as_posix(),
        }
        logs.append(
            {
                "rule": "layer1_catalog",
                "columns": catalog_payload.get("field_count"),
                "rows": catalog_payload.get("row_count"),
                "path": catalog_path.as_posix(),
            }
        )
        layer1_field_count = catalog_payload.get("field_count")
        layer1_row_count = catalog_payload.get("row_count")
    feature_spec = _load_feature_spec(feature_dir)
    main_ts = feature_spec.get("main_ts") if isinstance(feature_spec, dict) else None
    leakage_id_like = _identify_id_like(columns)
    leakage_after_event = _detect_after_event(df, feature_spec if isinstance(feature_spec, dict) else {}, main_ts if isinstance(main_ts, str) else None)
    leakage_payload = {
        "id_like": leakage_id_like,
        "after_event_like": leakage_after_event,
        "notes": f"main_ts={main_ts}, business_event_ts={feature_spec.get('business_event_ts') if isinstance(feature_spec, dict) else None}",
    }

    psi_candidates = ["COD_AMOUNT", "WEIGHT_KG", "VOLUMETRIC_WEIGHT"]
    stability_payload, psi_evaluated, psi_warn_features, psi_stop_features = _psi_analysis(df, main_ts if isinstance(main_ts, str) else None, psi_candidates)

    key_stats = {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "missing_cells_pct": missing_ratio,
        "nzv_count": nzv_count,
        "high_corr_pairs": corr_count,
        "psi_columns_evaluated": psi_evaluated,
        "nzv_summary": nzv_summary_payload,
    }

    gate_status = "PASS"
    stop_reasons: List[str] = []
    warn_reasons: List[str] = []

    if psi_stop_features:
        stop_reasons.append("psi_drift")
    if nzv_ratio > 0.10:
        warn_reasons.append("nzv_ratio_high")
    if corr_ratio > 0.05:
        warn_reasons.append("high_corr_ratio")
    if psi_warn_features:
        warn_reasons.append("psi_warn")
    if missing_ratio > 0.30:
        warn_reasons.append("missing_cells_high")

    readiness_notes: List[str] = []
    if policy.enable_readiness_adjustment:
        ratio_value = nzv_ratio
        if ratio_value < policy.max_nzv_ratio_for_pass and not critical_hits:
            if "nzv_ratio_high" in warn_reasons:
                warn_reasons = [reason for reason in warn_reasons if reason != "nzv_ratio_high"]
                message = (
                    "Many low-variance metadata fields detected, but no KPI-critical fields are NZV; treated as contextual metadata only."
                )
                readiness_notes.append(message)
                logs.append(
                    {
                        "rule": "nzv_adjustment",
                        "status": "bypassed",
                        "ratio": ratio_value,
                        "max_ratio": policy.max_nzv_ratio_for_pass,
                    }
                )
        else:
            detail_parts: List[str] = []
            if ratio_value >= policy.max_nzv_ratio_for_pass:
                detail_parts.append(
                    f"nzv_ratio {ratio_value:.2f} >= max_nzv_ratio_for_pass {policy.max_nzv_ratio_for_pass:.2f}"
                )
            if critical_hits:
                detail_parts.append(f"critical NZV columns: {', '.join(critical_hits)}")
                if "critical_nzv_columns" not in warn_reasons:
                    warn_reasons.append("critical_nzv_columns")
            if detail_parts:
                note = "; ".join(detail_parts)
                readiness_notes.append(note)
                logs.append(
                    {
                        "rule": "nzv_adjustment",
                        "status": "blocked",
                        "ratio": ratio_value,
                        "max_ratio": policy.max_nzv_ratio_for_pass,
                        "critical_hits": critical_hits,
                    }
                )

    if stop_reasons:
        gate_status = "STOP"
        gate_reasons = stop_reasons
    elif warn_reasons:
        gate_status = "WARN"
        gate_reasons = warn_reasons
    else:
        gate_reasons = []

    readiness_report = {
        "run_id": run_id,
        "gate": {"status": gate_status, "reasons": gate_reasons},
        "key_stats": key_stats,
        "schema_hash": schema_hash,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": raw_path.as_posix(),
        "nzv_summary": nzv_summary_payload,
        "critical_nzv_columns": critical_hits,
    }
    if nzv_source_path:
        readiness_report["nzv_source"] = nzv_source_path.as_posix()
    if readiness_notes:
        readiness_report["nzv_notes"] = readiness_notes
    report_path = out_dir / "readiness_report.json"
    report_path.write_text(json.dumps(readiness_report, ensure_ascii=False, indent=2), encoding="utf-8")

    decision_entries: List[Dict[str, Any]] = []
    if nzv_details:
        decision_entries.append(
            {
                "action": "review_or_drop",
                "reason": "near_zero_variance",
                "features": [item["feature"] for item in nzv_details],
                "details": nzv_details[:20],
            }
        )
    if corr_flagged:
        decision_entries.append(
            {
                "action": "evaluate_correlated_pairs",
                "reason": "high_correlation",
                "pairs": corr_flagged[:50],
                "summary": {"total_flagged": len(corr_flagged)},
            }
        )
    if leakage_id_like or leakage_after_event:
        decision_entries.append(
            {
                "action": "check_leakage",
                "reason": "potential_leakage",
                "id_like": leakage_id_like,
                "after_event_like": leakage_after_event,
            }
        )
    if psi_stop_features or psi_warn_features:
        decision_entries.append(
            {
                "action": "monitor_drift",
                "reason": "psi_alert",
                "stop_features": psi_stop_features,
                "warn_features": psi_warn_features,
            }
        )
    if missing_ratio > 0.30:
        decision_entries.append(
            {
                "action": "investigate_missingness",
                "reason": "high_missing_ratio",
                "missing_ratio": missing_ratio,
            }
        )

    redundancy_payload = {
        "near_zero_variance": nzv_details,
        "high_corr_pairs": corr_flagged,
    }
    (out_dir / "redundancy.json").write_text(json.dumps(redundancy_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    (out_dir / "correlations.json").write_text(json.dumps(corr_top, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "correlations_datetime.json").write_text(
        json.dumps(corr_time_top, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_correlations_kpi(out_dir, corr_top, logs)
    _kpi_fallback(out_dir, df, decision_entries, redundancy_payload, leakage_after_event, logs)
    (out_dir / "leakage_scan.json").write_text(json.dumps(leakage_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "stability.json").write_text(json.dumps(stability_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    logs.extend(
        [
            {"rule": "missingness", "value": missing_ratio},
            {"rule": "nzv", "count": nzv_count, "ratio": nzv_ratio},
            {"rule": "high_corr_pairs", "count": corr_count, "ratio": corr_ratio},
            {"rule": "datetime_corr_pairs", "count": len(corr_time_top)},
            {"rule": "leakage_id_like", "count": len(leakage_id_like)},
            {"rule": "leakage_after_event", "count": len(leakage_after_event)},
            {
                "rule": "psi",
                "evaluated": psi_evaluated,
                "warn": len(psi_warn_features),
                "stop": len(psi_stop_features),
            },
            {"rule": "gate", "status": gate_status, "reasons": gate_reasons},
        ]
    )
    _write_logs(out_dir, logs)

    row_meta = {"phase": "07", "n_rows": n_rows, "source": raw_path.as_posix(), "n_cols": n_cols}
    (out_dir / "row_meta.json").write_text(json.dumps(row_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    decision_manifest = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate_status": gate_status,
        "reasons": gate_reasons,
        "entries": decision_entries,
        "critical_nzv_columns": critical_hits,
    }
    if readiness_notes:
        decision_manifest["nzv_notes"] = readiness_notes
    decision_manifest_path = out_dir / "decision_manifest.json"
    decision_manifest_path.write_text(json.dumps(decision_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Generate diagnostics.json
    diagnostics = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate_status": gate_status,
        "gate_reasons": gate_reasons,
        "key_stats": key_stats,
        "summary": {
            "n_rows": n_rows,
            "n_cols": n_cols,
            "missing_ratio": missing_ratio,
            "nzv_count": nzv_count,
            "nzv_ratio": nzv_ratio,
            "high_corr_pairs_count": corr_count,
            "high_corr_ratio": corr_ratio,
            "leakage_id_like_count": len(leakage_id_like),
            "leakage_after_event_count": len(leakage_after_event),
            "psi_evaluated": psi_evaluated,
            "psi_warn_count": len(psi_warn_features),
            "psi_stop_count": len(psi_stop_features),
            "critical_nzv_columns": critical_hits,
        },
        "decision_entries_count": len(decision_entries),
        "nzv_summary": nzv_summary_payload,
    }
    diagnostics_path = out_dir / "diagnostics.json"
    diagnostics_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")

    # Generate network.json in stage_07_correlations directory
    correlations_dir = artifacts_root / run_id / "stage_07_correlations"
    correlations_dir.mkdir(parents=True, exist_ok=True)
    
    # Build network graph from correlations
    nodes_map: Dict[str, Dict[str, Any]] = {}
    edges_list: List[Dict[str, Any]] = []
    node_ids_set: Set[str] = set()
    
    # Process top correlations to build network
    for pair in corr_top[:100]:  # Limit to top 100 for network
        feature_a = str(pair.get("feature_a", ""))
        feature_b = str(pair.get("feature_b", ""))
        corr_value = float(pair.get("abs_correlation", 0.0))
        
        if not feature_a or not feature_b or corr_value < 0.3:  # Filter weak correlations
            continue
        
        # Add nodes
        for feat in [feature_a, feature_b]:
            if feat not in node_ids_set:
                node_ids_set.add(feat)
                nodes_map[feat] = {
                    "id": feat,
                    "label": feat,
                    "type": "feature",
                    "score": 0.0,
                }
        
        # Add edge
        edges_list.append({
            "source": feature_a,
            "target": feature_b,
            "value": round(corr_value, 4),
            "label": "correlation",
        })
    
    # Build network structure
    network = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nodes": list(nodes_map.values()),
        "edges": edges_list,
        "categories": ["feature"],
    }
    network_path = correlations_dir / "network.json"
    network_path.write_text(json.dumps(network, ensure_ascii=False, indent=2), encoding="utf-8")

    kpi_candidates_info = _generate_kpi_candidates(df, run_id, artifacts_root, out_dir, config or {}, logs)

    outputs = {
        "raw": raw_path.as_posix(),
        "readiness_report": report_path.as_posix(),
        "redundancy": (out_dir / "redundancy.json").as_posix(),
        "correlations": (out_dir / "correlations.json").as_posix(),
        "correlations_kpi": (out_dir / "correlations_kpi.json").as_posix(),
        "correlations_datetime": (out_dir / "correlations_datetime.json").as_posix(),
        "leakage_scan": (out_dir / "leakage_scan.json").as_posix(),
        "stability": (out_dir / "stability.json").as_posix(),
        "decision_manifest": decision_manifest_path.as_posix(),
        "diagnostics": diagnostics_path.as_posix(),
        "network": network_path.as_posix(),
    }
    if layer1_catalog_paths:
        outputs.update(layer1_catalog_paths)
    if layer1_field_count is not None:
        key_stats["layer1_fields"] = int(layer1_field_count)
    if layer1_row_count is not None:
        key_stats["layer1_rows"] = int(layer1_row_count)
    if kpi_candidates_info:
        outputs["kpi_candidates"] = kpi_candidates_info["path"]
        key_stats["kpi_llm_selected"] = kpi_candidates_info["selected"]

    return {
        "run_id": run_id,
        "status": gate_status,
        "outputs": outputs,
        "metrics": key_stats,
        "logs_uri": (out_dir / "logs.jsonl").as_posix(),
    }


__all__ = ["run", "_infer_semantic_role", "_build_layer1_catalog"]
