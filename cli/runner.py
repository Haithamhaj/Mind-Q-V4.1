from __future__ import annotations

import argparse
import json
import os
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import anyio
from fastapi import HTTPException

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.app.services.pipeline_api.app import (
    IngestionRequest,
    PhaseRequest,
    run_phase01,
    run_phase02,
    run_phase03,
    run_phase03_5,
    run_phase04,
    run_phase05,
    run_phase06,
    run_phase07,
    run_phase07_5,
    run_phase07_6,
    run_phase07_7,
    run_phase07_analytics,
    run_phase07_knime_bridge,
    run_phase07_timeseries,
    run_phase08,
    run_phase09,
    run_phase09_5,
    run_phase10,
    run_phase12,
)
from src.app.services.stage_11_ml_sandbox import build_ml_base_table, run_client_clustering

LLM_ENV_KEYS: Sequence[str] = ("OPENAI_API_KEY", "GOOGLE_API_KEY", "KPI_API_KEY")
BI_MODE_ENV_KEYS: Sequence[str] = ("MINDQ_BI_PREP_MODE", "BI_PREP_MODE")


@dataclass
class PipelineFlags:
    run_textops: bool = True
    run_stage07_analytics: bool = False
    run_stage07_timeseries: bool = False
    stage07_timeseries_inputs: Optional[Dict[str, Any]] = None
    run_causal: bool = False
    causal_problem_name: Optional[str] = None
    run_routing: bool = False
    routing_inputs: Optional[Dict[str, Any]] = None


def _default_data_files() -> List[str]:
    data_csv = Path("data/basic.csv")
    fallback_csv = Path("data/header_offset.csv")
    if data_csv.exists():
        return [data_csv.resolve().as_posix()]
    if fallback_csv.exists():
        return [fallback_csv.resolve().as_posix()]
    return []


def _load_json_payload(path_str: str) -> Dict[str, Any]:
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return data


def _llm_credentials_available() -> bool:
    return any(os.environ.get(key) for key in LLM_ENV_KEYS)


def _ensure_bi_prep_mode() -> None:
    if any(os.environ.get(key) for key in BI_MODE_ENV_KEYS):
        return
    os.environ["MINDQ_BI_PREP_MODE"] = "auto"


def _rollup_status(statuses: Sequence[Optional[str]]) -> Optional[str]:
    normalized = [str(status).upper() for status in statuses if isinstance(status, str) and status]
    if not normalized:
        return None
    for marker in ("STOP", "ERROR"):
        if marker in normalized:
            return marker
    if "WARN" in normalized:
        return "WARN"
    return normalized[0]


def _derive_status(phase_id: str, payload: Dict[str, Any]) -> Optional[str]:
    status = payload.get("status")
    if isinstance(status, str) and status:
        return status.upper()
    if phase_id == "06_standardize":
        statuses = []
        for subphase in ("standardize", "feature_eng"):
            subpayload = payload.get(subphase)
            if isinstance(subpayload, dict):
                statuses.append(subpayload.get("status"))
        return _rollup_status(statuses)
    return None


def _extract_n_rows(entry: Dict[str, Any]) -> Optional[int]:
    metrics = entry.get("metrics")
    if isinstance(metrics, dict):
        value = metrics.get("n_rows")
        if isinstance(value, (int, float)):
            return int(value)
    for key in ("feature_eng", "standardize"):
        subpayload = entry.get(key)
        if isinstance(subpayload, dict):
            submetrics = subpayload.get("metrics")
            if isinstance(submetrics, dict):
                value = submetrics.get("n_rows")
                if isinstance(value, (int, float)):
                    return int(value)
    return None


