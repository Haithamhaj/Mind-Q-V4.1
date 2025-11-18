from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
import re

try:
    import pandas as pd  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("pandas is required for phase 06 standardize") from exc

from shared import baseline as baseline_utils  # type: ignore
try:
    from .normalizer import normalize_values  # type: ignore
except ImportError:  # pragma: no cover
    import importlib.util
    CURRENT_DIR = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("standardize_normalizer", (CURRENT_DIR / "normalizer.py").as_posix())
    if spec is None or spec.loader is None:
        raise
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    normalize_values = module.normalize_values  # type: ignore

SECTOR_PROTECT: Set[str] = {
    "cod_amount",
    "rto_flag",
    "rto_rate",
    "sla_target",
    "sla_achieved",
    "zone",
    "area",
    "carrier",
    "service_level",
    "weight_kg",
    "volumetric_weight",
    "payment_type",
    "weekday",
    "month",
    "pickup_window",
    "delivery_slot",
    "return_reason",
}

EXCLUSION_KEYS = {"columns", "drop", "exclusions", "features"}

_RE_CANON = re.compile(r"[^0-9A-Za-z]+")


def _canonical_name(name: str) -> str:
    cleaned = _RE_CANON.sub("_", str(name).strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "column"


def _comparison_key(name: str) -> str:
    return _canonical_name(name).upper()


CANON_SECTOR_PROTECT: Set[str] = {_comparison_key(entry) for entry in SECTOR_PROTECT}

NUMERIC_HINT_DEFAULTS = {
    "cod_amount",
    "sla_target",
    "sla_achieved",
    "rto_rate",
    "rto_flag",
    "weight",
    "weight_kg",
    "volumetric_weight",
    "latitude",
    "longitude",
    "distance_km",
    "distance",
    "cod_value",
    "cod_collected",
    "collection_amount",
    "delivery_time_minutes",
    "delivery_time_hours",
    "on_weight",
    "on_pieces",
    "pieces",
    "amount_due",
    "amount_paid",
    "total_amount",
    "sla_value",
}

CANON_NUMERIC_HINTS: Set[str] = {_comparison_key(entry) for entry in NUMERIC_HINT_DEFAULTS}
STRUCTURED_TEXTOPS_DIR = "stage_03_5_textops"
STRUCTURED_FIELDS_FILE = "structured_fields.parquet"
STRUCTURED_JOIN_CANDIDATES: Tuple[str, ...] = ("AWB_NO", "awb_no", "shipment_id", "SHIPMENT_ID")
PHONE_DEFAULT_COUNTRY = "966"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_dataframe(raw_path: Path) -> pd.DataFrame:
    return pd.read_parquet(raw_path)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _load_exclusions(payload: Any) -> Set[str]:
    if payload is None:
        return set()
    if isinstance(payload, str):
        potential_path = Path(payload).expanduser()
        if potential_path.exists():
            try:
                data = json.loads(potential_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return set()
            return _load_exclusions(data)
        return {payload}
    if isinstance(payload, dict):
        cols: Set[str] = set()
        for key, value in payload.items():
            if key in EXCLUSION_KEYS:
                cols.update(_load_exclusions(value))
        return cols
    if isinstance(payload, (list, tuple, set)):
        cols = set()
        for item in payload:
            cols.update(_load_exclusions(item))
        return cols
    return set()


def _write_logs(out_dir: Path, records: Iterable[Dict[str, Any]]) -> None:
    log_path = out_dir / "logs.jsonl"
    with log_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_structured_fields(artifacts_root: Path, run_id: str) -> Tuple[Optional["pd.DataFrame"], Optional[Path], Optional[str]]:
    path = artifacts_root / run_id / STRUCTURED_TEXTOPS_DIR / STRUCTURED_FIELDS_FILE
    if not path.exists():
        return None, None, None
    try:
        data = pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - defensive
        return None, path, str(exc)
    return data, path, None


def _select_structured_join_key(columns_a: Sequence[str], columns_b: Sequence[str]) -> Optional[str]:
    for candidate in STRUCTURED_JOIN_CANDIDATES:
        if candidate in columns_a and candidate in columns_b:
            return candidate
    return None


def _normalize_phone_e164(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    if text.startswith("+") or digits.startswith(PHONE_DEFAULT_COUNTRY):
        normalized = f"+{digits}"
    elif digits.startswith("00"):
        normalized = f"+{digits[2:]}"
    elif digits.startswith("0"):
        normalized = f"+{PHONE_DEFAULT_COUNTRY}{digits.lstrip('0')}"
    else:
        normalized = f"+{PHONE_DEFAULT_COUNTRY}{digits}"
    if len(re.sub(r"\D", "", normalized)) < 9:
        return None
    return normalized


def _parse_components(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def _sans_validate_components(value: Any) -> Optional[bool]:
    components = _parse_components(value)
    if not components:
        return None
    return len(components) >= 3


def _apply_structured_fields(
    df: "pd.DataFrame", structured_df: "pd.DataFrame", join_key: str
) -> Tuple["pd.DataFrame", List[Dict[str, Any]]]:
    logs: List[Dict[str, Any]] = []
    if structured_df.empty or join_key not in structured_df.columns:
        return df, logs
    structured_indexed = structured_df.dropna(subset=[join_key]).set_index(join_key)
    if structured_indexed.empty:
        return df, logs
    column_lookup = {col.lower(): col for col in df.columns}

    def _resolve_column(candidates: Sequence[str]) -> Optional[str]:
        for candidate in candidates:
            actual = column_lookup.get(candidate.lower())
            if actual:
                return actual
        return None

    phone_targets = {
        "sender_phone_structured": ("SENDER_PHONE", "sender_phone", "shipper_phone"),
        "receiver_phone_structured": ("RECEIVER_PHONE", "receiver_phone", "consignee_phone"),
    }
    for source_col, target_candidates in phone_targets.items():
        if source_col not in structured_indexed.columns:
            continue
        target_col = _resolve_column(target_candidates)
        if not target_col:
            continue
        mapped = df[join_key].map(structured_indexed[source_col])
        normalized = mapped.map(_normalize_phone_e164)
        existing = df[target_col] if target_col in df.columns else pd.Series(index=df.index)
        df[target_col] = normalized.combine_first(existing)
        applied = int(normalized.notna().sum())
        logs.append({"event": "structured_phone_applied", "column": target_col, "count": applied})

    address_targets = {
        "sender_address_components": "sender_address_sans_valid",
        "receiver_address_components": "receiver_address_sans_valid",
    }
    for source_col, target_col in address_targets.items():
        if source_col not in structured_indexed.columns:
            continue
        components = df[join_key].map(structured_indexed[source_col])
        validity = components.map(_sans_validate_components)
        df[target_col] = validity
        positive = int(validity.fillna(False).sum())
        logs.append({"event": "structured_address_validated", "column": target_col, "valid": positive})

    return df, logs


def _collect_hint_strings(payload: Any) -> Set[str]:
    if payload is None:
        return set()
    if isinstance(payload, str):
        return {payload}
    if isinstance(payload, Mapping):
        collected: Set[str] = set()
        for key in payload.keys():
            if isinstance(key, str):
                collected.add(key)
        for value in payload.values():
            collected.update(_collect_hint_strings(value))
        return collected
    if isinstance(payload, Iterable) and not isinstance(payload, (bytes, bytearray)):
        collected: Set[str] = set()
        for item in payload:
            collected.update(_collect_hint_strings(item))
        return collected
    return {str(payload)}


def _resolve_numeric_hint_keys(config: Any) -> Set[str]:
    hint_keys = CANON_NUMERIC_HINTS.copy()
    if not isinstance(config, Mapping):
        return hint_keys
    for key in ("numeric_hints", "numeric_columns", "force_numeric"):
        if key in config:
            entries = _collect_hint_strings(config.get(key))
            hint_keys.update(_comparison_key(entry) for entry in entries if entry)
    return hint_keys


def _coercion_threshold(config: Any, default: float = 0.9) -> float:
    if isinstance(config, Mapping) and "numeric_coercion_threshold" in config:
        try:
            return float(config["numeric_coercion_threshold"])  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
    return default


def _coerce_numeric_columns(df: "pd.DataFrame", config: Any) -> Tuple["pd.DataFrame", List[Dict[str, Any]]]:
    if df.empty:
        return df, []
    hints = _resolve_numeric_hint_keys(config)
    threshold = _coercion_threshold(config)
    df_out = df.copy()
    logs: List[Dict[str, Any]] = []

    for column in list(df_out.columns):
        series = df_out[column]
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            continue
        key = _comparison_key(column)
        if hints and key not in hints:
            continue

        str_values = series.astype(str).str.strip()
        lower = str_values.str.lower()
        nullish = lower.isin({"", "none", "null", "nan"})
        str_values = str_values.mask(nullish)
        cleaned = str_values.fillna("").str.replace(r"[^\d\-\.,]", "", regex=True)
        cleaned = cleaned.str.replace(",", "", regex=True)
        cleaned = cleaned.replace({"": None, "-": None})

        numeric_series = pd.to_numeric(cleaned, errors="coerce")
        candidate_mask = str_values.notna()
        candidate_count = int(candidate_mask.sum())
        if candidate_count == 0:
            continue
        valid_numeric = int(numeric_series[candidate_mask].notna().sum())
        valid_ratio = valid_numeric / candidate_count if candidate_count else 0.0
        if valid_numeric == 0 or valid_ratio < threshold:
            logs.append(
                {
                    "event": "numeric_coercion_skipped",
                    "column": column,
                    "valid_ratio": round(valid_ratio, 4),
                    "threshold": threshold,
                }
            )
            continue

        int_like = bool(numeric_series.dropna().apply(lambda value: float(value).is_integer()).all())
        if int_like:
            converted = numeric_series.round().astype("Int64")
            dtype_label = "Int64"
        else:
            converted = numeric_series.astype("Float64")
            dtype_label = "Float64"
        df_out[column] = converted
        logs.append(
            {
                "event": "numeric_coercion_applied",
                "column": column,
                "dtype": dtype_label,
                "valid_ratio": round(valid_ratio, 4),
            }
        )

    return df_out, logs


def _load_nzv_metadata(
    artifacts_root: Path,
    run_id: str,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], Path]:
    """Load Stage 05 NZV payload and build lookups keyed by name and lowered name."""
    nzv_path = artifacts_root / run_id / "stage_05_missing" / "nzv_summaries.json"
    payload = _load_json(nzv_path)
    if not isinstance(payload, Mapping):
        return None, {}, {}, nzv_path

    columns = payload.get("columns")
    if not isinstance(columns, list):
        return dict(payload), {}, {}, nzv_path

    direct: Dict[str, Dict[str, Any]] = {}
    lowered: Dict[str, Dict[str, Any]] = {}
    for entry in columns:
        if not isinstance(entry, Mapping):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        direct[name] = dict(entry)
        lowered[name.lower()] = dict(entry)
    return dict(payload), direct, lowered, nzv_path


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    artifacts_root = Path((config or {}).get("artifacts_root", "artifacts"))
    out_dir = artifacts_root / run_id / "stage_06_standardize"
    _ensure_dir(out_dir)
    feature_dir = artifacts_root / run_id / "stage_06_feature_eng"
    _ensure_dir(feature_dir)
    nzv_payload, nzv_lookup, nzv_lookup_lower, nzv_path = _load_nzv_metadata(artifacts_root, run_id)

    raw_uri = (inputs or {}).get("raw") or (inputs or {}).get("raw_uri")
    if not isinstance(raw_uri, str):
        raise ValueError("Stage 06 standardize requires inputs['raw'] pointing to parquet data")
    raw_path = Path(raw_uri).expanduser().resolve()
    if not raw_path.exists():
        raise FileNotFoundError(f"raw data for standardize not found: {raw_path}")

    df_pre = _load_dataframe(raw_path)
    rename_map: Dict[str, str] = {}
    seen: Set[str] = set()
    column_provenance: Dict[str, str] = {}
    for column in list(df_pre.columns):
        canon = _canonical_name(column)
        base = canon
        counter = 1
        while canon in seen and canon != column:
            counter += 1
            canon = f"{base}_{counter}"
        if canon != column:
            rename_map[str(column)] = canon
        seen.add(canon)
        column_provenance[canon] = str(column)
    if rename_map:
        df_pre = df_pre.rename(columns=rename_map)
    renamed_columns = {orig: new for orig, new in rename_map.items() if orig != new}
    column_lookup: Dict[str, str] = {_comparison_key(col): col for col in df_pre.columns}

    n_rows = int(len(df_pre))

    created_series = None
    if "ENTRY_DATE" in df_pre.columns:
        try:
            created_series = pd.to_datetime(df_pre["ENTRY_DATE"], errors="coerce")
        except Exception:
            created_series = None
    if created_series is not None and "created_at" not in df_pre.columns:
        df_pre = df_pre.copy()
        df_pre["created_at"] = created_series
        column_provenance.setdefault("created_at", "created_at")

    n_cols_in = int(len(df_pre.columns))
    dtype_before_map = {col: str(df_pre[col].dtype) for col in df_pre.columns}

    baseline = baseline_utils.load(artifacts_root, run_id)
    expected_rows = int(baseline.get("n_rows", 0)) if baseline else None
    baseline_utils.enforce_row_guard(expected=expected_rows, actual=n_rows, phase="06", out_dir=out_dir)

    exclusions_payload = (inputs or {}).get("exclusions") or (inputs or {}).get("exclusions_json")
    if exclusions_payload is None:
        candidate_path = out_dir / "exclusions.json"
        if candidate_path.exists():
            exclusions_payload = candidate_path.as_posix()

    requested_exclusions_raw = _load_exclusions(exclusions_payload)
    requested_exclusions_map: Dict[str, str] = {}
    for entry in requested_exclusions_raw:
        key = _comparison_key(entry)
        requested_exclusions_map.setdefault(key, str(entry))

    requested_keys = set(requested_exclusions_map.keys())
    protected_hit_keys = sorted(requested_keys & CANON_SECTOR_PROTECT)
    filtered_exclusion_keys = sorted(
        key for key in requested_keys if key not in CANON_SECTOR_PROTECT and key in column_lookup
    )
    ignored_keys_raw = sorted(
        key for key in requested_keys if key not in set(filtered_exclusion_keys) and key not in set(protected_hit_keys)
    )

    filtered_exclusions = [column_lookup[key] for key in filtered_exclusion_keys]
    protected_hits = [
        column_lookup.get(key, requested_exclusions_map.get(key, key)) for key in protected_hit_keys
    ]
    ignored_keys = [requested_exclusions_map.get(key, key) for key in ignored_keys_raw]

    pending_logs: List[Dict[str, Any]] = []
    if filtered_exclusions:
        pending_logs.append(
            {
                "event": "exclusions_requested_ignored",
                "columns": filtered_exclusions,
                "reason": "stage05_authoritative_dataset",
            }
        )
    df_post = df_pre.copy()
    structured_logs: List[Dict[str, Any]] = []
    structured_df, structured_path, structured_error = _load_structured_fields(artifacts_root, run_id)
    if structured_error:
        structured_logs.append(
            {
                "event": "structured_fields_error",
                "path": structured_path.as_posix() if structured_path else None,
                "message": structured_error,
            }
        )
    elif structured_df is not None:
        join_key_struct = _select_structured_join_key(df_post.columns, structured_df.columns)
        if join_key_struct:
            df_post, applied_logs = _apply_structured_fields(df_post, structured_df, join_key_struct)
            structured_logs.extend(applied_logs)
        else:
            structured_logs.append({"event": "structured_fields_join_key_missing"})

    if created_series is not None and "created_at" not in df_post.columns:
        df_post = df_post.copy()
        df_post["created_at"] = created_series

    logs: List[Dict[str, Any]] = [
        {"event": "baseline_rows", "expected": expected_rows, "actual": n_rows},
        {"event": "exclusions_requested", "count": len(requested_keys)},
        {"event": "exclusions_applied", "columns": filtered_exclusions},
    ]
    logs.extend(pending_logs)
    logs.extend(structured_logs)
    if renamed_columns:
        logs.append({"event": "column_rename", "count": len(renamed_columns), "mapping": renamed_columns})
    if protected_hits:
        logs.append({"event": "exclusions_protected", "columns": protected_hits})
    if ignored_keys:
        logs.append({"event": "exclusions_ignored", "columns": ignored_keys})
    if nzv_payload is None:
        logs.append({"event": "nzv_summary_missing", "path": nzv_path.as_posix()})
    else:
        summary_snapshot = nzv_payload.get("nzv_summary") if isinstance(nzv_payload, Mapping) else None
        logs.append({"event": "nzv_summary_loaded", "path": nzv_path.as_posix(), "summary": summary_snapshot})

    df_post, normalization_result = normalize_values(df_post, run_id, artifacts_root, out_dir, config or {})
    normalization_logs = normalization_result.get("logs", [])
    normalization_mapping_files = normalization_result.get("mapping_files", [])
    normalization_pending_path = normalization_result.get("pending_path")
    if normalization_logs:
        logs.extend(normalization_logs)

    df_post, numeric_logs = _coerce_numeric_columns(df_post, config or {})
    if numeric_logs:
        logs.extend(numeric_logs)

    n_cols_out = int(len(df_post.columns))

    if n_cols_out == 0:
        payload = {
            "phase": "06",
            "n_in": n_cols_in,
            "n_out": n_cols_out,
            "reason": "all_columns_excluded",
        }
        (out_dir / "shape_mismatch.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_logs(out_dir, logs)
        raise SystemExit(1)

    clean_path = out_dir / "clean.parquet"
    df_post.to_parquet(clean_path, index=False)

    features_pre_path = feature_dir / "features.pre.parquet"
    curated_path = feature_dir / "features.curated.parquet"
    df_pre.to_parquet(features_pre_path, index=False)
    df_post.to_parquet(curated_path, index=False)

    for column in df_post.columns:
        column_provenance.setdefault(column, column)

    meta = {
        "phase": "06",
        "n_rows": n_rows,
        "n_cols_in": n_cols_in,
        "n_cols_out": n_cols_out,
        "applied_exclusions": filtered_exclusions,
        "protected_columns": protected_hits,
        "ignored_keys": ignored_keys,
        "source": raw_path.as_posix(),
        "features_pre": features_pre_path.as_posix(),
        "features_curated": curated_path.as_posix(),
        "column_renames": renamed_columns,
    }
    columns_meta: Dict[str, Dict[str, Any]] = {}
    dtype_after_map = {col: str(df_post[col].dtype) for col in df_post.columns}
    nzv_summary_block = None
    if isinstance(nzv_payload, Mapping):
        nzv_summary_block = nzv_payload.get("nzv_summary")
        if nzv_summary_block:
            meta["nzv_summary"] = nzv_summary_block
            meta["nzv_summaries_path"] = nzv_path.as_posix()

    for column in df_post.columns:
        provenance_name = column_provenance.get(column, column)
        entry: Dict[str, Any] = {
            "original_name": provenance_name,
            "standardized_name": column,
            "dtype_before": dtype_before_map.get(column),
            "dtype_after": dtype_after_map.get(column),
        }
        nzv_entry = None
        if nzv_lookup:
            nzv_entry = nzv_lookup.get(provenance_name) or nzv_lookup_lower.get(provenance_name.lower())
        if nzv_entry:
            entry["is_nzv"] = bool(nzv_entry.get("is_nzv"))
            entry["nzv_category"] = nzv_entry.get("nzv_category")
            entry["nzv_reason"] = nzv_entry.get("nzv_reason") or nzv_entry.get("reason")
            entry["nzv_dominant_value"] = nzv_entry.get("dominant_value")
            entry["nzv_dominant_pct"] = nzv_entry.get("dominant_pct")
            if entry.get("is_nzv"):
                entry["usage_hint"] = "context_only"
        columns_meta[column] = entry
    if columns_meta:
        meta["columns"] = columns_meta

    if normalization_mapping_files:
        meta["value_normalization"] = {
            "mapping_files": normalization_mapping_files,
            "pending_review": normalization_pending_path,
        }
    (out_dir / "standardize_report.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "row_meta.json").write_text(
        json.dumps({"phase": "06", "n_rows": n_rows, "source": curated_path.as_posix()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "exclusions_applied.json").write_text(
        json.dumps({"applied": filtered_exclusions, "protected": protected_hits, "ignored": ignored_keys}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (feature_dir / "exclusions_applied.json").write_text(
        json.dumps({"applied": filtered_exclusions, "protected": protected_hits, "ignored": ignored_keys}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_logs(out_dir, logs)

    outputs: Dict[str, Any] = {
        "raw": curated_path.as_posix(),
        "features_curated": curated_path.as_posix(),
        "features_pre": features_pre_path.as_posix(),
        "source_raw": raw_path.as_posix(),
        "exclusions_applied": filtered_exclusions,
        "clean": clean_path.as_posix(),
        "clean_dataset": clean_path.as_posix(),
    }
    if normalization_mapping_files:
        outputs["normalization_maps"] = normalization_mapping_files
    if normalization_pending_path:
        outputs["normalization_pending"] = normalization_pending_path

    return {
        "run_id": run_id,
        "status": "PASS",
        "outputs": outputs,
        "metrics": {"n_rows": n_rows, "n_cols": n_cols_out, "n_cols_in": n_cols_in},
        "logs_uri": (out_dir / "logs.jsonl").as_posix(),
    }
