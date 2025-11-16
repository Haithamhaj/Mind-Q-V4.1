from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import math
import numpy as np
import pandas as pd
import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Literal

from src.agents.llm_adapter import invoke_model
from src.app.services.sla_sop import build_gap_analysis as build_sop_gap_analysis
from src.app.services.sla_dashboard_builder import build_dashboard_payload
from shared.llm_prompts import compose_system_prompt
MODULE_PATH = Path(__file__).resolve()
BACKEND_ROOT = MODULE_PATH.parents[3]
PROJECT_ROOT = MODULE_PATH.parents[4]
BI_ROOT = PROJECT_ROOT / "bi"

try:  # Optional analytics dependencies
    from sklearn.cluster import KMeans  # type: ignore
    from sklearn.ensemble import IsolationForest  # type: ignore
    from sklearn.preprocessing import StandardScaler  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    KMeans = None
    IsolationForest = None
    StandardScaler = None

_ARTIFACT_ROOT_CANDIDATES = [
    PROJECT_ROOT / "artifacts",
    BACKEND_ROOT / "artifacts",
]

SOP_EXPECTATIONS_FILENAME = "sop_expectations.json"
SOP_RECOMMENDATIONS_FILENAME = "sop_recommendations.json"
FALLBACK_SOP_EXPECTATIONS_PATH = BI_ROOT / "semantic" / SOP_EXPECTATIONS_FILENAME
FALLBACK_SOP_RECOMMENDATIONS_PATH = BI_ROOT / "semantic" / SOP_RECOMMENDATIONS_FILENAME


def _existing_artifact_roots() -> List[Path]:
    roots: List[Path] = []
    for root in _ARTIFACT_ROOT_CANDIDATES:
        if root.exists():
            roots.append(root)
    return roots or _ARTIFACT_ROOT_CANDIDATES[:1]


def _iter_artifact_roots() -> Iterable[Path]:
    """Yield unique artifact roots, preferring the project-level path when available."""
    seen: set[str] = set()
    for root in _existing_artifact_roots():
        key = root.as_posix()
        if key in seen:
            continue
        seen.add(key)
        yield root

METRICS_PATH = BI_ROOT / "semantic" / "metrics.yml"
FALLBACK_DIMENSIONS_PATH = BI_ROOT / "semantic" / "dimensions.json"
FALLBACK_INSIGHTS_PATH = BI_ROOT / "insights" / "insights.json"
MAX_ROWS = 25_000
DEFAULT_RAW_LLM_PROVIDER = os.getenv("RAW_METRICS_LLM_PROVIDER", "openai")
DEFAULT_RAW_LLM_MODEL = os.getenv("RAW_METRICS_LLM_MODEL", "gpt-4o-mini")
DEFAULT_CORRELATION_LLM_PROVIDER = os.getenv("CORRELATION_LLM_PROVIDER", DEFAULT_RAW_LLM_PROVIDER)
DEFAULT_CORRELATION_LLM_MODEL = os.getenv("CORRELATION_LLM_MODEL", DEFAULT_RAW_LLM_MODEL)
DEFAULT_LAYER2_AGENT_PROVIDER = os.getenv("LAYER2_AGENT_PROVIDER", DEFAULT_RAW_LLM_PROVIDER)
DEFAULT_LAYER2_AGENT_MODEL = os.getenv("LAYER2_AGENT_MODEL", DEFAULT_RAW_LLM_MODEL)
CORRELATION_ENRICHED_KEYS = {
    "feature_a_label",
    "feature_b_label",
    "feature_a_domain",
    "feature_b_domain",
    "feature_a_sensitivity",
    "feature_b_sensitivity",
    "feature_a_description",
    "feature_b_description",
    "business_label",
    "impact_summary",
    "sensitivity",
    "kpi_tag",
    "kpi_label",
    "kpi_direction",
    "kpi_unit",
    "kpi_feature",
    "impact_driver_feature",
    "impact_driver_label",
    "effect_direction",
    "effect_is_positive",
    "expected_kpi_delta",
    "expected_kpi_delta_pct",
    "driver_domain",
    "is_persistent",
    "history_runs",
}

logger = logging.getLogger(__name__)
DELIVERED_REGEX = r"(?:delivered|success|completed|تم التسليم|تم التوصيل|وصل|successful)"
OUT_FOR_DELIVERY_REGEX = r"(?:out for delivery|outbound|forward|attempt|قيد التسليم|محاولة|شحنة خارجة)"
RETURNED_REGEX = r"(?:return|rto|refus|reject|مرتجع|راجع|معاد|استرجاع)"
WEEKDAY_LABELS = {
    0: "الاثنين",
    1: "الثلاثاء",
    2: "الأربعاء",
    3: "الخميس",
    4: "الجمعة",
    5: "السبت",
    6: "الأحد",
}

SLA_METRIC_INFO: Dict[str, Dict[str, Any]] = {
    "sla_pct": {
        "label": "On-Time Delivery Rate",
        "format": "percentage",
        "unit": "ratio",
        "keywords": ["sla", "on time", "التزام", "الالتزام", "نسبة الالتزام", "تسليم في الوقت", "نسبة sla"],
    },
    "rto_pct": {
        "label": "Return to Origin Rate",
        "format": "percentage",
        "unit": "ratio",
        "keywords": ["rto", "return", "ارجاع", "إرجاع", "مرتجع", "عودة", "ارتداد"],
    },
    "lead_time_p50": {
        "label": "Lead Time P50",
        "format": "duration_hours",
        "unit": "hours",
        "keywords": ["lead time", "p50", "median", "زمن التوصيل", "زمن التسليم", "متوسط الزمن"],
    },
    "lead_time_p90": {
        "label": "Lead Time P90",
        "format": "duration_hours",
        "unit": "hours",
        "keywords": ["lead time", "p90", "الوقت 90", "زمن التسليم الأعلى", "زمن التسليم الطويل"],
    },
    "cod_rate": {
        "label": "COD Share",
        "format": "percentage",
        "unit": "ratio",
        "keywords": ["cod", "cash on delivery", "دفع عند الاستلام", "نسبة cod", "حصة الدفع نقداً"],
    },
    "cod_total": {
        "label": "COD Collected",
        "format": "currency",
        "unit": "currency",
        "keywords": ["cod", "إجمالي", "تحصيل", "مبالغ نقدية", "cash on delivery", "قيمة التحصيل"],
    },
}

router = APIRouter(prefix="/api/bi", tags=["bi-mvp"])


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _sop_candidate_paths(run_path: Optional[Path], filename: str, fallback: Path) -> Iterable[Path]:
    if run_path:
        yield run_path / "stage_10_bi" / "semantic" / filename
    yield fallback


def _load_sop_json(
    run_path: Optional[Path],
    run_label: str,
    filename: str,
    fallback: Path,
    *,
    required: bool = True,
) -> Any:
    for path in _sop_candidate_paths(run_path, filename, fallback):
        try:
            return _load_json(path)
        except FileNotFoundError:
            continue
    if required:
        raise HTTPException(status_code=404, detail=f"SOP file '{filename}' not found for run {run_label}")
    return None


