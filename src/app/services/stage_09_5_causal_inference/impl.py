from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pandas as pd  # type: ignore
import yaml  # type: ignore

from .config_loader import CausalConfig, load_config
from .dag import build_and_export
from .estimate import EstimationOutputs, estimate_propensity, run_estimators
from .identify import identify_estimand
from .recommend import build_recommendations
from .refute import run_refuters

try:  # pragma: no cover - optional dependency
    import polars as pl  # type: ignore
except Exception:  # pragma: no cover - defensive
    pl = None  # type: ignore

MODULE_PATH = Path(__file__).resolve()
BACKEND_ROOT = MODULE_PATH.parents[4]
PROJECT_ROOT = MODULE_PATH.parents[5]
ARTIFACT_ROOT_CANDIDATES = [
    PROJECT_ROOT / "artifacts",
    BACKEND_ROOT / "artifacts",
]

ADVISORY_STATUS_SUPPORTED = "SUPPORTED"
ADVISORY_STATUS_UNSUPPORTED = "UNSUPPORTED"
EPS = 1e-3


FLAG_TRUE_VALUES = {"1", "true", "yes", "on", "t", "y"}




def _is_flag_enabled(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and value.strip().lower() in FLAG_TRUE_VALUES)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _select_artifacts_root() -> Path:
    for candidate in ARTIFACT_ROOT_CANDIDATES:
        if candidate.exists():
            return candidate
    return ARTIFACT_ROOT_CANDIDATES[0]


def _ensure_stage_dir(run_dir: Path) -> Path:
    out_dir = run_dir / "stage_09_5_causal"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _log_entry(records: List[Dict[str, Any]], step: str, status: str, started: float, **details: Any) -> None:
    records.append(
        {
            "ts": _utc_now(),
            "step": step,
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "details": details,
        }
    )


def _load_bi_feed(path: Path) -> pd.DataFrame:
    if pl is not None:  # pragma: no cover - exercised in integration tests
        frame = pl.read_parquet(path.as_posix())
        return frame.to_pandas()
    return pd.read_parquet(path.as_posix())


def _required_columns(config: CausalConfig) -> List[str]:
    columns = {config.treatment, config.outcome}
    columns.update(config.common_causes)
    columns.update(config.effect_modifiers)
    columns.update(config.instrumental_variables)
    columns.update(config.frontdoor_variables)
    return [col for col in columns if col]


def _check_preconditions(df: pd.DataFrame, config: CausalConfig) -> Dict[str, Any]:
    required = _required_columns(config)
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Required columns missing from Stage 09 feed: {missing}")

    null_columns = [col for col in required if df[col].isna().all()]
    if null_columns:
        raise ValueError(f"Columns contain only nulls: {null_columns}")

    treatment_series = df[config.treatment]
    if treatment_series.nunique(dropna=True) <= 1:
        raise ValueError("Treatment column has no variance; cannot estimate effect")

    return {"required_columns_checked": len(required)}


def _overlap_gate(propensity: pd.Series) -> Dict[str, Any]:
    min_score = float(propensity.min())
    max_score = float(propensity.max())
    overlap = min_score > EPS and max_score < 1 - EPS
    return {"overlap": overlap, "min_propensity": min_score, "max_propensity": max_score}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_logs(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _compose_summary(config: CausalConfig, result: EstimationOutputs, status: str, overlap_ok: bool) -> Dict[str, Any]:
    headline = (
        f"Estimated effect under assumptions for {config.treatment} → {config.outcome}: "
        f"{result.ate:+.3f}" if result.ate is not None else
        f"Estimated effect under assumptions for {config.treatment} → {config.outcome} is inconclusive."
    )

    return {
        "advisory_only": True,
        "status": status,
        "headline": headline,
        "confidence_level": config.confidence_level,
        "overlap_passed": overlap_ok,
        "method_baseline": result.method_baseline,
        "method_advanced": result.method_advanced,
    }


def build_root_cause_hints_payload(
    run_id: str,
    config: CausalConfig,
    estimation: EstimationOutputs,
    assumptions: Sequence[str],
    overlap_ok: bool,
) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "method": "adapter",
        "problem_name": config.problem_name,
        "generated_at": _utc_now(),
        "ate": estimation.ate,
        "cate_mean": estimation.cate_mean,
        "segments": estimation.cate_segments,
        "assumptions": list(assumptions),
        "overlap_ok": overlap_ok,
        "baseline_method": estimation.method_baseline,
        "advanced_method": estimation.method_advanced,
    }


async def run(run_id: str, problem_name: str) -> Dict[str, Any]:
    if os.getenv("MINDQ_ENABLE_CAUSAL", "false").lower() != "true":
        return {"skipped": True, "reason": "feature disabled"}
    if not problem_name:
        return {"skipped": True, "reason": "causal problem name is required"}

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _execute, run_id, problem_name)