async def _run_pipeline(
    run_id: str,
    data_files: List[str],
    artifacts_root: Path,
    llm_summary: bool,
    flags: PipelineFlags,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    async def _record(phase_id: str, runner) -> Optional[str]:
        try:
            payload = await runner
            entry: Dict[str, Any] = {"phase": phase_id}
            if isinstance(payload, dict):
                status = _derive_status(phase_id, payload)
                if status:
                    entry["status"] = status
                entry.update(payload)
                if status:
                    entry["status"] = status
            else:
                entry["result"] = payload
                entry["status"] = None
            results.append(entry)
            return entry.get("status")
        except HTTPException as exc:
            entry = {"phase": phase_id, "status": "ERROR", "error": exc.detail, "status_code": exc.status_code}
            results.append(entry)
            return "ERROR"
        except Exception as exc:
            entry = {"phase": phase_id, "status": "ERROR", "error": str(exc)}
            results.append(entry)
            return "ERROR"

    artifacts_root_str = artifacts_root.as_posix()
    ingestion_request = IngestionRequest(
        data_files=data_files,
        sla_files=None,
        artifacts_root=artifacts_root_str,
        config={"artifacts_root": artifacts_root_str},
        ingestion_overrides={
            "min_file_size_bytes": 0,
            "dtype_overrides": {
                "COD_AMOUNT": "float",
            },
        },
    )
    status = await _record("01_ingestion", run_phase01(run_id, ingestion_request))
    if status == "STOP":
        return results

    async def _phase_request(use_defaults: bool = True) -> PhaseRequest:
        return PhaseRequest(artifacts_root=artifacts_root_str, use_defaults=use_defaults)

    for phase_id, runner_factory in (("02_quality", run_phase02),):
        status = await _record(phase_id, runner_factory(run_id, await _phase_request()))
        if status == "STOP":
            return results

    status = await _record("03_schema", run_phase03(run_id, await _phase_request()))
    if status == "STOP":
        return results

    if flags.run_textops:
        status = await _record("03_5_textops", run_phase03_5(run_id, await _phase_request()))
        if status == "STOP":
            return results
    else:
        results.append(
            {
                "phase": "03_5_textops",
                "status": "SKIP",
                "reason": "Stage 03.5 disabled for this run",
            }
        )

    for phase_id, runner_factory in (("04_profile", run_phase04), ("05_missing", run_phase05)):
        status = await _record(phase_id, runner_factory(run_id, await _phase_request()))
        if status == "STOP":
            return results

    status = await _record("06_standardize", run_phase06(run_id, await _phase_request()))
    if status == "STOP":
        return results

    status = await _record("07_readiness", run_phase07(run_id, await _phase_request()))
    if status == "STOP":
        return results

    status = await _record("07_5_feature_report", run_phase07_5(run_id, await _phase_request()))
    if status == "STOP":
        return results

    if llm_summary:
        status = await _record("07_6_llm_summary", run_phase07_6(run_id, await _phase_request()))
        if status == "STOP":
            return results
    else:
        results.append(
            {
                "phase": "07_6_llm_summary",
                "status": "SKIP",
                "reason": "LLM credentials not detected; stage skipped.",
            }
        )

    status = await _record("07_7_business_correlations", run_phase07_7(run_id, await _phase_request()))
    if status == "STOP":
        return results

    if flags.run_stage07_analytics:
        status = await _record("07_analytics", run_phase07_analytics(run_id, await _phase_request()))
        if status == "STOP":
            return results

    if flags.run_stage07_timeseries:
        if not flags.stage07_timeseries_inputs:
            raise HTTPException(status_code=400, detail="Stage 07 timeseries requires --stage07-timeseries-config")
        ts_request = PhaseRequest(artifacts_root=artifacts_root_str, use_defaults=False, inputs=dict(flags.stage07_timeseries_inputs))
        status = await _record("07_timeseries", run_phase07_timeseries(run_id, ts_request))
        if status == "STOP":
            return results

    status = await _record("07_knime_bridge", run_phase07_knime_bridge(run_id, await _phase_request()))
    if status == "STOP":
        return results

    status = await _record("08_insights", run_phase08(run_id, await _phase_request()))
    if status == "STOP":
        return results

    status = await _record("09_business_validation", run_phase09(run_id, await _phase_request()))
    if status == "STOP":
        return results

    if flags.run_causal:
        if not flags.causal_problem_name:
            raise HTTPException(status_code=400, detail="Stage 09.5 requires --causal-problem when enabled")
        causal_request = PhaseRequest(
            artifacts_root=artifacts_root_str,
            use_defaults=False,
            inputs={"problem_name": flags.causal_problem_name},
        )
        status = await _record("09_5_causal", run_phase09_5(run_id, causal_request))
        if status == "STOP":
            return results

    await _record("10_bi", run_phase10(run_id, await _phase_request(use_defaults=False)))

    if flags.run_routing:
        if not flags.routing_inputs:
            raise HTTPException(status_code=400, detail="Stage 12 routing requires --routing-config when enabled")
        routing_request = PhaseRequest(
            artifacts_root=artifacts_root_str,
            use_defaults=False,
            inputs=dict(flags.routing_inputs),
        )
        await _record("12_routing", run_phase12(run_id, routing_request))

    return results


def flow(run_id: str, flags: PipelineFlags, artifacts_root: Path) -> None:
    _ensure_bi_prep_mode()
    artifacts_root = artifacts_root.expanduser().resolve()
    artifacts_root.mkdir(parents=True, exist_ok=True)

    data_files = _default_data_files()
    llm_summary = _llm_credentials_available()

    results = anyio.run(_run_pipeline, run_id, data_files, artifacts_root, llm_summary, flags)

    flow_path = artifacts_root / run_id / "flow_results.json"
    flow_path.parent.mkdir(parents=True, exist_ok=True)
    flow_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_dir = artifacts_root / run_id / "_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    phases_summary: List[Dict[str, Any]] = []
    for entry in results:
        phases_summary.append(
            {
                "phase": entry.get("phase"),
                "status": entry.get("status"),
                "n_rows": _extract_n_rows(entry),
            }
        )
    run_report: Dict[str, Any] = {"run_id": run_id, "phases": phases_summary}
    (summary_dir / "run_report.json").write_text(json.dumps(run_report, ensure_ascii=False, indent=2), encoding="utf-8")

    if run_id != "run-latest":
        latest_dir = artifacts_root / "run-latest"
        source_dir = artifacts_root / run_id
        try:
            if latest_dir.exists():
                shutil.rmtree(latest_dir)
            shutil.copytree(source_dir, latest_dir)
            print(f"Updated run-latest to point at {run_id}")
        except Exception as exc:
            print(f"Warning: failed to update run-latest: {exc}", file=sys.stderr)


def run_ml_sandbox(flow_run_id: str, artifacts_root: Path, n_clusters: int) -> None:
    """
    Build the Stage 11 ML sandbox outputs without touching the upstream BI flow.
    """

    _ensure_bi_prep_mode()
    artifacts_root = artifacts_root.expanduser().resolve()
    stage_dir = artifacts_root / flow_run_id / "stage_11_ml_sandbox"
    stage_dir.mkdir(parents=True, exist_ok=True)

    base_meta = build_ml_base_table(flow_run_id, stage_dir.as_posix())
    cluster_meta = run_client_clustering(flow_run_id, stage_dir.as_posix(), n_clusters=n_clusters)

    payload = {"run_id": flow_run_id, "base_table": base_meta, "clustering": cluster_meta}
    summary_path = stage_dir / "ml_sandbox_summary.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="cli.runner")
    parser.add_argument(
        "command",
        help="Pipeline command to execute",
        nargs="?",
        default="flow",
        choices=("flow", "ml-sandbox"),
    )
    parser.add_argument("--run-id", dest="run_id", default="demo")
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Root directory where run artifacts are stored (default: %(default)s)",
    )
    parser.add_argument(
        "--textops",
        dest="run_textops",
        action="store_true",
        help="Enable Stage 03.5 TextOps (default).",
    )
    parser.add_argument(
        "--no-textops",
        dest="run_textops",
        action="store_false",
        help="Disable Stage 03.5 TextOps.",
    )
    parser.set_defaults(run_textops=True)
    parser.add_argument(
        "--run-stage07-analytics",
        action="store_true",
        help="Enable the Python-based Stage 07 analytics suite",
    )
    parser.add_argument(
        "--run-stage07-timeseries",
        action="store_true",
        help="Enable Stage 07 timeseries forecasting templates",
    )
    parser.add_argument(
        "--stage07-timeseries-config",
        help="Path to JSON file containing Stage 07 timeseries inputs",
    )
    parser.add_argument(
        "--run-causal",
        action="store_true",
        help="Enable the Stage 09.5 causal advisory flow",
    )
    parser.add_argument(
        "--causal-problem",
        dest="causal_problem",
        help="Problem name to trigger Stage 09.5 causal advisory",
    )
    parser.add_argument(
        "--run-routing",
        action="store_true",
        help="Enable Stage 12 routing optimization",
    )
    parser.add_argument(
        "--routing-config",
        help="Path to JSON scenario file for Stage 12 routing",
    )
    parser.add_argument(
        "--n-clusters",
        type=int,
        default=5,
        help="Number of clusters for the ML sandbox command (default: %(default)s)",
    )
    args = parser.parse_args()
    artifacts_root = Path(args.artifacts_root)

    if args.command == "ml-sandbox":
        run_ml_sandbox(args.run_id, artifacts_root, n_clusters=args.n_clusters)
        return

    timeseries_inputs = None
    if args.stage07_timeseries_config:
        timeseries_inputs = _load_json_payload(args.stage07_timeseries_config)
    run_stage07_timeseries = args.run_stage07_timeseries or bool(timeseries_inputs)
    if run_stage07_timeseries and not timeseries_inputs:
        parser.error("--stage07-timeseries-config is required when --run-stage07-timeseries is set")
    routing_inputs = None
    if args.routing_config:
        routing_inputs = _load_json_payload(args.routing_config)
    run_routing = args.run_routing or bool(routing_inputs)
    if run_routing and not routing_inputs:
        parser.error("--routing-config is required when --run-routing is set")
    causal_problem = args.causal_problem
    run_causal = args.run_causal or bool(causal_problem)
    if run_causal and not causal_problem:
        parser.error("--causal-problem is required when --run-causal is set")
    flags = PipelineFlags(
        run_textops=args.run_textops,
        run_stage07_analytics=args.run_stage07_analytics,
        run_stage07_timeseries=run_stage07_timeseries,
        stage07_timeseries_inputs=timeseries_inputs,
        run_causal=run_causal,
        causal_problem_name=causal_problem,
        run_routing=run_routing,
        routing_inputs=routing_inputs,
    )
    flow(args.run_id, flags, artifacts_root)


if __name__ == "__main__":
    main()
