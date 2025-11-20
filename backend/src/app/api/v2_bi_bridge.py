from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import duckdb
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["bi_v2_bridge"])

ARTIFACTS_ROOT_DEFAULT = Path("artifacts")
FACT_REL_PATH = Path("stage_10_bi/marts/fact_business.parquet")
INSIGHTS_REL_PATH = Path("stage_08_insights/story_ops.json")
INSIGHTS_REPORT_PATH = Path("stage_08_insights/insights_report.json")
_SAFE_COLUMN_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
TABLE_FILTER_MAP: Mapping[str, str] = {
    "city": "locale",
    "carrier": "CARRIER",
}
DATE_COLUMN = "ts"
CITY_DIMENSION = "locale"
CARRIER_DIMENSION = "CARRIER"
KPI_METRIC_EXPRESSIONS: Mapping[str, str] = {
    "rto_rate": "kpi_rto_pct",
    "cod_delay_pct": "kpi_cod_rate",
    "sla_breach_pct": "CAST(sla_breached_contract AS DOUBLE)",
}
DEFAULT_METRIC = "kpi_rto_pct"


class TableColumn(BaseModel):
    field: str
    type: str = Field(description="Primitive data type hint (string|number|boolean)")


class TableResponse(BaseModel):
    columns: List[TableColumn] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)


class HeatmapResponse(BaseModel):
    x_labels: List[str] = Field(default_factory=list)
    y_labels: List[str] = Field(default_factory=list)
    data: List[List[float]] = Field(default_factory=list)


class InsightItem(BaseModel):
    id: str
    title: str
    insight_text: str
    severity: str = Field(description="critical|warning|info")
    deep_dive_filters: Dict[str, Any] = Field(default_factory=dict)
    demotion_note: Optional[str] = None


class InsightsResponse(BaseModel):
    items: List[InsightItem] = Field(default_factory=list)


def _resolve_artifacts_root(artifacts_root: Optional[str] = None) -> Path:
    if artifacts_root:
        return Path(artifacts_root).expanduser().resolve()
    return ARTIFACTS_ROOT_DEFAULT.expanduser().resolve()


def _resolve_fact_path(run_id: str, artifacts_root: Optional[str]) -> Path:
    base = _resolve_artifacts_root(artifacts_root)
    return base / run_id / FACT_REL_PATH


def _resolve_insights_path(run_id: str, artifacts_root: Optional[str]) -> Path:
    base = _resolve_artifacts_root(artifacts_root)
    return base / run_id / INSIGHTS_REL_PATH


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _infer_type(values: Iterable[Any]) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float, Decimal)):
            return "number"
        return "string"
    return "string"


def _duckdb_select(sql: str, params: Sequence[Any]) -> tuple[list[str], list[tuple[Any, ...]]]:
    logger.debug("Executing DuckDB SQL: %s | params=%s", sql, params)
    try:
        with duckdb.connect(database=":memory:") as con:
            cur = con.execute(sql, params)
            rows = cur.fetchall()
            columns = [col[0] for col in (cur.description or [])]
            return columns, rows
    except duckdb.Error as exc:  # pragma: no cover - defensive logging
        logger.exception("DuckDB query failed: %s", exc)
        raise HTTPException(status_code=400, detail=f"DuckDB query failed: {exc}") from exc