def _resolve_run(run: str) -> Optional[Path]:
    roots = list(_iter_artifact_roots())
    if run == "run-latest":
        candidates: List[Path] = []
        for root in roots:
            for path in root.iterdir():
                if not path.is_dir():
                    continue
                # Skip control folders such as "_global" or workspace caches
                if path.name.startswith("_"):
                    continue
                progress_file = path / "_status" / "pipeline_progress.json"
                if not progress_file.exists():
                    continue
                candidates.append(path)
        candidates.sort(key=lambda candidate: candidate.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None

    for root in roots:
        candidate = root / run
        if candidate.exists():
            return candidate
    return None


def _dimension_candidates(run_path: Optional[Path]) -> Iterable[Path]:
    if run_path:
        yield run_path / "stage_10_bi" / "semantic" / "dimensions.json"
    yield FALLBACK_DIMENSIONS_PATH


def _insight_candidates(run_path: Optional[Path]) -> Iterable[Path]:
    if run_path:
        yield run_path / "stage_10_bi" / "insights" / "insights.json"
    yield FALLBACK_INSIGHTS_PATH


def _metrics_candidates(run_path: Optional[Path]) -> Iterable[Path]:
    if run_path:
        stage10_semantic = run_path / "stage_10_bi" / "semantic"
        yield stage10_semantic / "metrics.yaml"
        yield stage10_semantic / "metrics.yml"
    yield METRICS_PATH


def _load_first_available(paths: Iterable[Path]) -> Any:
    for path in paths:
        try:
            return _load_json(path)
        except FileNotFoundError:
            continue
    raise HTTPException(status_code=404, detail="Artefact not found for requested resource.")


def _parse_threshold_expr(expr: str) -> Optional[Tuple[str, float]]:
    if not expr:
        return None
    match = re.match(r"(>=|<=|>|<|==)\s*(-?\d+(?:\.\d+)?)", expr.strip())
    if not match:
        return None
    op, value = match.groups()
    try:
        return op, float(value)
    except ValueError:
        return None


def _evaluate_threshold(value: float, expr: Optional[str]) -> bool:
    parsed = _parse_threshold_expr(expr or "")
    if not parsed:
        return False
    op, threshold = parsed
    if op == ">=":
        return value >= threshold
    if op == "<=":
        return value <= threshold
    if op == ">":
        return value > threshold
    if op == "<":
        return value < threshold
    if op == "==":
        return value == threshold
    return False


def _metric_status(value: Optional[float], warn_expr: Optional[str], stop_expr: Optional[str]) -> str:
    if value is None:
        return "unknown"
    if _evaluate_threshold(value, stop_expr):
        return "stop"
    if _evaluate_threshold(value, warn_expr):
        return "warn"
    return "pass"


def _build_sla_payload(run: str) -> Dict[str, Any]:
    run_path = _resolve_run(run)
    if not run_path:
        raise HTTPException(status_code=404, detail=f"Run '{run}' not found.")
    stage_dir = run_path / "stage_09_business_validation"
    if not stage_dir.exists():
        raise HTTPException(status_code=404, detail=f"Stage 09 outputs not found for run {run_path.name}.")

    try:
        validation = _load_json(stage_dir / "validation_report.json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"validation_report.json missing for run {run_path.name}") from exc

    sla_summary = _load_optional_json(stage_dir / "sla_summary.json") or {}
    targets = _load_optional_json(stage_dir / "targets.json") or {}

    manifest_path = run_path / "stage_01_ingestion" / "sla_manifest.json"
    manifest_payload = _load_optional_json(manifest_path) if manifest_path.exists() else None

    contracts_path = PROJECT_ROOT / "contracts" / "sla_processed" / run_path.name / "contracts.json"
    contracts_payload = _load_optional_json(contracts_path) if contracts_path.exists() else None

    stage_sources: Dict[str, str] = {
        "validation_report": (stage_dir / "validation_report.json").as_posix(),
        "sla_summary": (stage_dir / "sla_summary.json").as_posix(),
    }
    targets_path = stage_dir / "targets.json"
    if targets_path.exists():
        stage_sources["targets"] = targets_path.as_posix()
    if manifest_path.exists():
        stage_sources["manifest"] = manifest_path.as_posix()
    if contracts_path.parent.exists():
        if contracts_path.exists():
            stage_sources["contracts_index"] = contracts_path.as_posix()
        else:
            stage_sources["contracts_root"] = contracts_path.parent.as_posix()

    payload = build_dashboard_payload(
        run_id=run_path.name,
        validation=validation,
        sla_summary=sla_summary,
        targets=targets,
        manifest=manifest_payload,
        contracts_index=contracts_payload,
        stage_sources=stage_sources,
        metric_catalog=SLA_METRIC_INFO,
    )
    return payload


def _load_sop_payloads(run: str) -> Tuple[Mapping[str, Any], Optional[Mapping[str, Any]], Path]:
    run_path = _resolve_run(run)
    if not run_path:
        raise HTTPException(status_code=404, detail=f"Run '{run}' not found.")
    expectations = _load_sop_json(
        run_path,
        run_path.name,
        SOP_EXPECTATIONS_FILENAME,
        FALLBACK_SOP_EXPECTATIONS_PATH,
        required=False,
    )
    if not expectations:
        raise HTTPException(status_code=404, detail=f"SOP expectations not available for run '{run_path.name}'.")
    recommendations = _load_sop_json(
        run_path,
        run_path.name,
        SOP_RECOMMENDATIONS_FILENAME,
        FALLBACK_SOP_RECOMMENDATIONS_PATH,
        required=False,
    )
    return expectations, recommendations, run_path


def _normalise_metrics_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        metrics = payload.get("metrics")
        if metrics is None and isinstance(payload.get("items"), list):
            metrics = payload.get("items")
        metadata = {key: value for key, value in payload.items() if key not in {"metrics", "items"}}
        return {
            "metrics": metrics if isinstance(metrics, list) else [],
            "metadata": metadata,
        }
    if isinstance(payload, list):
        return {"metrics": payload, "metadata": {}}
    return {"metrics": [], "metadata": {"raw": payload}}


def _normalise_dimensions_payload(payload: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "generated_at": None,
        "row_count": None,
        "date": [],
        "numeric": [],
        "categorical": [],
        "bool": [],
        "metadata": {},
    }
    if not isinstance(payload, dict):
        base["metadata"] = {"raw": payload}
        return base

    if payload.get("generated_at"):
        base["generated_at"] = payload.get("generated_at")
    if payload.get("row_count") is not None:
        base["row_count"] = payload.get("row_count")

    if all(key in payload for key in ("date", "numeric", "categorical", "bool")):
        for key in ("date", "numeric", "categorical", "bool"):
            value = payload.get(key)
            if isinstance(value, list):
                base[key] = value
        extra = {
            key: value
            for key, value in payload.items()
            if key not in {"generated_at", "row_count", "date", "numeric", "categorical", "bool"}
        }
        base["metadata"] = extra
        return base

    dims = payload.get("dimensions")
    if isinstance(dims, list):
        for entry in dims:
            if not isinstance(entry, dict):
                continue
            dim_type = str(entry.get("type", "")).lower()
            record = {
                key: entry.get(key)
                for key in ("name", "dtype", "description", "values", "cardinality", "format")
                if entry.get(key) is not None
            }
            if dim_type in {"temporal", "date", "datetime", "time"}:
                base["date"].append(record)
            elif dim_type in {"boolean", "bool"}:
                base["bool"].append(record)
            elif dim_type in {"numeric", "measure", "number", "float", "integer"}:
                base["numeric"].append(record)
            else:
                base["categorical"].append(record)

    metadata: Dict[str, Any] = {
        key: value
        for key, value in payload.items()
        if key not in {"dimensions", "generated_at", "row_count", "metrics"}
    }
    if "metrics" in payload:
        metadata["metrics_catalog"] = payload["metrics"]
    base["metadata"] = metadata
    return base


@router.get("/metrics")
async def get_metrics(
    run: str = Query("run-latest"),
) -> Any:
    run_path = _resolve_run(run)
    for path in _metrics_candidates(run_path):
        try:
            payload = _load_yaml(path)
            return _normalise_metrics_payload(payload)
        except FileNotFoundError:
            continue
        except yaml.YAMLError as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=500, detail=f"Failed to parse metrics catalog at {path}: {exc}") from exc
    raise HTTPException(status_code=404, detail=f"Metrics catalog missing for run '{run}'")


@router.get("/kpi-catalog")
async def get_kpi_catalog(
    run: str = Query("run-latest"),
) -> Any:
    run_path = _resolve_run(run)
    if not run_path:
        raise HTTPException(status_code=404, detail=f"Run '{run}' not found.")
    catalog_json = run_path / "stage_09_business_validation" / "kpi_catalog.json"
    if catalog_json.exists():
        try:
            return json.loads(catalog_json.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("kpi_catalog_json_read_failed", exc_info=exc)
    catalog_yaml = PROJECT_ROOT / "configs" / "kpi" / "kpi_catalog.yaml"
    if catalog_yaml.exists():
        try:
            payload = yaml.safe_load(catalog_yaml.read_text(encoding="utf-8")) or {}
            return payload
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("kpi_catalog_yaml_read_failed", exc_info=exc)
    raise HTTPException(status_code=404, detail="KPI catalog not available.")


@router.get("/dimensions")
async def get_dimensions(run: str = Query("run-latest")) -> Any:
    run_path = _resolve_run(run)
    try:
        raw = _load_first_available(_dimension_candidates(run_path))
        return _normalise_dimensions_payload(raw)
    except HTTPException as exc:
        if run_path:
            # fallback to legacy BI root even if missing run artefact
            try:
                raw = _load_json(FALLBACK_DIMENSIONS_PATH)
                return _normalise_dimensions_payload(raw)
            except FileNotFoundError:
                pass
        raise exc


@router.get("/insights")
async def get_insights(run: str = Query("run-latest")) -> Any:
    run_path = _resolve_run(run)
    try:
        return _load_first_available(_insight_candidates(run_path))
    except HTTPException as exc:
        if run_path:
            try:
                return _load_json(FALLBACK_INSIGHTS_PATH)
            except FileNotFoundError:
                pass
        raise exc


def _collect_parquet_files(run_path: Optional[Path]) -> List[Path]:
    if not run_path:
        return []
    stage_dir = run_path / "stage_10_bi"
    if not stage_dir.exists():
        return []
    candidates = list(stage_dir.glob("**/*.parquet"))
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def _normalise_orders_frame(frame: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Bring various pipeline outputs to a unified orders schema."""
    aliases: List[Tuple[str, Sequence[str]]] = [
        ("order_id", ("order_id", "AWB_NO", "awb_no", "OrderNo", "ORDER_NO", "entity_id")),
        ("destination", ("destination", "DESTINATION", "Destination", "DESTINATION_HUB", "destination_city")),
        ("payment_method", ("payment_method", "payment method", "PAYMENT_METHOD", "RECEIVER MODE", "RECEIVER_MODE")),
        ("amount", ("amount", "AMOUNT", "total_amount", "TOTAL_AMOUNT", "Shipment_Value", "SHIPMENT_VALUE")),
        ("order_date", ("order_date", "ORDER_DATE", "ENTRY_DATE", "PICKUP_DATE", "CREATED_AT", "ts")),
        ("status", ("status", "STATUS", "Sub_Status", "SUB_STATUS")),
        ("cod_amount", ("cod_amount", "COD_AMOUNT", "cod", "COD")),
    ]

    frame = frame.copy()

    for target, options in aliases:
        if target in frame.columns:
            continue
        for alias in options:
            if alias in frame.columns:
                frame.rename(columns={alias: target}, inplace=True)
                break

    if "cod_amount" not in frame.columns and "amount" in frame.columns:
        frame["cod_amount"] = frame["amount"]
    if "amount" not in frame.columns and "cod_amount" in frame.columns:
        frame["amount"] = frame["cod_amount"]

    required = {"order_id", "destination", "payment_method", "amount", "order_date", "status", "cod_amount"}
    if not required.issubset(frame.columns):
        return None

    numeric_cols = {"amount", "cod_amount"}
    result = frame.copy()
    for column in required:
        if column in numeric_cols:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
        else:
            result[column] = result[column].astype(str).fillna("")
    return result


def _orders_frame_from_path(path: Path) -> Optional[pd.DataFrame]:
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return None
    return _normalise_orders_frame(frame)


def _load_orders_dataset(run: str) -> Optional[pd.DataFrame]:
    run_path = _resolve_run(run)
    candidates: List[Path] = []

    if run_path:
        candidates.append(run_path / "stage_06_feature_eng" / "layer1_dataset.parquet")
        stage10_root = run_path / "stage_10_bi"
        candidates.extend(
            [
                stage10_root / "datasets" / "orders.parquet",
                stage10_root / "marts" / "fact_business.parquet",
                stage10_root / "marts" / "bi_feed.parquet",
                run_path / "stage_09_business_validation" / "bi_feed.parquet",
                run_path / "stage_05_missing" / "clean_imputed.parquet",
                run_path / "stage_01_ingestion" / "raw.parquet",
            ]
        )

    if run != "run-latest":
        candidates.append(PROJECT_ROOT / "artifacts" / f"{run}.parquet")

    candidates.extend(
        [
            PROJECT_ROOT / "artifacts" / "p10.parquet",
            PROJECT_ROOT / "artifacts" / "run-latest" / "stage_10" / "orders.parquet",
        ]
    )

    for candidate in candidates:
        if not candidate.exists():
            continue
        frame = _orders_frame_from_path(candidate)
        if frame is not None and not frame.empty:
            return frame
    return None


def _load_raw_orders_dataset(run: str) -> Optional[pd.DataFrame]:
    run_path = _resolve_run(run)
    if not run_path:
        return None
    raw_path = run_path / "stage_01_ingestion" / "raw.parquet"
    frame = _orders_frame_from_path(raw_path)
    if frame is not None and not frame.empty:
        return frame
    return None


def _safe_load_json_list(path: Optional[Path]) -> List[Dict[str, Any]]:
    if not path or not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    return []


def _safe_load_parquet_rows(path: Optional[Path]) -> List[Dict[str, Any]]:
    if not path or not path.exists():
        return []
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return []
    if frame is None or frame.empty:
        return []
    return frame.to_dict(orient="records")


def _knime_data_candidates(run: str, run_path: Optional[Path]) -> List[Path]:
    candidates: List[Path] = []
    if run_path:
        knime_root = run_path / "phase_07_knime"
        for base in _knime_output_roots(knime_root):
            candidates.append(base / "data.parquet")
        candidates.append(run_path / "stage_07_knime_bridge" / "data.parquet")
    # Fallbacks in case the run directory cannot be resolved but common locations exist.
    for root in _iter_artifact_roots():
        base = root / run / "phase_07_knime"
        for candidate_root in _knime_output_roots(base):
            candidates.append(candidate_root / "data.parquet")
    candidates.append(PROJECT_ROOT / "artifacts" / "phase_07_knime" / "data.parquet")
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: List[Path] = []
    for candidate in candidates:
        key = candidate.as_posix()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            return _json_safe_value(value.item())
        except Exception:
            value = str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        if hasattr(pd, "isna") and pd.isna(value):
            return None
        if hasattr(value, "tz_convert"):
            return value.tz_convert(timezone.utc).isoformat() if getattr(value, "tzinfo", None) else value.isoformat()
        if getattr(value, "tzinfo", None):
            return value.astimezone(timezone.utc).isoformat()
        return value.isoformat()
    if isinstance(value, (pd.Timedelta, timedelta)):
        return value.isoformat()
    if isinstance(value, (float, int, str, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    if pd.isna(value):
        return None
    return str(value)


def _frame_to_json_records(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        clean: Dict[str, Any] = {}
        for key, value in record.items():
            clean[key] = _json_safe_value(value)
        records.append(clean)
    return records


def _json_safe_obj(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe_obj(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe_obj(item) for item in value]
    return _json_safe_value(value)


def _knime_output_roots(knime_root: Path) -> List[Path]:
    if not knime_root.exists():
        return []

    roots: List[Path] = []
    git_dirs: List[Tuple[float, Path]] = []
    for candidate in knime_root.glob("git_*"):
        if not candidate.is_dir():
            continue
        try:
            mtime = candidate.stat().st_mtime
        except OSError:
            mtime = 0.0
        git_dirs.append((mtime, candidate))
    for _, path in sorted(git_dirs, key=lambda item: item[0], reverse=True):
        roots.append(path)
    roots.append(knime_root)
    return roots


def _find_knime_artifact(roots: List[Path], *relative_segments: str) -> Optional[Path]:
    for root in roots:
        for segment in relative_segments:
            candidate = root / Path(segment)
            if candidate.exists():
                return candidate
    return None


def _collect_knime_exports(roots: List[Path]) -> List[Dict[str, Any]]:
    exports: List[Dict[str, Any]] = []
    for base in roots:
        transforms_dir = base / "transforms"
        if not transforms_dir.exists():
            continue
        try:
            entries = sorted(transforms_dir.rglob("*"))
        except Exception:
            continue
        for entry in entries:
            if not entry.is_file():
                continue
            suffix = entry.suffix.lower()
            if suffix not in {".parquet", ".csv", ".json"}:
                continue
            try:
                stat = entry.stat()
                size_bytes = stat.st_size
                updated_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
            except OSError:
                size_bytes = None
                updated_at = None

            relative_to_base = entry.relative_to(base)
            relative_parts = relative_to_base.parts
            domain = None
            if len(relative_parts) >= 2 and relative_parts[0] == "transforms":
                domain = relative_parts[1]

            filename = entry.stem
            table = filename
            version: Optional[str] = None
            if "__v" in filename:
                table, version = filename.rsplit("__v", 1)

            rows: Optional[int] = None
            columns: Optional[List[str]] = None
            if suffix == ".parquet":
                try:
                    import pyarrow.parquet as pq  # type: ignore

                    parquet_file = pq.ParquetFile(entry.as_posix())
                    rows = int(parquet_file.metadata.num_rows) if parquet_file.metadata else None
                    columns = [str(name) for name in getattr(parquet_file.schema, "names", [])]
                except Exception:
                    rows = None
                    columns = None

            exports.append(
                {
                    "path": entry.as_posix(),
                    "relative_path": relative_to_base.as_posix(),
                    "format": suffix.lstrip("."),
                    "domain": domain,
                    "table": table,
                    "version": version,
                    "size_bytes": size_bytes,
                    "updated_at": updated_at,
                    "rows": rows,
                    "columns": columns,
                }
            )
    return exports


def _augment_knime_report(report: Dict[str, Any], knime_root: Path) -> Dict[str, Any]:
    if not isinstance(report, dict):
        return report
    data_path: Optional[Path] = None
    for base in _knime_output_roots(knime_root):
        candidate = base / "data.parquet"
        if candidate.exists():
            data_path = candidate
            break
    if not data_path:
        return report
    try:
        frame = pd.read_parquet(data_path.as_posix())
    except Exception:
        return report
    if frame is None or frame.empty:
        return report

    extras: Dict[str, Any] = {}

    # helper to map preferred names to actual columns (case-insensitive)
    name_map = {column.lower(): column for column in frame.columns}

    def resolve_columns(preferred: Iterable[str]) -> List[str]:
        resolved: List[str] = []
        seen: set[str] = set()
        for name in preferred:
            if name in frame.columns:
                if name not in seen:
                    resolved.append(name)
                    seen.add(name)
                continue
            mapped = name_map.get(name.lower())
            if mapped:
                if mapped not in seen:
                    resolved.append(mapped)
                    seen.add(mapped)
        return resolved

    # Clustering for key operational metrics
    cluster_candidates = resolve_columns(["lead_time_hours", "COD_AMOUNT", "weight_kg", "amount", "cod_amount"])
    if KMeans and StandardScaler and len(cluster_candidates) >= 2:
        cluster_df = frame[cluster_candidates].dropna()
        if not cluster_df.empty and cluster_df.shape[0] >= 20:
            sample_limit = min(cluster_df.shape[0], 5000)
            if sample_limit < cluster_df.shape[0]:
                cluster_df = cluster_df.sample(sample_limit, random_state=42)
            try:
                scaler = StandardScaler()
                scaled = scaler.fit_transform(cluster_df.to_numpy())
                n_clusters = max(2, min(4, int(np.sqrt(cluster_df.shape[0] / 50)) or 2))
                kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
                labels = kmeans.fit_predict(scaled)
                cluster_df = cluster_df.assign(cluster=labels)
                summary: List[Dict[str, Any]] = []
                total = float(cluster_df.shape[0])
                for cluster_id, group in cluster_df.groupby("cluster"):
                    record: Dict[str, Any] = {
                        "cluster": int(cluster_id),
                        "records": int(group.shape[0]),
                        "share": float(group.shape[0] / total),
                    }
                    if "lead_time_hours" in group:
                        record["avg_lead_time_hours"] = float(group["lead_time_hours"].mean())
                    if "COD_AMOUNT" in group:
                        record["avg_cod_amount"] = float(group["COD_AMOUNT"].mean())
                    if "weight_kg" in group:
                        record["avg_weight_kg"] = float(group["weight_kg"].mean())
                    if "amount" in group:
                        record["avg_amount"] = float(group["amount"].mean())
                    summary.append(record)
                summary.sort(key=lambda item: item["records"], reverse=True)
                extras["clusters"] = {
                    "features": cluster_candidates,
                    "summary": summary,
                }
            except Exception:  # pragma: no cover - defensive
                pass

    # Anomaly detection
    anomaly_candidates = resolve_columns(["lead_time_hours", "COD_AMOUNT", "amount", "weight_kg", "cod_amount"])
    if IsolationForest and len(anomaly_candidates) >= 2:
        anomaly_df = frame[anomaly_candidates].dropna()
        if anomaly_df.shape[0] >= 50:
            try:
                iso = IsolationForest(
                    n_estimators=200,
                    contamination=0.03,
                    random_state=42,
                )
                iso.fit(anomaly_df)
                scores = iso.score_samples(anomaly_df)
                anomaly_df = anomaly_df.assign(score=scores)
                top_anomalies = anomaly_df.nsmallest(20, "score")
                anomaly_rows: List[Dict[str, Any]] = []
                identifier_columns = [column for column in ("order_id", "forward_awb_no", "reference_no") if column in frame.columns]
                for index, item in top_anomalies.iterrows():
                    record: Dict[str, Any] = {}
                    for column in anomaly_candidates:
                        record[column] = _json_safe_value(item[column])
                    for column in identifier_columns:
                        record[column] = _json_safe_value(frame.at[index, column])
                    record["score"] = float(item["score"])
                    anomaly_rows.append(record)
                extras["anomalies"] = {
                    "columns": anomaly_candidates,
                    "rows": anomaly_rows,
                    "identifier_columns": identifier_columns,
                }
            except Exception:  # pragma: no cover - defensive
                pass

    # Numeric correlations
    numeric_columns = [column for column in frame.select_dtypes(include=[np.number]).columns if frame[column].notnull().any()]
    if len(numeric_columns) >= 2:
        try:
            corr_matrix = frame[numeric_columns].corr(method="pearson").fillna(0.0)
            pairs: List[Dict[str, Any]] = []
            for i, left in enumerate(numeric_columns):
                for right in numeric_columns[i + 1 :]:
                    corr_value = float(corr_matrix.at[left, right])
                    if not math.isfinite(corr_value):
                        continue
                    abs_corr = abs(corr_value)
                    if abs_corr < 0.25:
                        continue
                    pairs.append(
                        {
                            "feature_a": left,
                            "feature_b": right,
                            "correlation": corr_value,
                            "abs_correlation": abs_corr,
                        }
                    )
            if pairs:
                pairs.sort(key=lambda item: item["abs_correlation"], reverse=True)
                extras["correlations"] = {
                    "pairs": pairs[:15],
                }
        except Exception:  # pragma: no cover
            pass

    # Simple demand forecast
    date_column = None
    for candidate in ("order_date", "entry_date", "ts"):
        if candidate in frame.columns:
            date_column = candidate
            break
    if date_column:
        try:
            date_series = pd.to_datetime(frame[date_column], errors="coerce")
            daily = (
                frame.assign(__date=date_series.dt.normalize())
                .dropna(subset=["__date"])
                .groupby("__date")
                .size()
                .sort_index()
            )
            if len(daily) >= 7:
                history = [
                    {"timestamp": index.date().isoformat(), "value": int(count)}
                    for index, count in daily.items()
                ]
                horizon = 3
                window = min(7, len(daily))
                avg_recent = float(daily.tail(window).mean())
                last_date = daily.index[-1].date()
                predictions = [
                    {
                        "timestamp": (last_date + timedelta(days=step)).isoformat(),
                        "value": round(avg_recent, 2),
                    }
                    for step in range(1, horizon + 1)
                ]
                extras["forecast"] = {
                    "metric": "orders_per_day",
                    "history": history[-30:],
                    "predictions": predictions,
                    "window_used": window,
                }
        except Exception:  # pragma: no cover
            pass

    if extras:
        report["extras"] = _json_safe_obj(extras)
    return report


def _collect_knime_report(run_path: Path) -> Dict[str, Any]:
    knime_root = run_path / "phase_07_knime"
    output_roots = _knime_output_roots(knime_root)
    if not output_roots:
        return {
            "dq_report": {"results": [], "source": None},
            "dq_coverage": None,
            "insights": {"items": [], "meta": None, "source": None},
            "layer2_candidate": None,
            "bridge_summary": None,
            "exports": [],
            "notes": None,
            "profile_files": [],
        }

    dq_report_path = _find_knime_artifact(output_roots, "profile/dq_report.json", "dq_report.json")
    dq_report_payload = _safe_read_payload(dq_report_path) if dq_report_path else None
    dq_results = _normalize_dq_results(dq_report_payload)

    coverage_path = _find_knime_artifact(output_roots, "profile/dq_coverage_summary.json")
    coverage_payload = _safe_read_payload(coverage_path) if coverage_path else None
    coverage_summary = _normalize_dq_coverage(coverage_payload)

    insights_path = _find_knime_artifact(
        output_roots,
        "insights_fdr.json",
        "profile/insights_fdr.json",
        "insights.json",
        "profile/insights.json",
    )
    insights_payload = _safe_read_payload(insights_path) if insights_path else None
    insights_data = _normalize_knime_insights(insights_payload)
    if insights_path:
        insights_data["source"] = insights_path.as_posix()
    else:
        insights_data["source"] = None

    layer2_path = _find_knime_artifact(output_roots, "profile/layer2_candidate.json")
    layer2_payload = _safe_read_payload(layer2_path) if layer2_path else None

    bridge_summary_path = _find_knime_artifact(output_roots, "profile/bridge_summary.json")
    bridge_summary_payload = _safe_read_payload(bridge_summary_path) if bridge_summary_path else None

    notes_path = _find_knime_artifact(output_roots, "notes/run_summary.md")
    notes_payload = None
    if notes_path:
        try:
            notes_payload = notes_path.read_text(encoding="utf-8")
        except Exception:
            notes_payload = None

    profile_dir = next((root / "profile" for root in output_roots if (root / "profile").exists()), None)
    profile_files: List[Dict[str, Any]] = []
    if profile_dir:
        try:
            for path in sorted(profile_dir.glob("*.json")):
                try:
                    stat = path.stat()
                    size_bytes = stat.st_size
                    updated_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
                except OSError:
                    size_bytes = None
                    updated_at = None
                profile_files.append(
                    {
                        "name": path.name,
                        "path": path.as_posix(),
                        "size_bytes": size_bytes,
                        "updated_at": updated_at,
                    }
                )
        except Exception:
            profile_files = []

    exports = _collect_knime_exports(output_roots)

    report = {
        "dq_report": {"results": dq_results, "source": dq_report_path.as_posix() if dq_report_path else None},
        "dq_coverage": {"summary": coverage_summary, "source": coverage_path.as_posix() if coverage_path else None}
        if coverage_summary
        else None,
        "insights": insights_data,
        "layer2_candidate": {
            "source": layer2_path.as_posix(),
            "payload": _json_safe_obj(layer2_payload),
        }
        if layer2_path and layer2_payload
        else None,
        "bridge_summary": {
            "source": bridge_summary_path.as_posix(),
            "payload": _json_safe_obj(bridge_summary_payload),
        }
        if bridge_summary_path and bridge_summary_payload
        else None,
        "exports": exports,
        "notes": {"run_summary": notes_payload, "source": notes_path.as_posix() if notes_path else None}
        if notes_payload
        else None,
        "profile_files": profile_files,
    }
    return _augment_knime_report(report, knime_root)


def _normalize_dq_results(payload: Any) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, dict):
        items = payload.get("results")
        results = items if isinstance(items, list) else []
    elif isinstance(payload, list):
        results = payload
    else:
        return []

    normalized: List[Dict[str, Any]] = []
    for entry in results:
        if not isinstance(entry, Mapping):
            continue
        record: Dict[str, Any] = {}
        identifier = entry.get("id")
        if identifier is not None:
            record["id"] = str(identifier)

        passed = entry.get("passed")
        if passed is not None:
            record["passed"] = bool(passed)

        status = entry.get("status")
        if status is None and passed is not None:
            status = "pass" if bool(passed) else "fail"
        if status is not None:
            record["status"] = str(status).lower()

        for key in ("title", "severity", "scope", "entity", "notes"):
            value = entry.get(key)
            if value is not None:
                record[key] = _json_safe_value(value)

        for key in ("evaluated_rows", "failed_rows"):
            value = entry.get(key)
            if value is not None:
                try:
                    record[key] = int(value)
                except (TypeError, ValueError):
                    record[key] = _json_safe_value(value)

        fail_rate = entry.get("fail_rate")
        if fail_rate is not None:
            try:
                record["fail_rate"] = float(fail_rate)
            except (TypeError, ValueError):
                record["fail_rate"] = _json_safe_value(fail_rate)

        sample_path = entry.get("sample_failures_path")
        if sample_path is not None:
            record["sample_failures_path"] = str(sample_path)

        normalized.append(record)
    return normalized


def _normalize_dq_coverage(payload: Any) -> Optional[Dict[str, Any]]:
    if payload is None:
        return None
    summary = None
    if isinstance(payload, Mapping):
        summary_candidate = payload.get("summary")
        if isinstance(summary_candidate, Mapping):
            summary = summary_candidate
        else:
            summary = payload
    if not isinstance(summary, Mapping):
        return None
    result: Dict[str, Any] = {}
    for key, value in summary.items():
        if isinstance(value, (int, float)):
            result[key] = float(value)
        else:
            safe = _json_safe_value(value)
            if safe is not None:
                result[key] = safe
    return result or None


def _normalize_knime_insights(payload: Any) -> Dict[str, Any]:
    if payload is None:
        return {"items": [], "meta": None}

    if isinstance(payload, Mapping):
        items = payload.get("insights")
        insights = items if isinstance(items, list) else []
        meta = {key: _json_safe_obj(value) for key, value in payload.items() if key != "insights"}
    elif isinstance(payload, list):
        insights = payload
        meta = None
    else:
        return {"items": [], "meta": None}

    normalized_items: List[Dict[str, Any]] = []
    for entry in insights:
        if not isinstance(entry, Mapping):
            continue
        normalized_entry: Dict[str, Any] = {}
        for key, value in entry.items():
            normalized_entry[str(key)] = _json_safe_obj(value)
        headline = (
            normalized_entry.get("insight")
            or normalized_entry.get("title")
            or normalized_entry.get("summary")
        )
        if headline is not None:
            normalized_entry["headline"] = str(headline)
        normalized_items.append(normalized_entry)

    return {"items": normalized_items, "meta": meta}


def _load_knime_snapshot(run: str, limit: int, offset: int) -> Optional[Dict[str, Any]]:
    run_path = _resolve_run(run)
    resolved_run = run_path.name if run_path else run
    for candidate in _knime_data_candidates(run, run_path):
        if not candidate.exists():
            continue
        try:
            frame = pd.read_parquet(candidate)
        except Exception:
            continue
        if frame is None or frame.empty:
            continue
        total_rows = int(frame.shape[0])
        bounded_offset = max(0, min(offset, total_rows))
        slice_end = min(bounded_offset + limit, total_rows)
        window = frame.iloc[bounded_offset:slice_end].copy()
        rows = _frame_to_json_records(window)
        try:
            stat = candidate.stat()
            updated_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
            size_bytes = stat.st_size
        except (FileNotFoundError, OSError):
            updated_at = None
            size_bytes = None
        return {
            "run": resolved_run,
            "columns": [str(column) for column in frame.columns],
            "rows": rows,
            "total_rows": total_rows,
            "limit": limit,
            "offset": bounded_offset,
            "path": candidate.as_posix(),
            "updated_at": updated_at,
            "size_bytes": size_bytes,
        }
    return None


def _normalize_correlation_pairs(
    entries: Iterable[Dict[str, Any]],
    *,
    left_key: str,
    right_key: str,
    value_key: str,
    abs_key: Optional[str],
    n_key: Optional[str],
    kind: str,
    source: Optional[str],
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        left = entry.get(left_key)
        right = entry.get(right_key)
        if left is None or right is None:
            continue

        raw_value = entry.get(value_key)
        corr: Optional[float] = None
        if raw_value is not None:
            try:
                corr = float(raw_value)
            except (TypeError, ValueError):
                corr = None
        if corr is not None and not math.isfinite(corr):
            corr = None

        raw_abs = entry.get(abs_key) if abs_key else None
        abs_corr: Optional[float] = None
        if raw_abs is not None:
            try:
                abs_corr = float(raw_abs)
            except (TypeError, ValueError):
                abs_corr = None
        if abs_corr is not None and not math.isfinite(abs_corr):
            abs_corr = None
        if abs_corr is None and corr is not None:
            abs_corr = abs(corr)

        if corr is None and abs_corr is None:
            continue

        raw_n = entry.get(n_key) if n_key else None
        sample: Optional[int] = None
        if raw_n is not None:
            try:
                sample_float = float(raw_n)
                if math.isfinite(sample_float):
                    sample = int(round(sample_float))
            except (TypeError, ValueError):
                sample = None

        record = {
            "feature_a": str(left),
            "feature_b": str(right),
            "correlation": corr,
            "abs_correlation": abs_corr,
            "sample_size": sample,
            "kind": kind,
            "source": source,
        }
        method = entry.get("method")
        if isinstance(method, str):
            record["method"] = method
        raw_p = entry.get("p_value")
        if isinstance(raw_p, (int, float)) and math.isfinite(float(raw_p)):
            record["p_value"] = float(raw_p)

        for key in CORRELATION_ENRICHED_KEYS:
            value = entry.get(key)
            if value is not None:
                record[key] = value
        notes = entry.get("notes")
        if notes is not None:
            record["notes"] = notes
        results.append(record)
    return results

def _safe_float(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(result):
        return result
    return None


def _sanitize_business_entries(
    entries: Iterable[Mapping[str, Any]],
    *,
    kind: str,
    source: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    sanitized: List[Dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        feature_a = entry.get("feature_a") or entry.get("numeric_feature") or entry.get("kpi")
        feature_b = entry.get("feature_b") or entry.get("categorical_feature") or entry.get("feature")
        if feature_a is None or feature_b is None:
            continue
        corr = _safe_float(entry.get("correlation") if "correlation" in entry else entry.get("score"))
        abs_corr = _safe_float(entry.get("abs_correlation") if "abs_correlation" in entry else entry.get("strength"))
        sample = entry.get("sample_size") or entry.get("n")
        if sample is not None:
            try:
                sample_int = int(float(sample))
            except (TypeError, ValueError):
                sample_int = None
        else:
            sample_int = None
        method = entry.get("method")
        notes = entry.get("notes") if isinstance(entry.get("notes"), (dict, list)) else None
        record = {
            "feature_a": str(feature_a),
            "feature_b": str(feature_b),
            "correlation": corr,
            "abs_correlation": abs_corr if abs_corr is not None else (abs(corr) if corr is not None else None),
            "sample_size": sample_int,
            "method": str(method) if isinstance(method, str) else None,
            "kind": kind,
            "source": source,
            "notes": notes,
        }
        raw_p = entry.get("p_value")
        if isinstance(raw_p, (int, float)) and math.isfinite(float(raw_p)):
            record["p_value"] = float(raw_p)
        for key in CORRELATION_ENRICHED_KEYS:
            value = entry.get(key)
            if value is not None:
                record[key] = value
        sanitized.append(record)
    sanitized.sort(key=lambda item: abs(item.get("abs_correlation") or 0.0), reverse=True)
    return sanitized[:limit]


def _collect_correlations(run_path: Optional[Path], top: int) -> Dict[str, Any]:
    numeric: List[Dict[str, Any]] = []
    datetime_pairs: List[Dict[str, Any]] = []
    business_groups: Dict[str, List[Dict[str, Any]]] = {
        "numeric_numeric": [],
        "numeric_categorical": [],
        "categorical_categorical": [],
    }
    sources: Dict[str, Optional[str]] = {"numeric": None, "datetime": None, "business": None}

    if run_path:
        stage07_dir = run_path / "stage_07_correlations"
        numeric_json = stage07_dir / "correlations.json"
        numeric_entries = _safe_load_json_list(numeric_json)
        if numeric_entries:
            sources["numeric"] = numeric_json.as_posix()
            numeric = _normalize_correlation_pairs(
                numeric_entries,
                left_key="f1",
                right_key="f2",
                value_key="r",
                abs_key="abs_r",
                n_key="n",
                kind="numeric",
                source=sources["numeric"],
            )

        datetime_parquet = run_path / "stage_10_bi" / "marts" / "datetime_correlations.parquet"
        datetime_entries: List[Dict[str, Any]] = []
        datetime_source: Optional[str] = None
        if datetime_parquet.exists():
            datetime_entries = _safe_load_parquet_rows(datetime_parquet)
            datetime_source = datetime_parquet.as_posix()
        elif stage07_dir.exists():
            datetime_json = stage07_dir / "correlations_datetime.json"
            datetime_entries = _safe_load_json_list(datetime_json)
            if datetime_entries:
                datetime_source = datetime_json.as_posix()

        if datetime_entries:
            sources["datetime"] = datetime_source
            if datetime_source and datetime_source.endswith(".parquet"):
                datetime_pairs = _normalize_correlation_pairs(
                    datetime_entries,
                    left_key="feature_x",
                    right_key="feature_y",
                    value_key="correlation",
                    abs_key="correlation_abs",
                    n_key="pair_n",
                    kind="datetime",
                    source=datetime_source,
                )
            else:
                datetime_pairs = _normalize_correlation_pairs(
                    datetime_entries,
                    left_key="f1",
                    right_key="f2",
                    value_key="r",
                    abs_key="abs_r",
                    n_key="n",
                    kind="datetime",
                    source=datetime_source,
                )

        business_dir = run_path / "stage_07_7_business_correlations"
        business_json = business_dir / "business_correlations.json"
        if business_json.exists():
            try:
                business_payload = _load_json(business_json)
            except Exception:
                business_payload = None
            if isinstance(business_payload, Mapping):
                highlights = business_payload.get("highlights")
                if isinstance(highlights, Mapping):
                    for bucket in business_groups.keys():
                        entries = highlights.get(bucket)
                        if isinstance(entries, list) and entries:
                            business_groups[bucket] = _sanitize_business_entries(
                                entries,
                                kind=bucket,
                                source=business_json.as_posix(),
                                limit=top,
                            )
                    if any(business_groups.values()):
                        sources["business"] = business_json.as_posix()

    numeric.sort(key=lambda item: item.get("abs_correlation") or 0.0, reverse=True)
    datetime_pairs.sort(key=lambda item: item.get("abs_correlation") or 0.0, reverse=True)

    return {
        "numeric": numeric[:top],
        "datetime": datetime_pairs[:top],
        "business": business_groups,
        "sources": sources,
    }


def _pair_key(feature_a: Any, feature_b: Any) -> str:
    return "::".join(
        sorted(
            [
                str(feature_a or "").strip().lower(),
                str(feature_b or "").strip().lower(),
            ]
        )
    )


class CorrelationExplanationCache:
    def __init__(self, artifacts_root: Path) -> None:
        self._path = artifacts_root / "_global" / "correlation_explanations.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._payload: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        if self._payload is not None:
            return self._payload
        if not self._path.exists():
            self._payload = {}
            return self._payload
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        self._payload = data
        return self._payload

    def make_key(
        self,
        *,
        run: str,
        feature_a: str,
        feature_b: str,
        kind: Optional[str],
        language: str,
        correlation: Optional[float],
    ) -> str:
        parts = [run, language, kind or "any", _pair_key(feature_a, feature_b)]
        if correlation is not None:
            try:
                parts.append(f"{float(correlation):.4f}")
            except (TypeError, ValueError):
                pass
        return "::".join(parts)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        payload = self._load()
        entry = payload.get(key)
        if isinstance(entry, dict):
            return entry
        return None

    def set(self, key: str, value: Mapping[str, Any]) -> None:
        payload = self._load()
        payload[key] = dict(value)
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._payload = payload


def _find_correlation_entry(
    run_path: Optional[Path],
    feature_a: str,
    feature_b: str,
    *,
    kind: Optional[str],
    top: int = 250,
) -> Optional[Dict[str, Any]]:
    if not run_path:
        return None
    correlations = _collect_correlations(run_path, top)
    target_key = _pair_key(feature_a, feature_b)

    search_buckets: List[Tuple[str, List[Dict[str, Any]]]] = [
        ("numeric", correlations.get("numeric") or []),
        ("datetime", correlations.get("datetime") or []),
    ]
    business_groups = correlations.get("business") or {}
    for bucket_name, entries in business_groups.items():
        search_buckets.append((bucket_name, entries or []))

    for bucket_name, entries in search_buckets:
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            entry_key = _pair_key(entry.get("feature_a"), entry.get("feature_b"))
            if entry_key != target_key:
                continue
            resolved_kind = entry.get("kind") or bucket_name
            if kind and resolved_kind != kind:
                continue
            candidate = dict(entry)
            candidate["kind"] = resolved_kind
            return candidate
    return None


def _fallback_correlation_summary(record: Mapping[str, Any], *, language: str = "ar") -> str:
    label_a = str(record.get("feature_a_label") or record.get("feature_a") or "المتغير الأول")
    label_b = str(record.get("feature_b_label") or record.get("feature_b") or "المتغير الثاني")
    corr = record.get("correlation")
    sample = record.get("sample_size")
    kpi_label = record.get("kpi_label")
    effect_direction = record.get("effect_direction")
    driver_label = str(record.get("impact_driver_label") or label_a)

    corr_text = ""
    if isinstance(corr, (int, float)) and math.isfinite(float(corr)):
        corr_text = f"{float(corr):+.2f}"
    sample_text = ""
    if isinstance(sample, (int, float)) and math.isfinite(float(sample)):
        sample_text = f"{int(float(sample)):,}"

    if language == "en":
        components = [f"{label_a} moves with {label_b}"]
        if corr_text:
            components.append(f"(r={corr_text})")
        if sample_text:
            components.append(f"based on ~{sample_text} rows")
        summary = " ".join(components).strip()
        if kpi_label and effect_direction:
            relation = "supports" if effect_direction == "improves" else "pressures"
            summary += f". Changes in {driver_label} {relation} {kpi_label}."
        return summary if summary.endswith(".") else summary + "."

    components = [f"{label_a} يتحرك مع {label_b}"]
    if corr_text:
        components.append(f"(معامل {corr_text})")
    if sample_text:
        components.append(f"استناداً إلى نحو {sample_text} صف")
    summary = " ".join(components).strip()
    if kpi_label and effect_direction:
        relation = "يحسّن" if effect_direction == "improves" else "يضعف"
        summary += f". زيادة {driver_label} {relation} {kpi_label}."
    return summary if summary.endswith("۔") or summary.endswith(".") else summary + "."


def _fallback_correlation_actions(record: Mapping[str, Any], *, language: str = "ar") -> List[str]:
    actions: List[str] = []
    driver_label = str(record.get("impact_driver_label") or record.get("feature_a_label") or record.get("feature_a") or "المؤشر")
    kpi_label = str(record.get("kpi_label") or ("KPI" if language == "en" else "المؤشر الرئيسي"))
    effect_direction = record.get("effect_direction")
    sensitivity = str(record.get("sensitivity") or "")

    if effect_direction:
        if language == "en":
            if effect_direction == "improves":
                actions.append(f"Invest in improving {driver_label} because it correlates with better {kpi_label}.")
            else:
                actions.append(f"Reduce variability in {driver_label} to protect {kpi_label}.")
        else:
            if effect_direction == "improves":
                actions.append(f"عزّز أداء {driver_label} لأنه يرتبط بتحسّن {kpi_label}.")
            else:
                actions.append(f"خفّض تذبذب {driver_label} لتقليل تدهور {kpi_label}.")

    notes = record.get("notes")
    top_hint = None
    if isinstance(notes, Mapping):
        top_hint = notes.get("top_category") or notes.get("top_pair")
    if isinstance(top_hint, Mapping):
        value = top_hint.get("value") or top_hint.get("value_a")
        if value:
            if language == "en":
                actions.append(f"Focus on segment '{value}' because it shows the strongest signal.")
            else:
                actions.append(f"ركّز على الشريحة '{value}' لأنها تظهر أقوى إشارة.")

    if language == "en":
        actions.append("Monitor this correlation weekly and alert if |r| moves by more than 0.05.")
    else:
        actions.append("تابع هذا الارتباط أسبوعياً ونبّه عند تغير المعامل بأكثر من ±0.05.")

    if sensitivity.lower() == "high":
        if language == "en":
            actions.append("Escalate persistent changes in this driver to the operations war-room.")
        else:
            actions.append("صعّد أي تغيّر مستمر في هذا المؤشر إلى غرفة التحكم التشغيلية.")

    deduped: List[str] = []
    for action in actions:
        if action and action not in deduped:
            deduped.append(action)
    return deduped[:3]


def _prepare_correlation_context(record: Mapping[str, Any]) -> Dict[str, Any]:
    context_keys = [
        "feature_a",
        "feature_b",
        "feature_a_label",
        "feature_b_label",
        "feature_a_domain",
        "feature_b_domain",
        "correlation",
        "abs_correlation",
        "sample_size",
        "kpi_label",
        "effect_direction",
        "expected_kpi_delta",
        "expected_kpi_delta_pct",
        "sensitivity",
        "notes",
        "impact_summary",
    ]
    context = {key: record.get(key) for key in context_keys if record.get(key) is not None}
    context["generated_at"] = datetime.utcnow().isoformat()
    return context


def _call_llm_for_correlation(
    record: Mapping[str, Any],
    request: "CorrelationExplainRequest",
    *,
    baseline_summary: str,
    fallback_actions: Sequence[str],
) -> Optional[Dict[str, Any]]:
    provider = request.provider or DEFAULT_CORRELATION_LLM_PROVIDER
    model = request.model or DEFAULT_CORRELATION_LLM_MODEL
    if not provider or not model:
        return None

    context = _prepare_correlation_context(record)
    context_json = json.dumps(context, ensure_ascii=False)
    language_name = "العربية" if request.language == "ar" else "English"
    system_prompt = compose_system_prompt(
        [
            "أنت مستشار عمليات في قطاع الشحن.",
            "قدّم توصيات عملية بناءً على البيانات دون الادعاء بالسببية.",
            "تجنّب استخدام كلمات مثل cause أو causal أو impact بشكل صريح.",
        ],
        enforce_data_scope=True,
    )
    user_prompt = (
        f"بيانات الارتباط:\n{context_json}\n\n"
        f"الملخص الأساسي:\n{baseline_summary}\n\n"
        "المهمة: اكتب ملخصاً تنفيذياً موجزاً للمديرين التشغيليين، ثم اقترح حتى ثلاثة إجراءات عملية يمكن تنفيذها فوراً. "
        "امتنع عن التصريح بأن هناك علاقة سببية، وتحدث بصيغة احتمالية.\n"
        "أجب بصيغة JSON بالحقول التالية:\n"
        '{\n  "summary": "فقرة قصيرة",\n  "recommended_actions": ["خطوة 1", "خطوة 2"],\n  "confidence": "عالي|متوسط|منخفض"\n}\n'
        f"اكتب الإجابة كاملة باللغة {language_name}."
    )

    try:
        response = invoke_model(
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=request.max_tokens or 600,
            temperature=request.temperature or 0.2,
            top_p=0.9,
            timeout=90,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("correlation_llm_failure", exc_info=exc)
        return None

    try:
        payload = json.loads(response.content)
    except Exception:
        payload = {"summary": response.content}

    summary = payload.get("summary")
    if isinstance(summary, str):
        summary = summary.strip()
    else:
        summary = None
    actions_payload = payload.get("recommended_actions")
    actions: List[str] = []
    if isinstance(actions_payload, list):
        for item in actions_payload:
            if isinstance(item, str):
                cleaned = item.strip()
                if cleaned:
                    actions.append(cleaned)
    confidence = payload.get("confidence")
    if isinstance(confidence, str):
        confidence = confidence.strip()
    else:
        confidence = None

    return {
        "summary": summary or baseline_summary,
        "recommended_actions": actions or list(fallback_actions),
        "confidence": confidence,
        "provider": response.provider,
        "model": response.model,
        "tokens_in": response.tokens_in,
        "tokens_out": response.tokens_out,
        "cost_estimate": response.cost_estimate,
        "duration_s": response.duration_s,
        "mode": "llm",
        "context": {
            "record": context,
            "baseline_summary": baseline_summary,
        },
    }


def _build_correlation_explanation(record: Mapping[str, Any], request: "CorrelationExplainRequest") -> Dict[str, Any]:
    baseline_summary = _fallback_correlation_summary(record, language=request.language)
    fallback_actions = _fallback_correlation_actions(record, language=request.language)
    explanation: Dict[str, Any] = {
        "summary": baseline_summary,
        "recommended_actions": fallback_actions,
        "confidence": None,
        "provider": None,
        "model": None,
        "mode": "fallback",
        "generated_at": datetime.utcnow().isoformat(),
        "context": {
            "impact_summary": record.get("impact_summary"),
            "kpi_label": record.get("kpi_label"),
            "effect_direction": record.get("effect_direction"),
            "expected_kpi_delta": record.get("expected_kpi_delta"),
            "expected_kpi_delta_pct": record.get("expected_kpi_delta_pct"),
        },
    }

    if request.use_llm:
        llm_payload = _call_llm_for_correlation(
            record,
            request,
            baseline_summary=baseline_summary,
            fallback_actions=fallback_actions,
        )
        if llm_payload:
            explanation.update(llm_payload)
            if "context" in llm_payload and isinstance(llm_payload["context"], Mapping):
                merged_context = dict(explanation.get("context") or {})
                merged_context.update(llm_payload["context"])
                explanation["context"] = merged_context
            explanation.setdefault("generated_at", datetime.utcnow().isoformat())

    explanation.setdefault("generated_at", datetime.utcnow().isoformat())
    return explanation


def _safe_round(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        return None
    return round(float(value), digits)


def _compute_raw_metrics(run: str, top: int) -> Dict[str, Any]:
    run_path = _resolve_run(run)
    correlations_payload = _collect_correlations(run_path, top)

    frame = _load_raw_orders_dataset(run)
    fallback_used = False
    if frame is None:
        frame = _load_orders_dataset(run)
        fallback_used = True
    if frame is None:
        raise HTTPException(status_code=404, detail="Raw dataset not found for requested run.")

    dataset = frame.copy()
    dataset["payment_method"] = dataset.get("payment_method", "").astype(str).replace({"None": "", "nan": ""}).fillna("")
    dataset["status"] = dataset.get("status", "").astype(str).replace({"None": "", "nan": ""}).fillna("")
    dataset["destination"] = dataset.get("destination", "").astype(str).replace({"None": "", "nan": ""}).fillna("")

    cod_series = pd.to_numeric(dataset.get("cod_amount"), errors="coerce").fillna(0.0)
    amount_series = pd.to_numeric(dataset.get("amount"), errors="coerce").fillna(0.0)
    order_dates = pd.to_datetime(dataset.get("order_date"), errors="coerce")

    dataset["cod_amount"] = cod_series
    dataset["status"] = dataset["status"].replace("", "Unknown")
    dataset["payment_method"] = dataset["payment_method"].replace("", "Unknown")
    dataset["destination"] = dataset["destination"].replace("", "Unknown")

    dataset["_delivered"] = dataset["status"].str.contains(DELIVERED_REGEX, case=False, regex=True, na=False).astype(int)
    dataset["_out_for_delivery"] = dataset["status"].str.contains(OUT_FOR_DELIVERY_REGEX, case=False, regex=True, na=False).astype(int)
    dataset["_returned"] = dataset["status"].str.contains(RETURNED_REGEX, case=False, regex=True, na=False).astype(int)

    total_orders = int(dataset.shape[0])
    cod_orders = int((cod_series > 0).sum())

    def _share(count: int) -> Optional[float]:
        if total_orders == 0:
            return None
        return round(float(count) / total_orders * 100, 2)

    def _build_breakdown(column: str, label: str) -> Optional[Dict[str, Any]]:
        if column not in dataset.columns:
            return None
        working = dataset[[column, "cod_amount", "_delivered", "_out_for_delivery", "_returned"]].copy()
        working[column] = working[column].fillna("").replace("", "Unknown")
        grouped = (
            working.groupby(column, dropna=False)
            .agg(
                orders=(column, "size"),
                delivered=("_delivered", "sum"),
                out_for_delivery=("_out_for_delivery", "sum"),
                returned=("_returned", "sum"),
                cod_total=("cod_amount", "sum"),
            )
            .reset_index()
        )
        grouped = grouped[grouped["orders"] > 0].sort_values("orders", ascending=False).head(top)
        if grouped.empty:
            return None

        values: List[Dict[str, Any]] = []
        chart_data: List[Dict[str, Any]] = []
        include_delivered = bool(grouped["delivered"].sum())
        include_out_for_delivery = bool(grouped["out_for_delivery"].sum())
        include_returned = bool(grouped["returned"].sum())

        for _, row in grouped.iterrows():
            value_label = str(row[column])
            orders = int(row["orders"])
            entry = {
                "value": value_label,
                "orders": orders,
                "share_pct": _share(orders),
                "delivered": int(row["delivered"]),
                "out_for_delivery": int(row["out_for_delivery"]),
                "returned": int(row["returned"]),
                "cod_total": _safe_round(row["cod_total"]),
            }
            values.append(entry)

            chart_row: Dict[str, Any] = {"label": value_label, "orders": orders}
            if include_delivered:
                chart_row["delivered"] = entry["delivered"]
            if include_out_for_delivery:
                chart_row["out_for_delivery"] = entry["out_for_delivery"]
            if include_returned:
                chart_row["returned"] = entry["returned"]
            chart_data.append(chart_row)

        y_keys = ["orders"]
        if include_delivered:
            y_keys.append("delivered")
        if include_out_for_delivery:
            y_keys.append("out_for_delivery")
        if include_returned:
            y_keys.append("returned")

        chart = None
        if chart_data:
            chart = {
                "title": f"توزيع {label}",
                "type": "bar",
                "x": "label",
                "y": y_keys,
                "data": chart_data,
            }

        return {"dimension": column, "label": label, "values": values, "chart": chart}

    dimension_labels = {
        "payment_method": "طرق الدفع",
        "status": "الحالة التشغيلية",
        "destination": "الوجهة",
        "origin": "نقطة الانطلاق",
        "ORIGIN": "نقطة الانطلاق",
        "ON HOLD": "حالة التعليق",
        "3PLSTATUS": "حالة شركة التوصيل",
        # Customer/Client dimensions
        "customer_id": "رقم العميل",
        "customer_name": "اسم العميل",
        "client_id": "رقم العميل",
        "client_name": "اسم العميل",
        "sender_name": "اسم المرسل",
        "receiver_name": "اسم المستلم",
        # Carrier/Shipping company dimensions
        "carrier": "شركة الشحن",
        "carrier_name": "شركة الشحن",
        "courier": "شركة التوصيل",
        "courier_name": "شركة التوصيل",
        "shipping_company": "شركة الشحن",
        "delivery_company": "شركة التوصيل",
        "forward_company": "شركة التوصيل",
        "logistics_provider": "مزود الخدمات اللوجستية",
        # Shipment type dimensions
        "shipment_type": "نوع الشحنة",
        "product_type": "نوع المنتج",
        "product_category": "فئة المنتج",
        "service_type": "نوع الخدمة",
        "package_type": "نوع الطرد",
    }

    candidate_dimensions: List[Tuple[str, str]] = []
    seen_dimensions: set[str] = set()

    for column, label in dimension_labels.items():
        if column in dataset.columns and column not in seen_dimensions:
            candidate_dimensions.append((column, label))
            seen_dimensions.add(column)

    # Auto-detect important columns by matching common patterns
    column_patterns = {
        # Customer patterns (case-insensitive)
        r"(?i)(customer|client|buyer|purchaser|عميل|مشتري)": "العميل",
        # Carrier/Shipper patterns
        r"(?i)(carrier|courier|shipper|delivery|forward|logistics|3pl|شركة|ناقل|توصيل)": "شركة التوصيل",
        # Shipment/Product type patterns
        r"(?i)(shipment.*type|product.*type|service.*type|package.*type|نوع.*شحن|نوع.*منتج)": "نوع الشحنة",
        # Driver patterns
        r"(?i)(driver|سائق)": "السائق",
    }
    
    for column in dataset.columns:
        if column in seen_dimensions or column.startswith("_"):
            continue
        series = dataset[column]
        if not pd.api.types.is_object_dtype(series):
            continue
        
        # Check if column matches any known pattern
        matched_label = None
        for pattern, label in column_patterns.items():
            if re.match(pattern, column):
                matched_label = label
                break
        
        unique_count = series.nunique(dropna=True)
        # Include columns with reasonable cardinality (2 to top*2, max 20)
        if 2 <= unique_count <= min(max(10, top * 2), 20):
            display_label = matched_label or column
            candidate_dimensions.append((column, display_label))
            seen_dimensions.add(column)

    skip_auto = {"order_id", "amount", "cod_amount", "order_date"}
    # Clean up: remove already processed columns from final auto-detection
    for column in list(seen_dimensions):
        if column in skip_auto:
            continue

    breakdowns: List[Dict[str, Any]] = []
    for column, label in candidate_dimensions:
        breakdown = _build_breakdown(column, label)
        if breakdown:
            breakdowns.append(breakdown)

    trends: Dict[str, Any] = {}
    if not order_dates.dropna().empty:
        dataset["_order_day"] = order_dates.dt.strftime("%Y-%m-%d")
        daily_group = (
            dataset.groupby("_order_day", dropna=False)
            .agg(
                orders=("_order_day", "size"),
                delivered=("_delivered", "sum"),
                cod_total=("cod_amount", "sum"),
            )
            .reset_index()
            .sort_values("_order_day")
        )
        if not daily_group.empty:
            daily_data: List[Dict[str, Any]] = []
            include_delivered = bool(daily_group["delivered"].sum())
            for _, row in daily_group.iterrows():
                entry: Dict[str, Any] = {
                    "date": str(row["_order_day"]),
                    "orders": int(row["orders"]),
                }
                if include_delivered:
                    entry["delivered"] = int(row["delivered"])
                cod_total = _safe_round(row["cod_total"])
                if cod_total is not None:
                    entry["cod_total"] = cod_total
                daily_data.append(entry)
            y_keys = ["orders"]
            if include_delivered:
                y_keys.append("delivered")
            trends["daily"] = {
                "title": "الطلبات حسب اليوم",
                "type": "line",
                "x": "date",
                "y": y_keys,
                "data": daily_data,
            }

        dataset["_order_hour"] = order_dates.dt.hour
        hour_group = (
            dataset.dropna(subset=["_order_hour"])
            .groupby("_order_hour")
            .agg(
                orders=("_order_hour", "size"),
                delivered=("_delivered", "sum"),
            )
            .reset_index()
            .sort_values("_order_hour")
        )
        if not hour_group.empty:
            hour_data: List[Dict[str, Any]] = []
            include_delivered = bool(hour_group["delivered"].sum())
            for _, row in hour_group.iterrows():
                entry: Dict[str, Any] = {
                    "hour": f"{int(row['_order_hour']):02d}",
                    "orders": int(row["orders"]),
                }
                if include_delivered:
                    entry["delivered"] = int(row["delivered"])
                hour_data.append(entry)
            y_keys = ["orders"]
            if include_delivered:
                y_keys.append("delivered")
            trends["hour_of_day"] = {
                "title": "الطلبات بحسب الساعة",
                "type": "bar",
                "x": "hour",
                "y": y_keys,
                "data": hour_data,
            }

        dataset["_order_weekday"] = order_dates.dt.weekday
        weekday_group = (
            dataset.dropna(subset=["_order_weekday"])
            .groupby("_order_weekday")
            .agg(
                orders=("_order_weekday", "size"),
                delivered=("_delivered", "sum"),
            )
            .reset_index()
            .sort_values("_order_weekday")
        )
        if not weekday_group.empty:
            weekday_data: List[Dict[str, Any]] = []
            include_delivered = bool(weekday_group["delivered"].sum())
            for _, row in weekday_group.iterrows():
                idx = int(row["_order_weekday"])
                entry: Dict[str, Any] = {
                    "weekday": WEEKDAY_LABELS.get(idx, str(idx)),
                    "orders": int(row["orders"]),
                }
                if include_delivered:
                    entry["delivered"] = int(row["delivered"])
                weekday_data.append(entry)
            y_keys = ["orders"]
            if include_delivered:
                y_keys.append("delivered")
            trends["weekday"] = {
                "title": "الطلبات حسب أيام الأسبوع",
                "type": "bar",
                "x": "weekday",
                "y": y_keys,
                "data": weekday_data,
            }

    response: Dict[str, Any] = {
        "run": run,
        "artifacts_root": run_path.as_posix() if run_path else None,
        "fallback_used": fallback_used,
        "totals": {
            "orders": total_orders,
            "orders_cod": cod_orders,
            "orders_cod_share_pct": _share(cod_orders),
            "orders_non_cod": total_orders - cod_orders,
            "amount_total": _safe_round(amount_series.sum()),
            "cod_total": _safe_round(cod_series.sum()),
            "cod_average": _safe_round(cod_series.mean()),
            "cod_min": _safe_round(cod_series.min()),
            "cod_max": _safe_round(cod_series.max()),
        },
        "breakdowns": breakdowns,
        "correlations": correlations_payload,
    }

    if trends:
        response["trends"] = trends

    if not order_dates.dropna().empty:
        response["order_date_range"] = {
            "min": order_dates.min().isoformat(),
            "max": order_dates.max().isoformat(),
        }

    return response


def _build_sla_text(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    summary = payload.get("summary") or {}
    compliance_pct = summary.get("compliance_pct")
    if compliance_pct is not None:
        lines.append(f"Overall compliance: {compliance_pct:.2f}% (status: {summary.get('status', 'unknown')}).")
    documents_total = summary.get("documents_total")
    terms_total = summary.get("terms_total")
    if documents_total is not None and terms_total is not None:
        lines.append(f"Documents analysed: {documents_total} | Terms evaluated: {terms_total}.")

    kpis = payload.get("kpis") or []
    if kpis:
        lines.append("Key SLA indicators:")
        for kpi in kpis:
            label = kpi.get("label") or kpi.get("id")
            value_pct = kpi.get("value_pct")
            if value_pct is not None:
                display = f"{value_pct:.2f}%"
            else:
                raw_value = kpi.get("raw_value")
                display = f"{raw_value:,.2f}" if isinstance(raw_value, (int, float)) else str(raw_value)
            lines.append(f"- {label}: {display} (status: {kpi.get('status', 'unknown')})")
    else:
        for metric in payload.get("metrics", []):
            value = metric.get("value")
            if value is None:
                continue
            label = metric.get("label") or metric.get("id")
            fmt = metric.get("format")
            if fmt == "percentage":
                display = f"{value * 100:.2f}%"
            elif fmt == "duration_hours":
                display = f"{value:.2f} hours"
            elif fmt == "currency":
                display = f"{value:,.2f} SAR"
            else:
                display = f"{value:,.2f}"
            lines.append(f"- {label}: {display} (status: {metric.get('status', 'unknown')})")

    alerts = payload.get("alerts") or []
    if alerts:
        lines.append("Alerts:")
        for alert in alerts[:6]:
            lines.append(f"  * {alert.get('message')}")

    rule_failures = payload.get("rule_failures", [])
    if rule_failures:
        lines.append("Rule failures:")
        for item in rule_failures:
            lines.append(f"  * {item.get('rule_id')}: {item.get('message')} (level={item.get('level')}, count={item.get('count')})")

    notes = payload.get("notes") or []
    if notes:
        lines.append("Notes:")
        for note in notes:
            lines.append(f"  - {note}")
    return "\n".join(lines)


STATUS_AR_LABELS: Dict[str, str] = {
    "pass": "ضمن الحدود",
    "warn": "تحذير",
    "stop": "توقف",
    "unknown": "غير محدد",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\u0621-\u064A]+", " ", value.lower()).strip()


def _question_mentions(normalized_question: str, keyword: str) -> bool:
    normalized_keyword = _normalize_text(keyword)
    if not normalized_keyword:
        return False
    return normalized_keyword in normalized_question


def _format_kpi_value_for_text(metric: Mapping[str, Any]) -> str:
    value_pct = metric.get("value_pct")
    unit = metric.get("unit")
    if value_pct is not None:
        if unit and unit not in {"%", "ratio"}:
            raw = metric.get("raw_value", value_pct)
            try:
                return f"{float(raw):,.2f} {unit}".strip()
            except (TypeError, ValueError):
                return f"{raw} {unit}".strip()
        return f"{float(value_pct):.2f}%"

    raw_value = metric.get("raw_value")
    if raw_value is None:
        return "??? ?????"
    try:
        formatted = f"{float(raw_value):,.2f}"
    except (TypeError, ValueError):
        formatted = str(raw_value)
    return f"{formatted} {unit}".strip() if unit else formatted


def _describe_kpi(metric: Mapping[str, Any]) -> str:
    label = metric.get("label") or metric.get("id") or "Metric"
    formatted = _format_kpi_value_for_text(metric)
    status = STATUS_AR_LABELS.get(metric.get("status"), STATUS_AR_LABELS["unknown"])
    warn = metric.get("warn_threshold_pct") or metric.get("warn_threshold_raw")
    stop = metric.get("stop_threshold_pct") or metric.get("stop_threshold_raw")

    parts = [f"{label}: {formatted}", f"?????? ???????: {status}"]
    threshold_parts = []
    if warn:
        threshold_parts.append(f"????? ??? ({warn})")
    if stop:
        threshold_parts.append(f"???? ??? ({stop})")
    if threshold_parts:
        parts.append("??????: " + " / ".join(threshold_parts))
    return " | ".join(parts)


def _answer_sla_question_locally(question: str, payload: Mapping[str, Any]) -> Optional[str]:
    normalized_question = _normalize_text(question)
    if not normalized_question:
        return None

    kpis = payload.get("kpis") or []
    matched_kpis: List[Mapping[str, Any]] = []
    for kpi in kpis:
        metric_id = kpi.get("id", "")
        info = SLA_METRIC_INFO.get(metric_id, {})
        keywords = set(info.get("keywords", []))
        label = kpi.get("label")
        if label:
            keywords.add(label)
        keywords.add(metric_id)
        if any(_question_mentions(normalized_question, keyword) for keyword in keywords):
            matched_kpis.append(kpi)

    if matched_kpis:
        lines = [f"?????: {payload.get('run', '??? ????')}"]
        summary = payload.get("summary") or {}
        generated_at = summary.get("last_execution") or payload.get("generated_at")
        if generated_at:
            lines.append(f"??? ?????: {generated_at}")
        overall_score = summary.get("compliance_pct")
        if overall_score is not None:
            status_ar = STATUS_AR_LABELS.get(summary.get("status"), STATUS_AR_LABELS["unknown"])
            lines.append(f"???????? ?????: {overall_score:.2f}% (??????: {status_ar})")
        lines.append("?????? ??????:")
        for kpi in matched_kpis:
            lines.append(f"- {_describe_kpi(kpi)}")
        return "\n".join(lines)

    gate = payload.get("gate") or {}
    reasons = gate.get("reasons") or []
    if reasons and any(_question_mentions(normalized_question, keyword) for keyword in ["???", "?????", "gate", "???", "?????"]):
        status_ar = STATUS_AR_LABELS.get(gate.get("status"), STATUS_AR_LABELS["unknown"])
        reason_lines = "\n".join(f"- {reason}" for reason in reasons)
        return f"?????? ??????? ???????: {status_ar}\n??????? ???????:\n{reason_lines}"

    documents = payload.get("documents") or []
    if documents and any(_question_mentions(normalized_question, keyword) for keyword in ["???", "?????", "documents", "???????"]):
        lines = ["???? ????? SLA:"]
        for document in documents:
            title = document.get("display_name") or document.get("title") or document.get("id") or "?????"
            status = STATUS_AR_LABELS.get(document.get("status"), STATUS_AR_LABELS["unknown"])
            compliance = document.get("compliance_pct") or document.get("compliance")
            term_counts = document.get("term_counts") or {}
            passed = term_counts.get("passed", 0)
            total_terms = term_counts.get("evaluated", 0)
            if compliance is not None:
                lines.append(f"- {title}: ?????? {status} | ???????? {float(compliance):.2f}% | ?????? {passed}/{total_terms}")
            else:
                lines.append(f"- {title}: ?????? {status}")
        return "\n".join(lines)

    if any(_question_mentions(normalized_question, keyword) for keyword in ["?????", "recommend", "??????"]):
        notes = payload.get("notes") or []
        summaries = payload.get("sla_results") or []
        suggestions = [note for note in notes if isinstance(note, str)]
        for entry in summaries:
            if isinstance(entry, Mapping):
                recommendation = entry.get("recommendation")
                if isinstance(recommendation, str):
                    suggestions.append(recommendation)
        if suggestions:
            unique_suggestions = list(dict.fromkeys(suggestions))
            lines = ["??????? ????? ?????? ?? ????? 09/???? SLA:"]
            lines.extend(f"- {suggestion}" for suggestion in unique_suggestions[:5])
            return "\n".join(lines)

    return None


def _classify_sla_question(question: str) -> str:
    normalized_question = _normalize_text(question)
    if not normalized_question:
        return "general_overview"

    for info in SLA_METRIC_INFO.values():
        for keyword in info.get("keywords", []):
            if _question_mentions(normalized_question, keyword):
                return "metric_detail"

    if any(_question_mentions(normalized_question, keyword) for keyword in ["سبب", "ليش", "why", "أسباب", "root"]):
        return "root_cause"
    if any(_question_mentions(normalized_question, keyword) for keyword in ["تحسين", "recommend", "اقتراح", "حل"]):
        return "improvement"
    if any(_question_mentions(normalized_question, keyword) for keyword in ["عقد", "وثيقة", "document", "اتفاق"]):
        return "document_status"
    if any(_question_mentions(normalized_question, keyword) for keyword in ["threshold", "حد", "حدود", "warn", "stop"]):
        return "thresholds"
    if any(_question_mentions(normalized_question, keyword) for keyword in ["gate", "بوابة", "رفض", "ايقاف"]):
        return "gate_status"
    return "general_overview"


def _format_sla_context(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") or {}
    context_payload: Dict[str, Any] = {
        "run": payload.get("run"),
        "generated_at": summary.get("last_execution") or payload.get("generated_at"),
        "summary": summary,
        "kpis": [
            {
                "id": kpi.get("id"),
                "label": kpi.get("label"),
                "value_pct": kpi.get("value_pct"),
                "raw_value": kpi.get("raw_value"),
                "formatted_value": _format_kpi_value_for_text(kpi),
                "status": kpi.get("status"),
                "warn_threshold_pct": kpi.get("warn_threshold_pct"),
                "stop_threshold_pct": kpi.get("stop_threshold_pct"),
            }
            for kpi in payload.get("kpis", [])
        ],
        "alerts": payload.get("alerts"),
        "documents": [
            {
                "id": document.get("id"),
                "display_name": document.get("display_name") or document.get("title"),
                "status": document.get("status"),
                "compliance_pct": document.get("compliance_pct"),
                "term_counts": document.get("term_counts"),
                "kpi_refs": document.get("kpi_refs"),
            }
            for document in payload.get("documents", [])
        ],
        "gate": payload.get("gate"),
        "rule_failures": payload.get("rule_failures"),
        "notes": payload.get("notes"),
        "metadata": payload.get("metadata"),
    }
    serialized = json.dumps(context_payload, ensure_ascii=False, indent=2)
    if len(serialized) > 6000:
        return serialized[:6000] + "\n... (truncated context)"
    return serialized


class Layer2AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Layer2AssistantRequest(BaseModel):
    run: str = Field(default="run-latest", description="Run identifier to scope catalog context.")
    question: str = Field(..., min_length=1, description="User question about Layer 2 visuals.")
    filters: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Current filter selections keyed by dimension.",
    )
    history: List[Layer2AssistantMessage] = Field(
        default_factory=list,
        description="Prior turns in the conversation.",
    )
    provider: Optional[str] = Field(default=None, description="Override LLM provider identifier.")
    model: Optional[str] = Field(default=None, description="Override LLM model identifier.")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=512, ge=128, le=2048)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)


def _collect_layer2_catalog(run: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    run_path = _resolve_run(run)
    metrics_payload: Dict[str, Any] = {"metrics": [], "metadata": {}}
    for path in _metrics_candidates(run_path):
        try:
            candidate = _normalise_metrics_payload(_load_yaml(path))
        except FileNotFoundError:
            continue
        except yaml.YAMLError as exc:
            logger.warning("layer2_metrics_catalog_parse_error at %s", path.as_posix(), exc_info=exc)
            continue
        metrics_payload = candidate
        if metrics_payload.get("metrics"):
            break

    try:
        raw_dimensions = _load_first_available(_dimension_candidates(run_path))
        dimensions_payload = _normalise_dimensions_payload(raw_dimensions)
    except HTTPException:
        dimensions_payload = _normalise_dimensions_payload({})
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("layer2_dimensions_catalog_parse_error", exc_info=exc)
        dimensions_payload = _normalise_dimensions_payload({})

    return metrics_payload, dimensions_payload


def _summarise_metrics_for_prompt(
    metrics: Sequence[Mapping[str, Any]],
    limit: int = 20,
) -> Tuple[List[str], List[Dict[str, Optional[str]]]]:
    lines: List[str] = []
    summary: List[Dict[str, Optional[str]]] = []
    seen: set[str] = set()
    for metric in metrics:
        if not isinstance(metric, Mapping):
            continue
        metric_id = str(metric.get("id") or "").strip()
        metric_title = str(metric.get("title") or "").strip()
        key = metric_id or metric_title
        if not key:
            continue
        if key.lower() in seen:
            continue
        seen.add(key.lower())
        unit = metric.get("unit") or metric.get("units")
        fmt = metric.get("fmt") or metric.get("format")
        description = metric.get("description") or metric.get("summary")
        pieces: List[str] = []
        if metric_id:
            pieces.append(metric_id)
        if metric_title and metric_title.lower() != metric_id.lower():
            pieces.append(metric_title)
        extra_parts: List[str] = []
        if unit:
            extra_parts.append(f"unit={unit}")
        if fmt:
            extra_parts.append(f"fmt={fmt}")
        if description:
            extra_parts.append(str(description))
        text = " - ".join(pieces) if pieces else ""
        if extra_parts:
            extra = "; ".join(extra_parts)
            text = f"{text} ({extra})" if text else extra
        if text:
            lines.append(f"- {text}")
            summary.append(
                {
                    "id": metric_id or None,
                    "title": metric_title or None,
                    "unit": str(unit) if unit else None,
                    "fmt": str(fmt) if fmt else None,
                }
            )
        if len(lines) >= limit:
            break
    return lines, summary


def _summarise_dimensions_for_prompt(
    dimensions: Mapping[str, Any],
    limit: int = 20,
) -> Tuple[List[str], Dict[str, List[str]]]:
    lines: List[str] = []
    summary: Dict[str, List[str]] = {"categorical": [], "numeric": [], "date": [], "bool": []}
    for key in ("categorical", "numeric", "date", "bool"):
        entries = dimensions.get(key)
        if not isinstance(entries, list):
            continue
        names: List[str] = []
        for entry in entries:
            name: Optional[str] = None
            if isinstance(entry, Mapping):
                raw = entry.get("name") or entry.get("id")
                if raw:
                    name = str(raw)
            elif isinstance(entry, str):
                name = entry
            if name:
                names.append(name)
        if not names:
            continue
        preview = ", ".join(names[:limit])
        lines.append(f"- {key}: {preview}")
        summary[key] = names[:limit]
    return lines, summary


def _sample_dimension_values(
    frame: Optional[pd.DataFrame],
    dimension_names: Sequence[str],
    *,
    limit: int = 3,
) -> Dict[str, List[str]]:
    if frame is None or frame.empty:
        return {}
    samples: Dict[str, List[str]] = {}
    sample_frame = frame.head(500)
    for name in dimension_names:
        if name not in sample_frame.columns:
            continue
        try:
            series = sample_frame[name].dropna()
        except Exception:  # pragma: no cover - defensive
            continue
        if series.empty:
            continue
        try:
            normalized = series.astype(str)
        except Exception:
            normalized = series.apply(lambda value: str(value))
        top_values = normalized.value_counts().head(limit).index.tolist()
        if top_values:
            samples[name] = [str(value) for value in top_values]
    return samples


def _format_layer2_history_block(history: Sequence[Layer2AssistantMessage]) -> str:
    if not history:
        return "No previous conversation."
    lines: List[str] = []
    for message in history[-6:]:
        role = "USER" if message.role == "user" else "ASSISTANT"
        content = message.content.strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "No previous conversation."


def _compose_layer2_user_prompt(
    *,
    question: str,
    history_block: str,
    metrics_lines: Sequence[str],
    dimensions_lines: Sequence[str],
    sample_values: Mapping[str, Sequence[str]],
    filters_text: str,
) -> str:
    metrics_block = "\n".join(metrics_lines) if metrics_lines else "No metrics available."
    dimensions_block = "\n".join(dimensions_lines) if dimensions_lines else "No dimensions available."
    samples_block = (
        json.dumps(sample_values, ensure_ascii=False)
        if sample_values
        else "No sample dimension values available."
    )
    return (
        "CATALOG CONTEXT\n"
        f"Metrics:\n{metrics_block}\n\n"
        f"Dimensions:\n{dimensions_block}\n\n"
        f"Sample dimension values:\n{samples_block}\n\n"
        f"Active filters (dimension -> values):\n{filters_text or 'none'}\n\n"
        f"Conversation history:\n{history_block}\n\n"
        "Instructions: Reply strictly in JSON with keys 'reply' (string) and 'recommendation' (object). "
        "The recommendation object may include 'metric_id', 'metric_label', 'dimension', 'chart', "
        "'filters', 'rationale', 'language', and 'confidence'. "
        "Always return 'filters' as an object mapping dimension names to an array of string values. "
        "Use the same language as the user's question when composing the reply. "
        "If the best recommendation is unsure, provide the closest helpful guidance.\n\n"
        f"QUESTION:\n{question.strip()}"
    )


def _normalise_layer2_recommendation(payload: Any) -> Dict[str, Any]:
    recommendation: Dict[str, Any] = {
        "metric_id": None,
        "metric_label": None,
        "dimension": None,
        "chart": None,
        "filters": {},
        "rationale": None,
        "language": None,
        "confidence": None,
    }
    if not isinstance(payload, Mapping):
        return recommendation

    metric_id = payload.get("metric_id") or payload.get("metric") or payload.get("metricKey")
    if metric_id:
        recommendation["metric_id"] = str(metric_id)
    metric_label = payload.get("metric_label") or payload.get("metric_name") or payload.get("metricTitle")
    if metric_label:
        recommendation["metric_label"] = str(metric_label)
    dimension = payload.get("dimension") or payload.get("group_by") or payload.get("dimensionKey")
    if dimension:
        recommendation["dimension"] = str(dimension)
    chart = payload.get("chart") or payload.get("chart_type") or payload.get("visual")
    if chart:
        recommendation["chart"] = str(chart)
    rationale = payload.get("rationale") or payload.get("reasoning") or payload.get("notes")
    if rationale:
        recommendation["rationale"] = str(rationale)
    language = payload.get("language")
    if language:
        recommendation["language"] = str(language)
    confidence = payload.get("confidence")
    if confidence:
        recommendation["confidence"] = str(confidence)

    filters_payload = payload.get("filters") or payload.get("filter_values") or {}
    filters: Dict[str, List[str]] = {}
    if isinstance(filters_payload, Mapping):
        for key, value in filters_payload.items():
            if not key:
                continue
            values: List[str] = []
            if isinstance(value, list):
                values = [str(item) for item in value if isinstance(item, (str, int, float, bool))]
            elif value is not None:
                values = [str(value)]
            if values:
                filters[str(key)] = values
    recommendation["filters"] = filters
    return recommendation


def _layer2_agent_fallback(
    question: str,
    metrics: Sequence[Mapping[str, Any]],
    dimensions: Mapping[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    lower = question.lower()
    matched_metric: Optional[Mapping[str, Any]] = None
    for metric in metrics:
        if not isinstance(metric, Mapping):
            continue
        metric_id = str(metric.get("id") or "").lower()
        metric_title = str(metric.get("title") or "").lower()
        if metric_id and metric_id in lower:
            matched_metric = metric
            break
        if metric_title and metric_title in lower:
            matched_metric = metric
            break

    categorical_entries = dimensions.get("categorical") if isinstance(dimensions, Mapping) else None
    categorical_names = []
    if isinstance(categorical_entries, list):
        for item in categorical_entries:
            if isinstance(item, Mapping):
                name = item.get("name") or item.get("id")
            else:
                name = item if isinstance(item, str) else None
            if name:
                categorical_names.append(str(name))
    matched_dimension: Optional[str] = None
    for name in categorical_names:
        if name.lower() in lower:
            matched_dimension = name
            break

    reply_parts: List[str] = []
    recommendation = {
        "metric_id": None,
        "metric_label": None,
        "dimension": None,
        "chart": None,
        "filters": {},
        "rationale": None,
        "language": None,
        "confidence": None,
    }

    if matched_metric:
        metric_id = str(matched_metric.get("id") or "") or None
        metric_label = str(matched_metric.get("title") or "") or metric_id
        recommendation["metric_id"] = metric_id
        recommendation["metric_label"] = metric_label
        reply_parts.append(
            f"Focusing on metric '{metric_label or metric_id}'."
        )
    if matched_dimension:
        recommendation["dimension"] = matched_dimension
        reply_parts.append(f"Try segmenting by '{matched_dimension}'.")

    if not reply_parts:
        metric_hints = ", ".join(
            str(metric.get("id"))
            for metric in metrics[:5]
            if isinstance(metric, Mapping) and metric.get("id")
        )
        dimension_hints = ", ".join(categorical_names[:5])
        reply_parts.append(
            "I could not match the question to a specific metric. "
            f"Available metrics include: {metric_hints or 'not specified'}."
        )
        if dimension_hints:
            reply_parts.append(f"Key dimensions: {dimension_hints}.")
        else:
            reply_parts.append("No categorical dimensions are currently defined.")

    reply = " ".join(reply_parts).strip()
    return reply or "No direct match found; please refine the question.", recommendation


class RawMetricsMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class RawMetricsLLMRequest(BaseModel):
    run: str = Field(default="run-latest", description="Run identifier to read raw metrics from.")
    top: int = Field(default=5, ge=1, le=50, description="Maximum rows per breakdown table.")
    question: str = Field(..., min_length=1, description="User question about the raw metrics.")
    history: List[RawMetricsMessage] = Field(default_factory=list, description="Previous Q&A turns.")
    provider: Optional[str] = Field(
        default=None,
        description="LLM provider identifier (defaults to RAW_METRICS_LLM_PROVIDER or openai).",
    )
    model: Optional[str] = Field(
        default=None,
        description="LLM model identifier (defaults to RAW_METRICS_LLM_MODEL or gpt-4o-mini).",
    )
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=512, ge=128, le=2048)


class SLAAssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class SLAAssistantRequest(BaseModel):
    run: str = Field(default="run-latest", description="Run identifier to read SLA compliance data from.")
    question: str = Field(..., min_length=1, description="Question scoped to SLA compliance.")
    history: List[SLAAssistantMessage] = Field(default_factory=list, description="Previous Q&A turns.")
    provider: Optional[str] = Field(default=None, description="LLM provider identifier.")
    model: Optional[str] = Field(default=None, description="LLM model identifier.")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=512, ge=128, le=1024)


def _raw_metrics_to_text(metrics: Dict[str, Any]) -> str:
    totals = metrics.get("totals", {})
    lines: List[str] = []

    total_orders = totals.get("orders")
    if total_orders is not None:
        lines.append(f"- إجمالي الطلبات: {int(total_orders)}")

    cod_orders = totals.get("orders_cod")
    if cod_orders is not None:
        share = totals.get("orders_cod_share_pct")
        share_text = f"{share}%" if share is not None else "غير متاح"
        lines.append(f"- طلبات COD: {int(cod_orders)} (حصة {share_text})")

    cod_total = totals.get("cod_total")
    if cod_total is not None:
        lines.append(f"- إجمالي تحصيل COD: {cod_total} SAR")

    cod_average = totals.get("cod_average")
    if cod_average is not None:
        lines.append(f"- متوسط تذكرة COD: {cod_average} SAR")

    cod_min = totals.get("cod_min")
    cod_max = totals.get("cod_max")
    if cod_min is not None and cod_max is not None:
        lines.append(f"- نطاق قيم COD: {cod_min}  → {cod_max} SAR")

    amount_total = totals.get("amount_total")
    if amount_total is not None:
        lines.append(f"- إجمالي القيمة لجميع طرق الدفع: {amount_total} SAR")

    breakdowns = metrics.get("breakdowns", [])
    if breakdowns:
        for breakdown in breakdowns[:3]:
            label = breakdown.get("label", breakdown.get("dimension", "البعد"))
            values = breakdown.get("values", [])
            if not values:
                continue
            lines.append(f"- {label}:")
            for value in values[:6]:
                parts = [f"{value.get('orders', 0)} طلب"]
                share = value.get("share_pct")
                if share is not None:
                    parts.append(f"حصة {share}%")
                delivered = value.get("delivered")
                if delivered:
                    parts.append(f"{int(delivered)} تم تسليمها")
                returned = value.get("returned")
                if returned:
                    parts.append(f"{int(returned)} مرتجع")
                cod_value = value.get("cod_total")
                if cod_value:
                    parts.append(f"تحصيل {cod_value} SAR")
                lines.append(f"  • {value.get('value', 'غير معروف')}: {', '.join(parts)}")

    trends = metrics.get("trends", {})
    daily = trends.get("daily", {}).get("data", [])
    if daily:
        best = max(daily, key=lambda row: row.get("orders", 0))
        lines.append(
            f"- أعلى يوم نشاط: {best.get('date')} بعدد {best.get('orders', 0)} طلب، والتحصيل {best.get('cod_total', 'غير متاح')} SAR"
        )

    order_date_range = metrics.get("order_date_range")
    if order_date_range:
        lines.append(
            f"- نطاق التواريخ في الشيت: {order_date_range.get('min', 'غير متاح')} → {order_date_range.get('max', 'غير متاح')}"
        )

    return "\n".join(lines)


def _correlations_to_text_block(correlations: Any, limit: int = 5) -> str:
    if not isinstance(correlations, dict):
        return ""

    lines: List[str] = []

    def _fmt(value: Optional[float]) -> str:
        if value is None:
            return "???"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "???"
        if not math.isfinite(numeric):
            return "???"
        return f"{numeric:.2f}"

    numeric_pairs = correlations.get("numeric") or []
    if isinstance(numeric_pairs, list) and numeric_pairs:
        lines.append("أعلى الارتباطات العددية:")
        for pair in numeric_pairs[:limit]:
            if not isinstance(pair, dict):
                continue
            left = pair.get("feature_a")
            right = pair.get("feature_b")
            if not left or not right:
                continue
            corr = _fmt(pair.get("correlation"))
            sample = pair.get("sample_size")
            sample_text = "???"
            if isinstance(sample, (int, float)):
                try:
                    if math.isfinite(float(sample)):
                        sample_text = f"{int(round(float(sample))):,}"
                except (TypeError, ValueError):
                    sample_text = "???"
            lines.append(f"- {left} ↔ {right}: r={corr} (عدد العيّنات ≈ {sample_text})")

    datetime_pairs = correlations.get("datetime") or []
    if isinstance(datetime_pairs, list) and datetime_pairs:
        lines.append("أعلى الارتباطات الزمنية:")
        for pair in datetime_pairs[:limit]:
            if not isinstance(pair, dict):
                continue
            left = pair.get("feature_a")
            right = pair.get("feature_b")
            if not left or not right:
                continue
            corr = _fmt(pair.get("correlation"))
            sample = pair.get("sample_size")
            sample_text = "???"
            if isinstance(sample, (int, float)):
                try:
                    if math.isfinite(float(sample)):
                        sample_text = f"{int(round(float(sample))):,}"
                except (TypeError, ValueError):
                    sample_text = "???"
            lines.append(f"- {left} ↔ {right}: r={corr} (عدد العيّنات ≈ {sample_text})")

    return "\n".join(lines)


@router.get("/correlations")
async def get_correlations(
    run: str = Query("run-latest"),
    top: int = Query(25, ge=1, le=200),
) -> Any:
    run_path = _resolve_run(run)
    correlations = _collect_correlations(run_path, top)
    return {
        "run": run,
        "artifacts_root": run_path.as_posix() if run_path else None,
        "top": top,
        **correlations,
    }


class CorrelationExplainRequest(BaseModel):
    run: str = Field(default="run-latest", description="Run identifier to inspect")
    feature_a: str = Field(..., description="First feature in the correlation pair")
    feature_b: str = Field(..., description="Second feature in the correlation pair")
    kind: Optional[str] = Field(
        default=None,
        description="Correlation bucket (numeric, datetime, numeric_numeric, numeric_categorical, categorical_categorical)",
    )
    language: Literal["ar", "en"] = Field(default="ar", description="Preferred response language")
    use_llm: bool = Field(default=True, description="Enable LLM-based narrative generation")
    force_refresh: bool = Field(default=False, description="Ignore cached explanation if present")
    provider: Optional[str] = Field(default=None, description="Override LLM provider identifier")
    model: Optional[str] = Field(default=None, description="Override LLM model identifier")
    temperature: Optional[float] = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=600, ge=128, le=2000)


class ChartExplainRequest(BaseModel):
    chart_title: str = Field(..., description="Title or description of the chart")
    chart_type: Optional[str] = Field(default="line", description="Chart type (line, bar, area, etc.)")
    data_summary: Optional[str] = Field(default=None, description="Summary of chart data")
    business_layer: Optional[Literal["operational", "commercial", "financial", "general"]] = Field(
        default=None, 
        description="Business layer context: operational (operations/delivery), commercial (sales/customers), financial (costs/revenue), or general"
    )
    language: Literal["ar", "en"] = Field(default="ar", description="Preferred response language")
    use_llm: bool = Field(default=True, description="Enable LLM-based explanation")
    provider: Optional[str] = Field(default=None, description="Override LLM provider")
    model: Optional[str] = Field(default=None, description="Override LLM model")
    temperature: Optional[float] = Field(default=0.3, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=400, ge=128, le=1500)


@router.post("/correlations/explain")
async def explain_correlation(request: CorrelationExplainRequest) -> Any:
    run_path = _resolve_run(request.run)
    if run_path is None:
        raise HTTPException(status_code=404, detail=f"Run '{request.run}' not found.")

    record = _find_correlation_entry(
        run_path,
        request.feature_a,
        request.feature_b,
        kind=request.kind,
        top=250,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Correlation pair not available in current artifacts.")

    kind = record.get("kind") or request.kind or "numeric"
    cache_root = run_path.parent if run_path.parent else run_path
    cache = CorrelationExplanationCache(cache_root)
    cache_key = cache.make_key(
        run=request.run,
        feature_a=str(record.get("feature_a")),
        feature_b=str(record.get("feature_b")),
        kind=kind,
        language=request.language,
        correlation=record.get("correlation"),
    )

    if not request.force_refresh:
        cached_entry = cache.get(cache_key)
        if cached_entry:
            cached_copy = dict(cached_entry)
            cached_copy["mode"] = cached_copy.get("mode", "cache")
            return {
                "run": request.run,
                "feature_a": record.get("feature_a"),
                "feature_b": record.get("feature_b"),
                "kind": kind,
                "correlation": record.get("correlation"),
                "record": record,
                "explanation": cached_copy,
            }

    explanation = _build_correlation_explanation(record, request)
    cache_payload = {
        **explanation,
        "run": request.run,
        "feature_a": record.get("feature_a"),
        "feature_b": record.get("feature_b"),
        "kind": kind,
        "language": request.language,
        "correlation": record.get("correlation"),
        "generated_at": explanation.get("generated_at") or datetime.utcnow().isoformat(),
    }
    cache.set(cache_key, cache_payload)

    response_payload = dict(cache_payload)
    return {
        "run": request.run,
        "feature_a": record.get("feature_a"),
        "feature_b": record.get("feature_b"),
        "kind": kind,
        "correlation": record.get("correlation"),
        "record": record,
        "explanation": response_payload,
    }


@router.post("/charts/explain")
async def explain_chart(request: ChartExplainRequest) -> Any:
    """Explain a chart or visualization using LLM with domain and layer-specific context."""
    if not request.use_llm:
        fallback_text = (
            f"رسم بياني من نوع {request.chart_type}: {request.chart_title}"
            if request.language == "ar"
            else f"{request.chart_type} chart: {request.chart_title}"
        )
        return {
            "explanation": fallback_text,
            "mode": "fallback",
            "chart_title": request.chart_title,
            "chart_type": request.chart_type,
        }

    provider = request.provider or DEFAULT_CORRELATION_LLM_PROVIDER
    model = request.model or DEFAULT_CORRELATION_LLM_MODEL
    
    if not provider or not model:
        fallback_text = (
            f"تحليل الرسم البياني: {request.chart_title}"
            if request.language == "ar"
            else f"Chart analysis: {request.chart_title}"
        )
        return {
            "explanation": fallback_text,
            "mode": "fallback",
            "chart_title": request.chart_title,
        }

    # Determine business layer context (explicit or auto-detect)
    layer = request.business_layer
    if not layer:
        # Auto-detect from chart title
        chart_lower = (request.chart_title or "").lower()
        if any(keyword in chart_lower for keyword in ["تكلفة", "إيراد", "ربح", "cost", "revenue", "profit", "مالي", "financial"]):
            layer = "financial"
        elif any(keyword in chart_lower for keyword in ["سائق", "مركبة", "توصيل", "driver", "vehicle", "delivery", "عملياتي", "operational"]):
            layer = "operational"
        elif any(keyword in chart_lower for keyword in ["عميل", "طلب", "رضا", "customer", "order", "satisfaction", "تجاري", "commercial"]):
            layer = "commercial"
        else:
            layer = "general"
    
    # Layer-specific expertise configuration
    layer_configs = {
        "financial": [
            "أنت مستشار مالي متخصص في تحليل تكاليف وإيرادات عمليات الشحن.",
            "ركز على الربحية، هوامش الربح، وتحسين التكاليف التشغيلية.",
            "قدم توصيات لتحسين الأداء المالي والعائد على الاستثمار.",
        ],
        "operational": [
            "أنت مستشار عمليات متخصص في تحسين عمليات الشحن والتوصيل.",
            "ركز على كفاءة التوصيل، أداء السائقين، واستغلال المركبات.",
            "قدم توصيات لتحسين سرعة التوصيل وتقليل الوقت الضائع.",
        ],
        "commercial": [
            "أنت مستشار تجاري متخصص في تحليل سلوك العملاء وأداء المبيعات.",
            "ركز على رضا العملاء، معدلات التحويل، وقيمة العميل مدى الحياة.",
            "قدم توصيات لتحسين تجربة العميل وزيادة الإيرادات.",
        ],
        "general": [
            "أنت مستشار بيانات متخصص في قطاع الشحن والتوصيل اللوجستي.",
            "ركز على الكفاءة التشغيلية، الجودة، ورضا العملاء.",
            "قدم توصيات قابلة للتنفيذ لتحسين الأداء العام.",
        ],
    }
    
    layer_context = layer_configs.get(layer, layer_configs["general"])
    layer_context.extend([
        "قدّم شرحاً واضحاً ومختصراً للرسوم البيانية في 2-3 جمل.",
        "ركز على الاتجاهات والأنماط الرئيسية والقيم البارزة.",
    ])
    
    language_name = "العربية" if request.language == "ar" else "English"
    system_prompt = compose_system_prompt(
        layer_context,
        enforce_data_scope=True,
    )
    
    data_context = request.data_summary or "بيانات الرسم البياني"
    user_prompt = (
        f"الرسم البياني: {request.chart_title}\n"
        f"نوع الرسم: {request.chart_type}\n"
        f"ملخص البيانات: {data_context}\n\n"
        "المهمة: اشرح هذا الرسم البياني بفقرة واحدة قصيرة (2-3 جمل) تركز على:\n"
        "1. الاتجاه العام أو النمط الرئيسي\n"
        "2. أي ملاحظة مهمة أو قيمة بارزة\n"
        "3. توصية عملية واحدة إن أمكن\n\n"
        f"اكتب الإجابة كاملة باللغة {language_name}."
    )

    try:
        response = invoke_model(
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=request.max_tokens or 400,
            temperature=request.temperature or 0.3,
            top_p=0.9,
            timeout=60,
        )
        
        return {
            "explanation": response.content.strip(),
            "mode": "llm",
            "chart_title": request.chart_title,
            "chart_type": request.chart_type,
            "business_layer": layer,  # Return detected/specified layer
            "provider": response.provider,
            "model": response.model,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "cost_estimate": response.cost_estimate,
            "duration_s": response.duration_s,
        }
    except Exception as exc:
        logger.warning("chart_llm_failure", exc_info=exc)
        fallback_text = (
            f"تحليل الرسم البياني: {request.chart_title}. {data_context}"
            if request.language == "ar"
            else f"Chart analysis: {request.chart_title}. {data_context}"
        )
        return {
            "explanation": fallback_text,
            "mode": "fallback_after_error",
            "business_layer": layer,  # Return layer even on error
            "chart_title": request.chart_title,
            "error": str(exc),
        }


@router.get("/sla")
async def get_sla(run: str = Query("run-latest")) -> Any:
    return _build_sla_payload(run)


@router.get("/sla/sop")
async def get_sla_sop(run: str = Query("run-latest")) -> Any:
    expectations_payload, recommendations_payload, run_path = _load_sop_payloads(run)
    documents = expectations_payload.get("documents", [])
    document_summaries = [
        {
            "title": doc.get("title"),
            "source": doc.get("source"),
            "path": doc.get("path"),
            "run_id": doc.get("run_id"),
        }
        for doc in documents
        if isinstance(doc, Mapping)
    ]
    return {
        "run": run_path.name,
        "expectations": expectations_payload.get("expectations", []),
        "documents": document_summaries,
        "provider": expectations_payload.get("provider"),
        "model": expectations_payload.get("model"),
        "logs": expectations_payload.get("logs", []),
        "recommendations": (recommendations_payload or {}).get("recommendations", []),
    }


@router.get("/sla/gap-analysis")
async def get_sla_gap_analysis(run: str = Query("run-latest")) -> Any:
    expectations_payload, recommendations_payload, run_path = _load_sop_payloads(run)
    sla_payload = _build_sla_payload(run)
    documents = expectations_payload.get("documents", [])
    document_summaries = [
        {
            "title": doc.get("title"),
            "source": doc.get("source"),
            "path": doc.get("path"),
            "run_id": doc.get("run_id"),
        }
        for doc in documents
        if isinstance(doc, Mapping)
    ]
    analysis = build_sop_gap_analysis(
        expectations_payload.get("expectations", []),
        sla_payload,
        SLA_METRIC_INFO,
    )
    return {
        "run": run_path.name,
        "analysis": analysis,
        "expectations_meta": {
            "provider": expectations_payload.get("provider"),
            "model": expectations_payload.get("model"),
            "documents": document_summaries,
        },
        "recommendations": (recommendations_payload or {}).get("recommendations", []),
    }


@router.get("/data")
async def get_data(
    run: str = Query("run-latest"),
    limit: int = Query(MAX_ROWS, ge=1, le=MAX_ROWS),
) -> Any:
    run_path = _resolve_run(run)
    frames: List[pd.DataFrame] = []

    for parquet in _collect_parquet_files(run_path):
        try:
            frame = pd.read_parquet(parquet)
        except Exception:
            continue
        if frame.empty:
            continue
        frames.append(frame)
        if sum(frame.shape[0] for frame in frames) >= limit:
            break

    if not frames:
        return {"rows": [], "source": None}

    dataset = pd.concat(frames, ignore_index=True).head(limit)
    return {
        "rows": dataset.to_dict(orient="records"),
        "columns": dataset.columns.tolist(),
        "source": run_path.as_posix() if run_path else None,
        "count": int(dataset.shape[0]),
    }



@router.post("/sla/assistant")
async def converse_sla(request: SLAAssistantRequest) -> Any:
    payload = _build_sla_payload(request.run)
    summary_text = _build_sla_text(payload)
    intent = _classify_sla_question(request.question)
    local_reply = _answer_sla_question_locally(request.question, payload)
    structured_context = _format_sla_context(payload)
    history_lines: List[str] = []
    for message in request.history[-6:]:
        role = "USER" if message.role == "user" else "ASSISTANT"
        history_lines.append(f"{role}: {message.content.strip()}")
    history_block = "\n".join(history_lines) if history_lines else "No previous conversation."

    if local_reply:
        return {
            "reply": {"reply": local_reply, "source": "local"},
            "provider": "local-rules",
            "model": "heuristic-v1",
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_estimate": 0.0,
            "duration_s": 0.0,
            "context": {"metrics": payload, "summary": summary_text, "intent": intent, "mode": "local"},
        }

    system_prompt = compose_system_prompt(
        [
            "حلّل مؤشرات SLA في ضوء البيانات المرفقة، وقدّم جوابًا تنفيذيًا بالعربية يتضمن الأرقام الفعلية "
            "وملخصًا واضحًا، مع قسم اختياري بعنوان 'إجراءات مقترحة' عندما يتطلب السياق. "
            "إذا خرج السؤال عن نطاق SLA فوضّح الحدود بلطف."
        ],
        enforce_data_scope=True,
    )

    user_prompt = (
        f"سياق منظم (JSON):\n{structured_context}\n\n"
        f"ملخص نصي:\n{summary_text}\n\n"
        f"تصنيف السؤال: {intent}\n"
        f"سجل المحادثة السابق:\n{history_block}\n\n"
        "التعليمات: استخدم البيانات المرفقة للإجابة عن السؤال. "
        "ركز على تفسير الحالة الحالية، واذكر إن وُجدت حدود التحذير/التوقف، واضف توصية عملية قصيرة إن كانت الحالة Warn أو Stop. "
        "اكتب الرد بالعربية وبنية واضحة يسهل قراءتها.\n\n"
        f"السؤال: {request.question.strip()}"
    )

    provider = request.provider or DEFAULT_RAW_LLM_PROVIDER
    model = request.model or DEFAULT_RAW_LLM_MODEL
    try:
        llm_response = invoke_model(
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=0.9,
            timeout=90,
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        fallback_reply = (
            "تعذر الوصول إلى مزود الـLLM حالياً.\n"
            "نقدّم لك موجزاً محلياً للحالة إلى حين استعادة الخدمة:\n\n"
            f"{summary_text or 'لا تتوفر بيانات SLA مفصلة في هذا التشغيل.'}"
        )
        return {
            "reply": {
                "reply": fallback_reply,
                "source": "local-fallback",
                "error": str(exc),
            },
            "provider": "local-fallback",
            "model": "sla-fallback",
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_estimate": 0.0,
            "duration_s": 0.0,
            "context": {
                "metrics": payload,
                "summary": summary_text,
                "intent": intent,
                "mode": "fallback",
                "error": str(exc),
            },
        }

    try:
        parsed_content = json.loads(llm_response.content)
    except Exception:
        parsed_content = {"reply": llm_response.content}

    return {
        "reply": parsed_content,
        "provider": llm_response.provider,
        "model": llm_response.model,
        "tokens_in": llm_response.tokens_in,
        "tokens_out": llm_response.tokens_out,
        "cost_estimate": llm_response.cost_estimate,
        "duration_s": llm_response.duration_s,
        "context": {
            "metrics": payload,
            "summary": summary_text,
            "intent": intent,
            "mode": "llm",
        },
    }


@router.get("/metrics/raw")
async def get_raw_metrics(
    run: str = Query("run-latest"),
    top: int = Query(5, ge=1, le=50),
) -> Any:
    return _compute_raw_metrics(run, top)


@router.post("/metrics/raw/llm")
async def converse_raw_metrics(request: RawMetricsLLMRequest) -> Any:
    metrics = _compute_raw_metrics(request.run, request.top)
    summary_text = _raw_metrics_to_text(metrics)
    correlation_block = _correlations_to_text_block(metrics.get("correlations"), limit=6)
    if correlation_block:
        summary_text = f"{summary_text}\n\n{correlation_block}" if summary_text else correlation_block

    history_lines = []
    for message in request.history[-6:]:
        role = "USER" if message.role == "user" else "ASSISTANT"
        history_lines.append(f"{role}: {message.content.strip()}")
    history_block = "\n".join(history_lines) if history_lines else "No previous conversation."

    system_prompt = compose_system_prompt(
        [
            "حلّل المؤشرات الخام كما هي، وقدّم توصيات تشغيلية أو مالية مبنية على البيانات المتاحة فقط. "
            "اذكر بوضوح أي حدود واقترح العودة للمراحل اللاحقة عند الحاجة."
        ],
        enforce_data_scope=True,
    )

    user_prompt = (
        f"ملخص الأرقام الخام:\n{summary_text}\n\n"
        f"سجل المحادثة:\n{history_block}\n\n"
        "التعليمات: أجب بالاعتماد على هذه المرحلة فقط. أعد الاستجابة بصيغة JSON تحتوي على المفتاح reply (نص عربي موجز) "
        "والمفتاح الاختياري recommendations (قائمة من جمل قصيرة). إذا لم تتوفر بيانات كافية فاذكر ذلك.\n\n"
        f"السؤال الحالي:\n{request.question.strip()}"
    )

    provider = request.provider or DEFAULT_RAW_LLM_PROVIDER
    model = request.model or DEFAULT_RAW_LLM_MODEL
    try:
        llm_response = invoke_model(
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=0.9,
            timeout=90,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"LLM request failed: {exc}") from exc

    try:
        parsed_content = json.loads(llm_response.content)
    except Exception:
        parsed_content = {"reply": llm_response.content}

    return {
        "reply": parsed_content,
        "provider": llm_response.provider,
        "model": llm_response.model,
        "tokens_in": llm_response.tokens_in,
        "tokens_out": llm_response.tokens_out,
        "cost_estimate": llm_response.cost_estimate,
        "duration_s": llm_response.duration_s,
        "metrics": metrics,
    }


def _safe_read_payload(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_time_points(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return []
    if frame.empty:
        return []
    points: List[Dict[str, Any]] = []
    sorted_frame = frame.sort_values(by="time_bucket")
    for _, row in sorted_frame.iterrows():
        timestamp_raw = row.get("time_bucket")
        if pd.isna(timestamp_raw):
            continue
        timestamp = str(timestamp_raw)
        value_raw = row.get("n") or 0
        try:
            value = int(value_raw)
        except (TypeError, ValueError):
            value = 0
        share_raw = row.get("share") or 0
        try:
            share = float(share_raw)
        except (TypeError, ValueError):
            share = 0.0
        points.append({"timestamp": timestamp, "value": value, "share": share})
    return points


def _build_network_graph(insights_payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    if isinstance(insights_payload, Mapping):
        for entry in insights_payload.get("insights", []) or []:
            if not isinstance(entry, Mapping):
                continue
            relation = entry.get("relation")
            left = None
            right = None
            if isinstance(relation, str) and "<->" in relation:
                lhs, rhs = relation.split("<->", 1)
                left, right = lhs.strip(), rhs.strip()
            else:
                left = str(entry.get("kpi") or "").strip() or None
                right = str(entry.get("segment") or entry.get("feature") or entry.get("bucket") or "").strip() or None
            if not left or not right:
                continue
            kpi_label = str(entry.get("kpi") or "").strip()
            direction = entry.get("direction")
            strength_raw = entry.get("strength") or entry.get("effect") or 0.0
            try:
                strength = abs(float(strength_raw))
            except (TypeError, ValueError):
                strength = 0.0
            coverage_raw = entry.get("coverage") or 0.0
            try:
                coverage = float(coverage_raw)
            except (TypeError, ValueError):
                coverage = 0.0
            confidence_raw = entry.get("confidence") or 0.0
            try:
                confidence = float(confidence_raw)
            except (TypeError, ValueError):
                confidence = 0.0

            if left not in nodes:
                nodes[left] = {
                    "id": left,
                    "label": left,
                    "type": "kpi" if left == kpi_label else "feature",
                    "score": max(confidence, coverage),
                }
            else:
                nodes[left]["score"] = max(nodes[left].get("score", 0.0), max(confidence, coverage))
            if right not in nodes:
                nodes[right] = {
                    "id": right,
                    "label": right,
                    "type": "feature" if right != kpi_label else "kpi",
                    "score": max(confidence, coverage),
                }
            else:
                nodes[right]["score"] = max(nodes[right].get("score", 0.0), max(confidence, coverage))

            edges.append(
                {
                    "source": left,
                    "target": right,
                    "value": round(strength or 0.05, 4),
                    "label": direction,
                }
            )
    categories = []
    for node in nodes.values():
        node_type = node.get("type", "feature")
        if node_type not in categories:
            categories.append(node_type)
        node["category"] = categories.index(node_type)
        node["score"] = round(float(node.get("score") or 0.0), 4)
        node["symbolSize"] = 30 + 40 * node["score"]
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "categories": categories,
    }


def _build_sankey_payload(insights_payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    nodes: List[str] = []
    links: List[Dict[str, Any]] = []
    if isinstance(insights_payload, Mapping):
        for entry in insights_payload.get("insights", []) or []:
            if not isinstance(entry, Mapping):
                continue
            kpi = str(entry.get("kpi") or "KPI").strip()
            bucket = str(entry.get("bucket") or entry.get("direction") or "MIXED").strip()
            if not bucket:
                continue
            if kpi not in nodes:
                nodes.append(kpi)
            if bucket not in nodes:
                nodes.append(bucket)
            coverage = entry.get("coverage") or 0.0
            strength = entry.get("strength") or 0.0
            try:
                weight = max(float(coverage), abs(float(strength)))
            except (TypeError, ValueError):
                weight = 0.05
            links.append(
                {
                    "source": kpi,
                    "target": bucket,
                    "value": round(max(weight, 0.05), 4),
                    "label": entry.get("relation"),
                }
            )
    return {"nodes": nodes, "links": links}


def _build_anomaly_timeline(
    time_points: List[Dict[str, Any]],
    diagnostics_payload: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    anomalies: List[Dict[str, Any]] = []
    if isinstance(diagnostics_payload, Mapping):
        anomaly_block = diagnostics_payload.get("anomalies")
        if isinstance(anomaly_block, Mapping):
            records = anomaly_block.get("records") or []
            for index, record in enumerate(records[:5]):
                if not isinstance(record, Mapping):
                    continue
                z_raw = record.get("z_score")
                try:
                    severity_score = abs(float(z_raw))
                except (TypeError, ValueError):
                    severity_score = 0.0
                severity = "medium"
                if severity_score >= 4:
                    severity = "critical"
                elif severity_score >= 3:
                    severity = "high"
                label_parts = []
                for key, value in record.items():
                    if key.startswith("_") or key in {"z_score"}:
                        continue
                    label_parts.append(f"{key}={value}")
                label = ", ".join(label_parts) or f"Signal {index + 1}"
                timestamp = time_points[min(index, len(time_points) - 1)]["timestamp"] if time_points else f"S{index + 1}"
                anomalies.append(
                    {
                        "timestamp": timestamp,
                        "label": label,
                        "severity": severity,
                        "score": round(severity_score, 3),
                    }
                )
    if not anomalies and time_points:
        sorted_points = sorted(time_points, key=lambda item: item.get("value", 0), reverse=True)
        for point in sorted_points[:3]:
            anomalies.append(
                {
                    "timestamp": point["timestamp"],
                    "label": "High volume",
                    "severity": "high",
                    "score": float(point.get("value", 0)),
                }
            )
    series = [
        {
            "name": "Orders",
            "points": [
                {
                    "timestamp": point["timestamp"],
                    "value": point["value"],
                    "share": round(float(point.get("share", 0.0)), 4),
                }
                for point in time_points
            ],
        }
    ]
    return {"metric": "Orders Volume", "series": series, "anomalies": anomalies}


def _build_predictive_trends(time_points: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not time_points:
        return {
            "metric": "Orders Volume",
            "series": [],
            "unit": "orders",
            "horizon": "0d",
        }
    actual_points = [
        {"timestamp": point["timestamp"], "value": point["value"]}
        for point in time_points
    ]
    forecast_points: List[Dict[str, Any]] = []
    if len(actual_points) >= 2:
        try:
            last_date = datetime.fromisoformat(actual_points[-1]["timestamp"])
        except ValueError:
            last_date = datetime.utcnow()
        try:
            previous_value = float(actual_points[-2]["value"])
        except (TypeError, ValueError):
            previous_value = float(actual_points[-1]["value"])
        try:
            last_value = float(actual_points[-1]["value"])
        except (TypeError, ValueError):
            last_value = previous_value
        growth = last_value - previous_value
        for step in range(1, 4):
            horizon_date = (last_date + timedelta(days=step)).date().isoformat()
            next_value = max(last_value + growth * step, 0.0)
            forecast_points.append({"timestamp": horizon_date, "value": round(next_value, 2)})

    series = [
        {"name": "Actual", "kind": "actual", "points": actual_points},
    ]
    if forecast_points:
        series.append({"name": "Forecast", "kind": "forecast", "points": forecast_points})
    return {
        "metric": "Orders Volume",
        "unit": "orders",
        "horizon": f"{len(forecast_points)}d",
        "series": series,
    }


def _collect_knime_profile(run_path: Path, run_key: str) -> Dict[str, Any]:
    knime_root = run_path / "phase_07_knime"
    run_meta = _safe_read_payload(knime_root / "run_meta.json")
    report = _collect_knime_report(run_path)
    files: List[Dict[str, Any]] = report.get("profile_files", [])
    dq_results = report.get("dq_report", {}).get("results", []) if isinstance(report, Mapping) else []
    insight_items = report.get("insights", {}).get("items", []) if isinstance(report, Mapping) else []
    exports = report.get("exports", []) if isinstance(report, Mapping) else []
    dq_failed = sum(
        1
        for entry in dq_results
        if isinstance(entry, Mapping)
        and (
            (entry.get("passed") is False)
            or str(entry.get("status", "")).lower() in {"fail", "failed"}
        )
    )
    coverage = None
    dq_coverage = report.get("dq_coverage") if isinstance(report, Mapping) else None
    if isinstance(dq_coverage, Mapping):
        summary = dq_coverage.get("summary")
        if isinstance(summary, Mapping):
            coverage_value = summary.get("coverage")
            if coverage_value is not None:
                try:
                    coverage = float(coverage_value)
                except (TypeError, ValueError):
                    coverage = None
    report_summary = {
        "dq_rules": len(dq_results),
        "dq_failed": dq_failed,
        "insight_count": len(insight_items),
        "export_count": len(exports),
        "coverage": coverage,
    }
    data_parquet: Optional[Dict[str, Any]] = None
    snapshot = _load_knime_snapshot(run_path.name if run_path else run_key, limit=10, offset=0)
    if snapshot:
        data_parquet = {
            "path": snapshot.get("path"),
            "rows": snapshot.get("total_rows"),
            "columns": snapshot.get("columns"),
            "preview": snapshot.get("rows"),
            "updated_at": snapshot.get("updated_at"),
            "size_bytes": snapshot.get("size_bytes"),
        }
    return {
        "run_id": (run_meta or {}).get("run_id") if isinstance(run_meta, Mapping) else run_path.name,
        "mode": (run_meta or {}).get("prompt", {}).get("mode") if isinstance(run_meta, Mapping) else None,
        "files": files,
        "metadata": run_meta if isinstance(run_meta, Mapping) else None,
        "data_parquet": data_parquet,
        "report_summary": report_summary,
    }


def _load_advanced_bundle(stage08_dir: Path) -> Dict[str, Any]:
    advanced_dir = stage08_dir / "advanced"
    if not advanced_dir.exists():
        return {}
    bundle: Dict[str, Any] = {}

    summary_payload = _safe_read_payload(advanced_dir / "summary.json")
    if isinstance(summary_payload, Mapping):
        bundle["summary"] = summary_payload

    for name in ("cluster_summary", "anomalies", "correlation_matrix"):
        payload = _safe_read_payload(advanced_dir / f"{name}.json")
        if isinstance(payload, Mapping):
            bundle[name] = payload

    forecast_path = advanced_dir / "orders_forecast.parquet"
    if forecast_path.exists():
        try:
            forecast_df = pd.read_parquet(forecast_path)
            bundle["orders_forecast"] = {
                "path": forecast_path.as_posix(),
                "rows": len(forecast_df),
                "preview": forecast_df.head(20).to_dict(orient="records"),
            }
        except Exception as exc:  # pragma: no cover - defensive
            bundle["orders_forecast"] = {
                "path": forecast_path.as_posix(),
                "error": str(exc),
            }
    return bundle


def _load_stage09_business_bundle(run_path: Path) -> Dict[str, Any]:
    stage09_dir = run_path / "stage_09_business_validation"
    if not stage09_dir.exists():
        return {}
    bundle: Dict[str, Any] = {}
    gate_payload = _safe_read_payload(stage09_dir / "gate.json")
    diagnostics_payload = _safe_read_payload(stage09_dir / "diagnostics.json")
    validation_payload = _safe_read_payload(stage09_dir / "validation_report.json")
    data_health_payload = _safe_read_payload(stage09_dir / "data_health.json")
    if isinstance(gate_payload, Mapping):
        bundle["gate"] = gate_payload
    if isinstance(diagnostics_payload, Mapping):
        bundle["diagnostics"] = diagnostics_payload
    if isinstance(validation_payload, Mapping):
        bundle["validation_report"] = validation_payload
    if isinstance(data_health_payload, Mapping):
        bundle["data_health"] = data_health_payload
    return bundle


@router.get("/knime-data")
async def get_knime_data(
    run: str = Query("run-latest"),
    limit: int = Query(250, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> Any:
    snapshot = _load_knime_snapshot(run, limit, offset)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"KNIME data not found for run '{run}'.")
    return snapshot


@router.get("/knime-report")
async def get_knime_report(
    run: str = Query("run-latest"),
) -> Any:
    run_path = _resolve_run(run)
    if not run_path:
        raise HTTPException(status_code=404, detail=f"Run '{run}' not found.")
    report = _collect_knime_report(run_path)
    return report


def _compose_intelligence_response(run: str, run_path: Path) -> Dict[str, Any]:
    stage08_dir = run_path / "stage_08_insights"
    insights_payload = _safe_read_payload(stage08_dir / "insights_report.json")
    diagnostics_payload = _safe_read_payload(stage08_dir / "diagnostics.json")
    time_points = _load_time_points(stage08_dir / "time_stats.parquet")
    advanced_bundle = _load_advanced_bundle(stage08_dir)
    business_bundle = _load_stage09_business_bundle(run_path)
    return {
        "run": run,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "network": _build_network_graph(insights_payload if isinstance(insights_payload, Mapping) else None),
        "sankey": _build_sankey_payload(insights_payload if isinstance(insights_payload, Mapping) else None),
        "anomalies": _build_anomaly_timeline(time_points, diagnostics_payload if isinstance(diagnostics_payload, Mapping) else None),
        "predictive": _build_predictive_trends(time_points),
        "advanced": advanced_bundle or None,
        "business_validation": business_bundle or None,
        "knime": _collect_knime_profile(run_path, run),
    }


@router.get("/intelligence")
async def get_intelligence(
    run: str = Query("run-latest"),
) -> Any:
    run_path = _resolve_run(run)
    if not run_path:
        raise HTTPException(status_code=404, detail=f"Run '{run}' not found.")
    payload = _compose_intelligence_response(run, run_path)
    return payload


@router.get("/orders")
async def get_orders(
    run: str = Query("run-latest"),
    limit: int = Query(MAX_ROWS, ge=1, le=MAX_ROWS),
) -> Any:
    frame = _load_orders_dataset(run)
    if frame is None:
        return await get_data(run=run, limit=limit)

    dataset = frame.head(limit)
    def safe_int(val):
        try:
            if isinstance(val, float) and val.is_integer():
                return int(val)
            elif isinstance(val, int):
                return val
            else:
                return val
        except Exception:
            return val

    rows = dataset.to_dict(orient="records")
    # Safely convert any float values that are actually integers
    for row in rows:
        for k, v in row.items():
            row[k] = safe_int(v)

    count = safe_int(dataset.shape[0])
    return {
        "rows": rows,
        "columns": list(dataset.columns),
        "count": count,
        "source": f"orders:{run}",
    }


@router.post("/layer2/assistant")
async def converse_layer2_assistant(request: Layer2AssistantRequest) -> Any:
    metrics_payload, dimensions_payload = _collect_layer2_catalog(request.run)
    metrics_lines, metrics_summary = _summarise_metrics_for_prompt(metrics_payload.get("metrics", []))
    dimensions_lines, dimension_summary = _summarise_dimensions_for_prompt(dimensions_payload)

    dataset = _load_orders_dataset(request.run)
    categorical_names = dimension_summary.get("categorical", []) or []
    dimension_samples = _sample_dimension_values(dataset, categorical_names)

    history_block = _format_layer2_history_block(request.history)
    filters_text = json.dumps(request.filters, ensure_ascii=False) if request.filters else "none"

    system_prompt = compose_system_prompt(
        [
            "You are the Layer 2 analytics assistant for MindQ BI. Analyse bilingual questions (Arabic or English) "
            "and map them to the provided metrics, dimensions, and filters. Propose a relevant visual summary without "
            "inventing unseen data.",
            "Return JSON only. Any recommendation must reference existing catalog items and stay within scope.",
        ],
        enforce_data_scope=True,
    )
    user_prompt = _compose_layer2_user_prompt(
        question=request.question,
        history_block=history_block,
        metrics_lines=metrics_lines,
        dimensions_lines=dimensions_lines,
        sample_values=dimension_samples,
        filters_text=filters_text,
    )

    provider = request.provider or DEFAULT_LAYER2_AGENT_PROVIDER
    model = request.model or DEFAULT_LAYER2_AGENT_MODEL

    llm_response = None
    used_fallback = False
    try:
        llm_response = invoke_model(
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            timeout=90,
        )
        try:
            parsed_content = json.loads(llm_response.content)
        except Exception:
            parsed_content = {"reply": llm_response.content}
        reply_text = str(parsed_content.get("reply") or parsed_content.get("message") or "").strip()
        recommendation = _normalise_layer2_recommendation(parsed_content.get("recommendation"))
        if not reply_text:
            raise ValueError("Empty reply from LLM")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("layer2_assistant_llm_failure", exc_info=exc)
        reply_text, recommendation = _layer2_agent_fallback(
            request.question,
            metrics_payload.get("metrics", []),
            dimensions_payload,
        )
        used_fallback = True
        llm_response = None

    context_summary = {
        "metrics": metrics_summary,
        "dimensions": dimension_summary,
        "samples": dimension_samples,
        "filters": request.filters,
    }

    return {
        "reply": reply_text,
        "recommendation": recommendation,
        "provider": provider,
        "model": model,
        "tokens_in": llm_response.tokens_in if llm_response else 0,
        "tokens_out": llm_response.tokens_out if llm_response else 0,
        "cost_estimate": llm_response.cost_estimate if llm_response else 0.0,
        "duration_s": llm_response.duration_s if llm_response else 0.0,
        "context": context_summary,
        "used_fallback": used_fallback,
    }


