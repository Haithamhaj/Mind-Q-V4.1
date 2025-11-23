from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import polars as pl  # type: ignore
import yaml  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TIMEZONE = "Asia/Riyadh"
DEFAULT_CURRENCY = "SAR"

MART_SOURCES: Tuple[Tuple[str, str, str], ...] = (
    ("stage_09_business_validation", "bi_feed.parquet", "fact_business.parquet"),
    ("stage_09_business_validation", "row_decisions.parquet", "fact_decisions.parquet"),
    ("stage_09_business_validation", "benchmarks.parquet", "fact_benchmarks.parquet"),
    ("stage_09_business_validation", "segment_insights.parquet", "segment_insights.parquet"),
)

TILE_DIR = "bi_tiles"
SEMANTIC_DIRNAME = "semantic"
MARTS_DIRNAME = "marts"
INSIGHTS_DIRNAME = "insights"
DATASETS_DIRNAME = "datasets"
ORDERS_DATASET_FILENAME = "orders.parquet"
DIMENSIONS_FILENAME = "dimensions.json"
INSIGHTS_FILENAME = "insights.json"

CANDIDATE_SCHEMA = {
    "kpi": pl.Utf8,
    "feature": pl.Utf8,
    "metric": pl.Utf8,
    "effect": pl.Float64,
    "strength": pl.Float64,
    "direction": pl.Utf8,
    "n": pl.Float64,
    "coverage": pl.Float64,
    "confidence": pl.Float64,
    "bucket": pl.Utf8,
    "stability_score": pl.Float64,
    "low_signal": pl.Boolean,
    "source": pl.Utf8,
    "notes": pl.Utf8,
}

INSIGHT_SCHEMA = {
    "kpi": pl.Utf8,
    "feature": pl.Utf8,
    "strength": pl.Float64,
    "confidence": pl.Float64,
    "coverage": pl.Float64,
    "bucket": pl.Utf8,
    "segment": pl.Utf8,
    "direction": pl.Utf8,
    "window": pl.Utf8,
    "business_context": pl.Utf8,
}

SUMMARY_SCHEMA = {
    "metric": pl.Utf8,
    "category": pl.Utf8,
    "value": pl.Float64,
    "unit": pl.Utf8,
    "source": pl.Utf8,
}

DATETIME_CORR_SCHEMA = {
    "feature_x": pl.Utf8,
    "feature_y": pl.Utf8,
    "correlation": pl.Float64,
    "correlation_abs": pl.Float64,
    "pair_n": pl.Int64,
}

CAUSAL_FACT_SCHEMA = {
    "segment": pl.Utf8,
    "estimate_type": pl.Utf8,
    "effect": pl.Float64,
    "n": pl.Int64,
    "priority": pl.Utf8,
    "method": pl.Utf8,
    "problem_name": pl.Utf8,
}

ORDERS_DATASET_SCHEMA = {
    # Core order fields (7 original columns)
    "order_id": pl.Utf8,
    "destination": pl.Utf8,
    "payment_method": pl.Utf8,
    "status": pl.Utf8,
    "order_date": pl.Utf8,
    "amount": pl.Float64,
    "cod_amount": pl.Float64,
    
    # Customer/Client columns (for customer analytics)
    "customer_id": pl.Utf8,
    "sender_name": pl.Utf8,
    "sender_address": pl.Utf8,
    "sender_phone": pl.Utf8,
    "receiver_name": pl.Utf8,
    "receiver_address": pl.Utf8,
    "receiver_phone": pl.Utf8,
    
    # Carrier/Logistics columns (for shipping company analytics)
    "forward_company": pl.Utf8,
    "driver_name": pl.Utf8,
    "driver_code": pl.Utf8,
    "carrier_status": pl.Utf8,  # 3PLSTATUS
    "carrier_last_status": pl.Utf8,  # 3PL Last Status
    "forward_awb": pl.Utf8,  # FORWARD AWB No
    
    # Location/Geography columns (for geographic analytics)
    "origin": pl.Utf8,
    "origin_hub": pl.Utf8,
    "destination_hub": pl.Utf8,
    "area_name": pl.Utf8,
    "area_street": pl.Utf8,
    "latitude": pl.Float64,
    "longitude": pl.Float64,
    
    # Shipment details (for product/service type analytics)
    "description": pl.Utf8,
    "sub_category": pl.Utf8,  # Sub_Category_Details
    "sub_category_comment": pl.Utf8,
    "pieces": pl.Float64,  # ON PIECES
    "weight": pl.Float64,  # ON WEIGHT
    "volumetric_weight": pl.Float64,
    
    # Date/Time tracking (for performance analytics)
    "pickup_date": pl.Utf8,
    "pickup_time": pl.Utf8,
    "entry_date": pl.Utf8,
    "deliver_date": pl.Utf8,
    "schedule_date": pl.Utf8,
    "on_hold_date": pl.Utf8,
    
    # Status details (for operational analytics)
    "sub_status": pl.Utf8,
    "on_hold": pl.Utf8,
    "on_hold_reason": pl.Utf8,
    "delivery_attempts": pl.Float64,  # D ATTEMPT
    "call_attempts": pl.Float64,  # CALL ATTEMPT
    
    # Reference fields (for tracking)
    "reference_no": pl.Utf8,  # REFRENCE No
    "shipper_ref": pl.Utf8,  # SHIPPER REF No
    "transaction_number": pl.Utf8,
    
    # Financial tracking (for financial analytics)
    "pay_invoice_status": pl.Utf8,
    "payable_status": pl.Utf8,
    "receivable_status": pl.Utf8,
    "receivable_invoice": pl.Utf8,
    
    # System fields
    "system_name": pl.Utf8,
    "super_id": pl.Utf8,
}


