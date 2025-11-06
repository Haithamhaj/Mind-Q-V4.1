from __future__ import annotations

import importlib
import json
import os
import shutil
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import asyncio
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple, Union

import anyio
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, root_validator
from dotenv import dotenv_values

from src.app.api.bi import router as bi_router
from src.app.api.pipeline import router as pipeline_router
from src.app.services.pipeline_api.timeline import build_run_timeline
from src.app.services.stage_07_knime_bridge import impl as knime_bridge_impl
from shared.run_events import PhaseRunRecorder, derive_phase_identity

try:  # pragma: no cover - optional patch for modern Polars
    import polars as pl  # type: ignore

    if not hasattr(pl.Series, "apply"):  # pragma: no cover - compatibility shim
        def _series_apply(self, func, return_dtype: Optional["pl.DataType"] = None):  # type: ignore[override]
            dtype = return_dtype or pl.Utf8
            return self.map_elements(func, return_dtype=dtype)

        pl.Series.apply = _series_apply  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - defensive
    pl = None  # type: ignore

logger = logging.getLogger(__name__)

ARTIFACTS_ROOT_DEFAULT = Path("artifacts")
PROJECT_ROOT = Path(__file__).resolve().parents[5]
BACKEND_ROOT = PROJECT_ROOT / "backend"

PHASE_MODULES = {
    "01_ingestion": "phases.01_ingestion.impl",
    "02_quality": "phases.02_quality.impl",
    "03_schema": "phases.03_schema.impl",
    "03_5_textops": "backend.src.app.services.stage_03_5_textops.impl",
    "04_profile": "phases.04_profile.impl",
    "05_missing": "phases.05_missing.impl",
    "06_standardize": "phases.06_standardize.impl",
    "06_feature_eng": "phases.06_feature_eng.impl",
    "07_readiness": "phases.07_readiness.impl",
    "07_7_business_correlations": "phases.07_7_business_correlations.impl",
    "07_5_feature_report": "phases.07_5_feature_report.impl",
    "07_6_llm_summary": "phases.07_6_llm_summary.impl",
    "07_knime_bridge": "src.app.services.stage_07_knime_bridge.impl",
    "08_insights": "src.app.services.stage_08_insights.impl",
    "09_business_validation": "phases.09_business_validation.impl",
    "09_5_causal": "src.app.services.stage_09_5_causal_inference.impl",
    "phase10_bi_builder": "phases.phase10_bi.impl",
    "12_routing": "backend.src.app.services.stage_12_routing.impl",
}

AUTO_PURGE_OLD_RUNS = os.getenv("MINDQ_AUTO_PURGE_RUNS", "false").lower() in ("1", "true", "yes", "on")

LLM_PROVIDER_KEYS: Tuple[Tuple[str, str, str], ...] = (
    ("OPENAI_API_KEY", "openai", "openai_api_key"),
    ("GOOGLE_API_KEY", "google", "google_api_key"),
    ("KPI_API_KEY", "kpi", "kpi_api_key"),
)

LLM_ENV_ALLOWED_PREFIXES: Tuple[str, ...] = (
    "OPENAI_",
    "AZURE_OPENAI_",
    "GOOGLE_",
    "ANTHROPIC_",
    "MISTRAL_",
    "KPI_",
)


def _iter_llm_credential_files(config: Optional[Mapping[str, Any]] = None) -> Iterable[Path]:
    seen: set[str] = set()
    ordered: List[Path] = []

    def _collect(candidate: Optional[Union[str, Path]]) -> None:
        if not candidate:
            return
        path = Path(candidate).expanduser()
        try:
            resolved = path.resolve()
        except OSError:
            return
        ordered.append(resolved)

    if config:
        direct = config.get("llm_credentials_file")
        if isinstance(direct, str):
            _collect(direct)
        llm_section = config.get("llm")
        if isinstance(llm_section, Mapping):
            for key in ("credentials_file", "env_file"):
                value = llm_section.get(key)
                if isinstance(value, str):
                    _collect(value)

    override = os.getenv("MINDQ_LLM_CREDENTIALS_FILE")
    if override:
        _collect(override)

    defaults: List[Path] = [
        BACKEND_ROOT / "llm.env",
        BACKEND_ROOT / ".env",
        PROJECT_ROOT / "llm.env",
        PROJECT_ROOT / ".env",
        Path.cwd() / ".env",
    ]
    for candidate in defaults:
        _collect(candidate)

    for resolved in ordered:
        key = resolved.as_posix()
        if key in seen:
            continue
        seen.add(key)
        if resolved.exists():
            yield resolved


def _load_llm_credentials(config: Optional[Mapping[str, Any]] = None) -> Dict[str, str]:
    credentials: Dict[str, str] = {}
    for env_path in _iter_llm_credential_files(config):
        try:
            entries = dotenv_values(env_path)
        except Exception:
            continue
        for key, value in entries.items():
            if not value or key in credentials:
                continue
            if any(key.startswith(prefix) for prefix in LLM_ENV_ALLOWED_PREFIXES):
                credentials[key] = value
    return credentials

STAGE_LABELS: Dict[str, str] = {
    "stage_01_ingestion": "Ingestion",
    "stage_02_quality": "Quality",
    "stage_03_schema": "Schema",
    "stage_03_5_textops": "TextOps",
    "stage_04_profile": "Profile",
    "stage_05_missing": "Missing Value Repair",
    "stage_06_standardize": "Standardize",
    "stage_06_feature_eng": "Feature Engineering",
    "stage_07_readiness": "Readiness",
    "stage_07_correlations": "Correlations",
    "stage_07_7_business_correlations": "Business Correlations",
    "stage_07_5_feature_report": "Feature Report",
    "stage_07_6_llm_summary": "LLM Summary",
    "stage_07_knime_bridge": "KNIME Bridge",
    # Non-standard phase folder (prepared by bridge and KNIME batch)
    "phase_07_knime": "KNIME Profile",
    "stage_08_insights": "Insights",
    "stage_09_business_validation": "Business Validation",
    "stage_09_5_causal": "Causal Insights (Advisory)",
    "stage_10_bi": "BI Delivery",
}

TEXTUAL_SUFFIXES = {".json", ".jsonl", ".txt", ".md", ".csv", ".yaml", ".yml"}

PIPELINE_PHASE_SEQUENCE: Tuple[str, ...] = (
    "01_ingestion",
    "02_quality",
    "03_schema",
    "03_5_textops",
    "04_profile",
    "05_missing",
    "06_standardize",
    "07_readiness",
    "07_5_feature_report",
    "07_6_llm_summary",
    "07_7_business_correlations",
    "07_knime_bridge",
    "08_insights",
    "09_business_validation",
    "10_bi",
)


