from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

try:
    import pandas as pd  # type: ignore
    from pandas.api import types as ptypes  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("pandas is required for phase 06 feature engineering") from exc

from shared import baseline as baseline_utils  # type: ignore


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_dataframe(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def _write_logs(out_dir: Path, records: List[Dict[str, Any]]) -> None:
    log_path = out_dir / "logs.jsonl"
    with log_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_exclusions(feature_dir: Path) -> Set[str]:
    exclusions_path = feature_dir / "exclusions_applied.json"
    if not exclusions_path.exists():
        return set()
    try:
        payload = json.loads(exclusions_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    entries = payload.get("applied") if isinstance(payload, dict) else None
    if isinstance(entries, list):
        return {str(item) for item in entries}
    return set()


STRING_DTYPE = "string[pyarrow]"
TRUE_VALUES = {"true", "t", "yes", "y", "1", "on", "enabled"}
FALSE_VALUES = {"false", "f", "no", "n", "0", "off", "disabled"}


@dataclass(frozen=True)
class Layer1FieldSpec:
    name: str
    role: str
    dtype: str
    sources: Sequence[str] = ()
    derive: Optional[str] = None
    description_en: Optional[str] = None
    description_ar: Optional[str] = None


AR_LABEL_OVERRIDES: Dict[str, str] = {
    "order_id": "\u0645\u0639\u0631\u0641\u0020\u0627\u0644\u0634\u062d\u0646\u0629",
    "order_date": "\u062a\u0627\u0631\u064a\u062e\u0020\u0627\u0644\u0637\u0644\u0628",
    "pickup_date": "\u062a\u0627\u0631\u064a\u062e\u0020\u0627\u0644\u0627\u0633\u062a\u0644\u0627\u0645",
    "pickup_time": "\u0648\u0642\u062a\u0020\u0627\u0644\u0627\u0633\u062a\u0644\u0627\u0645",
    "schedule_date": "\u062a\u0627\u0631\u064a\u062e\u0020\u0627\u0644\u062c\u062f\u0648\u0644\u0629",
    "delivery_date": "\u062a\u0627\u0631\u064a\u062e\u0020\u0627\u0644\u062a\u0633\u0644\u064a\u0645",
    "status": "\u0627\u0644\u062d\u0627\u0644\u0629",
    "sub_status": "\u0627\u0644\u062d\u0627\u0644\u0629\u0020\u0627\u0644\u0641\u0631\u0639\u064a\u0629",
    "on_hold_flag": "\u0645\u0624\u0634\u0631\u0020\u0627\u0644\u062a\u0639\u0644\u064a\u0642",
    "payment_method": "\u0637\u0631\u064a\u0642\u0629\u0020\u0627\u0644\u062f\u0641\u0639",
    "invoice_status": "\u062d\u0627\u0644\u0629\u0020\u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629",
    "cod_amount": "\u0642\u064a\u0645\u0629\u0020\u0627\u0644\u062f\u0641\u0639\u0020\u0639\u0646\u062f\u0020\u0627\u0644\u0627\u0633\u062a\u0644\u0627\u0645",
    "amount": "\u0642\u064a\u0645\u0629\u0020\u0627\u0644\u0634\u062d\u0646\u0629",
    "weight_kg": "\u0627\u0644\u0648\u0632\u0646\u0020\u0628\u0627\u0644\u0643\u064a\u0644\u0648",
    "volumetric_weight": "\u0627\u0644\u0648\u0632\u0646\u0020\u0627\u0644\u062d\u062c\u0645\u064a",
    "piece_count": "\u0639\u062f\u062f\u0020\u0627\u0644\u0642\u0637\u0639",
    "origin_city": "\u0645\u062f\u064a\u0646\u0629\u0020\u0627\u0644\u0625\u0631\u0633\u0627\u0644",
    "destination_city": "\u0645\u062f\u064a\u0646\u0629\u0020\u0627\u0644\u0648\u062c\u0647\u0629",
    "area_name": "\u0627\u0633\u0645\u0020\u0627\u0644\u0645\u0646\u0637\u0642\u0629",
    "latitude": "\u062e\u0637\u0020\u0627\u0644\u0639\u0631\u0636",
    "longitude": "\u062e\u0637\u0020\u0627\u0644\u0637\u0648\u0644",
    "call_attempts": "\u0639\u062f\u062f\u0020\u0627\u0644\u0645\u0643\u0627\u0644\u0645\u0627\u062a",
    "delivery_attempts": "\u0639\u062f\u062f\u0020\u0645\u062d\u0627\u0648\u0644\u0627\u062a\u0020\u0627\u0644\u062a\u0633\u0644\u064a\u0645",
    "cod_flag": "\u0645\u0624\u0634\u0631\u0020\u0627\u0644\u062f\u0641\u0639\u0020\u0639\u0646\u062f\u0020\u0627\u0644\u0627\u0633\u062a\u0644\u0627\u0645",
    "geocoded_flag": "\u0645\u0624\u0634\u0631\u0020\u0627\u0644\u0625\u062d\u062f\u0627\u062b\u064a\u0627\u062a",
    "delivery_delay_days": "\u062a\u0623\u062e\u064a\u0631\u0020\u0627\u0644\u062a\u0633\u0644\u064a\u0645\u0020\u0628\u0627\u0644\u0623\u064a\u0627\u0645",
    "order_weekday": "\u0627\u0644\u064a\u0648\u0645",
    "order_month": "\u0627\u0644\u0634\u0647\u0631",
    "sender_name": "\u0627\u0633\u0645\u0020\u0627\u0644\u0645\u0631\u0633\u0644",
    "receiver_name": "\u0627\u0633\u0645\u0020\u0627\u0644\u0645\u0633\u062a\u0644\u0645",
    "receiver_phone": "\u0647\u0627\u062a\u0641\u0020\u0627\u0644\u0645\u0633\u062a\u0644\u0645",
}


LAYER1_FIELD_SPECS: Sequence[Layer1FieldSpec] = (
    Layer1FieldSpec(name="order_id", role="dimension", dtype="string", sources=("AWB_NO",), description_en="Air Waybill identifier for each shipment."),
    Layer1FieldSpec(name="reference_no", role="dimension", dtype="string", sources=("REFRENCE_No",)),
    Layer1FieldSpec(name="shipper_ref_no", role="dimension", dtype="string", sources=("SHIPPER_REF_No",)),
    Layer1FieldSpec(name="transaction_number", role="dimension", dtype="string", sources=("Transaction_Number",)),
    Layer1FieldSpec(name="status", role="dimension", dtype="string", sources=("STATUS",), description_en="Operational status reported by the logistics platform."),
    Layer1FieldSpec(name="sub_status", role="dimension", dtype="string", sources=("SUB_STATUS",)),
    Layer1FieldSpec(name="on_hold_flag", role="flag", dtype="bool", sources=("ON_HOLD",)),
    Layer1FieldSpec(name="on_hold_reason", role="dimension", dtype="string", sources=("ON_HOLD_REASON",)),
    Layer1FieldSpec(name="on_hold_date", role="temporal", dtype="datetime", sources=("ON_HOLD_DATE",)),
    Layer1FieldSpec(name="payment_method", role="dimension", dtype="string", sources=("RECEIVER_MODE",)),
    Layer1FieldSpec(name="invoice_status", role="dimension", dtype="string", sources=("PAY_INVOICE_STATUS",)),
    Layer1FieldSpec(name="receivable_status", role="dimension", dtype="string", sources=("Recievable_Status",)),
    Layer1FieldSpec(name="payable_status", role="dimension", dtype="string", sources=("Payable_Status",)),
    Layer1FieldSpec(name="receivable_invoice_no", role="dimension", dtype="string", sources=("Recievable_Invoice_No",)),
    Layer1FieldSpec(name="inbound_status", role="dimension", dtype="string", sources=("Receive_Inbound",)),
    Layer1FieldSpec(name="origin_city", role="dimension", dtype="string", sources=("ORIGIN",)),
    Layer1FieldSpec(name="origin_hub", role="dimension", dtype="string", sources=("ORIGIN_HUB",)),
    Layer1FieldSpec(name="destination_city", role="dimension", dtype="string", sources=("DESTINATION",)),
    Layer1FieldSpec(name="destination_hub", role="dimension", dtype="string", sources=("DESTINATION_HUB",)),
    Layer1FieldSpec(name="area_name", role="dimension", dtype="string", sources=("Area_Name",)),
    Layer1FieldSpec(name="area_code", role="dimension", dtype="string", sources=("ON_AREA",)),
    Layer1FieldSpec(name="area_street", role="dimension", dtype="string", sources=("AREA_STREET",)),
    Layer1FieldSpec(name="forward_company", role="dimension", dtype="string", sources=("FORWARD_COMPANY",)),
    Layer1FieldSpec(name="driver_name", role="dimension", dtype="string", sources=("DRIVER_NAME",)),
    Layer1FieldSpec(name="driver_code", role="dimension", dtype="string", sources=("DRIVER_CODE",)),
    Layer1FieldSpec(name="third_party_status", role="dimension", dtype="string", sources=("3PLSTATUS",)),
    Layer1FieldSpec(name="third_party_last_status", role="dimension", dtype="string", sources=("3PL_Last_Status",)),
    Layer1FieldSpec(name="esnad_forwarded_awb", role="dimension", dtype="string", sources=("Esnad_Fowarded_AWB",)),
    Layer1FieldSpec(name="sender_name", role="dimension", dtype="string", sources=("SENDER_NAME",)),
    Layer1FieldSpec(name="sender_phone", role="dimension", dtype="string", sources=("SENDER_PHONE",)),
    Layer1FieldSpec(name="receiver_name", role="dimension", dtype="string", sources=("RECEIVER_NAME",)),
    Layer1FieldSpec(name="receiver_phone", role="dimension", dtype="string", sources=("RECEIVER_PHONE",)),
    Layer1FieldSpec(name="forward_awb_no", role="dimension", dtype="string", sources=("FORWARD_AWB_No",)),
    Layer1FieldSpec(name="super_id", role="dimension", dtype="string", sources=("Super_ID",)),
    Layer1FieldSpec(name="system_name", role="dimension", dtype="string", sources=("System_Name",)),
    Layer1FieldSpec(name="pickup_date", role="temporal", dtype="datetime", sources=("PICKUP_DATE",)),
    Layer1FieldSpec(name="pickup_time", role="dimension", dtype="string", sources=("PICKUP_TIME",)),
    Layer1FieldSpec(name="entry_date", role="temporal", dtype="datetime", sources=("ENTRY_DATE",)),
    Layer1FieldSpec(name="entry_time", role="dimension", dtype="string", sources=("entry_TIME",)),
    Layer1FieldSpec(name="schedule_date", role="temporal", dtype="datetime", sources=("SCHEDULE_DATE",)),
    Layer1FieldSpec(name="delivery_date", role="temporal", dtype="datetime", sources=("DELIVER_DATE",)),
    Layer1FieldSpec(name="last_delivery_attempt_date", role="temporal", dtype="datetime", sources=("D_ATTEMPT_Date",)),
    Layer1FieldSpec(name="call_attempts", role="metric", dtype="int", sources=("CALL_ATTEMPT",)),
    Layer1FieldSpec(name="delivery_attempts", role="metric", dtype="int", sources=("D_ATTEMPT",)),
    Layer1FieldSpec(name="cod_amount", role="metric", dtype="float", sources=("COD_AMOUNT",)),
    Layer1FieldSpec(name="amount", role="metric", dtype="float", derive="amount_from_cod", description_en="Shipment amount aligned with COD value when separate total is unavailable."),
    Layer1FieldSpec(name="weight_kg", role="metric", dtype="float", sources=("ON_WEIGHT",)),
    Layer1FieldSpec(name="volumetric_weight", role="metric", dtype="float", sources=("Volumetric_Weight",)),
    Layer1FieldSpec(name="piece_count", role="metric", dtype="int", sources=("ON_PIECES",)),
    Layer1FieldSpec(name="latitude", role="metric", dtype="float", sources=("LATITUDE",), description_en="Latitude extracted from shipment record coordinates."),
    Layer1FieldSpec(name="longitude", role="metric", dtype="float", sources=("LONGITUDE",), description_en="Longitude extracted from shipment record coordinates."),
    Layer1FieldSpec(name="order_date", role="temporal", dtype="datetime", derive="order_date", description_en="Best-effort order timestamp using entry then pickup dates."),
    Layer1FieldSpec(name="delivery_delay_days", role="metric", dtype="float", derive="delivery_delay_days", description_en="Difference in days between delivery and pickup/scheduled dates."),
    Layer1FieldSpec(name="cod_flag", role="flag", dtype="bool", derive="cod_flag", description_en="Indicates whether the shipment collected COD value."),
    Layer1FieldSpec(name="geocoded_flag", role="flag", dtype="bool", derive="geocoded_flag", description_en="True when both latitude and longitude are known."),
    Layer1FieldSpec(name="order_weekday", role="dimension", dtype="string", derive="order_weekday", description_en="Weekday label derived from order_date."),
    Layer1FieldSpec(name="order_month", role="dimension", dtype="string", derive="order_month", description_en="Year-month label derived from order_date."),
)


def _label_en(spec: Layer1FieldSpec) -> str:
    return spec.name.replace("_", " ").title()


def _label_ar(spec: Layer1FieldSpec) -> str:
    return AR_LABEL_OVERRIDES.get(spec.name, _label_en(spec))


def _default_description_en(spec: Layer1FieldSpec) -> str:
    if spec.sources:
        return f"{_label_en(spec)} sourced from {', '.join(spec.sources)}"
    if spec.derive:
        return f"{_label_en(spec)} derived via '{spec.derive}' rule"
    return f"{_label_en(spec)} field"


def _default_description_ar(spec: Layer1FieldSpec) -> str:
    return AR_LABEL_OVERRIDES.get(spec.name, _label_en(spec))


def _series_from_sources(df: "pd.DataFrame", sources: Sequence[str]) -> "pd.Series":
    for column in sources:
        if column in df.columns:
            return df[column]
    return pd.Series([None] * len(df), index=df.index)


def _coerce_string(series: "pd.Series") -> "pd.Series":
    return series.astype(STRING_DTYPE)


def _coerce_float(series: "pd.Series") -> "pd.Series":
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.astype("Float64")


def _coerce_int(series: "pd.Series") -> "pd.Series":
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.round().astype("Int64")


def _coerce_bool(series: "pd.Series") -> "pd.Series":
    text = series.astype(str).str.strip().str.lower()
    mapped = text.map(lambda value: True if value in TRUE_VALUES else False if value in FALSE_VALUES else pd.NA)
    return mapped.astype("boolean")


def _coerce_datetime(series: "pd.Series") -> "pd.Series":
    return pd.to_datetime(series, errors="coerce")


def _apply_dtype(series: "pd.Series", dtype: str) -> "pd.Series":
    if dtype == "string":
        return _coerce_string(series)
    if dtype == "float":
        return _coerce_float(series)
    if dtype == "int":
        return _coerce_int(series)
    if dtype == "bool":
        return _coerce_bool(series)
    if dtype == "datetime":
        return _coerce_datetime(series)
    raise ValueError(f"Unsupported dtype '{dtype}' for layer1 dataset")


def _derive_layer1_column(key: str, df: "pd.DataFrame", layer1: "pd.DataFrame") -> "pd.Series":
    index = df.index
    if not isinstance(index, pd.Index):
        index = pd.Index(index)
    if key == "order_date":
        primary = pd.to_datetime(df.get("ENTRY_DATE"), errors="coerce")
        secondary = pd.to_datetime(df.get("PICKUP_DATE"), errors="coerce")
        return primary.fillna(secondary).reindex(index)
    if key == "amount_from_cod":
        return pd.to_numeric(df.get("COD_AMOUNT"), errors="coerce").reindex(index)
    if key == "delivery_delay_days":
        delivery = pd.to_datetime(layer1.get("delivery_date"), errors="coerce")
        pickup = pd.to_datetime(layer1.get("pickup_date"), errors="coerce")
        schedule = pd.to_datetime(layer1.get("schedule_date"), errors="coerce")
        baseline = pickup.fillna(schedule)
        delta = (delivery - baseline).dt.total_seconds() / 86400.0
        return pd.Series(delta, index=index)
    if key == "cod_flag":
        cod = pd.to_numeric(layer1.get("cod_amount"), errors="coerce")
        amount = pd.to_numeric(layer1.get("amount"), errors="coerce") if "amount" in layer1 else pd.Series([pd.NA] * len(index), index=index)
        combined = cod.fillna(amount)
        mask = combined.notna()
        result = pd.Series(pd.NA, index=index, dtype="boolean")
        result.loc[mask] = combined.loc[mask] > 0
        return result
    if key == "geocoded_flag":
        lat = pd.to_numeric(layer1.get("latitude"), errors="coerce")
        lon = pd.to_numeric(layer1.get("longitude"), errors="coerce")
        mask = (~lat.isna()) & (~lon.isna())
        result = pd.Series(pd.NA, index=index, dtype="boolean")
        result.loc[mask] = True
        result.loc[~mask & (lat.isna() | lon.isna())] = False
        return result
    if key == "order_weekday":
        order_date = pd.to_datetime(layer1.get("order_date"), errors="coerce")
        return order_date.dt.strftime("%A").reindex(index)
    if key == "order_month":
        order_date = pd.to_datetime(layer1.get("order_date"), errors="coerce")
        return order_date.dt.strftime("%Y-%m").reindex(index)
    return pd.Series([None] * len(index), index=index)


def _sample_values(series: "pd.Series", limit: int = 8) -> List[Any]:
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


def _count_roles(entries: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        role = entry.get("role", "dimension")
        counts[role] = counts.get(role, 0) + 1
    return counts


def _build_layer1_dataset(df: "pd.DataFrame", run_id: str) -> Tuple["pd.DataFrame", Dict[str, Any]]:
    layer1 = pd.DataFrame(index=df.index)
    metadata: List[Dict[str, Any]] = []

    for spec in LAYER1_FIELD_SPECS:
        if spec.derive:
            series = _derive_layer1_column(spec.derive, df, layer1)
        else:
            series = _series_from_sources(df, spec.sources)
        coerced = _apply_dtype(series, spec.dtype)
        layer1[spec.name] = coerced

        entry: Dict[str, Any] = {
            "name": spec.name,
            "role": spec.role,
            "dtype": spec.dtype,
            "label": {"en": _label_en(spec), "ar": _label_ar(spec)},
            "description": {
                "en": spec.description_en or _default_description_en(spec),
                "ar": spec.description_ar or _default_description_ar(spec),
            },
            "nullable": bool(coerced.isna().any()),
            "source_columns": list(spec.sources),
        }
        if not coerced.isna().all():
            entry["sample_values"] = _sample_values(coerced)
            try:
                entry["unique_values"] = int(coerced.dropna().nunique())
            except Exception:
                entry["unique_values"] = None
        metadata.append(entry)

    schema = {
        "run_id": run_id,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "row_count": int(len(df)),
        "field_count": len(LAYER1_FIELD_SPECS),
        "role_counts": _count_roles(metadata),
        "columns": metadata,
    }

    return layer1, schema


def _serialize_preview_rows(frame: "pd.DataFrame", limit: int = 200) -> List[Dict[str, Any]]:
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
            preview[column] = series.astype(STRING_DTYPE).where(~series.isna(), None)
    return preview.replace({pd.NA: None}).to_dict(orient="records")


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[override]
    artifacts_root = Path((config or {}).get("artifacts_root", "artifacts"))
    out_dir = artifacts_root / run_id / "stage_06_feature_eng"
    _ensure_dir(out_dir)

    curated_uri = (inputs or {}).get("raw") or (inputs or {}).get("raw_uri") or (inputs or {}).get("features_curated")
    if not isinstance(curated_uri, str):
        raise ValueError("Stage 06 feature_eng requires curated features via inputs['raw']")
    curated_path = Path(curated_uri).expanduser().resolve()
    if not curated_path.exists():
        raise FileNotFoundError(f"curated feature dataset not found: {curated_path}")

    pre_features_uri = (inputs or {}).get("features_pre") or (out_dir / "features.pre.parquet").as_posix()
    pre_path = Path(pre_features_uri).expanduser().resolve()

    df_pre_exists = pre_path.exists()
    if df_pre_exists:
        pre_df = _load_dataframe(pre_path)
        n_in_rows = int(len(pre_df))
        pre_columns: Set[str] = {str(col) for col in pre_df.columns}
    else:
        pre_df = None
        pre_columns = set()
        n_in_rows = None

    df_curated = _load_dataframe(curated_path)
    n_rows = int(len(df_curated))
    post_columns: List[str] = [str(col) for col in df_curated.columns]

    baseline = baseline_utils.load(artifacts_root, run_id)
    expected_rows = int(baseline.get("n_rows", 0)) if baseline else None
    baseline_utils.enforce_row_guard(expected=expected_rows, actual=n_rows, phase="06F", out_dir=out_dir)

    if n_in_rows is None:
        n_in_rows = n_rows
        pre_columns = set(post_columns)

    if n_in_rows != n_rows:
        mismatch_payload = {
            "phase": "06F",
            "n_in": int(n_in_rows),
            "n_out": int(n_rows),
            "reason": "row_count_change",
        }
        (out_dir / "shape_mismatch.json").write_text(json.dumps(mismatch_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit(1)

    if not post_columns:
        payload = {
            "phase": "06F",
            "n_in": len(pre_columns),
            "n_out": 0,
            "reason": "all_columns_excluded",
        }
        (out_dir / "shape_mismatch.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit(1)

    final_path = out_dir / "features.parquet"
    df_final = df_curated  # placeholder for future feature engineering steps
    df_final.to_parquet(final_path, index=False)

    layer1_frame, layer1_schema = _build_layer1_dataset(df_final, run_id)
    layer1_path = out_dir / "layer1_dataset.parquet"
    layer1_frame.to_parquet(layer1_path, index=False)
    layer1_schema_path = out_dir / "layer1_schema.json"
    layer1_schema_path.write_text(json.dumps(layer1_schema, ensure_ascii=False, indent=2), encoding="utf-8")
    layer1_sample_path = out_dir / "layer1_sample.json"
    layer1_preview_rows = _serialize_preview_rows(layer1_frame)
    layer1_sample_payload = {
        "run_id": run_id,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "row_count": int(layer1_frame.shape[0]),
        "field_count": int(layer1_frame.shape[1]),
        "rows": layer1_preview_rows,
    }
    layer1_sample_path.write_text(json.dumps(layer1_sample_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    exclusions_applied = _load_exclusions(out_dir)
    kept_cols = sorted(set(post_columns) & pre_columns)
    dropped_cols = sorted(pre_columns - set(post_columns))
    added_cols = sorted(set(post_columns) - pre_columns)
    from_exclusions = sorted(exclusions_applied & set(dropped_cols))

    diff_report = {
        "n_in": int(n_in_rows),
        "n_out": int(n_rows),
        "cols_in": len(pre_columns),
        "cols_out": len(post_columns),
        "kept_cols": kept_cols,
        "dropped_cols": dropped_cols,
        "from_exclusions": from_exclusions,
        "added_cols": added_cols,
        "row_change_detected": False,
    }
    diff_path = out_dir / "diff_report.json"
    diff_path.write_text(json.dumps(diff_report, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "columns": post_columns,
        "source_curated": curated_path.as_posix(),
        "source_pre": pre_path.as_posix() if df_pre_exists else None,
    }
    (out_dir / "feature_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    logs = [
        {"event": "rows_in", "value": int(n_in_rows)},
        {"event": "rows_out", "value": n_rows},
        {"event": "cols_out", "value": len(post_columns)},
        {"event": "kept_cols", "count": len(kept_cols)},
        {"event": "dropped_cols", "count": len(dropped_cols)},
        {"event": "added_cols", "count": len(added_cols)},
    ]
    logs.append(
        {
            "event": "layer1_dataset",
            "rows": int(layer1_frame.shape[0]),
            "columns": int(layer1_frame.shape[1]),
            "path": layer1_path.as_posix(),
        }
    )
    _write_logs(out_dir, logs)

    row_meta = {"phase": "06F", "n_rows": n_rows, "source": final_path.as_posix(), "n_cols": len(post_columns)}
    (out_dir / "row_meta.json").write_text(json.dumps(row_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Auto-detect main timestamp column for feature_spec.json
    def _detect_main_ts(columns: List[str], df: pd.DataFrame) -> Optional[str]:
        """Detect the main timestamp column from available columns."""
        preferred = ["created_at", "CREATED_AT", "EVENT_TS", "CREATED_AT_TS", "PICKUP_DATE", "ENTRY_DATE", "DELIVER_DATE"]
        for name in preferred:
            if name in columns:
                series = df[name]
                if ptypes.is_datetime64_any_dtype(series) or ptypes.is_object_dtype(series):
                    return name
        # Try to find any datetime column
        for col in columns:
            if col in df.columns:
                series = df[col]
                if ptypes.is_datetime64_any_dtype(series):
                    return col
                # Try parsing as datetime
                try:
                    pd.to_datetime(series.iloc[0:10], errors="raise")
                    return col
                except (ValueError, TypeError, IndexError):
                    continue
        return None

    main_ts = _detect_main_ts(post_columns, df_final)
    feature_spec = {}
    if main_ts:
        feature_spec["main_ts"] = main_ts
    (out_dir / "feature_spec.json").write_text(json.dumps(feature_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    # Ensure features.curated.parquet exists in output directory
    curated_output_path = out_dir / "features.curated.parquet"
    if curated_output_path == curated_path:
        # Input is already the output file, no action needed
        pass
    elif curated_path.exists() and curated_path != final_path:
        # Copy from input if it's different from final and exists
        import shutil
        if not curated_output_path.exists() or curated_output_path.stat().st_mtime < curated_path.stat().st_mtime:
            shutil.copy2(curated_path, curated_output_path)
    else:
        # Save current final as curated (they are the same dataset)
        if not curated_output_path.exists() or curated_output_path != final_path:
            df_final.to_parquet(curated_output_path, index=False)

    outputs = {
        "raw": final_path.as_posix(),
        "features": final_path.as_posix(),
        "features_curated": curated_output_path.as_posix(),
        "features_pre": pre_path.as_posix() if df_pre_exists else None,
        "diff_report": diff_path.as_posix(),
    }
    outputs["layer1_dataset"] = layer1_path.as_posix()
    outputs["layer1_schema"] = layer1_schema_path.as_posix()
    outputs["layer1_sample"] = layer1_sample_path.as_posix()
    outputs["feature_spec"] = (out_dir / "feature_spec.json").as_posix()

    return {
        "run_id": run_id,
        "status": "PASS",
        "outputs": outputs,
        "metrics": {"n_rows": n_rows, "n_cols": len(post_columns)},
        "logs_uri": (out_dir / "logs.jsonl").as_posix(),
    }


__all__ = ["run"]