def _load_column_policy_map(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    policies: Dict[str, Dict[str, Any]] = {}
    for entry in payload.get("columns", []) or []:
        name = entry.get("name")
        if not name:
            continue
        policies[str(name)] = {
            "classification": entry.get("classification", "internal"),
            "include_in_bi_feed": bool(entry.get("include_in_bi_feed", True)),
            "include_in_semantic": bool(entry.get("include_in_semantic", True)),
            "include_in_exports": bool(entry.get("include_in_exports", True)),
            "tags": list(entry.get("tags") or []),
        }
    return policies


def _filtered_orders_schema(column_policies: Mapping[str, Dict[str, Any]]) -> Dict[str, pl.DataType]:
    if not column_policies:
        return dict(ORDERS_DATASET_SCHEMA)
    schema: Dict[str, pl.DataType] = {}
    for name, dtype in ORDERS_DATASET_SCHEMA.items():
        policy = column_policies.get(name)
        if policy and not policy.get("include_in_exports", True):
            continue
        schema[name] = dtype
    return schema


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _copy_parquet(src: Path, dest: Path) -> bool:
    if not src.exists():
        return False
    _ensure_dir(dest.parent)
    shutil.copy2(src, dest)
    return True


def _empty_frame(schema: Mapping[str, pl.DataType]) -> pl.DataFrame:
    columns = {name: pl.Series(name=name, values=[], dtype=dtype) for name, dtype in schema.items()}
    return pl.DataFrame(columns)


def _write_parquet(df: pl.DataFrame, dest: Path) -> None:
    _ensure_dir(dest.parent)
    if df.is_empty():
        df = df.with_columns([pl.Series(name=col, values=[], dtype=dt) for col, dt in df.schema.items()])
    df.write_parquet(dest.as_posix())


def _read_parquet(path: Path) -> Optional[pl.DataFrame]:
    if not path.exists():
        return None
    try:
        return pl.read_parquet(path.as_posix())
    except Exception:
        return None


def _normalised_orders_dataset(
    marts_dir: Path,
    column_policies: Mapping[str, Dict[str, Any]],
) -> Tuple[Optional[pl.DataFrame], List[str]]:
    # Read from stage 01 raw data instead of stage 09 aggregated KPIs
    # Navigate up from stage_10_bi/marts to artifacts root, then to stage_01_ingestion
    run_dir = marts_dir.parent.parent  # Go up from marts/ to stage_10_bi/ to run directory
    source = run_dir / "stage_01_ingestion" / "raw.parquet"
    frame = _read_parquet(source)
    if frame is None or frame.is_empty():
        return None, []

    alias_map: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
        # Core order fields
        ("order_id", ("order_id", "AWB_NO", "awb_no", "OrderNo", "ORDER_NO", "entity_id")),
        ("destination", ("destination", "DESTINATION", "Destination", "DESTINATION_HUB")),
        ("payment_method", ("payment_method", "payment method", "PAYMENT_METHOD", "RECEIVER MODE", "RECEIVER_MODE")),
        ("amount", ("amount", "AMOUNT", "total_amount", "TOTAL_AMOUNT", "Shipment_Value", "SHIPMENT_VALUE")),
        ("order_date", ("order_date", "ORDER_DATE", "ENTRY_DATE", "PICKUP_DATE", "CREATED_AT", "ts")),
        ("status", ("status", "STATUS", "Sub_Status", "SUB_STATUS")),
        ("cod_amount", ("cod_amount", "COD_AMOUNT", "cod", "COD", "cash_on_delivery_amount")),
        
        # Customer/Client mappings
        ("customer_id", ("customer_id", "Account_NO", "account_no", "CLIENT_ID", "client_id")),
        ("sender_name", ("sender_name", "SENDER NAME", "SENDER_NAME", "sender", "CLIENT_NAME")),
        ("sender_address", ("sender_address", "SENDER ADDRESS", "SENDER_ADDRESS")),
        ("sender_phone", ("sender_phone", "SENDER PHONE", "SENDER_PHONE")),
        ("receiver_name", ("receiver_name", "RECEIVER NAME", "RECEIVER_NAME", "receiver", "consignee")),
        ("receiver_address", ("receiver_address", "RECEIVER ADDRESS", "RECEIVER_ADDRESS")),
        ("receiver_phone", ("receiver_phone", "RECEIVER PHONE", "RECEIVER_PHONE")),
        
        # Carrier/Logistics mappings
        ("forward_company", ("forward_company", "FORWARD COMPANY", "FORWARD_COMPANY", "carrier", "CARRIER", "courier", "COURIER")),
        ("driver_name", ("driver_name", "DRIVER NAME", "DRIVER_NAME", "driver")),
        ("driver_code", ("driver_code", "DRIVER CODE", "DRIVER_CODE")),
        ("carrier_status", ("carrier_status", "3PLSTATUS", "3PL STATUS", "3pl_status")),
        ("carrier_last_status", ("carrier_last_status", "3PL Last Status", "3PL_LAST_STATUS")),
        ("forward_awb", ("forward_awb", "FORWARD AWB No", "FORWARD_AWB_NO", "Esnad Fowarded AWB")),
        
        # Location/Geography mappings
        ("origin", ("origin", "ORIGIN", "ORIGIN_HUB", "source_hub")),
        ("origin_hub", ("origin_hub", "ORIGIN_HUB", "ORIGIN HUB")),
        ("destination_hub", ("destination_hub", "DESTINATION_HUB", "DESTINATION HUB")),
        ("area_name", ("area_name", "Area Name", "AREA_NAME")),
        ("area_street", ("area_street", "AREA STREET", "AREA_STREET")),
        ("latitude", ("latitude", "LATITUDE", "lat")),
        ("longitude", ("longitude", "LONGITUDE", "lon", "lng")),
        
        # Shipment details mappings
        ("description", ("description", "DESCRIPTION", "Sub_Category_Details", "SUB_CATEGORY_DETAILS", "product_type")),
        ("sub_category", ("sub_category", "Sub_Category_Details", "SUB_CATEGORY_DETAILS")),
        ("sub_category_comment", ("sub_category_comment", "Sub_Category_Comment", "SUB_CATEGORY_COMMENT")),
        ("pieces", ("pieces", "ON PIECES", "ON_PIECES", "pieces_count")),
        ("weight", ("weight", "ON WEIGHT", "ON_WEIGHT", "weight_kg")),
        ("volumetric_weight", ("volumetric_weight", "Volumetric Weight", "VOLUMETRIC_WEIGHT")),
        
        # Date/Time tracking mappings
        ("pickup_date", ("pickup_date", "PICKUP_DATE", "PICKUP DATE")),
        ("pickup_time", ("pickup_time", "PICKUP_TIME", "PICKUP TIME")),
        ("entry_date", ("entry_date", "ENTRY_DATE", "ENTRY DATE", "entry_TIME")),
        ("deliver_date", ("deliver_date", "DELIVER DATE", "DELIVER_DATE", "delivery_date")),
        ("schedule_date", ("schedule_date", "SCHEDULE DATE", "SCHEDULE_DATE")),
        ("on_hold_date", ("on_hold_date", "ON HOLD DATE", "ON_HOLD_DATE")),
        
        # Status details mappings
        ("sub_status", ("sub_status", "SUB_STATUS", "Sub_Status", "SUB STATUS")),
        ("on_hold", ("on_hold", "ON HOLD", "ON_HOLD")),
        ("on_hold_reason", ("on_hold_reason", "ON HOLD REASON", "ON_HOLD_REASON")),
        ("delivery_attempts", ("delivery_attempts", "D ATTEMPT", "D_ATTEMPT", "delivery_attempt_count")),
        ("call_attempts", ("call_attempts", "CALL ATTEMPT", "CALL_ATTEMPT")),
        
        # Reference fields mappings
        ("reference_no", ("reference_no", "REFRENCE No", "REFERENCE_NO", "ref_no")),
        ("shipper_ref", ("shipper_ref", "SHIPPER REF No", "SHIPPER_REF_NO")),
        ("transaction_number", ("transaction_number", "Transaction Number", "TRANSACTION_NUMBER")),
        
        # Financial tracking mappings
        ("pay_invoice_status", ("pay_invoice_status", "PAY INVOICE STATUS", "PAY_INVOICE_STATUS")),
        ("payable_status", ("payable_status", "Payable Status", "PAYABLE_STATUS")),
        ("receivable_status", ("receivable_status", "Recievable Status", "RECEIVABLE_STATUS")),
        ("receivable_invoice", ("receivable_invoice", "Recievable Invoice No", "RECEIVABLE_INVOICE_NO")),
        
        # System fields mappings
        ("system_name", ("system_name", "System_Name", "SYSTEM_NAME")),
        ("super_id", ("super_id", "Super ID", "SUPER_ID")),
    )

    for target, aliases in alias_map:
        if target in frame.columns:
            continue
        for alias in aliases:
            if alias in frame.columns:
                frame = frame.rename({alias: target})
                break

    # If cod_amount is missing but amount exists, create cod_amount from amount
    if "cod_amount" not in frame.columns and "amount" in frame.columns:
        frame = frame.with_columns(pl.col("amount").alias("cod_amount"))

    required = {"order_id", "destination", "payment_method", "amount", "order_date", "status", "cod_amount"}
    if not required.issubset(frame.columns):
        return None, []

    # Process string columns
    string_cols = [
        "order_id", "destination", "payment_method", "status",
        "customer_id", "sender_name", "sender_address", "sender_phone",
        "receiver_name", "receiver_address", "receiver_phone",
        "forward_company", "driver_name", "driver_code", 
        "carrier_status", "carrier_last_status", "forward_awb",
        "origin", "origin_hub", "destination_hub", 
        "area_name", "area_street",
        "description", "sub_category", "sub_category_comment",
        "sub_status", "on_hold", "on_hold_reason",
        "reference_no", "shipper_ref", "transaction_number",
        "pay_invoice_status", "payable_status", 
        "receivable_status", "receivable_invoice",
        "system_name", "super_id",
    ]
    for col in string_cols:
        if col in frame.columns:
            frame = frame.with_columns(pl.col(col).cast(pl.Utf8, strict=False).fill_null("").str.strip())

    # Process numeric columns
    numeric_cols = [
        "amount", "cod_amount", 
        "latitude", "longitude",
        "pieces", "weight", "volumetric_weight",
        "delivery_attempts", "call_attempts",
    ]
    for col in numeric_cols:
        if col in frame.columns:
            frame = frame.with_columns(pl.col(col).cast(pl.Float64, strict=False).fill_null(0.0))

    # Process date columns
    date_cols = [
        "order_date", "pickup_date", "entry_date", 
        "deliver_date", "schedule_date", "on_hold_date",
    ]
    for col in date_cols:
        if col not in frame.columns:
            continue
        col_dtype = frame.schema.get(col)
        if col_dtype is not None:
            if col_dtype in (pl.Datetime, pl.Date):
                frame = frame.with_columns(pl.col(col).dt.strftime("%Y-%m-%dT%H:%M:%S").fill_null(""))
            else:
                frame = frame.with_columns(pl.col(col).cast(pl.Utf8, strict=False).fill_null("").str.strip())

    # Ensure cod_amount is populated when amount is available
    frame = frame.with_columns(
        pl.when(pl.col("cod_amount") == 0)
        .then(pl.col("amount"))
        .otherwise(pl.col("cod_amount"))
        .alias("cod_amount")
    )

    # Select columns that exist in the frame from our schema
    suppressed_export_columns = [
        name
        for name, policy in column_policies.items()
        if not policy.get("include_in_exports", True) and name in frame.columns
    ]
    if suppressed_export_columns:
        frame = frame.drop(suppressed_export_columns)

    desired_columns = [
        # Core fields (always required)
        "order_id", "destination", "payment_method", "status", "order_date", "amount", "cod_amount",
        
        # Customer analytics
        "customer_id", "sender_name", "sender_address", "sender_phone",
        "receiver_name", "receiver_address", "receiver_phone",
        
        # Carrier analytics
        "forward_company", "driver_name", "driver_code", 
        "carrier_status", "carrier_last_status", "forward_awb",
        
        # Geographic analytics
        "origin", "origin_hub", "destination_hub", 
        "area_name", "area_street", "latitude", "longitude",
        
        # Shipment analytics
        "description", "sub_category", "sub_category_comment",
        "pieces", "weight", "volumetric_weight",
        
        # Performance analytics
        "pickup_date", "pickup_time", "entry_date", "deliver_date", 
        "schedule_date", "on_hold_date",
        
        # Operational analytics
        "sub_status", "on_hold", "on_hold_reason", 
        "delivery_attempts", "call_attempts",
        
        # Reference tracking
        "reference_no", "shipper_ref", "transaction_number",
        
        # Financial analytics
        "pay_invoice_status", "payable_status", 
        "receivable_status", "receivable_invoice",
        
        # System tracking
        "system_name", "super_id",
    ]
    if column_policies:
        desired_columns = [
            column
            for column in desired_columns
            if column_policies.get(column, {}).get("include_in_exports", True)
        ]

    available_columns = []
    
    for col in desired_columns:
        if col in frame.columns:
            available_columns.append(col)
    
    dataset = frame.select(available_columns) if available_columns else pl.DataFrame()
    return dataset, suppressed_export_columns


