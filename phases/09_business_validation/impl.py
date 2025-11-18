from __future__ import annotations

import json
import time
import math
import pickle
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import duckdb  # type: ignore
import polars as pl  # type: ignore
import yaml  # type: ignore
from zoneinfo import ZoneInfo

from shared import sla as sla_utils  # type: ignore
from backend.src.app.services.system_health import SystemHealth  # type: ignore

from . import io, models

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_HASH = models.stable_hash(Path(__file__).read_text(encoding="utf-8"))
TZ = ZoneInfo(io.DEFAULT_TIMEZONE)

STAGE_01_DIR = "stage_01_ingestion"
STAGE_06_DIR = "stage_06_standardize"
STAGE_08_DIR = "stage_08_insights"
OUT_STAGE = "stage_09_business_validation"
LOW_VARIANCE_CATEGORIES = {"constant_like", "near_zero_variance"}

OPS_ALIAS_CANDIDATES: Dict[str, List[str]] = {
    "created_ts": ["ENTRY_DATE", "created_at", "entry_datetime"],
    "delivered_ts": ["DELIVER_DATE", "DELIVERY_DATE", "delivered_at"],
    "status": ["STATUS", "Sub_Status"],
    "awb_no": ["AWB_NO"],
    "cod_amount": ["COD_AMOUNT", "COD"],
    "receiver_mode": ["RECEIVER_MODE", "RECEIVER MODE", "payment_mode"],
    "city": ["DESTINATION", "CITY"],
    "carrier": ["FORWARD_COMPANY", "FORWARD COMPANY", "carrier"],
}

OPS_METRIC_KEYS = {"sla_pct", "rto_pct", "lead_time_p50", "lead_time_p90"}
MODEL_CATALOG_DEFAULT = PROJECT_ROOT / "contracts" / "models" / "models_catalog.yml"


@dataclass
class ModelCatalogEntry:
    key: str
    target: str
    features: Optional[List[str]]
    model: Any


def _load_model_from_catalog(model_key: str, catalog_path: Optional[Path] = None) -> Optional[ModelCatalogEntry]:
    path = catalog_path or MODEL_CATALOG_DEFAULT
    try:
        catalog_data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None
    if not isinstance(catalog_data, Mapping):
        return None
    models_section = catalog_data.get("models")
    if not isinstance(models_section, Mapping):
        return None
    entry_raw = models_section.get(model_key)
    if not isinstance(entry_raw, Mapping):
        return None
    model_path_raw = entry_raw.get("path")
    target = entry_raw.get("target")
    if not isinstance(model_path_raw, str) or not isinstance(target, str):
        return None
    resolved_path = Path(model_path_raw).expanduser()
    if not resolved_path.is_absolute():
        resolved_path = (PROJECT_ROOT / resolved_path).resolve()
    if not resolved_path.exists():
        return None
    try:
        with resolved_path.open("rb") as handle:
            model = pickle.load(handle)
    except Exception:
        return None
    features_value = entry_raw.get("features")
    features_list = [str(name) for name in features_value] if isinstance(features_value, (list, tuple)) else None
    return ModelCatalogEntry(key=model_key, target=target, features=features_list, model=model)


def _predict_scores(entry: ModelCatalogEntry, frame: pl.DataFrame) -> Optional[List[float]]:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return None

    if entry.features:
        missing = [col for col in entry.features if col not in frame.columns]
        if missing:
            return None
        feature_frame = frame.select(entry.features)
    else:
        numeric_cols = [
            col
            for col, dtype in zip(frame.columns, frame.dtypes)
            if dtype in {pl.Float64, pl.Float32, pl.Int64, pl.Int32, pl.UInt64, pl.UInt32}
        ]
        if not numeric_cols:
            return None
        feature_frame = frame.select(numeric_cols)

    try:
        pandas_df = feature_frame.to_pandas()  # type: ignore[attr-defined]
    except Exception:
        return None

    model = entry.model
    predictions: Optional[List[float]] = None
    if hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba(pandas_df)
            predictions = [float(row[-1]) for row in proba]
        except Exception:
            predictions = None
    if predictions is None and hasattr(model, "predict"):
        try:
            raw = model.predict(pandas_df)
            predictions = [float(value) for value in raw]
        except Exception:
            predictions = None
    return predictions

SLA_LIMIT_HOURS = 48.0
RTO_PATTERN = "RTO|RETURN"

# Core KPI and business logic columns (original)
REQUIRED_FACT_COLUMNS = [
    "entity_id",
    "ts",
    "ORIGIN",
    "DESTINATION",
    "RECEIVER_MODE",
    "STATUS",
    "COD_AMOUNT",
    "kpi_orders_cnt",
    "kpi_cod_total",
    "kpi_cod_avg",
    "kpi_cod_rate",
    "kpi_sla_pct",
    "kpi_rto_pct",
    "kpi_lead_time_p50",
    "kpi_lead_time_p90",
    "eff_effect_size",
    "eff_confidence",
    "eff_coverage_p90",
    "eff_stability_time_pct",
    "eff_stability_segment_pct",
    "eff_simpson_flag",
    "eff_small_n_flag",
    "decision",
    "explain_key",
    "row_deeplink",
    "tz",
    "locale",
    "currency",
    "time_grain",
    "scenario_id",
]

# DEPRECATED: Static column list replaced by dynamic selection in _bi_feed()
# Phase 09 now automatically selects ALL columns from Phase 06 (standardized + engineered)
# This list is kept for backward compatibility reference only - NOT USED IN CODE
# NOTE: schedule_date (99.9% null), sub_status (99.1% null) were previously removed
ADDITIONAL_BI_COLUMNS = [
    # Core Customer Information (4 columns)
    "sender_name",
    "sender_phone",
    "receiver_name", 
    "receiver_phone",
    
    # Carrier & Logistics (3 columns)
    "forward_company",
    "driver_name",
    "driver_code",
    
    # Shipment Tracking (4 columns)
    "order_id",
    "reference_no",
    "shipper_ref_no",
    "forward_awb_no",
    
    # Key Dates & Times (4 columns) - removed schedule_date (99.9% null)
    "order_date",
    "entry_date",
    "pickup_date",
    "delivery_date",
    
    # Status Details (1 column) - removed sub_status (99.1% null)
    "payment_method",
    
    # Geographic Intelligence (6 columns)
    "origin_city",
    "destination_city",
    "area_name",
    "area_street",
    "latitude",
    "longitude",
    
    # Operational Metrics (3 columns)
    "piece_count",
    "weight_kg",
    "delivery_attempts",
]


def _resolve_input_path(inputs: Mapping[str, Any], key: str, default: Path) -> Path:
    value = inputs.get(key)
    if value:
        return Path(str(value)).expanduser().resolve()
    return default


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_safe(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _safe_json_value(value: Any) -> Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _load_stage05_nzv(artifacts_root: Path, run_id: str) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Path]]:
    nzv_path = artifacts_root / run_id / "stage_05_missing" / "nzv_summaries.json"
    payload = _read_json_safe(nzv_path)
    if not payload:
        return [], None, None
    columns_payload = payload.get("columns")
    summary = payload.get("nzv_summary") if isinstance(payload.get("nzv_summary"), dict) else None
    column_entries = [entry for entry in columns_payload if isinstance(entry, dict)] if isinstance(columns_payload, list) else []
    return column_entries, summary, nzv_path


def _load_standardize_columns(artifacts_root: Path, run_id: str) -> Tuple[Dict[str, Dict[str, Any]], Optional[Path]]:
    report_path = artifacts_root / run_id / STAGE_06_DIR / "standardize_report.json"
    payload = _read_json_safe(report_path)
    if not payload:
        return {}, None
    columns_payload = payload.get("columns")
    if isinstance(columns_payload, dict):
        return {str(name): dict(meta) for name, meta in columns_payload.items() if isinstance(meta, dict)}, report_path
    return {}, report_path