def _execute(run_id: str, problem_name: str) -> Dict[str, Any]:
    logs: List[Dict[str, Any]] = []
    start_time = time.perf_counter()

    artifacts_root = _select_artifacts_root()
    run_dir = artifacts_root / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir.as_posix()}")
    stage09_feed = run_dir / "stage_09_business_validation" / "bi_feed.parquet"
    if not stage09_feed.exists():
        raise FileNotFoundError("Expected Stage 09 bi_feed.parquet is missing.")

    out_dir = _ensure_stage_dir(run_dir)

    timer = time.perf_counter()
    config = load_config(problem_name)
    _log_entry(logs, "load_config", "ok", timer, problem=config.problem_name)

    timer = time.perf_counter()
    df = _load_bi_feed(stage09_feed)
    n_obs = int(len(df))
    _log_entry(logs, "load_data", "ok", timer, rows=n_obs, columns=list(df.columns))

    timer = time.perf_counter()
    preconditions = _check_preconditions(df, config)
    _log_entry(logs, "preconditions", "ok", timer, **preconditions, sample_size=n_obs)

    if n_obs < config.min_sample_size:
        raise ValueError(
            f"Insufficient rows for advisory causal analysis (n={n_obs} < min_sample_size={config.min_sample_size})"
        )

    timer = time.perf_counter()
    feature_candidates = list({*config.common_causes, *config.effect_modifiers})
    if not feature_candidates:
        feature_candidates = [col for col in df.columns if col not in {config.treatment, config.outcome}]
    propensity = estimate_propensity(df, config.treatment, feature_candidates)
    overlap_info = _overlap_gate(propensity)
    _log_entry(logs, "propensity", "ok", timer, **overlap_info)
    overlap_ok = bool(overlap_info["overlap"])

    timer = time.perf_counter()
    dag_paths = build_and_export(config, out_dir)
    _log_entry(logs, "dag", "ok", timer, artifacts=dag_paths)

    timer = time.perf_counter()
    model, estimand, assumptions = identify_estimand(df, config)
    assumptions = list(dict.fromkeys(assumptions))
    _log_entry(logs, "identify", "ok", timer, assumptions=assumptions)

    timer = time.perf_counter()
    estimation = run_estimators(model, estimand, df, config)
    _log_entry(
        logs,
        "estimate",
        "ok",
        timer,
        ate=estimation.ate,
        cate_mean=estimation.cate_mean,
        baseline_method=estimation.method_baseline,
        advanced_method=estimation.method_advanced,
    )

    timer = time.perf_counter()
    refute_result = run_refuters(model, estimation.baseline_estimate, config.refutation_tests)
    _log_entry(
        logs,
        "refute",
        "ok",
        timer,
        passed=refute_result["passed_count"],
        tests=refute_result["tests"],
    )

    timer = time.perf_counter()
    recommendations = build_recommendations(config, estimation.cate_segments, estimation.ate, estimation.cate_mean)
    _log_entry(logs, "recommend", "ok", timer, items=len(recommendations["structured"]))

    hints_method = "baseline"
    root_cause_payload: Optional[Dict[str, Any]] = None
    root_cause_reason: Optional[str] = None
    adapter_flag = _is_flag_enabled("USE_EXT_ROOT_CAUSE_HINTS")
    if adapter_flag:
        if config.common_causes:
            try:
                root_cause_payload = build_root_cause_hints_payload(
                    run_id,
                    config,
                    estimation,
                    assumptions,
                    overlap_ok,
                )
                hints_method = "adapter"
            except Exception as exc:
                root_cause_reason = f"adapter_error: {exc}"
                logs.append({"ts": _utc_now(), "step": "root_cause_hints", "status": "error", "details": {"message": str(exc)}})
                root_cause_payload = None
        else:
            root_cause_reason = "missing_common_causes"
    else:
        root_cause_reason = "flag_disabled"

    supported = bool(
        overlap_ok and refute_result.get("passed_count", 0) >= 3 and estimation.ate is not None
    )
    status = ADVISORY_STATUS_SUPPORTED if supported else ADVISORY_STATUS_UNSUPPORTED

    insight_payload = {
        "advisory_only": True,
        "status": status,
        "problem_name": config.problem_name,
        "run_id": run_id,
        "method": hints_method,
        "n": n_obs,
        "assumptions": assumptions,
        "effect": {
            "ATE": estimation.ate,
            "CATE_mean": estimation.cate_mean,
        },
        "CATE_by_segment": estimation.cate_segments,
        "method_baseline": estimation.method_baseline,
        "method_advanced": estimation.method_advanced,
        "confidence_level": config.confidence_level,
        "bi_display": {
            "priority": "HIGH" if supported else "HIDDEN",
            "badge": "ASSUMPTIONS-BOUND" if supported else "INSUFFICIENT-EVIDENCE",
        },
        "text_recommendations": recommendations["text"],
        "propensity_summary": {
            "min": overlap_info["min_propensity"],
            "max": overlap_info["max_propensity"],
        },
    }

    summary_payload = _compose_summary(config, estimation, status, overlap_ok)
    summary_payload["method"] = hints_method
    refute_payload = {
        "advisory_only": True,
        "status": status,
        "method": hints_method,
        "tests": refute_result["tests"],
        "passed_count": refute_result["passed_count"],
        "overlap_check": overlap_ok,
    }
    recommendations_payload = {
        "advisory_only": True,
        "status": status,
        "method": hints_method,
        "items": recommendations["structured"],
    }

    _write_json(out_dir / "causal_insights.json", insight_payload)
    _write_json(out_dir / "causal_summary.json", summary_payload)
    _write_json(out_dir / "refutation_report.json", refute_payload)
    _write_json(out_dir / "causal_recommendations.json", recommendations_payload)
    if hints_method == "adapter" and root_cause_payload:
        hints_path = out_dir / "root_cause_hints.json"
        _write_json(hints_path, root_cause_payload)
        logs.append({"ts": _utc_now(), "step": "root_cause_hints", "status": "ok", "details": {"method": "adapter", "path": hints_path.as_posix()}})
    else:
        reason = root_cause_reason or "baseline"
        logs.append({"ts": _utc_now(), "step": "root_cause_hints", "status": "baseline", "details": {"method": "baseline", "reason": reason}})

    _write_yaml(out_dir / "causal_config_used.yml", config.as_dict())

    total_duration = round((time.perf_counter() - start_time) * 1000, 2)
    logs.append({"ts": _utc_now(), "step": "complete", "status": status, "duration_ms": total_duration})
    _write_logs(out_dir / "logs.jsonl", logs)

    return insight_payload