def _collect_unique_strings(frame: Optional[pl.DataFrame], column: str, limit: int = 50) -> List[str]:
    if frame is None or column not in frame.columns:
        return []
    values: List[str] = []
    for value in frame.get_column(column).to_list():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            values.append(text)
    unique_sorted = sorted(set(values))
    return unique_sorted[:limit]


def _build_dimensions_payload(
    dataset: Optional[pl.DataFrame],
) -> Dict[str, Any]:
    dimensions: List[Dict[str, Any]] = []
    for column in ("destination", "payment_method", "status"):
        values = _collect_unique_strings(dataset, column)
        dimensions.append(
            {
                "name": column,
                "type": "categorical",
                "values": values,
                "description": "",
            }
        )
    if dataset is not None and "order_date" in dataset.columns:
        dimensions.append(
            {
                "name": "order_date",
                "type": "temporal",
                "format": "datetime",
                "description": "",
            }
        )

    metrics: List[Dict[str, Any]] = []
    total_orders = int(dataset.height) if dataset is not None else 0
    metrics.append({"name": "total_orders", "type": "count", "description": "Total number of orders", "value": total_orders})
    if dataset is not None and "amount" in dataset.columns:
        try:
            total_amount = float(dataset.get_column("amount").sum())
        except Exception:
            total_amount = 0.0
        metrics.append(
            {
                "name": "total_amount",
                "type": "sum",
                "field": "amount",
                "description": "Total shipment amount",
                "value": total_amount,
            }
        )
    if dataset is not None and {"payment_method", "cod_amount"}.issubset(set(dataset.columns)):
        try:
            payment_values = [str(v).strip().upper() for v in dataset.get_column("payment_method").to_list() if v]
            cod_orders = sum(1 for v in payment_values if v == "COD")
            cod_rate = (cod_orders / len(payment_values)) if payment_values else 0.0
        except Exception:
            cod_rate = 0.0
        try:
            cod_series = dataset.get_column("cod_amount").to_list()
            cod_amounts = [float(v) for v in cod_series if isinstance(v, (int, float))]
            avg_cod = sum(cod_amounts) / len(cod_amounts) if cod_amounts else 0.0
        except Exception:
            avg_cod = 0.0
        metrics.append({"name": "cod_rate", "type": "percentage", "description": "COD share of orders", "value": cod_rate})
        metrics.append(
            {
                "name": "avg_cod_amount",
                "type": "average",
                "field": "cod_amount",
                "description": "Average COD amount for COD orders",
                "value": avg_cod,
            }
        )

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "row_count": total_orders,
        "dimensions": dimensions,
        "metrics": metrics,
    }


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _build_insights_payload(
    payload: Mapping[str, Any],
    *,
    metrics_catalog: str,
    dimensions_catalog: str,
    sources: Mapping[str, Optional[str]],
    extra_context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        generated_at = datetime.utcnow().isoformat() + "Z"

    insights_raw = payload.get("insights")
    insights: List[Dict[str, Any]] = []
    if isinstance(insights_raw, list):
        for entry in insights_raw:
            if isinstance(entry, Mapping):
                insights.append(dict(entry))

    log_raw = payload.get("log")
    log_entries: List[str] = []
    if isinstance(log_raw, list):
        for item in log_raw:
            if item is None:
                continue
            log_entries.append(str(item))

    stats_by_type: Dict[str, int] = {}
    for entry in insights:
        entry_type = str(entry.get("type") or "unknown")
        stats_by_type[entry_type] = stats_by_type.get(entry_type, 0) + 1

    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else None

    result = {
        "generated_at": generated_at,
        "metrics_catalog": metrics_catalog,
        "dimensions_catalog": dimensions_catalog,
        "sources": dict(sources),
        "insights": insights,
        "log": log_entries,
        "summary": summary,
        "stats": {
            "insights_total": len(insights),
            "by_type": stats_by_type,
        },
    }
    if extra_context:
        result["context"] = dict(extra_context)
    return result


def include_causal_advisory(run_id: str, artifacts_root: Path, marts_dir: Path) -> Optional[Path]:
    stage_dir = artifacts_root / run_id / "stage_09_5_causal"
    insights_path = stage_dir / "causal_insights.json"
    if not insights_path.exists():
        return None

    try:
        payload = json.loads(insights_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not (payload.get("advisory_only") and payload.get("status") == "SUPPORTED"):
        return None

    recommendations_path = stage_dir / "causal_recommendations.json"
    priority_map: Dict[str, str] = {}
    if recommendations_path.exists():
        try:
            rec_payload = json.loads(recommendations_path.read_text(encoding="utf-8"))
            for item in rec_payload.get("items", []):
                if isinstance(item, Mapping):
                    segment = item.get("segment")
                    if segment:
                        priority_map[str(segment)] = str(item.get("priority", "")).upper() or "MEDIUM"
        except Exception:
            priority_map = {}

    rows: List[Dict[str, Any]] = []
    effect_info = payload.get("effect") or {}
    ate = effect_info.get("ATE")
    if isinstance(ate, (int, float)):
        rows.append(
            {
                "segment": "overall",
                "estimate_type": "ATE",
                "effect": float(ate),
                "n": int(payload.get("n", 0) or 0),
                "priority": "HIGH",
                "method": payload.get("method_baseline") or payload.get("method_advanced"),
                "problem_name": payload.get("problem_name"),
            }
        )

    for segment_entry in payload.get("CATE_by_segment", []):
        if not isinstance(segment_entry, Mapping):
            continue
        segment = str(segment_entry.get("segment") or "").strip()
        if not segment:
            continue
        effect = segment_entry.get("effect")
        if not isinstance(effect, (int, float)):
            continue
        rows.append(
            {
                "segment": segment,
                "estimate_type": "CATE",
                "effect": float(effect),
                "n": int(segment_entry.get("n", 0) or 0),
                "priority": priority_map.get(segment, "MEDIUM"),
                "method": payload.get("method_advanced") or payload.get("method_baseline"),
                "problem_name": payload.get("problem_name"),
            }
        )

    df = pl.DataFrame(rows) if rows else _empty_frame(CAUSAL_FACT_SCHEMA)
    if not df.is_empty():
        df = df.select(list(CAUSAL_FACT_SCHEMA.keys()))
    else:
        df = df.select(list(CAUSAL_FACT_SCHEMA.keys())) if df.columns else _empty_frame(CAUSAL_FACT_SCHEMA)

    dest = marts_dir / "fact_causal_effects.parquet"
    _write_parquet(df, dest)
    return dest


def _candidate_rows(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for candidate in payload.get("candidates", []):
        if not isinstance(candidate, Mapping):
            continue
        notes = candidate.get("notes") or []
        if isinstance(notes, Iterable) and not isinstance(notes, (str, bytes)):
            note_text = "; ".join(str(item) for item in notes)
        else:
            note_text = str(notes) if notes else ""
        rows.append(
            {
                "kpi": candidate.get("kpi"),
                "feature": candidate.get("feature"),
                "metric": candidate.get("metric"),
                "effect": candidate.get("effect"),
                "strength": candidate.get("strength"),
                "direction": candidate.get("direction"),
                "n": candidate.get("n"),
                "coverage": candidate.get("coverage"),
                "confidence": candidate.get("confidence"),
                "bucket": candidate.get("bucket"),
                "stability_score": candidate.get("stability_score"),
                "low_signal": bool(candidate.get("low_signal")),
                "source": candidate.get("source"),
                "notes": note_text,
            }
        )
    return rows


def _official_rows(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in payload.get("insights", []):
        if not isinstance(item, Mapping):
            continue
        business_context = item.get("business_context")
        context_serialized: Optional[str]
        if business_context is None:
            context_serialized = None
        else:
            try:
                context_serialized = json.dumps(business_context, ensure_ascii=False)
            except Exception:
                context_serialized = None
        rows.append(
            {
                "kpi": item.get("kpi"),
                "feature": item.get("feature"),
                "strength": item.get("strength"),
                "confidence": item.get("confidence"),
                "coverage": item.get("coverage"),
                "bucket": item.get("bucket"),
                "segment": item.get("segment"),
                "direction": item.get("direction"),
                "window": item.get("window"),
                "business_context": context_serialized,
            }
        )
    return rows


def _datetime_corr_rows(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    rows: List[Dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, Mapping):
            continue
        f1 = entry.get("f1")
        f2 = entry.get("f2")
        r_val = entry.get("r")
        abs_r = entry.get("abs_r")
        n_val = entry.get("n")
        try:
            pair_n = int(n_val) if n_val is not None else None
        except (TypeError, ValueError):
            pair_n = None
        rows.append(
            {
                "feature_x": f1,
                "feature_y": f2,
                "correlation": float(r_val) if r_val is not None else None,
                "correlation_abs": float(abs_r) if abs_r is not None else None,
                "pair_n": pair_n,
            }
        )
    return rows


def _collect_summary_rows(
    validation_report: Mapping[str, Any],
    metrics_payload: Mapping[str, Any],
    insights_summary: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for entry in validation_report.get("kpi_recalc", []) or []:
        if not isinstance(entry, Mapping):
            continue
        value = entry.get("recomputed")
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "metric": str(entry.get("name", "kpi")),
                "category": "kpi_recalc",
                "value": numeric,
                "unit": "",
                "source": "phase09",
            }
        )

    perf = validation_report.get("perf") or {}
    if isinstance(perf, Mapping):
        for key, value in perf.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "metric": str(key),
                    "category": "performance",
                    "value": numeric,
                    "unit": "ratio" if "pct" in key else "",
                    "source": "phase09",
                }
            )

    for key, value in metrics_payload.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "metric": str(key),
                "category": "phase09_metrics",
                "value": numeric,
                "unit": "",
                "source": "phase09",
            }
        )

    if isinstance(insights_summary, Mapping):
        for key, value in insights_summary.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "metric": str(key),
                    "category": "phase08_summary",
                    "value": numeric,
                    "unit": "",
                    "source": "phase08",
                }
            )

    return rows