def _build_nzv_metadata(
    artifacts_root: Path,
    run_id: str,
) -> Tuple[Dict[str, Dict[str, Any]], Optional[Dict[str, Any]], Optional[Path], Optional[Path], List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    stage05_columns, stage05_summary, stage05_path = _load_stage05_nzv(artifacts_root, run_id)
    stage06_columns, stage06_path = _load_standardize_columns(artifacts_root, run_id)

    stage05_lookup: Dict[str, Dict[str, Any]] = {}
    stage05_lookup_lower: Dict[str, Dict[str, Any]] = {}
    for entry in stage05_columns:
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        stage05_lookup[name] = entry
        stage05_lookup_lower[name.lower()] = entry

    nzv_lookup: Dict[str, Dict[str, Any]] = {}
    if stage06_columns:
        for standardized, meta in stage06_columns.items():
            category = str(meta.get("nzv_category") or "").lower()
            is_nzv = bool(meta.get("is_nzv")) or category in LOW_VARIANCE_CATEGORIES
            if not is_nzv:
                continue
            original = meta.get("original_name")
            stage05_entry = None
            if isinstance(original, str):
                stage05_entry = stage05_lookup.get(original) or stage05_lookup_lower.get(original.lower())
            if stage05_entry is None:
                stage05_entry = stage05_lookup.get(standardized) or stage05_lookup_lower.get(standardized.lower())
            record = {
                "standardized_name": standardized,
                "original_name": original or standardized,
                "nzv_category": meta.get("nzv_category"),
                "nzv_reason": meta.get("nzv_reason"),
                "nzv_source": stage05_path.as_posix() if stage05_path else stage06_path.as_posix() if stage06_path else None,
                "is_nzv": True,
                "dominant_value": None,
                "dominant_pct": None,
                "unique_count": None,
                "missing_pct": None,
                "top_values": None,
            }
            if stage05_entry:
                record["dominant_value"] = stage05_entry.get("dominant_value")
                record["dominant_pct"] = stage05_entry.get("dominant_pct")
                record["unique_count"] = stage05_entry.get("unique_count")
                record["missing_pct"] = stage05_entry.get("missing_pct")
                record["top_values"] = stage05_entry.get("top_values")
            else:
                record["dominant_value"] = meta.get("nzv_dominant_value")
                record["dominant_pct"] = meta.get("nzv_dominant_pct")
            nzv_lookup[standardized] = record
    elif stage05_columns:
        for entry in stage05_columns:
            name = entry.get("name")
            if not isinstance(name, str):
                continue
            category = str(entry.get("nzv_category") or "").lower()
            is_nzv = category in LOW_VARIANCE_CATEGORIES or bool(entry.get("is_nzv"))
            if not is_nzv:
                continue
            nzv_lookup[name] = {
                "standardized_name": name,
                "original_name": name,
                "nzv_category": entry.get("nzv_category"),
                "nzv_reason": entry.get("nzv_reason"),
                "nzv_source": stage05_path.as_posix() if stage05_path else None,
                "is_nzv": True,
                "dominant_value": entry.get("dominant_value"),
                "dominant_pct": entry.get("dominant_pct"),
                "unique_count": entry.get("unique_count"),
                "missing_pct": entry.get("missing_pct"),
                "top_values": entry.get("top_values"),
            }

    if stage05_summary is None and stage06_path:
        stage06_payload = _read_json_safe(stage06_path)
        if stage06_payload:
            summary_candidate = stage06_payload.get("nzv_summary")
            if isinstance(summary_candidate, dict):
                stage05_summary = summary_candidate

    return nzv_lookup, stage05_summary, stage05_path, stage06_path, stage05_columns, stage06_columns


def _standardize_name(name: str, stage06_columns: Mapping[str, Dict[str, Any]]) -> str:
    if not name:
        return name
    if name in stage06_columns:
        return name
    lowered = name.lower()
    for standardized, meta in stage06_columns.items():
        original = meta.get("original_name")
        if isinstance(original, str) and original.lower() == lowered:
            return standardized
    return name


def _apply_low_variance_filter(
    df: pl.DataFrame,
    nzv_lookup: Mapping[str, Dict[str, Any]],
    protected: Set[str],
) -> Tuple[pl.DataFrame, List[Dict[str, Any]]]:
    if not nzv_lookup:
        return df, []
    protected_lower = {col.lower() for col in protected}
    details_lookup = {
        str(entry.get("standardized_name") or entry.get("original_name")).lower(): entry
        for entry in nzv_lookup.values()
        if entry.get("standardized_name") or entry.get("original_name")
        if str(entry.get("nzv_category") or "").lower() in LOW_VARIANCE_CATEGORIES
    }
    removed: List[str] = []
    for column in df.columns:
        lowered = column.lower()
        if lowered in protected_lower:
            continue
        if lowered in details_lookup:
            removed.append(column)
    if not removed:
        return df, []
    keep = [column for column in df.columns if column not in removed]
    filtered = df.select(keep) if keep else df
    removed_details: List[Dict[str, Any]] = []
    for column in removed:
        entry = details_lookup.get(column.lower())
        if entry:
            removed_details.append(
                {
                    "name": entry.get("standardized_name") or entry.get("original_name") or column,
                    "original_name": entry.get("original_name"),
                    "nzv_category": entry.get("nzv_category"),
                    "nzv_reason": entry.get("nzv_reason"),
                    "dominant_value": entry.get("dominant_value"),
                    "dominant_pct": entry.get("dominant_pct"),
                    "usage_hint": "context_only",
                }
            )
        else:
            removed_details.append({"name": column, "nzv_category": "near_zero_variance", "usage_hint": "context_only"})
    return filtered, removed_details


def _describe_high_imbalance(
    stage05_columns: Sequence[Mapping[str, Any]],
    stage06_columns: Mapping[str, Dict[str, Any]],
    present_columns: Sequence[str],
) -> List[Dict[str, Any]]:
    if not stage05_columns:
        return []
    present_lower = {col.lower() for col in present_columns}
    details: List[Dict[str, Any]] = []
    for entry in stage05_columns:
        category = str(entry.get("nzv_category") or "").lower()
        if category != "high_imbalance":
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        standardized = _standardize_name(name, stage06_columns)
        if standardized.lower() not in present_lower:
            continue
        details.append(
            {
                "name": standardized,
                "original_name": name,
                "dominant_value": entry.get("dominant_value"),
                "dominant_pct": entry.get("dominant_pct"),
                "high_imbalance": True,
            }
        )
    return details


def _load_renames(artifacts_root: Path, run_id: str) -> Dict[str, str]:
    report_path = artifacts_root / run_id / STAGE_06_DIR / "standardize_report.json"
    if not report_path.exists():
        return {}
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    renames = payload.get("column_renames")
    if isinstance(renames, dict):
        return {str(key): str(value) for key, value in renames.items()}
    return {}


def _pick(df: pl.DataFrame, renames: Mapping[str, str], candidates: Sequence[str]) -> Optional[str]:
    if not candidates:
        return None
    cleaned = {value for value in renames.values()}
    for candidate in candidates:
        if candidate in cleaned and candidate in df.columns:
            return candidate
    for candidate in candidates:
        mapped = renames.get(candidate)
        if mapped and mapped in df.columns:
            return mapped
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def _entity_series(df: pl.DataFrame) -> pl.Series:
    if "AWB_NO" in df.columns:
        return df["AWB_NO"].cast(pl.Utf8).fill_null("").alias("entity_id")

    candidate_sets: List[Sequence[str]] = [
        ("SHIPMENT_ID",),
        ("ORDER_ID",),
        ("FORWARD_AWB_NO",),
        ("ORDER_ID", "DESTINATION"),
        ("CUSTOMER_REFERENCE", "ORIGIN", "DESTINATION"),
    ]
    for columns in candidate_sets:
        if all(column in df.columns for column in columns):
            combined = pl.concat_str([pl.col(column).cast(pl.Utf8).fill_null("") for column in columns], separator="|")
            return combined.alias("entity_id")
    raise RuntimeError("Unable to derive stable entity identifier (AWB_NO missing and fallback columns unavailable)")


def _to_riyadh(series: pl.Series) -> pl.Series:
    if not series.dtype.is_temporal():
        now = datetime.now(TZ)
        return pl.Series("ts", [now] * series.len(), dtype=pl.Datetime(time_zone=io.DEFAULT_TIMEZONE))
    tz = getattr(series.dtype, "time_zone", None)
    if tz == io.DEFAULT_TIMEZONE:
        return series.rename("ts")
    if tz is None:
        try:
            return series.dt.replace_time_zone(io.DEFAULT_TIMEZONE).rename("ts")
        except Exception:  # pragma: no cover - defensive
            pass
        return series.dt.convert_time_zone(io.DEFAULT_TIMEZONE).rename("ts")
    return series.dt.convert_time_zone(io.DEFAULT_TIMEZONE).rename("ts")


def _extract_ts(df: pl.DataFrame) -> pl.Series:
    preferred = ["EVENT_TS", "CREATED_AT", "CREATED_AT_TS", "PICKUP_DATE", "DELIVERY_DATE"]
    for name in preferred:
        if name in df.columns and df[name].dtype.is_temporal():
            return _to_riyadh(df[name])
    for column, dtype in zip(df.columns, df.dtypes):
        if dtype.is_temporal():
            return _to_riyadh(df[column])
    now = datetime.now(TZ)
    return pl.Series("ts", [now] * df.height, dtype=pl.Datetime(time_zone=io.DEFAULT_TIMEZONE))


def _prepare_kpi_source(raw_path: Path, fallback: pl.DataFrame) -> pl.DataFrame:
    if not raw_path.exists():
        return fallback
    try:
        frame = pl.read_parquet(raw_path.as_posix())
    except Exception:
        return fallback

    rename_map: Dict[str, str] = {}
    for candidate in ("RECEIVER_MODE", "RECEIVER MODE", "receiver_mode", "Receiver Mode"):
        if candidate in frame.columns:
            if candidate != "RECEIVER_MODE":
                rename_map[candidate] = "RECEIVER_MODE"
            break
    for candidate in ("COD_AMOUNT", "COD Amount", "Cod Amount", "CODAMOUNT", "cod_amount", "COD"):
        if candidate in frame.columns:
            if candidate != "COD_AMOUNT":
                rename_map[candidate] = "COD_AMOUNT"
            break
    if rename_map:
        frame = frame.rename(rename_map)

    required = {"COD_AMOUNT", "RECEIVER_MODE"}
    if not required.issubset(set(frame.columns)):
        return fallback

    frame = frame.with_columns(
        [
            pl.col("COD_AMOUNT").cast(pl.Float64, strict=False).fill_null(0.0),
            pl.col("RECEIVER_MODE").cast(pl.Utf8, strict=False).fill_null(""),
        ]
    )

    # Calculated lead time columns are required for percentile KPIs; if the raw snapshot
    # does not carry them, fall back to the already-prepared clean frame.
    if frame.height != fallback.height:
        return fallback

    derived_series: List[pl.Series] = []
    for column in ("lead_time_hours", "lead_time_p50", "lead_time_p90"):
        if column not in frame.columns and column in fallback.columns:
            derived_series.append(fallback[column])
    if derived_series:
        frame = frame.with_columns(derived_series)

    if "lead_time_hours" not in frame.columns:
        return fallback

    base_columns = ["COD_AMOUNT", "RECEIVER_MODE"]
    optional_columns = [
        column for column in ("lead_time_hours", "lead_time_p50", "lead_time_p90") if column in frame.columns
    ]
    selected = [column for column in base_columns + optional_columns if column in frame.columns]
    return frame.select(selected)


def _prepare_ops(
    df: pl.DataFrame,
    artifacts_root: Path,
    run_id: str,
) -> Tuple[pl.DataFrame, Dict[str, Optional[str]]]:
    renames = _load_renames(artifacts_root, run_id)
    selections: Dict[str, Optional[str]] = {}

    prepared = df

    created_col = _pick(prepared, renames, OPS_ALIAS_CANDIDATES["created_ts"])
    selections["created_ts"] = created_col
    if created_col:
        created_series = _to_riyadh(prepared[created_col]).rename("ts_created")
        prepared = prepared.with_columns(created_series)
    else:
        prepared = prepared.with_columns(
            pl.lit(None).cast(pl.Datetime(time_zone=io.DEFAULT_TIMEZONE)).alias("ts_created")
        )

    delivered_col = _pick(prepared, renames, OPS_ALIAS_CANDIDATES["delivered_ts"])
    selections["delivered_ts"] = delivered_col
    if delivered_col:
        delivered_series = _to_riyadh(prepared[delivered_col]).rename("ts_delivered")
        prepared = prepared.with_columns(delivered_series)
    else:
        prepared = prepared.with_columns(
            pl.lit(None).cast(pl.Datetime(time_zone=io.DEFAULT_TIMEZONE)).alias("ts_delivered")
        )

    status_col = _pick(prepared, renames, OPS_ALIAS_CANDIDATES["status"])
    selections["status"] = status_col
    if status_col:
        prepared = prepared.with_columns(pl.col(status_col).cast(pl.Utf8).alias("STATUS"))
    else:
        prepared = prepared.with_columns(pl.lit(None, dtype=pl.Utf8).alias("STATUS"))

    cod_col = _pick(prepared, renames, OPS_ALIAS_CANDIDATES["cod_amount"])
    selections["cod_amount"] = cod_col
    if cod_col:
        prepared = prepared.with_columns(pl.col(cod_col).cast(pl.Float64, strict=False).alias("COD_AMOUNT"))
    else:
        prepared = prepared.with_columns(pl.lit(0.0).alias("COD_AMOUNT"))

    mode_col = _pick(prepared, renames, OPS_ALIAS_CANDIDATES["receiver_mode"])
    selections["receiver_mode"] = mode_col
    if mode_col:
        prepared = prepared.with_columns(pl.col(mode_col).cast(pl.Utf8).alias("RECEIVER_MODE"))
    else:
        prepared = prepared.with_columns(pl.lit(None, dtype=pl.Utf8).alias("RECEIVER_MODE"))

    prepared = prepared.with_columns(
        (pl.col("ts_delivered") - pl.col("ts_created")).dt.total_hours().alias("lead_time_hours")
    )
    prepared = prepared.with_columns(
        [
            (
                pl.col("lead_time_hours").is_not_null()
                & (pl.col("lead_time_hours") <= SLA_LIMIT_HOURS)
            ).alias("on_time"),
            pl.col("STATUS")
            .fill_null("")
            .str.to_uppercase()
            .str.contains(RTO_PATTERN)
            .alias("rto_flag"),
            pl.col("RECEIVER_MODE")
            .fill_null("")
            .str.to_uppercase()
            .eq("COD")
            .alias("is_cod"),
        ]
    )
    return prepared, selections


def _compute_ops_metrics(df: pl.DataFrame) -> Tuple[Dict[str, float], List[str]]:
    metrics: Dict[str, float] = {}
    warnings: List[str] = []

    total_rows = int(df.height)
    if total_rows == 0:
        for key in OPS_METRIC_KEYS:
            metrics[key] = math.nan
        warnings.append("kpi_guard::ops_metrics_no_rows")
        return metrics, warnings

    sla_guard = total_rows >= 200 and "on_time" in df.columns
    rto_guard = total_rows >= 200 and "rto_flag" in df.columns

    if sla_guard:
        metrics["sla_pct"] = float(df["on_time"].mean())
    else:
        metrics["sla_pct"] = math.nan
        warnings.append("kpi_guard::sla_pct_insufficient_n")

    if rto_guard:
        metrics["rto_pct"] = float(df["rto_flag"].mean())
    else:
        metrics["rto_pct"] = math.nan
        warnings.append("kpi_guard::rto_pct_insufficient_n")

    if "lead_time_hours" in df.columns:
        lead_series = df["lead_time_hours"].drop_nulls()
    else:
        lead_series = pl.Series(name="lead_time_hours", values=[], dtype=pl.Float64)
    lead_guard = lead_series.len() >= 200
    if lead_guard:
        metrics["lead_time_p50"] = float(lead_series.quantile(0.5, interpolation="nearest"))
        metrics["lead_time_p90"] = float(lead_series.quantile(0.9, interpolation="nearest"))
    else:
        metrics["lead_time_p50"] = math.nan
        metrics["lead_time_p90"] = math.nan
        warnings.append("kpi_guard::lead_time_insufficient_n")

    return metrics, warnings

def _compute_kpis(df: pl.DataFrame, catalog: models.KPICatalog) -> Dict[str, float]:
    conn = duckdb.connect(":memory:")
    try:
        conn.register("clean", df.to_arrow())
        results: Dict[str, float] = {}
        for entry in catalog.kpis:
            query = f"SELECT {entry.expr} AS value FROM clean"
            value = conn.execute(query).fetchone()[0]
            results[entry.name] = float(value) if value is not None else float("nan")
        return results
    finally:
        conn.close()


def _original_kpis(insights: Dict[str, Any]) -> Dict[str, float]:
    mapping: Dict[str, float] = {}
    if not insights:
        return mapping
    kpi_block = insights.get("kpis") or insights.get("kpi_snapshot")
    if isinstance(kpi_block, Mapping):
        for key, value in kpi_block.items():
            try:
                mapping[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
    summary = insights.get("summary")
    if isinstance(summary, Mapping):
        for key, value in summary.items():
            if isinstance(value, (int, float)):
                mapping.setdefault(str(key), float(value))
    return mapping


def _first_float(candidates: Iterable[Any]) -> Optional[float]:
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            if isinstance(candidate, bool):
                return float(candidate)
            return float(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _extract_effect_metrics(insights: Dict[str, Any]) -> Dict[str, Optional[float]]:
    diagnostics = insights.get("diagnostics") or {}
    effect_block = diagnostics.get("effect") or {}
    confidence_block = diagnostics.get("confidence") or {}
    coverage_block = diagnostics.get("coverage") or {}
    stability_block = diagnostics.get("stability") or {}
    flags_block = diagnostics.get("flags") or {}

    return {
        "eff_effect_size": _first_float(
            [
                effect_block.get("max_abs"),
                effect_block.get("median_abs"),
                insights.get("summary", {}).get("max_strength"),
            ]
        ),
        "eff_confidence": _first_float(
            [
                confidence_block.get("p50"),
                confidence_block.get("max"),
                insights.get("summary", {}).get("max_confidence"),
            ]
        ),
        "eff_coverage_p90": _first_float(
            [
                coverage_block.get("p90"),
                coverage_block.get("median"),
            ]
        ),
        "eff_stability_time_pct": _first_float(
            [
                stability_block.get("time"),
                diagnostics.get("stability", {}).get("time"),
            ]
        ),
        "eff_stability_segment_pct": _first_float(
            [
                stability_block.get("segment"),
                diagnostics.get("stability", {}).get("segment"),
            ]
        ),
        "eff_simpson_flag": _first_float([1.0 if flags_block.get("simpson") else 0.0 if flags_block else None]),
        "eff_small_n_flag": _first_float([1.0 if flags_block.get("small_n") else 0.0 if flags_block else None]),
    }


def _evaluate_range_rule(df: pl.DataFrame, rule: models.RuleSpec) -> models.RuleEvaluationResult:
    if not rule.column or rule.column not in df.columns:
        return models.RuleEvaluationResult(rule=rule, failing_ids=[], message=f"Column {rule.column!r} missing for range rule")
    expressions = []
    if rule.min is not None:
        expressions.append(pl.col(rule.column) < rule.min)
    if rule.max is not None:
        expressions.append(pl.col(rule.column) > rule.max)
    if not expressions:
        return models.RuleEvaluationResult(rule=rule, failing_ids=[], message="Range rule missing min/max bounds")
    mask = expressions[0]
    for expr in expressions[1:]:
        mask = mask | expr
    failing = df.filter(mask & pl.col(rule.column).is_not_null())
    ids = [str(value) for value in failing["entity_id"].to_list()]
    return models.RuleEvaluationResult(rule=rule, failing_ids=ids, message=rule.message)


def _evaluate_enum_rule(df: pl.DataFrame, rule: models.RuleSpec) -> models.RuleEvaluationResult:
    if not rule.column or rule.column not in df.columns:
        return models.RuleEvaluationResult(rule=rule, failing_ids=[], message=f"Column {rule.column!r} missing for enum rule")
    allowed = rule.allowed or []
    mask = (~pl.col(rule.column).is_in(allowed)) & pl.col(rule.column).is_not_null()
    failing = df.filter(mask)
    ids = [str(value) for value in failing["entity_id"].to_list()]
    return models.RuleEvaluationResult(rule=rule, failing_ids=ids, message=rule.message or "Value outside enum set")


def _evaluate_implication_rule(conn: duckdb.DuckDBPyConnection, rule: models.RuleSpec) -> models.RuleEvaluationResult:
    if not rule.if_expr or not rule.then_expr:
        return models.RuleEvaluationResult(rule=rule, failing_ids=[], message="Implication rule missing if/then expressions")
    query = f"SELECT entity_id FROM clean WHERE ({rule.if_expr}) AND NOT ({rule.then_expr})"
    try:
        ids = [str(row[0]) for row in conn.execute(query).fetchall()]
    except duckdb.Error as exc:  # pragma: no cover - defensive
        return models.RuleEvaluationResult(rule=rule, failing_ids=[], message=f"Implication evaluation error: {exc}")
    return models.RuleEvaluationResult(rule=rule, failing_ids=ids, message=rule.message)


def _evaluate_time_rule(df: pl.DataFrame, rule: models.RuleSpec) -> models.RuleEvaluationResult:
    meta = rule.metadata or {}
    start_col = meta.get("start_column") or rule.timestamp_start
    end_col = meta.get("end_column") or rule.timestamp_end
    window_days = rule.window_days or meta.get("window_days")
    if not start_col or not end_col or window_days is None:
        return models.RuleEvaluationResult(rule=rule, failing_ids=[], message="Time window rule missing configuration")
    if start_col not in df.columns or end_col not in df.columns:
        return models.RuleEvaluationResult(rule=rule, failing_ids=[], message="Time window rule columns missing")
    start = df[start_col]
    end = df[end_col]
    if not start.dtype.is_temporal() or not end.dtype.is_temporal():
        return models.RuleEvaluationResult(rule=rule, failing_ids=[], message="Time window columns must be datetime")
    delta_days = (end - start).dt.total_days()
    failing = df.with_columns(delta_days.alias("__delta_days")).filter(pl.col("__delta_days") > float(window_days))
    ids = [str(value) for value in failing["entity_id"].to_list()]
    return models.RuleEvaluationResult(rule=rule, failing_ids=ids, message=rule.message or "Exceeded time window")


def _evaluate_rules(df: pl.DataFrame, rules: models.RuleSet) -> Tuple[List[models.RuleEvaluationResult], Dict[str, Any]]:
    failures: List[models.RuleEvaluationResult] = []
    unit_currency_meta: Dict[str, Any] = {"unit_system": "metric", "currency": "SAR", "conversions_applied": []}
    conn = duckdb.connect(":memory:")
    try:
        conn.register("clean", df.to_arrow())
        for rule in rules.root:
            if rule.type == models.RuleType.RANGE:
                result = _evaluate_range_rule(df, rule)
            elif rule.type == models.RuleType.ENUM:
                result = _evaluate_enum_rule(df, rule)
            elif rule.type == models.RuleType.IMPLICATION:
                result = _evaluate_implication_rule(conn, rule)
            elif rule.type == models.RuleType.TIME_WINDOW:
                result = _evaluate_time_rule(df, rule)
            elif rule.type in {models.RuleType.CURRENCY, models.RuleType.UNIT}:
                if rule.metadata.get("currency"):
                    unit_currency_meta["currency"] = rule.metadata["currency"]
                if rule.metadata.get("unit_system"):
                    unit_currency_meta["unit_system"] = rule.metadata["unit_system"]
                result = models.RuleEvaluationResult(rule=rule, failing_ids=[], message=rule.message)
            else:  # pragma: no cover - defensive
                result = models.RuleEvaluationResult(rule=rule, failing_ids=[], message=f"Unsupported rule type: {rule.type}")
            if result.count > 0:
                failures.append(result)
        return failures, unit_currency_meta
    finally:
        conn.close()


def _load_sla_bundle(run_id: str, artifacts_root: Path) -> sla_utils.SLABundle:
    manifest_path = artifacts_root / run_id / "stage_01_ingestion" / "sla_manifest.json"
    return sla_utils.load_bundle(manifest_path)


def _evaluate_sla_terms(bundle: sla_utils.SLABundle, metrics: Mapping[str, float]) -> Tuple[List[sla_utils.SLATermResult], List[str], List[str]]:
    if not bundle.terms:
        return [], [], []
    results = sla_utils.evaluate_terms(bundle.terms, metrics)
    stop_flags: List[str] = []
    warn_flags: List[str] = []
    for result in results:
        marker = f"sla::{result.term.kpi}"
        if result.status == "STOP":
            stop_flags.append(marker)
        elif result.status == "WARN":
            warn_flags.append(marker)
    return results, stop_flags, warn_flags


def _gate_status(
    kpi_deltas: List[models.KPIDelta],
    failures: List[models.RuleEvaluationResult],
    thresholds: models.KPIThresholds,
    warnings: List[str],
    stop_flags: Optional[List[str]] = None,
    warn_flags: Optional[List[str]] = None,
) -> Tuple[models.GateStatus, List[str]]:
    reasons = list(warnings)
    stop_failure = any(result.rule.level == "STOP" and result.count > 0 for result in failures)
    warn_failure = any(result.rule.level == "WARN" and result.count > 0 for result in failures)
    if stop_flags:
        stop_failure = True
        reasons.extend(stop_flags)
    if warn_flags:
        warn_failure = True
        reasons.extend(warn_flags)
    for delta in kpi_deltas:
        if delta.rel_delta_pct is None:
            continue
        if delta.rel_delta_pct > thresholds.kpi_rel_delta_pct_stop:
            stop_failure = True
            reasons.append(f"kpi_delta_stop::{delta.name}")
        elif delta.rel_delta_pct > thresholds.kpi_rel_delta_pct_warn:
            warn_failure = True
            reasons.append(f"kpi_delta_warn::{delta.name}")
    if stop_failure:
        return "STOP", reasons
    if warn_failure:
        return "WARN", reasons
    return "PASS", reasons


def _row_decisions(df: pl.DataFrame, failures: List[models.RuleEvaluationResult]) -> Tuple[pl.DataFrame, List[models.RowDecision], List[models.OpsAction]]:
    hits: Dict[str, List[Tuple[models.RuleSpec, str]]] = defaultdict(list)
    for result in failures:
        for entity_id in result.failing_ids:
            hits[entity_id].append((result.rule, result.message or result.rule.message or "Rule violation"))

    decisions: List[models.RowDecision] = []
    actions: List[models.OpsAction] = []
    for entity_id in df.select("entity_id").unique().to_series().to_list():
        key = str(entity_id)
        entity_hits = hits.get(key, [])
        stop_hit = any(rule.level == "STOP" for rule, _ in entity_hits)
        decision_value: models.Decision = "REJECT" if stop_hit else "APPROVE"
        reasons = [message for _, message in entity_hits]
        rule_ids = [rule.rule_id for rule, _ in entity_hits]
        suggested_fix = entity_hits[0][0].suggested_fix if entity_hits else None
        severity = entity_hits[0][0].severity if entity_hits else None
        record = models.RowDecision(
            entity_id=key,
            decision=decision_value,
            reasons=reasons,
            rules_hits=rule_ids,
            suggested_fix=suggested_fix,
            severity=severity,
        )
        decisions.append(record)
        if stop_hit and entity_hits:
            top_rule = next(rule for rule, _ in entity_hits if rule.level == "STOP")
            actions.append(
                models.OpsAction(
                    action_type="FIX_DATA",
                    entity_id=key,
                    severity=top_rule.severity or "high",
                    reason=top_rule.message or "Rule STOP triggered",
                    suggested_fix=top_rule.suggested_fix or "Investigate and remediate record.",
                )
            )
    decisions_df = pl.DataFrame(
        {
            "entity_id": [item.entity_id for item in decisions],
            "decision": [item.decision for item in decisions],
            "rules_hit_ids": [item.rules_hits for item in decisions],
            "suggested_fix": [item.suggested_fix for item in decisions],
            "severity": [item.severity for item in decisions],
        }
    )
    return decisions_df, decisions, actions


def _build_whitelist_blacklist(
    row_decisions: List[models.RowDecision],
    kpi_deltas: List[models.KPIDelta],
    locale: str,
    currency: str,
    time_grain: str,
    explain_template: Optional[str],
    scenario_id: Optional[str],
    column_policy_map: Optional[Mapping[str, models.ColumnPolicy]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    delta_lookup = {delta.name: delta for delta in kpi_deltas}
    whitelist: List[Dict[str, Any]] = []
    blacklist: List[str] = []
    for decision in row_decisions:
        explain_key = models.stable_hash(decision.entity_id, length=16)
        deeplink = (
            explain_template.format(entity_id=decision.entity_id, explain_key=explain_key)
            if explain_template
            else None
        )
        delta_payload = [models.safe_model_dump(delta_lookup[name]) for name in sorted(delta_lookup.keys())]
        record: Dict[str, Any] = {
            "entity_id": decision.entity_id,
            "decision": decision.decision,
            "rules_hits": decision.rules_hits,
            "kpi_deltas": delta_payload,
            "explain_key": explain_key,
            "row_deeplink": deeplink,
            "why": decision.reasons,
            "locale": locale,
            "currency": currency,
            "time_grain": time_grain,
        }
        if scenario_id is not None:
            record["scenario_id"] = scenario_id
        if decision.decision == "APPROVE":
            whitelist.append(record)
        else:
            blacklist.append(decision.entity_id)
    return whitelist, blacklist


def _bi_feed(
    source_df: pl.DataFrame,
    effect_metrics: Dict[str, Optional[float]],
    kpi_values: Dict[str, float],
    decisions_df: pl.DataFrame,
    locale: str,
    currency: str,
    time_grain: str,
    explain_template: Optional[str],
    scenario_id: Optional[str],
    column_policy_map: Mapping[str, models.ColumnPolicy],
) -> pl.DataFrame:
    joined = source_df.join(decisions_df, on="entity_id", how="left")
    joined = joined.with_columns(pl.col("decision").fill_null("APPROVE"))
    explain_keys = pl.col("entity_id").map_elements(
        lambda value: models.stable_hash(str(value), length=16), return_dtype=pl.Utf8
    ).alias("explain_key")
    if explain_template:
        deeplink_col = pl.col("entity_id").map_elements(
            lambda value: explain_template.format(entity_id=value, explain_key=models.stable_hash(str(value), length=16)),
            return_dtype=pl.Utf8,
        ).alias("row_deeplink")
    else:
        deeplink_col = pl.lit(None).alias("row_deeplink")

    feed = joined.with_columns(
        [
            explain_keys,
            deeplink_col,
            pl.lit(io.DEFAULT_TIMEZONE).alias("tz"),
            pl.lit(locale).alias("locale"),
            pl.lit(currency).alias("currency"),
            pl.lit(time_grain).alias("time_grain"),
        ]
    )
    if scenario_id is not None:
        feed = feed.with_columns(pl.lit(scenario_id).alias("scenario_id"))
    else:
        feed = feed.with_columns(pl.lit(None).alias("scenario_id"))

    for kpi_name, value in kpi_values.items():
        column_name = f"kpi_{kpi_name}"
        if value is None:
            feed = feed.with_columns(pl.lit(None).alias(column_name))
        else:
            numeric_value = float(value)
            if math.isnan(numeric_value):
                feed = feed.with_columns(pl.lit(None).alias(column_name))
            else:
                feed = feed.with_columns(pl.lit(numeric_value).alias(column_name))
    for metric_name, metric_value in effect_metrics.items():
        feed = feed.with_columns(pl.lit(metric_value).alias(metric_name))

    missing = [column for column in REQUIRED_FACT_COLUMNS if column not in feed.columns]
    for column in missing:
        feed = feed.with_columns(pl.lit(None).alias(column))

    # Build final column list: required columns + ALL Phase 06 data columns dynamically
    final_columns = REQUIRED_FACT_COLUMNS.copy()
    excluded_columns = {
        name
        for name, policy in column_policy_map.items()
        if not policy.include_in_bi_feed
    }
    if excluded_columns:
        feed = feed.drop([name for name in excluded_columns if name in feed.columns])
    
    # DYNAMIC COLUMN SELECTION: Include ALL columns from Phase 06 automatically
    # This preserves: Phase 05 data (renamed/standardized) + engineered features + KPIs
    # Exclude only: KPI columns (already added), missing indicators, and policy-excluded columns
    for col in feed.columns:
        if col not in final_columns and col not in excluded_columns:
            # Skip missing indicators (converted to regular columns in Phase 06)
            if col.endswith('__is_missing') or col.endswith('_is_missing'):
                continue
            # Skip already-included required columns
            if col in REQUIRED_FACT_COLUMNS:
                continue
            # Include everything else from Phase 06 (standardized + engineered data)
            final_columns.append(col)
    
    # Also respect column policies that explicitly include columns
    for name, policy in column_policy_map.items():
        if policy.include_in_bi_feed and name in feed.columns and name not in final_columns:
            final_columns.append(name)

    return feed.select(final_columns)


def _tiles(feed: pl.DataFrame) -> Dict[str, pl.DataFrame]:
    if "ts" not in feed.columns:
        return {}
    day = (
        feed.with_columns(pl.col("ts").dt.truncate("1d").alias("day"))
        .group_by(["day", "DESTINATION"])
        .agg(
            [
                pl.count().alias("orders_cnt"),
                pl.col("COD_AMOUNT").sum().alias("cod_total"),
                pl.col("COD_AMOUNT").mean().alias("cod_avg"),
                pl.col("RECEIVER_MODE").eq("COD").mean().alias("cod_rate"),
            ]
        )
        .with_columns(
            [
                pl.col("orders_cnt").shift(1).over("DESTINATION").alias("orders_cnt_prev"),
                (pl.col("orders_cnt") - pl.col("orders_cnt").shift(1).over("DESTINATION")).alias("delta_orders_cnt"),
                pl.col("cod_rate").shift(1).over("DESTINATION").alias("cod_rate_prev"),
                (pl.col("cod_rate") - pl.col("cod_rate").shift(1).over("DESTINATION")).alias("delta_cod_rate"),
            ]
        )
        .sort(["day", "DESTINATION"])
    )
    week = (
        feed.with_columns(pl.col("ts").dt.truncate("1w").alias("week"))
        .group_by(["week", "STATUS"])
        .agg(
            [
                pl.count().alias("orders_cnt"),
                pl.col("COD_AMOUNT").sum().alias("cod_total"),
                pl.col("COD_AMOUNT").mean().alias("cod_avg"),
            ]
        )
        .with_columns(
            [
                pl.col("orders_cnt").shift(1).over("STATUS").alias("orders_cnt_prev"),
                (pl.col("orders_cnt") - pl.col("orders_cnt").shift(1).over("STATUS")).alias("delta_orders_cnt"),
            ]
        )
        .sort(["week", "STATUS"])
    )
    return {"day": day, "week": week}


def _benchmarks(feed: pl.DataFrame) -> pl.DataFrame:
    if "ts" not in feed.columns:
        return pl.DataFrame()
    ts_series = feed.select(pl.col("ts").max()).to_series()
    ts_max = ts_series[0] if ts_series.len() else None
    if ts_max is None:
        return pl.DataFrame()
    cutoff = ts_max - timedelta(weeks=13)
    window = feed.filter(pl.col("ts") >= cutoff)
    benchmark = (
        window.group_by(["DESTINATION", "STATUS"])
        .agg(
            [
                pl.count().alias("orders_cnt"),
                pl.col("COD_AMOUNT").mean().alias("cod_avg"),
                pl.col("COD_AMOUNT").quantile(0.5).alias("cod_avg_p50"),
                pl.col("COD_AMOUNT").quantile(0.9).alias("cod_avg_p90"),
            ]
        )
        .sort(["DESTINATION", "STATUS"])
    )
    return benchmark


def _segment_insights(insights: Dict[str, Any]) -> pl.DataFrame:
    records: List[Dict[str, Any]] = []
    for item in insights.get("insights", []):
        records.append(
            {
                "segment_key": item.get("segment") or item.get("relation"),
                "effect_size": item.get("strength"),
                "effect_confidence": item.get("confidence"),
                "n": item.get("n"),
                "coverage": item.get("coverage"),
                "period_start": item.get("window"),
                "period_end": item.get("window"),
            }
        )
    if not records:
        return pl.DataFrame(
            {
                "segment_key": pl.Series([], dtype=pl.Utf8),
                "effect_size": pl.Series([], dtype=pl.Float64),
                "effect_confidence": pl.Series([], dtype=pl.Float64),
                "n": pl.Series([], dtype=pl.Float64),
                "coverage": pl.Series([], dtype=pl.Float64),
                "period_start": pl.Series([], dtype=pl.Utf8),
                "period_end": pl.Series([], dtype=pl.Utf8),
            }
        )
    return pl.DataFrame(records)


def _targets_from_contract(contract: models.BIContract) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for kpi, rule in (contract.color_rules or {}).items():
        out[kpi] = dict(rule)
    return out


def _data_health(df: pl.DataFrame, catalog: models.KPICatalog) -> Dict[str, Any]:
    total_rows = max(df.height, 1)
    now_ts = datetime.now(TZ)
    duplicates_pct = 0.0
    if "entity_id" in df.columns and total_rows > 0:
        unique_entities = df["entity_id"].n_unique()
        duplicates_pct = round(max(total_rows - unique_entities, 0) / total_rows, 4)

    payload: Dict[str, Any] = {}
    for entry in catalog.kpis:
        coverage_columns = [column for column in entry.default_dimensions if column in df.columns]
        missing_pct = 0.0
        if coverage_columns:
            max_missing_rows = 0
            for column in coverage_columns:
                series = df[column]
                null_count = int(series.null_count())
                if series.dtype in (pl.Float32, pl.Float64):
                    try:
                        null_count += int(series.is_nan().sum())
                    except AttributeError:  # pragma: no cover - older polars
                        pass
                max_missing_rows = max(max_missing_rows, null_count)
            missing_pct = round(max_missing_rows / total_rows, 4)

        freshness_pct = 0.0
        if entry.freshness_sla_hours and "ts_created" in df.columns and total_rows > 0:
            threshold = now_ts - timedelta(hours=int(entry.freshness_sla_hours))
            stale_rows = df.filter(
                pl.col("ts_created").is_not_null() & (pl.col("ts_created") < threshold)
            ).height
            freshness_pct = round(stale_rows / total_rows, 4)

        payload[entry.name] = {
            "missing_pct": missing_pct,
            "duplicates_pct": duplicates_pct,
            "out_of_range_pct": freshness_pct,
            "n": int(total_rows),
            "window": "current",
            "coverage_columns": coverage_columns,
            "visibility": entry.visibility,
            "freshness_sla_hours": entry.freshness_sla_hours,
        }
    return payload


def _load_textops_context(inputs: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    profile_path = inputs.get("text_profile")
    findings_path = inputs.get("text_findings")
    sentiment_path = inputs.get("text_sentiment")
    context: Dict[str, Any] = {}
    if profile_path:
        profile_file = Path(str(profile_path))
        if profile_file.exists():
            try:
                profile = json.loads(profile_file.read_text(encoding="utf-8"))
            except Exception:
                profile = None
            if isinstance(profile, Mapping):
                columns = profile.get("columns") or {}
                tokens: List[Dict[str, Any]] = []
                for column, info in columns.items():
                    if not isinstance(info, Mapping):
                        continue
                    for token in (info.get("top_tokens") or [])[:3]:
                        if isinstance(token, Mapping):
                            tokens.append(
                                {
                                    "column": column,
                                    "token": token.get("t"),
                                    "count": token.get("c"),
                                }
                            )
                if tokens:
                    context["top_tokens"] = tokens[:5]
    if findings_path:
        findings_file = Path(str(findings_path))
        if findings_file.exists():
            try:
                findings = json.loads(findings_file.read_text(encoding="utf-8"))
            except Exception:
                findings = None
            if isinstance(findings, Mapping):
                context["warnings"] = findings.get("warnings", [])
                context["errors"] = findings.get("errors", [])
    if sentiment_path:
        sentiment_file = Path(str(sentiment_path))
        if sentiment_file.exists():
            try:
                sentiment_df = pl.read_parquet(sentiment_file.as_posix())
            except Exception:
                sentiment_df = None
            if sentiment_df is not None and not sentiment_df.is_empty():
                total = sentiment_df.height or 1
                negative = sentiment_df.filter(pl.col("sentiment_score") < -0.2).height
                context["sentiment"] = {
                    "negative_pct": round(negative / total, 4),
                    "observations": int(total),
                }
    return context or None


def _textops_actions(context: Mapping[str, Any]) -> List[models.OpsAction]:
    actions: List[models.OpsAction] = []
    sentiment = context.get("sentiment") if isinstance(context, Mapping) else None
    if isinstance(sentiment, Mapping):
        negative_pct = sentiment.get("negative_pct")
        if isinstance(negative_pct, (int, float)) and negative_pct > 0.3:
            actions.append(
                models.OpsAction(
                    action_type="REQUEST_UPDATE",
                    entity_id="textops::sentiment",
                    severity="high",
                    reason=f"Negative sentiment detected in {negative_pct:.0%} of feedback",
                    suggested_fix="Escalate to customer care and address top complaints",
                )
            )
    warnings = context.get("warnings") if isinstance(context, Mapping) else None
    if isinstance(warnings, list):
        for warning in warnings[:2]:
            actions.append(
                models.OpsAction(
                    action_type="REQUEST_UPDATE",
                    entity_id="textops::warning",
                    severity="medium",
                    reason=str(warning),
                    suggested_fix="Coordinate with operations team to triage textual complaints",
                )
            )
    return actions


def _write_contracts(out_dir: Path) -> None:
    schema_dir = out_dir / "contracts" / "stage_09"
    schema_dir.mkdir(parents=True, exist_ok=True)
    for filename, model in [
        ("validation_report.schema.json", models.ValidationReport),
        ("row_decision.schema.json", models.RowDecision),
        ("ops_action.schema.json", models.OpsAction),
    ]:
        io.ensure_contract(model.model_json_schema(), schema_dir / filename)
    bi_feed_schema = {
        "title": "bi_feed",
        "type": "object",
        "properties": {column: {"type": ["number", "string", "null"]} for column in REQUIRED_FACT_COLUMNS},
        "required": ["entity_id", "ts"],
    }
    io.ensure_contract(bi_feed_schema, schema_dir / "bi_feed.schema.json")
    io.ensure_contract({"type": "array"}, schema_dir / "bi_whitelist.schema.json")


def run(run_id: str, inputs: Mapping[str, Any], config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    start = time.time()
    config = dict(config or {})
    artifacts_root = Path(config.get("artifacts_root", "artifacts")).expanduser().resolve()
    health = SystemHealth(artifacts_root=artifacts_root)
    models_catalog_override = config.get("models_catalog")
    catalog_path = Path(str(models_catalog_override)).expanduser() if models_catalog_override else None
    out_dir = artifacts_root / run_id / OUT_STAGE
    out_dir.mkdir(parents=True, exist_ok=True)
    nzv_lookup, nzv_summary_payload, stage05_path, stage06_path, stage05_columns, stage06_columns = _build_nzv_metadata(
        artifacts_root, run_id
    )

    project_kpi_path, project_rules_dir, project_bi_path = io.ensure_configs_structure(PROJECT_ROOT)

    kpi_path = Path(str(inputs.get("kpi_cfg") or config.get("kpi_cfg") or project_kpi_path)).resolve()
    rules_dir = Path(str(inputs.get("rules") or config.get("rules_dir") or project_rules_dir)).resolve()
    bi_path = Path(str(inputs.get("bi_cfg") or config.get("bi_cfg") or project_bi_path)).resolve()
    what_if_raw = inputs.get("what_if") or config.get("what_if")
    what_if_path = Path(str(what_if_raw)).resolve() if what_if_raw else None

    textops_dir = artifacts_root / run_id / "stage_03_5_textops"
    textops_inputs = {
        "text_profile": (textops_dir / "text_profile.json").as_posix(),
        "text_findings": (textops_dir / "quality_findings.json").as_posix(),
        "text_sentiment": (textops_dir / "sentiment_features.parquet").as_posix(),
    }
    textops_context = _load_textops_context(textops_inputs)

    catalog = io.load_kpi_catalog(kpi_path)
    io.write_json_sorted(catalog.model_dump(mode="json"), out_dir / "kpi_catalog.json")
    column_policy_map: Dict[str, models.ColumnPolicy] = {policy.name: policy for policy in catalog.columns}
    rules = io.load_rules(rules_dir)
    contract = io.load_bi_contract(bi_path)
    what_if = io.load_what_if(what_if_path)

    # Read from Phase 06 Standardize - contains feature engineering + KPIs
    # Phase 06 includes all Phase 05 columns (renamed/standardized) + engineered features
    clean_default = artifacts_root / run_id / STAGE_06_DIR / "clean.parquet"
    insights_default = artifacts_root / run_id / STAGE_08_DIR / "insights_report.json"
    raw_default = artifacts_root / run_id / STAGE_01_DIR / "raw.parquet"

    clean_path = _resolve_input_path(inputs, "clean", clean_default)
    insights_path = _resolve_input_path(inputs, "insights", insights_default)
    raw_path = _resolve_input_path(inputs, "raw", raw_default)

    if not clean_path.exists():
        raise FileNotFoundError(f"Stage 06 clean parquet not found: {clean_path}")

    clean_df = pl.read_parquet(clean_path.as_posix())
    clean_df, _alias_matches = _prepare_ops(clean_df, artifacts_root, run_id)
    kpi_source_df = _prepare_kpi_source(raw_path, clean_df)
    protected_low_variance: Set[str] = set(REQUIRED_FACT_COLUMNS)
    clean_df, low_variance_removed = _apply_low_variance_filter(clean_df, nzv_lookup, protected_low_variance)
    if nzv_lookup and protected_low_variance:
        protected_lower = {column.lower() for column in protected_low_variance}
        removed_names = {str(entry.get("name")).lower() for entry in low_variance_removed if entry.get("name")}
        for entry in nzv_lookup.values():
            name = entry.get("standardized_name") or entry.get("original_name")
            if not isinstance(name, str):
                continue
            lowered = name.lower()
            if lowered not in protected_lower or lowered in removed_names:
                continue
            detail = {
                "name": name,
                "original_name": entry.get("original_name"),
                "nzv_category": entry.get("nzv_category"),
                "nzv_reason": entry.get("nzv_reason"),
                "dominant_value": entry.get("dominant_value"),
                "dominant_pct": entry.get("dominant_pct"),
                "usage_hint": "context_only_protected",
            }
            low_variance_removed.append(detail)
    high_imbalance_details = _describe_high_imbalance(stage05_columns, stage06_columns, clean_df.columns)
    nzv_source = stage05_path or stage06_path
    nzv_impact_payload = {
        "low_variance_ignored_columns": low_variance_removed,
        "high_imbalance_included_columns": high_imbalance_details,
        "nzv_summary": nzv_summary_payload,
        "nzv_source": nzv_source.as_posix() if nzv_source else None,
    }
    entity_ids = _entity_series(clean_df)
    clean_df = clean_df.with_columns(entity_ids.alias("entity_id"))
    clean_df = clean_df.with_columns(_extract_ts(clean_df))
    model_predictions_path: Optional[Path] = None
    model_logs: List[Dict[str, Any]] = []
    model_warning: Optional[str] = None
    model_entry = _load_model_from_catalog("sla_breach", catalog_path)
    if model_entry:
        scores = _predict_scores(model_entry, clean_df)
        if scores:
            score_col = f"{model_entry.key}_score"
            clean_df = clean_df.with_columns(pl.Series(score_col, scores))
            prediction_payload = {
                "run_id": run_id,
                "model": model_entry.key,
                "target": model_entry.target,
                "score_column": score_col,
                "n_rows": len(scores),
                "generated_at": datetime.now(TZ).isoformat(),
            }
            model_predictions_path = out_dir / f"{model_entry.key}_predictions.json"
            io.write_json_sorted(prediction_payload, model_predictions_path)
            model_logs.append({"event": "model_prediction", "model": model_entry.key, "score_column": score_col})
        else:
            model_warning = "sla_breach model could not produce predictions; skipping ML scores"
            model_logs.append(
                {
                    "event": "model_prediction_skipped",
                    "model": model_entry.key,
                    "reason": "no_scores",
                    "level": "WARN",
                    "message": model_warning,
                }
            )
    else:
        model_warning = "sla_breach model not available, skipping ML scores"
        model_logs.append(
            {
                "event": "model_prediction_skipped",
                "model": "sla_breach",
                "reason": "missing_catalog_entry",
                "level": "WARN",
                "message": model_warning,
            }
        )
    present_columns = set(clean_df.columns)
    suppressed_columns = sorted(
        name
        for name, policy in column_policy_map.items()
        if not policy.include_in_bi_feed and name in present_columns
    )
    missing_governed_columns = sorted(
        name
        for name, policy in column_policy_map.items()
        if policy.include_in_bi_feed and name not in present_columns
    )

    insights = _read_json(insights_path)
    stage08_gate_reasons: List[str] = []
    stage08_gate_status: Optional[str] = None
    stage08_gate_path = insights_path.parent / "gate.json"
    stage08_gate_payload = _read_json(stage08_gate_path)
    if isinstance(stage08_gate_payload, dict):
        status = stage08_gate_payload.get("status")
        if isinstance(status, str):
            stage08_gate_status = status.upper()
        reasons_payload = stage08_gate_payload.get("reasons")
        if isinstance(reasons_payload, list):
            stage08_gate_reasons = [str(reason) for reason in reasons_payload if isinstance(reason, str)]
    effect_metrics = _extract_effect_metrics(insights)
    missing_effect = [key for key, value in effect_metrics.items() if value is None]

    kpi_values = _compute_kpis(kpi_source_df, catalog)
    ops_metrics, ops_metric_warnings = _compute_ops_metrics(clean_df)
    kpi_values.update(ops_metrics)
    original_kpis = _original_kpis(insights)
    missing_reference = [
        name for name in kpi_values.keys() if name not in original_kpis and name not in OPS_METRIC_KEYS
    ]

    kpi_results = [
        models.KPIComputationResult(
            name=name,
            recomputed=value,
            original=original_kpis.get(name),
            thresholds=catalog.thresholds,
        )
        for name, value in kpi_values.items()
    ]
    kpi_deltas = [result.to_delta() for result in kpi_results]

    failures, unit_currency_meta = _evaluate_rules(clean_df, rules)
    decisions_df, decisions, ops_actions = _row_decisions(clean_df, failures)
    if textops_context:
        ops_actions.extend(_textops_actions(textops_context))

    locale = contract.formatting.get("locale", "ar")
    currency = contract.formatting.get("currency", "SAR")
    time_grain = contract.default_time_grain
    channel = config.get("channel") or contract.formatting.get("channel") or "canary"
    explain_template = contract.formatting.get("explain_url_template") or config.get("explain_url_template")

    scenario_id = None
    if what_if and what_if.scenarios:
        scenario_id = what_if.scenarios[0].scenario_id

    whitelist, blacklist = _build_whitelist_blacklist(
        decisions,
        kpi_deltas,
        locale=locale,
        currency=currency,
        time_grain=time_grain,
        explain_template=explain_template,
        scenario_id=scenario_id,
        column_policy_map=column_policy_map,
    )

    bi_feed_df = _bi_feed(
        clean_df,
        effect_metrics,
        kpi_values,
        decisions_df,
        locale=locale,
        currency=currency,
        time_grain=time_grain,
        explain_template=explain_template,
        scenario_id=scenario_id,
        column_policy_map=column_policy_map,
    )

    tiles = _tiles(bi_feed_df)
    benchmarks_df = _benchmarks(bi_feed_df)
    segment_df = _segment_insights(insights)
    targets_payload = _targets_from_contract(contract)
    data_health = _data_health(clean_df, catalog)
    data_health["nzv_impact"] = nzv_impact_payload
    if textops_context:
        data_health["text_ops"] = textops_context

    sla_bundle = _load_sla_bundle(run_id, artifacts_root)
    metrics_for_sla: Dict[str, float] = {name: value for name, value in kpi_values.items() if value is not None}
    for key, value in effect_metrics.items():
        if value is not None:
            metrics_for_sla.setdefault(key, value)
    sla_results, sla_stop_flags, sla_warn_flags = _evaluate_sla_terms(sla_bundle, metrics_for_sla)
    if sla_bundle.entries and not sla_results:
        sla_warn_flags.append("sla::no_terms_detected")
    gate_warn_flags = list(sla_warn_flags)
    gate_stop_flags = list(sla_stop_flags)
    sla_summary_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(TZ).isoformat(),
        "entries": sla_bundle.entries,
        "notes": sla_bundle.notes,
        "results": [sla_utils.term_result_to_dict(result) for result in sla_results],
    }
    sla_summary_path = out_dir / "sla_summary.json"
    io.write_json_sorted(sla_summary_payload, sla_summary_path)

    warnings: List[str] = list(ops_metric_warnings)
    if stage08_gate_reasons:
        warnings.extend(stage08_gate_reasons)
    if stage08_gate_status == "WARN":
        gate_warn_flags.append("stage08::warn")
    elif stage08_gate_status == "STOP":
        gate_stop_flags.append("stage08::stop")
    if suppressed_columns:
        warnings.append(f"column_policy::suppressed::{','.join(suppressed_columns)}")
    if missing_governed_columns:
        warnings.append(f"column_policy::missing::{','.join(missing_governed_columns)}")
    if missing_effect:
        warnings.append(f"missing_insights::{','.join(missing_effect)}")
        gate_warn_flags.append("missing_insights")
    if missing_reference:
        warnings.append(f"missing_kpi_reference::{','.join(missing_reference)}")
    if sla_bundle.manifest_path is None and not sla_bundle.entries:
        warnings.append("sla_manifest_missing")
    warnings.extend(f"sla_note::{note}" for note in sla_bundle.notes)
    if model_warning:
        warnings.append(model_warning)

    gate_status, gate_reasons = _gate_status(
        kpi_deltas,
        failures,
        catalog.thresholds,
        warnings,
        stop_flags=gate_stop_flags,
        warn_flags=gate_warn_flags,
    )

    total_decisions = max(len(decisions), 1)
    approved = sum(1 for item in decisions if item.decision == "APPROVE")
    rejected = total_decisions - approved
    decision_counts = {
        "total": len(decisions),
        "approve": approved,
        "reject": rejected,
    }
    perf = {
        "rows": int(clean_df.height),
        "approve_pct": round(approved / total_decisions, 4),
        "reject_pct": round(rejected / total_decisions, 4),
        "exec_seconds": round(time.time() - start, 4),
    }
    kpi_delta_payload = [delta.model_dump(mode="json") for delta in kpi_deltas]
    rule_failure_payload = [failure.to_failure().model_dump(mode="json") for failure in failures]
    effect_metrics_clean = {key: _safe_json_value(value) for key, value in effect_metrics.items()}
    ops_metrics_clean = {key: _safe_json_value(value) for key, value in ops_metrics.items()}

    rule_texts = [path.read_text(encoding="utf-8") for path in sorted(rules_dir.glob("*.yaml"))]
    rules_version = models.stable_hash("".join(rule_texts) or "rules::empty")

    provenance = {
        "run_id": run_id,
        "phases": ["06", "08", "09"],
        "code_hash": CODE_HASH,
        "rules_version": rules_version,
        "kpi_catalog_version": catalog.version,
        "locale": locale,
        "currency": currency,
        "bi_contract_id": contract.bi_contract_id,
        "bi_contract_version": contract.version,
    }

    validation_report = models.ValidationReport(
        gate={"status": gate_status, "reasons": gate_reasons},
        kpi_recalc=kpi_deltas,
        rule_failures=[failure.to_failure() for failure in failures],
        provenance=provenance,
        unit_currency_meta=unit_currency_meta,
        perf=perf,
        bi_hints={
            "time_grain": time_grain,
            "channel": channel,
            "explain_url_template": explain_template,
        },
        sla=sla_summary_payload["results"],
        nzv_impact=nzv_impact_payload,
    )
    gate_payload = {
        "status": gate_status,
        "reasons": gate_reasons,
        "counts": decision_counts,
        "warnings": warnings,
        "sla_flags": {
            "warn": sla_warn_flags,
            "stop": sla_stop_flags,
        },
        "nzv_impact": nzv_impact_payload,
    }
    diagnostics_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(TZ).isoformat(),
        "decision_counts": decision_counts,
        "kpi_deltas": kpi_delta_payload,
        "effect_metrics": effect_metrics_clean,
        "ops_metrics": ops_metrics_clean,
        "ops_metric_warnings": ops_metric_warnings,
        "rule_failures": rule_failure_payload,
        "warnings": warnings,
        "sla_results": sla_summary_payload["results"],
        "gate_status": gate_status,
        "nzv_impact": nzv_impact_payload,
    }

    io.write_json_sorted(validation_report.model_dump(mode="json"), out_dir / "validation_report.json")
    io.write_json_sorted(gate_payload, out_dir / "gate.json")
    io.write_json_sorted(diagnostics_payload, out_dir / "diagnostics.json")
    io.write_jsonl(whitelist, out_dir / "bi_whitelist.jsonl")
    io.write_json_sorted(blacklist, out_dir / "bi_blacklist.json")
    io.write_parquet(decisions_df, out_dir / "row_decisions.parquet")
    io.write_json_sorted([action.model_dump(mode="json") for action in ops_actions], out_dir / "ops_actions.json")
    io.write_json_sorted(data_health, out_dir / "data_health.json")
    io.write_parquet(bi_feed_df, out_dir / "bi_feed.parquet")
    for grain, frame in tiles.items():
        io.write_parquet(frame, out_dir / "bi_tiles" / f"{grain}.parquet")
    io.write_parquet(benchmarks_df, out_dir / "benchmarks.parquet")
    io.write_parquet(segment_df, out_dir / "segment_insights.parquet")
    io.write_json_sorted(targets_payload, out_dir / "targets.json")

    if what_if:
        io.write_json_sorted(
            {
                "scenarios": [scenario.model_dump(mode="json") for scenario in what_if.scenarios],
            },
            out_dir / "what_if_report.json",
        )

    io.copy_configs_snapshot(out_dir / "configs_snapshot", kpi_path, rules_dir, bi_path)

    logs = [
        {
            "event": "phase_start",
            "timestamp": datetime.now(TZ).isoformat(),
            "run_id": run_id,
        },
        {
            "event": "nzv_filter",
            "low_variance_removed": [entry.get("name") for entry in low_variance_removed if entry.get("name")],
            "high_imbalance_present": [entry.get("name") for entry in high_imbalance_details if entry.get("name")],
            "nzv_source": nzv_source.as_posix() if nzv_source else None,
        },
        {
            "event": "gate",
            "status": gate_status,
            "reasons": gate_reasons,
        },
        {
            "event": "phase_end",
            "duration_sec": round(time.time() - start, 4),
        },
    ] + model_logs
    io.write_jsonl(logs, out_dir / "logs.jsonl")

    io.write_json_sorted(
        {
            "ts": datetime.now(TZ).isoformat(),
            "gate": gate_status,
            "counts": {"approve": approved, "reject": rejected},
            "versions": {
                "code_hash": CODE_HASH,
                "rules_hash": rules_version,
                "kpi_catalog": catalog.version,
            },
        },
        out_dir / "changelog.json",
    )
    io.write_json_sorted(perf, out_dir / "metrics.json")

    _write_contracts(out_dir)

    exit_code = {"PASS": 0, "WARN": 2, "STOP": 3}[gate_status]

    outputs = {
        "validation_report": (out_dir / "validation_report.json").as_posix(),
        "bi_whitelist": (out_dir / "bi_whitelist.jsonl").as_posix(),
        "bi_blacklist": (out_dir / "bi_blacklist.json").as_posix(),
        "row_decisions": (out_dir / "row_decisions.parquet").as_posix(),
        "ops_actions": (out_dir / "ops_actions.json").as_posix(),
        "data_health": (out_dir / "data_health.json").as_posix(),
        "bi_feed": (out_dir / "bi_feed.parquet").as_posix(),
        "benchmarks": (out_dir / "benchmarks.parquet").as_posix(),
        "segment_insights": (out_dir / "segment_insights.parquet").as_posix(),
        "targets": (out_dir / "targets.json").as_posix(),
        "metrics": (out_dir / "metrics.json").as_posix(),
        "changelog": (out_dir / "changelog.json").as_posix(),
        "sla_summary": sla_summary_path.as_posix(),
        "gate": (out_dir / "gate.json").as_posix(),
        "diagnostics": (out_dir / "diagnostics.json").as_posix(),
    }
    if model_predictions_path:
        outputs["model_predictions"] = model_predictions_path.as_posix()

    duration = time.time() - start
    bi_rows = int(bi_feed_df.shape[0])
    denom = max(bi_rows / 1_000_000.0, 1e-6)
    health.log_ingestion_latency(run_id, bi_rows, (duration / 60.0) / denom)
    health.emit_report(extra={"stage": OUT_STAGE, "status": gate_status})

    return {
        "run_id": run_id,
        "status": gate_status,
        "exit_code": exit_code,
        "outputs": outputs,
        "logs_uri": (out_dir / "logs.jsonl").as_posix(),
    }


__all__ = ["run"]