@router.get("/bi/table", response_model=TableResponse)
def get_bi_table(
    run_id: str = Query(..., description="Pipeline run identifier"),
    city: Optional[str] = Query(default=None),
    carrier: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None, description="ISO date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(default=None, description="ISO date (YYYY-MM-DD) inclusive"),
    limit: int = Query(default=1000, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    artifacts_root: Optional[str] = Query(default=None, description="Override artifacts root (for testing)"),
) -> TableResponse:
    fact_path = _resolve_fact_path(run_id, artifacts_root)
    if not fact_path.exists():
        logger.warning("fact_business parquet missing for run %s (%s)", run_id, fact_path)
        return TableResponse()

    base_sql = "SELECT * FROM read_parquet(?)"
    params: List[Any] = [fact_path.as_posix()]
    filters: List[str] = []

    if city:
        column = TABLE_FILTER_MAP.get("city", "city")
        filters.append(f"{column} = ?")
        params.append(city)
    if carrier:
        column = TABLE_FILTER_MAP.get("carrier", "carrier")
        filters.append(f"{column} = ?")
        params.append(carrier)
    if date_from:
        parsed = _parse_date(date_from)
        if parsed:
            filters.append(f"{DATE_COLUMN} >= ?")
            params.append(parsed.isoformat())
    if date_to:
        parsed = _parse_date(date_to)
        if parsed:
            next_day = parsed + timedelta(days=1)
            filters.append(f"{DATE_COLUMN} < ?")
            params.append(next_day.isoformat())

    if filters:
        base_sql += " WHERE " + " AND ".join(filters)

    base_sql += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    columns, raw_rows = _duckdb_select(base_sql, params)
    row_dicts: List[Dict[str, Any]] = [
        {column: _normalize_value(value) for column, value in zip(columns, row)} for row in raw_rows
    ]
    column_meta = [
        TableColumn(field=column, type=_infer_type(row.get(column) for row in row_dicts)) for column in columns
    ]
    return TableResponse(columns=column_meta, rows=row_dicts)


def _sanitize_metric(metric: str) -> str:
    if not metric:
        return DEFAULT_METRIC
    if metric.lower() in KPI_METRIC_EXPRESSIONS:
        return KPI_METRIC_EXPRESSIONS[metric.lower()]
    if not _SAFE_COLUMN_PATTERN.match(metric):
        raise HTTPException(status_code=400, detail="Invalid KPI parameter")
    return metric


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@router.get("/bi/heatmap", response_model=HeatmapResponse)
def get_heatmap(
    run_id: str = Query(...),
    kpi: str = Query(default="rto_rate"),
    artifacts_root: Optional[str] = Query(default=None),
) -> HeatmapResponse:
    fact_path = _resolve_fact_path(run_id, artifacts_root)
    if not fact_path.exists():
        logger.warning("Heatmap source missing for run %s (%s)", run_id, fact_path)
        return HeatmapResponse()

    metric_expr = _sanitize_metric(kpi)
    inner_sql = f"""
        SELECT
            COALESCE({CITY_DIMENSION}, 'Unknown') AS __city,
            COALESCE({CARRIER_DIMENSION}, 'Unknown') AS __carrier,
            {metric_expr} AS __metric
        FROM read_parquet(?)
    """
    sql = f"""
        SELECT __city AS city, __carrier AS carrier, AVG(__metric) AS value
        FROM ({inner_sql})
        WHERE __metric IS NOT NULL
        GROUP BY __city, __carrier
    """
    columns, rows = _duckdb_select(sql, [fact_path.as_posix()])
    idx_city = columns.index("city") if "city" in columns else 0
    idx_carrier = columns.index("carrier") if "carrier" in columns else 1
    idx_value = columns.index("value") if "value" in columns else -1

    entries = [
        (
            _normalize_value(row[idx_city]),
            _normalize_value(row[idx_carrier]),
            float(row[idx_value]) if row[idx_value] is not None else None,
        )
        for row in rows
    ]
    cities = sorted({c for c, _, v in entries if c is not None and v is not None})
    carriers = sorted({c for _, c, v in entries if c is not None and v is not None})

    city_index = {value: idx for idx, value in enumerate(cities)}
    carrier_index = {value: idx for idx, value in enumerate(carriers)}

    matrix_data: List[List[float]] = []
    for city, carrier, value in entries:
        if city is None or carrier is None or value is None:
            continue
        matrix_data.append([city_index[city], carrier_index[carrier], value])

    return HeatmapResponse(x_labels=cities, y_labels=carriers, data=matrix_data)


def _map_priority(priority: Optional[str]) -> str:
    if not priority:
        return "info"
    normalized = priority.strip().lower()
    if normalized in {"critical", "severe", "high"}:
        return "critical"
    if normalized in {"medium", "moderate", "warn", "warning"}:
        return "warning"
    return "info"


@router.get("/ml/insights/feed", response_model=List[InsightItem])
def get_insights_feed(
    run_id: str = Query(...),
    artifacts_root: Optional[str] = Query(default=None),
) -> List[InsightItem]:
    insights_path = _resolve_insights_path(run_id, artifacts_root)
    if not insights_path.exists():
        logger.warning("Insights payload missing for run %s (%s)", run_id, insights_path)
        return []

    try:
        raw = json.loads(insights_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse story_ops.json (%s): %s", insights_path, exc)
        raise HTTPException(status_code=500, detail="Unable to parse insights feed") from exc

    items = raw.get("items") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []

    demotion_note = _load_demotion_note(insights_path.parent)

    response: List[InsightItem] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        insight_text_raw = item.get("what_we_see") or item.get("insight_text") or ""
        if isinstance(insight_text_raw, dict):
            insight_text = json.dumps(insight_text_raw, ensure_ascii=False)
        else:
            insight_text = str(insight_text_raw)
        response.append(
            InsightItem(
                id=str(item.get("id") or f"{run_id}-{idx}"),
                title=item.get("title") or "Untitled Insight",
                insight_text=insight_text,
                severity=_map_priority(item.get("priority")),
                deep_dive_filters=item.get("deep_dive_filters") or {
                    "where": item.get("where"),
                    "window": item.get("window"),
                },
                demotion_note=demotion_note,
            )
        )
    return response


def _load_demotion_note(insights_dir: Path) -> Optional[str]:
    report_path = insights_dir / "insights_report.json"
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    nzv = payload.get("nzv_impact")
    if isinstance(nzv, Mapping):
        note = nzv.get("demotion_note")
        if isinstance(note, str):
            return note
    return None
