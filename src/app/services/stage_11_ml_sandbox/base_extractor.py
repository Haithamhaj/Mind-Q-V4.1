from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import polars as pl  # type: ignore

BASE_FILENAME = "ml_base_orders.parquet"


@dataclass(frozen=True)
class _ColumnSpec:
    source: str
    alias: str
    dtype: pl.DataType | None = None


STRING_SPECS: Tuple[_ColumnSpec, ...] = (
    _ColumnSpec("entity_id", "shipment_id", pl.Utf8),
    _ColumnSpec("Account_NO", "client_id", pl.Utf8),
    _ColumnSpec("FORWARD_COMPANY", "carrier_id", pl.Utf8),
    _ColumnSpec("ORIGIN", "origin_city", pl.Utf8),
    _ColumnSpec("DESTINATION", "city", pl.Utf8),
    _ColumnSpec("DESTINATION_HUB", "zone", pl.Utf8),
    _ColumnSpec("AREA_STREET", "area_street", pl.Utf8),
    _ColumnSpec("SENDER_NAME", "sender_name", pl.Utf8),
    _ColumnSpec("RECEIVER_NAME", "receiver_name", pl.Utf8),
    _ColumnSpec("STATUS", "status", pl.Utf8),
    _ColumnSpec("3PLSTATUS", "carrier_status", pl.Utf8),
    _ColumnSpec("3PL_Last_Status", "carrier_last_status", pl.Utf8),
    _ColumnSpec("RECEIVER_MODE", "payment_method", pl.Utf8),
    _ColumnSpec("row_deeplink", "row_deeplink", pl.Utf8),
)

NUMERIC_SPECS: Tuple[_ColumnSpec, ...] = (
    _ColumnSpec("COD_AMOUNT", "cod_amount", pl.Float64),
    _ColumnSpec("ON_WEIGHT", "weight_kg", pl.Float64),
    _ColumnSpec("ON_PIECES", "pieces", pl.Float64),
    _ColumnSpec("D_ATTEMPT", "delivery_attempts", pl.Float64),
    _ColumnSpec("CALL_ATTEMPT", "call_attempts", pl.Float64),
    _ColumnSpec("kpi_sla_pct", "kpi_sla_pct", pl.Float64),
    _ColumnSpec("kpi_rto_pct", "kpi_rto_pct", pl.Float64),
    _ColumnSpec("kpi_cod_rate", "kpi_cod_rate", pl.Float64),
)

DATETIME_SPECS: Tuple[_ColumnSpec, ...] = (
    _ColumnSpec("ts_created", "created_at"),
    _ColumnSpec("ts_delivered", "delivered_at"),
    _ColumnSpec("SCHEDULE_DATE", "promised_date"),
)

BOOL_SPECS: Tuple[_ColumnSpec, ...] = (
    _ColumnSpec("on_time", "sla_met", pl.Boolean),
    _ColumnSpec("rto_flag", "is_rto", pl.Boolean),
    _ColumnSpec("is_cod", "is_cod", pl.Boolean),
)


def _resolve_run_dir(run_id: str, stage_dir: Path) -> Path:
    """Climb the tree until we find the run_id directory."""

    stage_dir = stage_dir.expanduser().resolve()
    for parent in (stage_dir, *stage_dir.parents):
        if parent.name == run_id:
            return parent
    raise FileNotFoundError(f"Unable to locate run directory for {run_id} using {stage_dir}")


def _fact_business_path(run_dir: Path) -> Path:
    return run_dir / "stage_10_bi" / "marts" / "fact_business.parquet"


def _col_expr(columns: Iterable[str], spec: _ColumnSpec) -> pl.Expr:
    if spec.source in columns:
        expr = pl.col(spec.source)
    else:
        expr = pl.lit(None)
    if spec.dtype is not None:
        expr = expr.cast(spec.dtype, strict=False)
    return expr.alias(spec.alias)