def _status_score(status: Optional[str]) -> float:
    mapping = {
        "PASS": 1.0,
        "OK": 1.0,
        "WARN": 0.5,
        "ALERT": 0.5,
        "STOP": 0.0,
        "CRITICAL_ALERT": 0.0,
    }
    if status is None:
        return 0.0
    return mapping.get(status.upper(), 0.0)


def _build_semantic_payload(
    timezone: str,
    currency: str,
    marts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    metrics = [
        {
            "id": "orders_total",
            "name": "Total Orders",
            "mart": "business_facts",
            "sql": (
                "SELECT 'total' AS dt, COUNT(*) AS val "
                "FROM fact_business"
            ),
            "default_chart": "number",
            "unit": "orders",
        },
        {
            "id": "orders_daily",
            "name": "Orders per Day",
            "mart": "business_facts", 
            "sql": (
                "SELECT "
                "CAST(entity_id AS TEXT) AS dt, "
                "COUNT(*) AS val "
                "FROM fact_business "
                "GROUP BY entity_id "
                "ORDER BY entity_id "
                "LIMIT 30"
            ),
            "default_chart": "line",
            "unit": "orders",
        },
        {
            "id": "orders_by_destination",
            "name": "Orders by Destination",
            "mart": "business_facts",
            "sql": (
                "SELECT DESTINATION AS dt, COUNT(*) AS val "
                "FROM fact_business "
                "GROUP BY DESTINATION "
                "ORDER BY val DESC "
                "LIMIT 20"
            ),
            "default_chart": "bar",
            "unit": "orders",
        },
        {
            "id": "orders_by_origin",
            "name": "Orders by Origin",
            "mart": "business_facts",
            "sql": (
                "SELECT ORIGIN AS dt, COUNT(*) AS val "
                "FROM fact_business "
                "GROUP BY ORIGIN "
                "ORDER BY val DESC"
            ),
            "default_chart": "bar", 
            "unit": "orders",
        },
        {
            "id": "cod_rate_by_receiver_mode",
            "name": "COD vs CC Distribution",
            "mart": "business_facts",
            "sql": (
                "SELECT RECEIVER_MODE AS dt, COUNT(*) AS val "
                "FROM fact_business "
                "GROUP BY RECEIVER_MODE "
                "ORDER BY val DESC"
            ),
            "default_chart": "pie",
            "unit": "orders",
        },
        {
            "id": "cod_rate_by_destination",
            "name": "COD Rate by Destination",
            "mart": "business_facts",
            "sql": (
                "SELECT DESTINATION AS dt, "
                "ROUND(AVG(CASE WHEN RECEIVER_MODE = 'COD' THEN 1.0 ELSE 0.0 END), 3) AS val "
                "FROM fact_business "
                "GROUP BY DESTINATION "
                "HAVING COUNT(*) >= 5 "
                "ORDER BY val DESC "
                "LIMIT 20"
            ),
            "default_chart": "bar",
            "unit": "ratio",
        },
        {
            "id": "avg_cod_amount_destination",
            "name": "Average COD Amount by Destination",
            "mart": "business_facts",
            "sql": (
                "SELECT DESTINATION AS dt, ROUND(AVG(COD_AMOUNT), 2) AS val "
                "FROM fact_business "
                "WHERE RECEIVER_MODE = 'COD' AND COD_AMOUNT > 0 "
                "GROUP BY DESTINATION "
                "HAVING COUNT(*) >= 3 "
                "ORDER BY val DESC "
                "LIMIT 15"
            ),
            "default_chart": "bar",
            "unit": currency,
        },
        {
            "id": "transaction_volume_by_region",
            "name": "Transaction Volume by Region",
            "mart": "business_facts",
            "sql": (
                "SELECT LEFT(DESTINATION, 5) AS dt, COUNT(*) AS val "
                "FROM fact_business "
                "GROUP BY LEFT(DESTINATION, 5) "
                "HAVING COUNT(*) >= 10 "
                "ORDER BY val DESC "
                "LIMIT 15"
            ),
            "default_chart": "bar",
            "unit": "orders",
        },
        {
            "id": "decision_distribution",
            "name": "Decision Distribution",
            "mart": "decision_facts",
            "sql": (
                "SELECT decision AS dt, COUNT(*) AS val "
                "FROM fact_decisions "
                "GROUP BY 1 "
                "ORDER BY val DESC"
            ),
            "default_chart": "bar",
        },
        {
            "id": "segment_effects",
            "name": "Segment Effects",
            "mart": "segment_insights",
            "sql": (
                "SELECT segment_key AS dt, COALESCE(effect_size, 0) AS val "
                "FROM segment_insights "
                "ORDER BY ABS(val) DESC"
            ),
            "default_chart": "bar",
            "cap": 50,
        },
        {
            "id": "summary_highlights",
            "name": "Summary KPI Highlights",
            "mart": "summary_metrics",
            "sql": (
                "SELECT metric AS dt, value AS val "
                "FROM summary_metrics "
                "WHERE category = 'kpi_recalc' "
                "ORDER BY dt"
            ),
            "default_chart": "bar",
        },
        # KPI Metrics
        {
            "id": "sla_pct",
            "name": "SLA Performance",
            "mart": "business_facts",
            "sql": "SELECT 'total' AS dt, AVG(kpi_sla_pct) AS val FROM fact_business WHERE kpi_sla_pct IS NOT NULL",
            "default_chart": "number",
            "unit": "percentage",
        },
        {
            "id": "rto_pct",
            "name": "RTO Rate",
            "mart": "business_facts", 
            "sql": "SELECT 'total' AS dt, AVG(kpi_rto_pct) AS val FROM fact_business WHERE kpi_rto_pct IS NOT NULL",
            "default_chart": "number",
            "unit": "percentage",
        },
        {
            "id": "lead_time_p50_hours",
            "name": "Lead Time P50",
            "mart": "business_facts",
            "sql": "SELECT 'total' AS dt, AVG(kpi_lead_time_p50) AS val FROM fact_business WHERE kpi_lead_time_p50 IS NOT NULL",
            "default_chart": "number", 
            "unit": "hours",
        },
        {
            "id": "lead_time_p90_hours",
            "name": "Lead Time P90",
            "mart": "business_facts",
            "sql": "SELECT 'total' AS dt, AVG(kpi_lead_time_p90) AS val FROM fact_business WHERE kpi_lead_time_p90 IS NOT NULL",
            "default_chart": "number",
            "unit": "hours",
        },
        {
            "id": "cod_rate",
            "name": "COD Rate",
            "mart": "business_facts",
            "sql": "SELECT 'total' AS dt, AVG(kpi_cod_rate) AS val FROM fact_business WHERE kpi_cod_rate IS NOT NULL",
            "default_chart": "number",
            "unit": "percentage",
        },
        {
            "id": "cod_total",
            "name": "Total COD Amount",
            "mart": "business_facts",
            "sql": "SELECT 'total' AS dt, SUM(kpi_cod_total) AS val FROM fact_business WHERE kpi_cod_total IS NOT NULL",
            "default_chart": "number",
            "unit": currency,
        },
    ]

    dimensions = [
        {"id": "destination", "name": "Destination", "column": "DESTINATION", "type": "string", "mart": "business_facts"},
        {"id": "receiver_mode", "name": "Receiver Mode", "column": "RECEIVER_MODE", "type": "string", "mart": "business_facts"},
        {"id": "decision", "name": "Decision", "column": "decision", "type": "string", "mart": "decision_facts"},
    ]

    return {
        "timezone": timezone,
        "currency": currency,
        "marts": marts,
        "dimensions": dimensions,
        "metrics": metrics,
    }


def run(run_id: str, inputs: Optional[Mapping[str, Any]], config: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    cfg = dict(config or {})
    overrides = dict(inputs or {})
    artifacts_root = Path(cfg.get("artifacts_root") or "artifacts").expanduser().resolve()
    kpi_cfg_path = Path(
        overrides.get("kpi_cfg")
        or cfg.get("kpi_cfg")
        or PROJECT_ROOT / "configs" / "kpi" / "kpi_catalog.yaml"
    ).resolve()
    column_policy_map = _load_column_policy_map(kpi_cfg_path)

    stage09_dir = artifacts_root / run_id / "stage_09_business_validation"
    stage08_dir = artifacts_root / run_id / "stage_08_insights"
    stage10_dir = artifacts_root / run_id / "stage_10_bi"
    marts_dir = stage10_dir / MARTS_DIRNAME
    semantic_dir = stage10_dir / SEMANTIC_DIRNAME
    insights_dir = stage10_dir / INSIGHTS_DIRNAME
    datasets_dir = stage10_dir / DATASETS_DIRNAME

    if not stage09_dir.exists():
        raise FileNotFoundError(f"Stage 09 outputs not found: {stage09_dir}")

    # Reset stage 10 directory for idempotent runs
    if stage10_dir.exists():
        shutil.rmtree(stage10_dir)
    _ensure_dir(marts_dir)
    _ensure_dir(semantic_dir)
    _ensure_dir(insights_dir)
    _ensure_dir(datasets_dir)

    created_marts: List[Dict[str, Any]] = []

    for subdir, source_name, target_name in MART_SOURCES:
        src = artifacts_root / run_id / subdir / source_name
        dest = marts_dir / target_name
        if _copy_parquet(src, dest):
            created_marts.append({"id": target_name, "source": source_name, "origin_stage": subdir})

    # Copy tiles if present
    tiles_dir = stage09_dir / TILE_DIR
    if tiles_dir.exists():
        for tile_path in tiles_dir.glob("*.parquet"):
            target_name = tile_path.name
            dest = marts_dir / target_name
            if _copy_parquet(tile_path, dest):
                created_marts.append({"id": target_name, "source": tile_path.name, "origin_stage": TILE_DIR})

    causal_fact = include_causal_advisory(run_id, artifacts_root, marts_dir)
    if causal_fact:
        created_marts.append({"id": causal_fact.name, "source": "causal_insights.json", "origin_stage": "stage_09_5_causal"})

    # Convert Stage 07 datetime correlations into a mart if available
    stage07_corr_dir = artifacts_root / run_id / "stage_07_correlations"
    stage07_business_dir = artifacts_root / run_id / "stage_07_7_business_correlations"
    datetime_corr_json = stage07_corr_dir / "correlations_datetime.json"
    if datetime_corr_json.exists():
        datetime_rows = _datetime_corr_rows(_load_json(datetime_corr_json))
        datetime_df = pl.DataFrame(datetime_rows) if datetime_rows else _empty_frame(DATETIME_CORR_SCHEMA)
        if not datetime_df.is_empty():
            datetime_df = datetime_df.select(list(DATETIME_CORR_SCHEMA.keys()))
        else:
            datetime_df = datetime_df.select(list(DATETIME_CORR_SCHEMA.keys())) if datetime_df.columns else _empty_frame(DATETIME_CORR_SCHEMA)
        datetime_dest = marts_dir / "datetime_correlations.parquet"
        _write_parquet(datetime_df, datetime_dest)
        created_marts.append({"id": "datetime_correlations.parquet", "source": "correlations_datetime.json", "origin_stage": "stage_07_correlations"})

    business_table = stage07_business_dir / "business_correlations.parquet"
    if _copy_parquet(business_table, marts_dir / "business_correlations.parquet"):
        created_marts.append({"id": "business_correlations.parquet", "source": business_table.name, "origin_stage": "stage_07_7_business_correlations"})

    # Convert Stage 08 insights to mart tables
    candidates_json = stage08_dir / "insights_candidates.json"
    candidates_rows = _candidate_rows(_load_json(candidates_json))
    candidates_df = pl.DataFrame(candidates_rows) if candidates_rows else _empty_frame(CANDIDATE_SCHEMA)
    # Ensure schema when rows exist
    if not candidates_df.is_empty():
        candidates_df = candidates_df.select(list(CANDIDATE_SCHEMA.keys()))
    else:
        candidates_df = candidates_df.select(list(CANDIDATE_SCHEMA.keys())) if candidates_df.columns else _empty_frame(CANDIDATE_SCHEMA)
    candidates_path = marts_dir / "insights_candidates.parquet"
    _write_parquet(candidates_df, candidates_path)
    created_marts.append({"id": "insights_candidates.parquet", "source": "insights_candidates.json", "origin_stage": "stage_08_insights"})

    insights_json = stage08_dir / "insights_report.json"
    insights_payload = _load_json(insights_json)
    official_rows = _official_rows(insights_payload)
    official_df = pl.DataFrame(official_rows) if official_rows else _empty_frame(INSIGHT_SCHEMA)
    if not official_df.is_empty():
        official_df = official_df.select(list(INSIGHT_SCHEMA.keys()))
    else:
        official_df = official_df.select(list(INSIGHT_SCHEMA.keys())) if official_df.columns else _empty_frame(INSIGHT_SCHEMA)
    official_path = marts_dir / "insights_official.parquet"
    _write_parquet(official_df, official_path)
    created_marts.append({"id": "insights_official.parquet", "source": "insights_report.json", "origin_stage": "stage_08_insights"})

    # Build summary metrics parquet
    validation_report = _load_json(stage09_dir / "validation_report.json")
    stage08_gate_payload = _load_json(stage08_dir / "gate.json")
    stage09_gate_payload = _load_json(stage09_dir / "gate.json")
    perf_metrics = _load_json(stage09_dir / "metrics.json")
    summary_rows = _collect_summary_rows(
        validation_report,
        perf_metrics,
        insights_payload.get("summary") if isinstance(insights_payload, Mapping) else {},
    )
    upstream_gates = (stage08_gate_payload or {}).get("upstream_gates") if isinstance(stage08_gate_payload, Mapping) else {}
    stage05_gate = upstream_gates.get("stage05") if isinstance(upstream_gates, Mapping) else {}
    stage07_gate = upstream_gates.get("stage07") if isinstance(upstream_gates, Mapping) else {}
    stage05_data_status = stage05_gate.get("data_gate_status") if isinstance(stage05_gate, Mapping) else None
    stage07_data_status = stage07_gate.get("data_gate_status") if isinstance(stage07_gate, Mapping) else None
    stage08_data_status = (
        stage08_gate_payload.get("data_gate_status")
        if isinstance(stage08_gate_payload, Mapping)
        else None
    )
    if stage08_data_status is None and isinstance(stage08_gate_payload, Mapping):
        stage08_data_status = stage08_gate_payload.get("status")
    stage09_data_status = None
    if isinstance(stage09_gate_payload, Mapping):
        stage09_data_status = stage09_gate_payload.get("data_gate_status") or stage09_gate_payload.get("status")
    if stage09_data_status is None:
        gate_block = validation_report.get("gate") if isinstance(validation_report, Mapping) else {}
        if isinstance(gate_block, Mapping):
            stage09_data_status = gate_block.get("data_gate_status") or gate_block.get("status")
    business_alerts = validation_report.get("business_alerts") if isinstance(validation_report, Mapping) else None
    if not isinstance(business_alerts, Mapping):
        business_alerts = stage09_gate_payload.get("business_alerts") if isinstance(stage09_gate_payload, Mapping) else {}
    business_gate_status = (
        stage09_gate_payload.get("business_gate_status")
        if isinstance(stage09_gate_payload, Mapping)
        else business_alerts.get("status") if isinstance(business_alerts, Mapping) else None
    )
    if business_gate_status is None and isinstance(business_alerts, Mapping):
        business_gate_status = business_alerts.get("status")
    if business_gate_status is None:
        business_gate_status = "OK"
    sla_alert_level = business_alerts.get("sla_alert_level") if isinstance(business_alerts, Mapping) else None
    rto_alert_level = business_alerts.get("rto_alert_level") if isinstance(business_alerts, Mapping) else None
    cod_alert_level = business_alerts.get("cod_alert_level") if isinstance(business_alerts, Mapping) else None
    data_gate_summary = {
        "stage05": stage05_data_status,
        "stage07": stage07_data_status,
        "stage08": stage08_data_status,
        "stage09": stage09_data_status,
    }
    business_gate_summary = {
        "overall": business_gate_status,
        "sla_alert_level": sla_alert_level or "OK",
        "rto_alert_level": rto_alert_level or "OK",
        "cod_alert_level": cod_alert_level or "OK",
        "notes": business_alerts.get("notes") if isinstance(business_alerts, Mapping) else None,
    }
    summary_rows.extend(
        [
            {
                "metric": "data_gate_overall",
                "category": "governance",
                "value": _status_score(stage09_data_status),
                "unit": (stage09_data_status or "")[:16],
                "source": "phase09",
            },
            {
                "metric": "business_gate_overall",
                "category": "governance",
                "value": _status_score(business_gate_status),
                "unit": (business_gate_status or "")[:16],
                "source": "phase09",
            },
            {
                "metric": "sla_alert_level",
                "category": "governance",
                "value": _status_score(business_gate_summary["sla_alert_level"]),
                "unit": business_gate_summary["sla_alert_level"],
                "source": "phase09",
            },
            {
                "metric": "rto_alert_level",
                "category": "governance",
                "value": _status_score(business_gate_summary["rto_alert_level"]),
                "unit": business_gate_summary["rto_alert_level"],
                "source": "phase09",
            },
            {
                "metric": "cod_alert_level",
                "category": "governance",
                "value": _status_score(business_gate_summary["cod_alert_level"]),
                "unit": business_gate_summary["cod_alert_level"],
                "source": "phase09",
            },
        ]
    )
    summary_df = pl.DataFrame(summary_rows) if summary_rows else _empty_frame(SUMMARY_SCHEMA)
    if not summary_df.is_empty():
        summary_df = summary_df.select(list(SUMMARY_SCHEMA.keys()))
    else:
        summary_df = summary_df.select(list(SUMMARY_SCHEMA.keys())) if summary_df.columns else _empty_frame(SUMMARY_SCHEMA)
    summary_path = marts_dir / "summary_metrics.parquet"
    _write_parquet(summary_df, summary_path)
    created_marts.append({"id": "summary_metrics.parquet", "source": "validation_report.json", "origin_stage": "stage_09_business_validation"})
    summary_text_parts = [
        f"Stage 09 data gate: {stage09_data_status or 'UNKNOWN'}.",
        f"Upstream data gates (05→07→08): {stage05_data_status or 'UNKNOWN'} → {stage07_data_status or 'UNKNOWN'} → {stage08_data_status or 'UNKNOWN'}.",
        f"Business gate: {business_gate_status} (SLA {business_gate_summary['sla_alert_level']}, RTO {business_gate_summary['rto_alert_level']}, COD {business_gate_summary['cod_alert_level']}).",
    ]
    if business_gate_summary.get("notes"):
        summary_text_parts.append(str(business_gate_summary["notes"]))
    business_state_payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(),
        "data_gate": data_gate_summary,
        "business_gate": business_gate_summary,
        "summary": " ".join(summary_text_parts),
    }
    business_state_path = stage10_dir / "business_state.json"
    business_state_path.write_text(json.dumps(business_state_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(),
        "data_gate_overall": stage09_data_status,
        "business_gate_overall": business_gate_status,
        "sla_alert_level": business_gate_summary["sla_alert_level"],
        "rto_alert_level": business_gate_summary["rto_alert_level"],
        "cod_alert_level": business_gate_summary["cod_alert_level"],
    }
    meta_path = stage10_dir / "meta.json"
    meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Determine timezone/currency
    timezone = (
        validation_report.get("provenance", {}).get("timezone")
        or insights_payload.get("timezone")
        or DEFAULT_TIMEZONE
    )
    currency = (
        validation_report.get("unit_currency_meta", {}).get("currency")
        or validation_report.get("provenance", {}).get("currency")
        or DEFAULT_CURRENCY
    )

    # Build semantic payload
    semantic_marts: List[Dict[str, Any]] = []
    mart_views = set()
    for entry in created_marts:
        file_name = entry["id"]
        view_name = Path(file_name).stem
        if file_name.endswith(".parquet"):
            semantic_marts.append({"id": view_name if view_name not in mart_views else file_name, "files": [file_name]})
            mart_views.add(view_name)

    semantic_payload = _build_semantic_payload(timezone, currency, semantic_marts)
    metrics_yaml_path = semantic_dir / "metrics.yaml"
    metrics_yaml_path.write_text(yaml.safe_dump(semantic_payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    orders_dataset, suppressed_export_columns = _normalised_orders_dataset(marts_dir, column_policy_map)
    filtered_orders_schema = _filtered_orders_schema(column_policy_map)
    if orders_dataset is None or orders_dataset.is_empty():
        orders_dataset = (
            _empty_frame(filtered_orders_schema) if filtered_orders_schema else pl.DataFrame()
        )
    else:
        allowed_columns = list(filtered_orders_schema.keys())
        if allowed_columns:
            orders_dataset = orders_dataset.select([col for col in orders_dataset.columns if col in allowed_columns])
    dataset_path = datasets_dir / ORDERS_DATASET_FILENAME
    _write_parquet(orders_dataset, dataset_path)

    dimensions_payload = _build_dimensions_payload(orders_dataset)
    dimensions_path = semantic_dir / DIMENSIONS_FILENAME
    dimensions_path.write_text(json.dumps(dimensions_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    data_health_payload = _load_json(stage09_dir / "data_health.json")
    ops_actions_payload = _load_json(stage09_dir / "ops_actions.json")
    text_ops_context = data_health_payload.get("text_ops") if isinstance(data_health_payload, Mapping) else None
    ops_highlights: List[Dict[str, Any]] = []
    if isinstance(ops_actions_payload, list):
        ops_highlights = [item for item in ops_actions_payload[:5] if isinstance(item, Mapping)]
    insights_extra_context = {
        "text_ops": text_ops_context,
        "ops_alerts": ops_highlights,
        "data_health_path": (stage09_dir / "data_health.json").as_posix(),
    }

    insights_output = _build_insights_payload(
        insights_payload,
        metrics_catalog=_relative_path(metrics_yaml_path, stage10_dir),
        dimensions_catalog=_relative_path(dimensions_path, stage10_dir),
        sources={
            "stage08": stage08_dir.as_posix() if stage08_dir.exists() else None,
            "stage09": stage09_dir.as_posix() if stage09_dir.exists() else None,
            "stage10": stage10_dir.as_posix(),
        },
        extra_context=insights_extra_context,
    )
    insights_path = insights_dir / INSIGHTS_FILENAME
    insights_path.write_text(json.dumps(insights_output, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "run_id": run_id,
        "status": "READY",
        "outputs": {
            "root": stage10_dir.as_posix(),
            "marts_dir": marts_dir.as_posix(),
            "semantic_path": metrics_yaml_path.as_posix(),
            "dimensions_path": dimensions_path.as_posix(),
            "insights_path": insights_path.as_posix(),
            "dataset_path": dataset_path.as_posix(),
            "meta_path": meta_path.as_posix(),
            "business_state": business_state_path.as_posix(),
        },
        "metrics": {
            "marts_created": len(created_marts),
            "semantic_metrics": len(semantic_payload.get("metrics", [])),
            "orders_rows": int(orders_dataset.height),
        },
        "context": {
            "timezone": timezone,
            "currency": currency,
            "marts": created_marts,
            "orders_dataset": dataset_path.as_posix(),
            "column_policy": {
                "config": kpi_cfg_path.as_posix(),
                "suppressed_exports": suppressed_export_columns,
            },
            "gate": {
                "data": data_gate_summary,
                "business": business_gate_summary,
            },
        },
    }


__all__ = ["run", "include_causal_advisory"]