def _isoformat(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _stage_label(stage_dir: str) -> str:
    return STAGE_LABELS.get(stage_dir, stage_dir.replace("_", " ").title())


def _stage_order(stage_dir: str) -> Tuple[int, str]:
    if stage_dir.startswith("stage_"):
        numeric = []
        for char in stage_dir[len("stage_") :]:
            if char.isdigit():
                numeric.append(char)
            else:
                break
        if numeric:
            try:
                return (int("".join(numeric)), stage_dir)
            except ValueError:
                pass
    return (999, stage_dir)


def _phase_display_label(phase_id: str) -> str:
    stage_key = f"stage_{phase_id}"
    if stage_key in STAGE_LABELS:
        return STAGE_LABELS[stage_key]
    return phase_id.replace("_", " ").title()


def _purge_run_history(current_run_id: str, artifacts_root: Path, *, force: bool = False) -> None:
    if not (AUTO_PURGE_OLD_RUNS or force):
        return
    for entry in artifacts_root.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        if name in {current_run_id, "run-latest"}:
            continue
        if not name.startswith("run-"):
            continue
        try:
            shutil.rmtree(entry)
            logger.info("Purged historical run %s", name)
        except Exception:  # pragma: no cover - defensive logging
            logger.warning("Failed to purge historical run %s", name, exc_info=True)


def _iter_run_directories(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return (entry for entry in root.iterdir() if entry.is_dir())


def _list_runs(root: Path) -> List[Dict[str, Any]]:
    runs: List[Dict[str, Any]] = []
    for directory in _iter_run_directories(root):
        stat = directory.stat()
        runs.append(
            {
                "run_id": directory.name,
                "path": directory.relative_to(root).as_posix(),
                "updated_at": _isoformat(stat.st_mtime),
            }
        )
    return sorted(runs, key=lambda item: item["updated_at"], reverse=True)


def _load_json_file(path: Any) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    try:
        candidate = Path(path).expanduser()
    except (TypeError, ValueError):
        return None
    if not candidate.exists():
        return None
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return None


def _format_stop_error(phase_id: str, result: Mapping[str, Any]) -> str:
    label = _phase_display_label(phase_id)
    message = f"Phase {phase_id} ({label}) returned STOP status"
    reasons: List[str] = []
    stops = result.get("stops")
    if isinstance(stops, (list, tuple)):
        reasons.extend(str(item) for item in stops if item)

    referenced_files: List[str] = []
    outputs = result.get("outputs")
    if isinstance(outputs, Mapping):
        gate_path = outputs.get("gate")
        gate_payload = _load_json_file(gate_path)
        if gate_payload:
            gate_reasons = gate_payload.get("reasons")
            if isinstance(gate_reasons, list):
                reasons.extend(str(item) for item in gate_reasons if item)
        for key in ("gate", "diagnostics", "report", "ingestion_report", "quality_report", "issues"):
            path_value = outputs.get(key)
            if isinstance(path_value, str) and path_value:
                referenced_files.append(path_value)

    logs_uri = result.get("logs_uri")
    if isinstance(logs_uri, str) and logs_uri:
        referenced_files.append(logs_uri)

    if reasons:
        unique_reasons = list(dict.fromkeys(reasons))
        message += f": {'; '.join(unique_reasons)}"
    if referenced_files:
        unique_files = list(dict.fromkeys(referenced_files))
        message += f". Related files: {', '.join(unique_files)}"
    return message


def _pipeline_progress_path(run_id: str, artifacts_root: Path) -> Path:
    status_dir = artifacts_root / run_id / "_status"
    status_dir.mkdir(parents=True, exist_ok=True)
    return status_dir / "pipeline_progress.json"


def _async_jobs_dir(run_id: str, artifacts_root: Path) -> Path:
    return artifacts_root / run_id / "_status" / "async_jobs"


def _async_job_manifest_path(run_id: str, artifacts_root: Path, job_id: str) -> Path:
    return _async_jobs_dir(run_id, artifacts_root) / f"{job_id}.json"


def _write_async_job_manifest(
    run_id: str, artifacts_root: Path, job_id: str, payload: Mapping[str, Any]
) -> Path:
    path = _async_job_manifest_path(run_id, artifacts_root, job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _remove_async_job_manifest(run_id: str, artifacts_root: Path, job_id: str) -> None:
    path = _async_job_manifest_path(run_id, artifacts_root, job_id)
    if path.exists():
        path.unlink()
    parent = path.parent
    if parent.exists():
        try:
            next(parent.iterdir())
        except StopIteration:
            parent.rmdir()


def _write_pipeline_progress(
    run_id: str,
    artifacts_root: Path,
    active_phases: Iterable[str],
    *,
    current_phase: Optional[str],
    completed: Iterable[str],
    skipped: Iterable[str],
    deferred: Iterable[str] = (),
    status: str = "running",
    error: Optional[str] = None,
    async_jobs: Optional[Dict[str, Any]] = None,
) -> None:
    phases_order = list(active_phases)
    completed_set = set(completed)
    skipped_set = set(skipped)
    deferred_set = set(deferred)
    phases_payload: List[Dict[str, Any]] = []
    effective_total = 0
    effective_completed = 0

    for index, phase_id in enumerate(phases_order, start=1):
        label = _phase_display_label(phase_id)
        if phase_id in skipped_set:
            phase_status = "skipped"
        elif phase_id in deferred_set:
            phase_status = "deferred"
        elif phase_id in completed_set:
            phase_status = "completed"
            effective_completed += 1
            effective_total += 1
        elif phase_id == current_phase:
            phase_status = "running"
            effective_total += 1
        else:
            phase_status = "pending"
            effective_total += 1

        phases_payload.append(
            {
                "id": phase_id,
                "label": label,
                "status": phase_status,
                "index": index,
            }
        )

    percent_complete = 0.0
    if effective_total:
        percent_complete = min(1.0, effective_completed / effective_total)

    payload: Dict[str, Any] = {
        "status": status,
        "current_phase": current_phase,
        "completed_count": effective_completed,
        "total_count": effective_total,
        "percent_complete": percent_complete,
        "phases": phases_payload,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if skipped_set:
        payload["skipped"] = sorted(skipped_set)
    if deferred_set:
        payload["deferred"] = sorted(deferred_set)
    if error:
        payload["error"] = error
    if async_jobs:
        payload["async_jobs"] = async_jobs

    progress_path = _pipeline_progress_path(run_id, artifacts_root)
    progress_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _list_stage_files(stage_dir: Path, base: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not stage_dir.exists():
        return entries
    for path in stage_dir.rglob("*"):
        if not path.is_file():
            continue
        stat = path.stat()
        entries.append(
            {
                "name": path.relative_to(stage_dir).as_posix(),
                "path": path.relative_to(base).as_posix(),
                "size": stat.st_size,
                "updated_at": _isoformat(stat.st_mtime),
            }
        )
    entries.sort(key=lambda item: item["name"])
    return entries


def _artifact_manifest(run_id: str, root: Path) -> Dict[str, Any]:
    run_dir = root / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Artifacts for run {run_id} not found under {root}")
    phases: List[Dict[str, Any]] = []
    for entry in sorted((path for path in run_dir.iterdir() if path.is_dir()), key=lambda p: _stage_order(p.name)):
        phases.append(
            {
                "id": entry.name,
                "label": _stage_label(entry.name),
                "files": _list_stage_files(entry, root),
            }
        )
    top_level_files = _list_stage_files(run_dir, root)
    if top_level_files:
        phases.insert(
            0,
            {
                "id": "root",
                "label": "Run Root",
                "files": top_level_files,
            },
        )
    return {
        "run_id": run_id,
        "artifacts_root": root.as_posix(),
        "phases": phases,
    }


def _read_artifact_text(run_id: str, root: Path, relative_path: str) -> Dict[str, Any]:
    if not relative_path:
        raise FileNotFoundError("Artifact path must be provided")
    run_dir = (root / run_id).resolve()
    target_path = (root / relative_path).resolve()
    if not target_path.exists() or not target_path.is_file():
        raise FileNotFoundError(f"Artifact {relative_path} not found under {run_dir}")
    try:
        if not target_path.is_relative_to(run_dir):
            raise PermissionError(f"Artifact path {relative_path} escapes run directory")
    except AttributeError:  # pragma: no cover - Python < 3.9 compatibility
        if run_dir not in target_path.parents:
            raise PermissionError(f"Artifact path {relative_path} escapes run directory")
    suffix = target_path.suffix.lower()
    if suffix not in TEXTUAL_SUFFIXES:
        raise ValueError(f"Artifact type {suffix or 'unknown'} is not viewable")

    text = target_path.read_text(encoding="utf-8")
    content: Any
    content_type = "text"
    if suffix == ".json":
        content = json.loads(text)
        content_type = "json"
    elif suffix == ".jsonl":
        content = [json.loads(line) for line in text.splitlines() if line.strip()]
        content_type = "jsonl"
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore

            content = yaml.safe_load(text)
            content_type = "yaml"
        except Exception:
            content = text
    else:
        content = text
    return {
        "run_id": run_id,
        "path": relative_path,
        "content_type": content_type,
        "content": content,
    }


class IngestionRequest(BaseModel):
    data_files: List[str] = Field(..., description="Absolute or relative paths to the raw data files (CSV/Parquet).")
    sla_files: Optional[List[str]] = Field(
        default=None,
        description="Optional list of SLA/SAL documents (PDF/DOCX/CSV/HTML...) to associate with the run.",
    )
    artifacts_root: Optional[str] = Field(default=None, description="Override root directory for artifacts.")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Optional config payload merged into phase config.")
    ingestion_overrides: Optional[Dict[str, Any]] = Field(
        default=None, description="Override keys applied to the ingestion sub-config (min_rows, etc.)."
    )

    @root_validator(pre=True)
    def _validate_data_files(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        files = values.get("data_files") or []
        if not files:
            raise ValueError("data_files must contain at least one file path.")
        return values


class PhaseRequest(BaseModel):
    inputs: Optional[Dict[str, Any]] = Field(
        default=None, description="Explicit inputs passed to the phase runner (overrides defaults)."
    )
    config: Optional[Dict[str, Any]] = Field(default=None, description="Optional additional config for the phase.")
    artifacts_root: Optional[str] = Field(default=None, description="Override artifacts root (defaults to ./artifacts).")
    use_defaults: bool = Field(
        default=True,
        description="Whether to auto-resolve canonical inputs from prior stages when not provided explicitly.",
    )


class PipelineRequest(BaseModel):
    data_files: List[str] = Field(..., description="Raw data files for Stage 01 ingestion.")
    sla_files: Optional[List[str]] = Field(default=None, description="Optional SLA documents passed to Stage 01.")
    artifacts_root: Optional[str] = Field(default=None, description="Artifacts root override.")
    stop_on_error: bool = Field(default=True, description="Whether to abort on the first phase failure.")
    llm_credentials_file: Optional[str] = Field(
        default=None,
        description="Optional .env-style file containing LLM API keys to apply across all phases.",
    )
    llm_summary: bool = Field(
        default=False,
        description="If true, Stage 07.6 LLM summary will be attempted (requires LLM credentials).",
    )


class PipelineResponse(BaseModel):
    run_id: str
    phases: List[Dict[str, Any]]


class PipelineAcceptedResponse(BaseModel):
    run_id: str
    status: str = "accepted"


class BiQueryRequest(BaseModel):
    sql: str = Field(..., description="SQL executed against Stage 10 marts.")
    artifacts_root: Optional[str] = Field(
        default=None, description="Optional artifacts root override for BI access."
    )
    timezone: Optional[str] = Field(default=None, description="Optional timezone override.")
    currency: Optional[str] = Field(default=None, description="Optional currency override.")
    llm_enabled: Optional[bool] = Field(default=None, description="Toggle LLM planner assistance.")


class BiPlanRequest(BaseModel):
    question: str = Field(..., description="Natural language question for the BI planner.")
    artifacts_root: Optional[str] = Field(
        default=None, description="Optional artifacts root override for BI access."
    )
    timezone: Optional[str] = Field(default=None, description="Optional timezone override.")
    currency: Optional[str] = Field(default=None, description="Optional currency override.")
    llm_enabled: Optional[bool] = Field(default=None, description="Toggle LLM planner assistance.")


def _resolve_artifacts_root(override: Optional[str]) -> Path:
    if override:
        root = Path(override).expanduser()
    else:
        env_override = os.getenv("ARTIFACTS_ROOT")
        root = Path(env_override).expanduser() if env_override else ARTIFACTS_ROOT_DEFAULT
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _ensure_exists(path: Path, *, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return path


@lru_cache(maxsize=None)
def _load_module(path: str):
    return importlib.import_module(path)


def _merge_dicts(base: Dict[str, Any], updates: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(base)
    if updates:
        merged.update(updates)
    return merged


def _default_stage01_inputs(run_id: str, artifacts_root: Path) -> Dict[str, Any]:  # pragma: no cover - trivial
    base = artifacts_root / run_id / "stage_01_ingestion"
    return {
        "raw": (base / "raw.parquet").as_posix(),
        "meta": (base / "meta_ingestion.json").as_posix(),
    }


def _default_raw(run_id: str, artifacts_root: Path) -> Path:
    return artifacts_root / run_id / "stage_01_ingestion" / "raw.parquet"


def _default_imputed(run_id: str, artifacts_root: Path) -> Path:
    base = artifacts_root / run_id / "stage_05_missing"
    clean = base / "clean_imputed.parquet"
    if clean.exists():
        return clean
    return base / "imputed.parquet"


def _default_features(run_id: str, artifacts_root: Path) -> Path:
    return artifacts_root / run_id / "stage_06_feature_eng" / "features.parquet"


def _default_curated(run_id: str, artifacts_root: Path) -> Path:
    return artifacts_root / run_id / "stage_06_feature_eng" / "features.curated.parquet"


def _default_readiness(run_id: str, artifacts_root: Path) -> Path:
    return artifacts_root / run_id / "stage_07_readiness"


def _ensure_correlations_bridge(run_id: str, artifacts_root: Path) -> Path:
    correlations_dir = artifacts_root / run_id / "stage_07_correlations"
    readiness_dir = _default_readiness(run_id, artifacts_root)
    if not readiness_dir.exists():
        return correlations_dir
    correlations_dir.mkdir(parents=True, exist_ok=True)
    for name in ("correlations.json", "correlations_kpi.json", "correlations_datetime.json", "redundancy.json"):
        src = readiness_dir / name
        if src.exists():
            dest = correlations_dir / name
            try:
                shutil.copy2(src, dest)
            except Exception:
                continue
    return correlations_dir


def _prepare_llm_environment(config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Optional[str]]]:
    credential_defaults = _load_llm_credentials(config)
    for env_key, value in credential_defaults.items():
        if env_key not in os.environ or not os.environ[env_key]:
            os.environ[env_key] = str(value)

    llm_cfg = config.get("llm") if isinstance(config.get("llm"), dict) else {}
    providers: Dict[str, bool] = {}
    values: Dict[str, Optional[str]] = {}
    applied_any = False

    for env_key, provider_name, cfg_key in LLM_PROVIDER_KEYS:
        cfg_value = llm_cfg.get(cfg_key)
        if cfg_value is None:
            cfg_value = config.get(cfg_key)
        if cfg_value is None:
            cfg_value = credential_defaults.get(env_key)

        if cfg_value is not None:
            os.environ[env_key] = str(cfg_value)
            providers[provider_name] = True
            values[env_key] = str(cfg_value)
            applied_any = True
        else:
            existing = os.environ.get(env_key)
            providers[provider_name] = bool(existing)
            values[env_key] = existing

    enabled = llm_cfg.get("enabled")
    if enabled is None:
        enabled = config.get("llm_enabled")
    if enabled is None:
        enabled = applied_any or any(providers.values())

    enabled_bool = bool(enabled)
    config["llm_enabled"] = enabled_bool

    state = {"enabled": enabled_bool, "providers": providers}
    return state, values


def _default_inputs_for_phase(phase_key: str, run_id: str, artifacts_root: Path) -> Dict[str, Any]:
    base = artifacts_root / run_id
    if phase_key == "02_quality":
        raw = _ensure_exists(_default_raw(run_id, artifacts_root), label="Stage 01 raw parquet")
        return {"raw": raw.as_posix()}
    if phase_key == "03_schema":
        raw = _ensure_exists(_default_raw(run_id, artifacts_root), label="Stage 01 raw parquet")
        return {"raw": raw.as_posix()}
    if phase_key == "03_5_textops":
        payload: Dict[str, Any] = {}
        shipments_candidate = _default_raw(run_id, artifacts_root)
        if shipments_candidate.exists():
            payload["shipments"] = shipments_candidate.as_posix()
        domain_candidates = [
            base / "stage_03" / "domain_dict.json",
            base / "stage_03_schema" / "domain_dict.json",
        ]
        for candidate in domain_candidates:
            if candidate.exists():
                payload.setdefault("domain_dict", candidate.as_posix())
        catalog_candidates = [
            base / "stage_03" / "text_columns_catalog.json",
            base / "stage_03_schema" / "text_columns_catalog.json",
        ]
        for candidate in catalog_candidates:
            if candidate.exists():
                payload.setdefault("text_catalog", candidate.as_posix())
        return payload
    if phase_key == "04_profile":
        raw = _ensure_exists(_default_raw(run_id, artifacts_root), label="Stage 01 raw parquet")
        return {"raw": raw.as_posix()}
    if phase_key == "05_missing":
        raw = _ensure_exists(_default_raw(run_id, artifacts_root), label="Stage 01 raw parquet")
        return {"raw": raw.as_posix()}
    if phase_key == "07_readiness":
        features = _ensure_exists(_default_features(run_id, artifacts_root), label="Stage 06 features.parquet")
        return {"raw": features.as_posix()}
    if phase_key == "07_7_business_correlations":
        features = _ensure_exists(_default_features(run_id, artifacts_root), label="Stage 06 features.parquet")
        return {"features": features.as_posix()}
    if phase_key == "07_5_feature_report":
        features = _ensure_exists(_default_features(run_id, artifacts_root), label="Stage 06 features.parquet")
        readiness_dir = _ensure_exists(_default_readiness(run_id, artifacts_root), label="Stage 07 readiness directory")
        decision_manifest = _ensure_exists(readiness_dir / "decision_manifest.json", label="decision_manifest.json")
        feature_spec = readiness_dir.parent / "stage_06_feature_eng" / "feature_spec.json"
        payload: Dict[str, Any] = {
            "features": features.as_posix(),
            "decision_manifest": decision_manifest.as_posix(),
        }
        if feature_spec.exists():
            payload["feature_spec"] = feature_spec.as_posix()
        return payload
    if phase_key == "07_6_llm_summary":
        report = _ensure_exists(
            base / "stage_07_5_feature_report" / "report.json", label="Stage 07.5 report.json"
        )
        kpis = PROJECT_ROOT / "contracts" / "kpis.yml"
        payload: Dict[str, Any] = {"report": report.as_posix()}
        if kpis.exists():
            payload["kpis"] = kpis.as_posix()
        return payload
    if phase_key == "07_knime_bridge":
        features = _ensure_exists(_default_features(run_id, artifacts_root), label="Stage 06 features.parquet")
        payload = {"features": features.as_posix()}
        layer1_candidate = features.parent / "layer1_dataset.parquet"
        if layer1_candidate.exists():
            payload["layer1_dataset"] = layer1_candidate.as_posix()
        readiness_dir = _default_readiness(run_id, artifacts_root)
        readiness_report = readiness_dir / "readiness_report.json"
        if readiness_report.exists():
            payload["readiness_report"] = readiness_report.as_posix()
        decision_manifest = readiness_dir / "decision_manifest.json"
        if decision_manifest.exists():
            payload["decision_manifest"] = decision_manifest.as_posix()
        feature_report = base / "stage_07_5_feature_report" / "report.json"
        if feature_report.exists():
            payload["feature_report"] = feature_report.as_posix()
        schema_candidate = base / "stage_03_schema" / "schema_v1.json"
        if schema_candidate.exists():
            payload["schema"] = schema_candidate.as_posix()
        else:
            default_schema = PROJECT_ROOT / "contracts" / "schema.json"
            if default_schema.exists():
                payload["schema"] = default_schema.as_posix()
        kpis = BACKEND_ROOT / "contracts" / "kpis.yml"
        if kpis.exists():
            payload["kpis"] = kpis.as_posix()
        return payload
    if phase_key == "08_insights":
        features = _ensure_exists(_default_features(run_id, artifacts_root), label="Stage 06 features.parquet")
        correlations_dir = _ensure_correlations_bridge(run_id, artifacts_root)
        correlations_kpi = correlations_dir / "correlations_kpi.json"
        correlations_path = correlations_kpi if correlations_kpi.exists() else correlations_dir / "correlations.json"
        correlations = _ensure_exists(
            correlations_path, label="Stage 07 correlations.json"
        )
        redundancy = _ensure_exists(
            correlations_dir / "redundancy.json", label="Stage 07 redundancy.json"
        )
        payload: Dict[str, Any] = {
            "features": features.as_posix(),
            "correlations": correlations.as_posix(),
            "redundancy": redundancy.as_posix(),
        }
        text_profile = base / "stage_03_5_textops" / "text_profile.json"
        sentiment = base / "stage_03_5_textops" / "sentiment_features.parquet"
        if text_profile.exists():
            payload["text_profile"] = text_profile.as_posix()
        if sentiment.exists():
            payload["sentiment"] = sentiment.as_posix()
        return payload
    if phase_key == "09_business_validation":
        clean_path = _ensure_exists(_default_features(run_id, artifacts_root), label="Stage 06 features.parquet")
        insights_path = _ensure_exists(
            base / "stage_08_insights" / "insights_report.json",
            label="Stage 08 insights_report.json",
        )
        payload: Dict[str, Any] = {
            "clean": clean_path.as_posix(),
            "insights": insights_path.as_posix(),
        }
        rules_dir = PROJECT_ROOT / "configs" / "rules"
        if rules_dir.exists():
            payload["rules"] = rules_dir.as_posix()
        kpi_cfg = PROJECT_ROOT / "configs" / "kpi" / "kpi_catalog.yaml"
        if kpi_cfg.exists():
            payload["kpi_cfg"] = kpi_cfg.as_posix()
        bi_cfg = PROJECT_ROOT / "configs" / "bi" / "bi_contract.yaml"
        if bi_cfg.exists():
            payload["bi_cfg"] = bi_cfg.as_posix()
        what_if = base / "stage_09_business_validation" / "what_if.yaml"
        if what_if.exists():
            payload["what_if"] = what_if.as_posix()
        return payload
    raise ValueError(f"No default resolver implemented for phase {phase_key}")


def _ingestion_config(base_config: Optional[Dict[str, Any]], overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = dict(base_config or {})
    ingestion_cfg = dict(cfg.get("ingestion") or {})
    if overrides:
        ingestion_cfg.update(overrides)
    cfg["ingestion"] = ingestion_cfg
    return cfg


async def _run_sync(func, *args, **kwargs):
    return await anyio.to_thread.run_sync(func, *args, **kwargs)


def _run_standard_phase(
    module_path: str,
    run_id: str,
    inputs: Dict[str, Any],
    config: Dict[str, Any],
    artifacts_root: Path,
) -> Dict[str, Any]:
    module = _load_module(module_path)
    phase_id, stage_dir = derive_phase_identity(module_path)
    with PhaseRunRecorder(
        artifacts_root=artifacts_root,
        run_id=run_id,
        phase_id=phase_id,
        stage_dir=stage_dir,
        inputs=inputs,
        config=config,
    ) as recorder:
        result = module.run(run_id, inputs, config)  # type: ignore[attr-defined]
        if not isinstance(result, dict):
            raise RuntimeError(f"Phase module {module_path} returned non-dict payload: {type(result)}")
        status = str(result.get("status", "UNKNOWN"))
        recorder.finalise(
            status,
            outputs=result.get("outputs") or {},
            metrics=result.get("metrics") or {},
            context=result.get("context") or {},
        )
    return result


def _run_phase06_bundle(run_id: str, artifacts_root: Path, request: PhaseRequest) -> Dict[str, Any]:
    std_inputs_default = {}
    raw_candidate = _default_imputed(run_id, artifacts_root)
    if raw_candidate.exists():
        std_inputs_default["raw"] = raw_candidate.as_posix()
    else:
        std_inputs_default["raw"] = _ensure_exists(
            _default_raw(run_id, artifacts_root), label="Standardize raw parquet"
        ).as_posix()
    std_inputs = std_inputs_default
    if request.inputs:
        std_inputs = _merge_dicts(std_inputs_default, request.inputs)

    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())
    _prepare_llm_environment(config)

    std_result = _run_standard_phase(
        PHASE_MODULES["06_standardize"],
        run_id,
        std_inputs,
        config,
        artifacts_root,
    )

    outputs = std_result.get("outputs") or {}
    curated = outputs.get("features_curated") or outputs.get("raw")
    if not curated:
        raise RuntimeError("Stage 06 standardize did not produce a curated dataset.")
    feat_inputs_default = {"raw": curated}
    if outputs.get("features_pre"):
        feat_inputs_default["features_pre"] = outputs["features_pre"]
    feat_inputs = feat_inputs_default
    feat_result = _run_standard_phase(
        PHASE_MODULES["06_feature_eng"],
        run_id,
        feat_inputs,
        config,
        artifacts_root,
    )
    return {"standardize": std_result, "feature_eng": feat_result}


def _run_phase07_6(
    run_id: str,
    inputs: Dict[str, Any],
    config: Dict[str, Any],
    artifacts_root: Path,
) -> Dict[str, Any]:
    return _run_standard_phase(
        PHASE_MODULES["07_6_llm_summary"],
        run_id,
        inputs,
        config,
        artifacts_root,
    )


def _run_phase07_7(
    run_id: str,
    inputs: Dict[str, Any],
    config: Dict[str, Any],
    artifacts_root: Path,
) -> Dict[str, Any]:
    return _run_standard_phase(
        PHASE_MODULES["07_7_business_correlations"],
        run_id,
        inputs,
        config,
        artifacts_root,
    )


def _run_phase08(
    run_id: str,
    inputs: Dict[str, Any],
    config: Dict[str, Any],
    artifacts_root: Path,
) -> Dict[str, Any]:
    return _run_standard_phase(
        PHASE_MODULES["08_insights"],
        run_id,
        inputs,
        config,
        artifacts_root,
    )


def _run_phase09(
    run_id: str,
    inputs: Dict[str, Any],
    config: Dict[str, Any],
    artifacts_root: Path,
) -> Dict[str, Any]:
    return _run_standard_phase(
        PHASE_MODULES["09_business_validation"],
        run_id,
        inputs,
        config,
        artifacts_root,
    )


def _build_bi_preview(run_id: str, artifacts_root: str, semantic: Dict[str, Any]) -> List[Dict[str, Any]]:
    from pathlib import Path as _Path

    from bi10.app.query import conn_for, run_sql

    marts_summary: List[Dict[str, Any]] = []
    with conn_for(run_id, artifacts_root) as connection:
        for mart in semantic.get("marts", []):
            mart_id = mart.get("id")
            for file_name in mart.get("files", []):
                view_name = _Path(file_name).stem
                row_count = None
                preview: List[Dict[str, Any]] = []
                try:
                    count_payload = run_sql(connection, f"SELECT COUNT(*) AS row_count FROM {view_name}")
                    if count_payload:
                        row_count = count_payload[0].get("row_count")
                except Exception:
                    row_count = None
                try:
                    preview = run_sql(connection, f"SELECT * FROM {view_name} LIMIT 5")
                except Exception:
                    preview = []
                marts_summary.append(
                    {
                        "mart": mart_id,
                        "view": view_name,
                        "file": file_name,
                        "row_count": row_count,
                        "preview": preview,
                    }
                )
    return marts_summary


def _bi_config_from_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    for key in ("artifacts_root", "timezone", "currency", "llm_enabled"):
        value = payload.get(key)
        if value is not None:
            config[key] = value
    return config


def _configure_bi10_settings(run_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    from bi10.app import config as bi_config  # lazy import

    llm_state, llm_values = _prepare_llm_environment(config)

    overrides = {
        "artifacts_root": config.get("artifacts_root") or ARTIFACTS_ROOT_DEFAULT.as_posix(),
        "default_run_id": run_id,
        "timezone": config.get("timezone", bi_config.settings.timezone),
        "currency": config.get("currency", bi_config.settings.currency),
        "llm_enabled": llm_state["enabled"],
        "kpi_api_key": llm_values.get("KPI_API_KEY"),
    }

    new_settings = bi_config.Settings(**overrides)
    bi_config.settings = new_settings
    try:
        from bi10.app import api as bi_api  # lazy import
        from bi10.app import bootstrap as bi_bootstrap  # lazy import
        from bi10.app import llm_router as bi_llm  # lazy import

        bi_api.settings = new_settings
        bi_bootstrap.settings = new_settings
        bi_llm.settings = new_settings
    except Exception:
        pass

    return {**overrides, "llm": llm_state}


def _run_phase10(run_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    from pathlib import Path as _Path

    from bi10.app import config as bi_config  # lazy import
    from bi10.app.bootstrap import preflight
    from bi10.app.query import conn_for, run_sql
    from bi10.app.semantic import load_semantic

    builder_module = _load_module(PHASE_MODULES["phase10_bi_builder"])
    builder_inputs = dict(config.get("inputs") or {})
    builder_result = builder_module.run(run_id, builder_inputs, config)  # type: ignore[attr-defined]

    artifacts_root_override = config.get("artifacts_root")
    if not artifacts_root_override:
        builder_outputs = builder_result.get("outputs", {}) if isinstance(builder_result, Mapping) else {}
        root_path = builder_outputs.get("root") if isinstance(builder_outputs, Mapping) else None
        if isinstance(root_path, str):
            try:
                resolved = _Path(root_path).resolve()
                target_parent: Optional[_Path] = None
                for parent in resolved.parents:
                    if parent.name == "artifacts":
                        target_parent = parent
                        break
                if target_parent is None:
                    target_parent = resolved.parents[1] if len(resolved.parents) > 1 else resolved.parent
                artifacts_root_override = target_parent.as_posix()
            except Exception:
                artifacts_root_override = root_path
    if not artifacts_root_override:
        artifacts_root_override = config.get("artifacts_root")
    if not artifacts_root_override:
        artifacts_root_override = ARTIFACTS_ROOT_DEFAULT.as_posix()

    config_for_bi = dict(config)
    config_for_bi["artifacts_root"] = _Path(str(artifacts_root_override)).expanduser().resolve().as_posix()

    overrides = _configure_bi10_settings(run_id, config_for_bi)
    llm_state = overrides.pop("llm")

    try:
        preflight(run_id)
    except SystemExit as exc:  # pragma: no cover - defensive
        raise FileNotFoundError(str(exc)) from exc

    semantic = load_semantic(run_id, bi_config.settings.artifacts_root)
    try:
        marts_summary = _build_bi_preview(run_id, bi_config.settings.artifacts_root, semantic)
    except FileNotFoundError as exc:
        raise FileNotFoundError(str(exc)) from exc

    return {
        "status": "READY",
        "run_id": run_id,
        "artifacts_root": overrides["artifacts_root"],
        "semantic": semantic,
        "marts": marts_summary,
        "llm_enabled": overrides.get("llm_enabled", True),
        "llm": llm_state,
        "builder": builder_result,
    }


app = FastAPI(
    title="Mind-Q Pipeline API",
    version="1.0.0",
    description="HTTP façade exposing Mind-Q pipeline phases for system integration.",
)

app.include_router(bi_router)
app.include_router(pipeline_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", tags=["system"])
def healthcheck() -> Dict[str, Any]:
    return {
        "status": "ok",
        "artifacts_root": ARTIFACTS_ROOT_DEFAULT.resolve().as_posix(),
        "project_root": PROJECT_ROOT.as_posix(),
    }


@app.post("/v1/runs/{run_id}/phases/01/ingestion", tags=["phases"])
async def run_phase01(run_id: str, request: IngestionRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = {"files": request.data_files}
    if request.sla_files:
        inputs["sla_files"] = request.sla_files
    config = _ingestion_config(request.config, request.ingestion_overrides)
    config.setdefault("artifacts_root", artifacts_root.as_posix())
    ingestion_cfg = config.setdefault("ingestion", {})
    dtype_cfg = ingestion_cfg.setdefault("dtype_overrides", {})
    dtype_cfg.setdefault("COD_AMOUNT", "float")

    def _execute():
        for file_path in request.data_files:
            if not Path(file_path).expanduser().resolve().exists():
                raise FileNotFoundError(f"Data file not found: {file_path}")
        if request.sla_files:
            for sla_path in request.sla_files:
                if not Path(sla_path).expanduser().resolve().exists():
                    raise FileNotFoundError(f"SLA file not found: {sla_path}")
        return _run_standard_phase(PHASE_MODULES["01_ingestion"], run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/02/quality", tags=["phases"])
async def run_phase02(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("02_quality", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())

    def _execute():
        _ensure_exists(Path(inputs["raw"]).expanduser().resolve(), label="Stage 02 raw input")
        return _run_standard_phase(PHASE_MODULES["02_quality"], run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/03/schema", tags=["phases"])
async def run_phase03(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("03_schema", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())

    def _execute():
        _ensure_exists(Path(inputs["raw"]).expanduser().resolve(), label="Stage 03 raw input")
        return _run_standard_phase(PHASE_MODULES["03_schema"], run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/03/textops", tags=["phases"])
async def run_phase03_5(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("03_5_textops", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())

    def _execute():
        return _run_standard_phase(PHASE_MODULES["03_5_textops"], run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/04/profile", tags=["phases"])
async def run_phase04(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("04_profile", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())

    def _execute():
        _ensure_exists(Path(inputs["raw"]).expanduser().resolve(), label="Stage 04 raw input")
        return _run_standard_phase(PHASE_MODULES["04_profile"], run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/05/missing", tags=["phases"])
async def run_phase05(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("05_missing", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())

    def _execute():
        _ensure_exists(Path(inputs["raw"]).expanduser().resolve(), label="Stage 05 raw input")
        return _run_standard_phase(PHASE_MODULES["05_missing"], run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/06/standardize", tags=["phases"])
async def run_phase06(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    def _execute():
        return _run_phase06_bundle(run_id, artifacts_root, request)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/07/readiness", tags=["phases"])
async def run_phase07(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("07_readiness", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())

    def _execute():
        _ensure_exists(Path(inputs["raw"]).expanduser().resolve(), label="Stage 07 readiness input")
        return _run_standard_phase(PHASE_MODULES["07_readiness"], run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/07/feature-report", tags=["phases"])
async def run_phase07_5(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("07_5_feature_report", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())

    def _execute():
        _ensure_exists(Path(inputs["features"]).expanduser().resolve(), label="Stage 07.5 features input")
        _ensure_exists(Path(inputs["decision_manifest"]).expanduser().resolve(), label="decision_manifest.json")
        return _run_standard_phase(PHASE_MODULES["07_5_feature_report"], run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/07/llm-summary", tags=["phases"])
async def run_phase07_6(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("07_6_llm_summary", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())
    _prepare_llm_environment(config)

    def _execute():
        _ensure_exists(Path(inputs["report"]).expanduser().resolve(), label="Stage 07.6 report.json")
        return _run_phase07_6(run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/07/business-correlations", tags=["phases"])
async def run_phase07_7(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("07_7_business_correlations", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())

    def _execute():
        _ensure_exists(Path(inputs["features"]).expanduser().resolve(), label="Stage 07.7 features input")
        return _run_phase07_7(run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/07/knime-bridge", tags=["phases"])
async def run_phase07_knime_bridge(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("07_knime_bridge", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())

    def _execute():
        _ensure_exists(Path(inputs["features"]).expanduser().resolve(), label="Stage 06 features.parquet")
        return _run_standard_phase(PHASE_MODULES["07_knime_bridge"], run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/08/insights", tags=["phases"])
async def run_phase08(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("08_insights", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())

    def _execute():
        for key in ("features", "correlations", "redundancy"):
            _ensure_exists(Path(inputs[key]).expanduser().resolve(), label=f"Stage 08 {key}")
        return _run_phase08(run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/09/business-validation", tags=["phases"])
async def run_phase09(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    inputs = dict(request.inputs or {})
    if request.use_defaults:
        defaults = _default_inputs_for_phase("09_business_validation", run_id, artifacts_root)
        inputs = _merge_dicts(defaults, inputs)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())

    def _execute():
        _ensure_exists(Path(inputs["clean"]).expanduser().resolve(), label="Stage 09 clean dataset")
        _ensure_exists(Path(inputs["insights"]).expanduser().resolve(), label="Stage 09 insights report")
        return _run_phase09(run_id, inputs, config, artifacts_root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/runs/{run_id}/phases/10/bi", tags=["phases"])
async def run_phase10(run_id: str, request: PhaseRequest) -> Dict[str, Any]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)
    config = dict(request.config or {})
    config.setdefault("artifacts_root", artifacts_root.as_posix())
    if request.inputs:
        config.setdefault("inputs", request.inputs)

    def _execute():
        return _run_phase10(run_id, config)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/v1/runs", tags=["pipeline"])
async def list_runs(artifacts_root: Optional[str] = None) -> Dict[str, Any]:
    root = _resolve_artifacts_root(artifacts_root)
    runs = _list_runs(root)
    return {"artifacts_root": root.as_posix(), "runs": runs}


@app.get("/v1/runs/{run_id}/artifacts", tags=["pipeline"])
async def list_run_artifacts(run_id: str, artifacts_root: Optional[str] = None) -> Dict[str, Any]:
    root = _resolve_artifacts_root(artifacts_root)
    try:
        return _artifact_manifest(run_id, root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/runs/{run_id}/timeline", tags=["pipeline"])
async def run_timeline(run_id: str, artifacts_root: Optional[str] = None) -> Dict[str, Any]:
    root = _resolve_artifacts_root(artifacts_root)

    def _execute():
        run_dir = root / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"Artifacts for run {run_id} not found under {root}")
        return build_run_timeline(run_id, root)

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/v1/runs/{run_id}/artifacts/content", tags=["pipeline"])
async def read_run_artifact(
    run_id: str, path: str, artifacts_root: Optional[str] = None
) -> Dict[str, Any]:
    if not path:
        raise HTTPException(status_code=400, detail="path query parameter is required")
    root = _resolve_artifacts_root(artifacts_root)
    try:
        return _read_artifact_text(run_id, root, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc


@app.get("/v1/runs/{run_id}/schema/terminology", tags=["schema"])
async def schema_terminology(
    run_id: str, artifacts_root: Optional[str] = None, format: str = Query("json", pattern="^(json|flat)$")
) -> Dict[str, Any]:
    root = _resolve_artifacts_root(artifacts_root)
    semantic_dir = root / run_id / "stage_03_schema" / "semantic"
    terminology_path = semantic_dir / "terminology.json"
    aliases_path = semantic_dir / "aliases.json"
    glossary_path = semantic_dir / "column_glossary.json"
    logs_path = semantic_dir / "terminology_logs.jsonl"

    if not semantic_dir.exists():
        raise HTTPException(status_code=404, detail=f"Terminology artifacts not found for run {run_id}")

    def _load_json_safe(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default

    terminology_payload = _load_json_safe(terminology_path, {"columns": []})
    aliases_payload = _load_json_safe(aliases_path, {})
    glossary_payload = _load_json_safe(glossary_path, [])
    logs_payload = []
    if logs_path.exists():
        with logs_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    logs_payload.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if format == "flat":
        columns = terminology_payload.get("columns") or []
        records = []
        for entry in columns:
            if not isinstance(entry, dict):
                continue
            record = {
                "column_id": entry.get("column_id"),
                "original_name": entry.get("original_name"),
                "display_en": entry.get("display", {}).get("en"),
                "display_ar": entry.get("display", {}).get("ar"),
                "description_en": entry.get("description", {}).get("en"),
                "description_ar": entry.get("description", {}).get("ar"),
                "synonyms_en": entry.get("synonyms", {}).get("en"),
                "synonyms_ar": entry.get("synonyms", {}).get("ar"),
                "tags": entry.get("tags"),
                "is_kpi": entry.get("is_kpi"),
                "kpi_links": entry.get("kpi_links"),
                "value_examples": entry.get("value_examples"),
                "dtype": entry.get("dtype"),
                "null_fraction": entry.get("null_fraction"),
                "unique_count": entry.get("unique_count"),
            }
            records.append(record)
        return {
            "run_id": run_id,
            "artifacts_root": root.as_posix(),
            "records": records,
            "aliases": aliases_payload,
        }

    return {
        "run_id": run_id,
        "artifacts_root": root.as_posix(),
        "terminology": terminology_payload,
        "aliases": aliases_payload,
        "glossary": glossary_payload,
        "logs": logs_payload,
    }


@app.get("/v1/runs/{run_id}/pipeline/status", tags=["pipeline"])
async def pipeline_status(run_id: str, artifacts_root: Optional[str] = None) -> Dict[str, Any]:
    root = _resolve_artifacts_root(artifacts_root)
    progress_path = _pipeline_progress_path(run_id, root)
    if not progress_path.exists():
        raise HTTPException(status_code=404, detail=f"Pipeline status not found for run {run_id}")
    try:
        return json.loads(progress_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Pipeline status file is corrupted") from exc


@app.get("/v1/bi/{run_id}/metrics/{metric_id}", tags=["bi"])
async def bi_metric(
    run_id: str, metric_id: str, artifacts_root: Optional[str] = None
) -> Dict[str, Any]:
    config_override: Dict[str, Any] = {}
    if artifacts_root:
        config_override["artifacts_root"] = artifacts_root

    def _execute():
        from bi10.app.query import conn_for, run_sql
        from bi10.app.semantic import load_semantic

        overrides = _configure_bi10_settings(run_id, config_override)
        semantic = load_semantic(run_id, overrides["artifacts_root"])
        metrics = semantic.get("metrics") or []
        metric = next((item for item in metrics if item.get("id") == metric_id), None)
        if metric is None:
            raise FileNotFoundError(f"Metric {metric_id} not found for run {run_id}")
        sql = metric.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            raise ValueError(f"Metric {metric_id} does not define a SQL query")
        with conn_for(run_id, overrides["artifacts_root"]) as connection:
            rows = run_sql(connection, sql)
        payload = {
            "run_id": run_id,
            "metric": {
                key: metric.get(key)
                for key in ("id", "name", "mart", "default_chart", "unit", "cap", "sql")
            },
            "data": rows,
            "artifacts_root": overrides["artifacts_root"],
            "timezone": overrides.get("timezone"),
            "currency": overrides.get("currency"),
        }
        return payload

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/v1/bi/{run_id}/meta", tags=["bi"])
async def bi_meta(run_id: str, artifacts_root: Optional[str] = None) -> Dict[str, Any]:
    config_override: Dict[str, Any] = {}
    if artifacts_root:
        config_override["artifacts_root"] = artifacts_root

    def _execute():
        from bi10.app.bootstrap import preflight
        from bi10.app.semantic import load_semantic

        overrides = _configure_bi10_settings(run_id, config_override)
        llm_state = overrides.pop("llm")
        try:
            preflight(run_id)
        except SystemExit as exc:
            raise FileNotFoundError(str(exc)) from exc
        semantic = load_semantic(run_id, overrides["artifacts_root"])
        marts_summary = _build_bi_preview(run_id, overrides["artifacts_root"], semantic)
        return {
            "run_id": run_id,
            "artifacts_root": overrides["artifacts_root"],
            "semantic": semantic,
            "marts": marts_summary,
            "timezone": overrides.get("timezone"),
            "currency": overrides.get("currency"),
            "llm_enabled": overrides.get("llm_enabled", True),
            "llm": llm_state,
        }

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/bi/{run_id}/query", tags=["bi"])
async def bi_query(run_id: str, request: BiQueryRequest) -> Dict[str, Any]:
    payload = request.dict()

    def _execute():
        from bi10.app.bootstrap import preflight
        from bi10.app.query import conn_for, run_sql

        overrides = _configure_bi10_settings(run_id, _bi_config_from_payload(payload))
        overrides.pop("llm", None)
        try:
            preflight(run_id)
        except SystemExit as exc:
            raise FileNotFoundError(str(exc)) from exc
        with conn_for(run_id, overrides["artifacts_root"]) as connection:
            rows = run_sql(connection, request.sql)
        return {
            "rows": rows,
            "n": len(rows),
            "artifacts_root": overrides.get("artifacts_root"),
            "timezone": overrides.get("timezone"),
            "currency": overrides.get("currency"),
        }

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/bi/{run_id}/llm-plan", tags=["bi"])
async def bi_llm_plan(run_id: str, request: BiPlanRequest) -> Dict[str, Any]:
    payload = request.dict()

    def _execute():
        from bi10.app.bootstrap import preflight
        from bi10.app.semantic import load_semantic
        from bi10.app.llm_router import plan_chart
        from bi10.app.query import conn_for, run_sql

        overrides = _configure_bi10_settings(run_id, _bi_config_from_payload(payload))
        llm_state = overrides.pop("llm", {"enabled": False, "providers": {}})
        try:
            preflight(run_id)
        except SystemExit as exc:
            raise FileNotFoundError(str(exc)) from exc
        semantic = load_semantic(run_id, overrides["artifacts_root"])
        plan = plan_chart(request.question, semantic)
        with conn_for(run_id, overrides["artifacts_root"]) as connection:
            data = run_sql(connection, plan["sql"])
        if not data:
            raise ValueError("Planned SQL returned no rows")
        return {
            "plan": plan,
            "data": data,
            "artifacts_root": overrides.get("artifacts_root"),
            "llm_enabled": overrides.get("llm_enabled", True),
            "llm": llm_state,
        }

    try:
        return await _run_sync(_execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _run_full_pipeline_impl(run_id: str, request: PipelineRequest, artifacts_root: Path) -> PipelineResponse:
    phases_results: List[Dict[str, Any]] = []
    shared_llm_config: Dict[str, Any] = {}
    if request.llm_credentials_file:
        shared_llm_config["llm_credentials_file"] = request.llm_credentials_file
    _prepare_llm_environment(shared_llm_config)

    active_phases: List[str] = list(PIPELINE_PHASE_SEQUENCE)
    skipped_phases: Set[str] = set()
    if not request.llm_summary:
        skipped_phases.add("07_6_llm_summary")
    completed_phases: List[str] = []
    current_phase: Optional[str] = None
    deferred_phases: Set[str] = set()
    async_jobs_state: Dict[str, Dict[str, Any]] = {}

    def _next_active_phase() -> Optional[str]:
        for phase_id in active_phases:
            if phase_id in skipped_phases:
                continue
            if phase_id not in completed_phases:
                return phase_id
        return None

    def _record_progress(*, status: str = "running", current: Optional[str] = None, error: Optional[str] = None) -> None:
        nonlocal current_phase
        if current is not None:
            current_phase = current
        elif status != "failed":
            current_phase = _next_active_phase()
        _write_pipeline_progress(
            run_id,
            artifacts_root,
            active_phases,
            current_phase=current_phase,
            completed=completed_phases,
            skipped=skipped_phases,
            deferred=deferred_phases,
            status=status,
            error=error,
            async_jobs=async_jobs_state if async_jobs_state else None,
        )

    def _phase_request(*, use_defaults: bool = True) -> PhaseRequest:
        config_payload = dict(shared_llm_config) if shared_llm_config else None
        return PhaseRequest(
            artifacts_root=artifacts_root.as_posix(),
            use_defaults=use_defaults,
            config=config_payload,
        )

    async def _run_phase(phase_id: str, runner):
        _record_progress(current=phase_id)
        result = await runner
        phases_results.append({"phase": phase_id, "result": result})
        status = result.get("status")
        if request.stop_on_error and isinstance(status, str) and status.upper() == "STOP":
            raise RuntimeError(_format_stop_error(phase_id, result))
        if phase_id not in completed_phases:
            completed_phases.append(phase_id)
        _record_progress()
        return result

    async def _run_async_phase(phase_id: str, runner) -> asyncio.Task:
        """Start a phase in the background and return the task handle."""
        async def _background_phase_runner():
            queued_at = datetime.now(timezone.utc).isoformat()
            async_jobs_state[phase_id] = {
                "id": phase_id,
                "phase": phase_id,
                "status": "running",
                "queued_at": queued_at,
            }
            _record_progress()
            try:
                result = await runner
                phases_results.append({"phase": phase_id, "result": result})
                status = result.get("status")
                if request.stop_on_error and isinstance(status, str) and status.upper() == "STOP":
                    async_jobs_state[phase_id]["status"] = "failed"
                    async_jobs_state[phase_id]["error"] = _format_stop_error(phase_id, result)
                    raise RuntimeError(_format_stop_error(phase_id, result))
                if phase_id not in completed_phases:
                    completed_phases.append(phase_id)
                async_jobs_state[phase_id]["status"] = "completed"
                async_jobs_state[phase_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
                _record_progress()
                return result
            except Exception as exc:
                async_jobs_state[phase_id]["status"] = "failed"
                async_jobs_state[phase_id]["error"] = str(exc)
                _record_progress()
                raise
        
        task = asyncio.create_task(_background_phase_runner())
        return task

    _record_progress()
    textops_task: Optional[asyncio.Task] = None

    try:
        ingestion_payload = IngestionRequest(
            data_files=request.data_files,
            sla_files=request.sla_files,
            artifacts_root=artifacts_root.as_posix(),
            config={"artifacts_root": artifacts_root.as_posix()},
            ingestion_overrides={
                "min_file_size_bytes": 0,
                "dtype_overrides": {
                    "COD_AMOUNT": "float",
                },
            },
        )
        await _run_phase("01_ingestion", run_phase01(run_id, ingestion_payload))
        await _run_phase("02_quality", run_phase02(run_id, _phase_request()))
        await _run_phase("03_schema", run_phase03(run_id, _phase_request()))
        
        textops_task = await _run_async_phase("03_5_textops", run_phase03_5(run_id, _phase_request()))
        
        await _run_phase("04_profile", run_phase04(run_id, _phase_request()))
        await _run_phase("05_missing", run_phase05(run_id, _phase_request()))

        _record_progress(current="06_standardize")
        phase06_result = await run_phase06(run_id, _phase_request())
        phases_results.append({"phase": "06_standardize", "result": phase06_result})
        if request.stop_on_error:
            for subphase in ("standardize", "feature_eng"):
                status = phase06_result.get(subphase, {}).get("status")
                if isinstance(status, str) and status.upper() == "STOP":
                    raise RuntimeError(f"Phase 06/{subphase} returned STOP status")
        if "06_standardize" not in completed_phases:
            completed_phases.append("06_standardize")
        _record_progress()

        await _run_phase("07_readiness", run_phase07(run_id, _phase_request()))
        await _run_phase("07_5_feature_report", run_phase07_5(run_id, _phase_request()))
        if request.llm_summary:
            await _run_phase("07_6_llm_summary", run_phase07_6(run_id, _phase_request()))
        else:
            skipped_phases.add("07_6_llm_summary")
            phases_results.append(
                {
                    "phase": "07_6_llm_summary",
                    "status": "SKIP",
                    "reason": "LLM credentials not detected; stage skipped.",
                }
            )
            _record_progress()
        await _run_phase(
            "07_7_business_correlations",
            run_phase07_7(run_id, _phase_request()),
        )
        knime_phase_request = _phase_request()
        knime_config = dict(knime_phase_request.config or {})
        knime_config.setdefault("artifacts_root", artifacts_root.as_posix())
        knime_config.setdefault("mode", "auto")
        knime_mode = knime_bridge_impl.resolve_mode(knime_config)
        knime_phase_request.config = knime_config
        _remove_async_job_manifest(run_id, artifacts_root, "knime_bridge")

        if knime_mode == "prompt":
            queued_at = datetime.now(timezone.utc).isoformat()
            deferred_phases.add("07_knime_bridge")
            manifest_path = _async_job_manifest_path(run_id, artifacts_root, "knime_bridge")
            try:
                manifest_ref = manifest_path.relative_to(artifacts_root).as_posix()
            except ValueError:
                manifest_ref = manifest_path.as_posix()
            request_payload = knime_phase_request.model_dump()
            job_payload: Dict[str, Any] = {
                "id": "knime_bridge",
                "phase": "07_knime_bridge",
                "status": "waiting_for_user",
                "mode": knime_mode,
                "queued_at": queued_at,
                "resume_endpoint": f"/v1/runs/{run_id}/phases/07/knime-bridge",
                "artifacts_root": artifacts_root.as_posix(),
                "request": request_payload,
                "instructions": [
                    f"Run POST /v1/runs/{run_id}/phases/07/knime-bridge to generate KNIME artifacts.",
                    "Set MINDQ_KNIME_MODE=auto to auto-approve future runs.",
                ],
                "manifest": manifest_ref,
            }
            _write_async_job_manifest(run_id, artifacts_root, "knime_bridge", job_payload)
            async_jobs_state["knime_bridge"] = job_payload
            phases_results.append(
                {
                    "phase": "07_knime_bridge",
                    "status": "DEFERRED",
                    "reason": "knime_bridge_waiting_for_manual_approval",
                    "meta": job_payload,
                }
            )
            _record_progress()
        else:
            await _run_phase(
                "07_knime_bridge",
                run_phase07_knime_bridge(run_id, knime_phase_request),
            )
        
        if textops_task is not None and not textops_task.done():
            logger.info("Phase 08 waiting for TextOps (Phase 3.5) to complete...")
            await textops_task
            logger.info("TextOps (Phase 3.5) completed, proceeding with Phase 08")
        
        await _run_phase("08_insights", run_phase08(run_id, _phase_request()))
        await _run_phase(
            "09_business_validation",
            run_phase09(run_id, _phase_request()),
        )
        await _run_phase(
            "10_bi",
            run_phase10(
                run_id,
                _phase_request(use_defaults=False),
            ),
        )
        final_status = "completed_with_deferred" if deferred_phases else "completed"
        _record_progress(status=final_status, current=None)
    except HTTPException as exc:
        if textops_task is not None and not textops_task.done():
            logger.warning("Cancelling background TextOps task due to pipeline failure")
            textops_task.cancel()
            try:
                await textops_task
            except asyncio.CancelledError:
                pass
        phases_results.append({"error": exc.detail, "status_code": exc.status_code})
        _record_progress(status="failed", current=current_phase, error=str(exc.detail))
        if request.stop_on_error:
            raise
    except Exception as exc:
        if textops_task is not None and not textops_task.done():
            logger.warning("Cancelling background TextOps task due to pipeline failure")
            textops_task.cancel()
            try:
                await textops_task
            except asyncio.CancelledError:
                pass
        phases_results.append({"error": str(exc)})
        _record_progress(status="failed", current=current_phase, error=str(exc))
        if request.stop_on_error:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return PipelineResponse(run_id=run_id, phases=phases_results)


def _promote_run_to_latest(run_id: str, artifacts_root: Path) -> None:
    if run_id == "run-latest":
        return
    source_dir = artifacts_root / run_id
    if not source_dir.exists():
        logger.warning("Cannot promote run %s to run-latest: source directory missing", run_id)
        return
    target_dir = artifacts_root / "run-latest"
    try:
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(source_dir, target_dir)
        logger.info("Promoted run %s to run-latest", run_id)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to promote run %s to run-latest", run_id)
        return
    _purge_run_history(run_id, artifacts_root)


@app.post(
    "/v1/runs/{run_id}/pipeline/full",
    response_model=Union[PipelineResponse, PipelineAcceptedResponse],
    tags=["pipeline"],
)
async def run_full_pipeline(
    run_id: str,
    request: PipelineRequest,
    async_mode: bool = Query(
        False,
        description="When true, start the pipeline run asynchronously and return 202 Accepted immediately.",
    ),
) -> Union[PipelineResponse, JSONResponse]:
    artifacts_root = _resolve_artifacts_root(request.artifacts_root)

    if async_mode:
        payload = request.model_dump()

        async def _background_run() -> None:
            copied_request = PipelineRequest(**payload)
            try:
                await _run_full_pipeline_impl(run_id, copied_request, artifacts_root)
                _promote_run_to_latest(run_id, artifacts_root)
            except Exception:  # pragma: no cover - background logging only
                logger.exception("Background pipeline run failed", extra={"run_id": run_id})

        asyncio.create_task(_background_run())
        accepted = PipelineAcceptedResponse(run_id=run_id)
        return JSONResponse(status_code=202, content=accepted.model_dump())

    response = await _run_full_pipeline_impl(run_id, request, artifacts_root)
    _promote_run_to_latest(run_id, artifacts_root)
    return response


__all__ = ["app"]