def _delivery_time_expr(columns: Iterable[str]) -> pl.Expr:
    lead_expr = None
    if "lead_time_hours" in columns:
        lead_expr = pl.col("lead_time_hours").cast(pl.Float64, strict=False)

    delta_expr = None
    if "ts_created" in columns and "ts_delivered" in columns:
        delta_expr = (
            (pl.col("ts_delivered") - pl.col("ts_created"))
            .dt.total_hours()
            .cast(pl.Float64, strict=False)
        )

    expr: pl.Expr | None = None
    if lead_expr is not None and delta_expr is not None:
        expr = pl.when(lead_expr.is_not_null()).then(lead_expr).otherwise(delta_expr)
    else:
        expr = lead_expr or delta_expr

    if expr is None:
        expr = pl.lit(None).cast(pl.Float64)
    return expr.alias("delivery_time_hours")


def _build_base_frame(fact_df: pl.DataFrame) -> pl.DataFrame:
    columns = set(fact_df.columns)
    expressions: List[pl.Expr] = []
    for spec in (*STRING_SPECS, *NUMERIC_SPECS, *DATETIME_SPECS, *BOOL_SPECS):
        expressions.append(_col_expr(columns, spec))
    expressions.append(_delivery_time_expr(columns))

    base = fact_df.select(expressions)
    base = base.with_columns(
        [
            (
                pl.col("client_id")
                .cast(pl.Utf8, strict=False)
                .str.strip_chars()
                .alias("client_id")
            ),
            pl.col("carrier_id").cast(pl.Utf8, strict=False),
            pl.col("city").cast(pl.Utf8, strict=False),
            pl.col("zone").cast(pl.Utf8, strict=False),
            pl.col("status").cast(pl.Utf8, strict=False),
            pl.col("payment_method").cast(pl.Utf8, strict=False),
            pl.col("delivery_time_hours").cast(pl.Float64, strict=False),
            pl.col("cod_amount").cast(pl.Float64, strict=False),
            pl.col("weight_kg").cast(pl.Float64, strict=False),
            pl.col("pieces").cast(pl.Float64, strict=False),
            pl.col("delivery_attempts").cast(pl.Float64, strict=False),
            pl.col("call_attempts").cast(pl.Float64, strict=False),
            pl.col("sla_met").cast(pl.Boolean, strict=False),
            pl.col("is_rto").cast(pl.Boolean, strict=False),
            pl.col("is_cod").cast(pl.Boolean, strict=False),
        ]
    )

    base = base.with_columns(
        [
            pl.when(
                pl.col("client_id").is_null() | (pl.col("client_id").str.len_chars() == 0)
            )
            .then(pl.lit("UNKNOWN"))
            .otherwise(pl.col("client_id"))
            .alias("client_id"),
            (
                pl.when(pl.col("sla_met").is_null())
                .then(pl.lit(None, dtype=pl.Boolean))
                .otherwise(pl.col("sla_met").not_())
                .alias("sla_breach")
            ),
            (pl.col("delivery_time_hours") / 24.0).alias("sla_days"),
        ]
    )

    if "shipment_id" in base.columns:
        base = base.unique(subset=["shipment_id"], keep="last")

    return base


def build_ml_base_table(run_id: str, output_dir: str) -> Dict[str, object]:
    """
    Build a normalized ML-ready base table for downstream sandbox stages.

    Parameters
    ----------
    run_id:
        Pipeline run identifier.
    output_dir:
        Destination directory for stage_11 artifacts (e.g. artifacts/{run}/stage_11_ml_sandbox).
    """

    stage_dir = Path(output_dir).expanduser().resolve()
    stage_dir.mkdir(parents=True, exist_ok=True)

    run_dir = _resolve_run_dir(run_id, stage_dir)
    fact_path = _fact_business_path(run_dir)
    if not fact_path.exists():
        raise FileNotFoundError(f"fact_business.parquet not found for run {run_id}: {fact_path}")

    fact_df = pl.read_parquet(fact_path.as_posix())
    base_df = _build_base_frame(fact_df)

    output_path = stage_dir / BASE_FILENAME
    base_df.write_parquet(output_path.as_posix())

    metadata: Dict[str, object] = {
        "run_id": run_id,
        "input_paths": [fact_path.as_posix()],
        "output_path": output_path.as_posix(),
        "row_count": base_df.height,
        "column_count": len(base_df.columns),
        "columns": base_df.columns,
    }
    return metadata
