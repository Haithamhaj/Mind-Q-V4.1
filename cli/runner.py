from __future__ import annotations

import argparse
import json
import os
import sys
import shutil
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
    run_phase04,
    run_phase05,
    run_phase06,
    run_phase07,
    run_phase07_5,
    run_phase07_6,
    run_phase07_7,
    run_phase07_knime_bridge,
    run_phase08,
    run_phase09,
    run_phase10,
)

LLM_ENV_KEYS: Sequence[str] = ("OPENAI_API_KEY", "GOOGLE_API_KEY", "KPI_API_KEY")
KNIME_MODE_KEY = "MINDQ_KNIME_MODE"


def _default_data_files() -> List[str]:
    data_csv = Path("data/basic.csv")
    fallback_csv = Path("data/header_offset.csv")
    if data_csv.exists():
        return [data_csv.resolve().as_posix()]
    if fallback_csv.exists():
        return [fallback_csv.resolve().as_posix()]
    return []


def _llm_credentials_available() -> bool:
    return any(os.environ.get(key) for key in LLM_ENV_KEYS)


def _ensure_knime_prompt_mode() -> None:
    mode = os.environ.get(KNIME_MODE_KEY, "")
    normalized = mode.strip().lower()
    if not normalized:
        os.environ[KNIME_MODE_KEY] = "prompt"
        print("MINDQ_KNIME_MODE not set; defaulting to 'prompt' for KNIME bridge safety.", file=sys.stderr)
    elif normalized != "prompt":
        print(
            f"Warning: MINDQ_KNIME_MODE is '{mode}'. Stage 07 KNIME bridge expects 'prompt' to require manual approval.",
            file=sys.stderr,
        )


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

    for phase_id, runner_factory in (
        ("02_quality", run_phase02),
        ("03_schema", run_phase03),
        ("04_profile", run_phase04),
        ("05_missing", run_phase05),
    ):
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

    status = await _record("07_knime_bridge", run_phase07_knime_bridge(run_id, await _phase_request()))
    if status == "STOP":
        return results

    status = await _record("08_insights", run_phase08(run_id, await _phase_request()))
    if status == "STOP":
        return results

    status = await _record("09_business_validation", run_phase09(run_id, await _phase_request()))
    if status == "STOP":
        return results

    await _record("10_bi", run_phase10(run_id, await _phase_request(use_defaults=False)))
    return results


def flow(run_id: str) -> None:
    _ensure_knime_prompt_mode()
    artifacts_root = Path("artifacts").resolve()
    artifacts_root.mkdir(parents=True, exist_ok=True)

    data_files = _default_data_files()
    llm_summary = _llm_credentials_available()

    results = anyio.run(_run_pipeline, run_id, data_files, artifacts_root, llm_summary)

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


def main() -> None:
    parser = argparse.ArgumentParser(prog="cli.runner")
    parser.add_argument("flow", help="run the default flow", nargs="?")
    parser.add_argument("--run-id", dest="run_id", default="demo")
    args = parser.parse_args()
    flow(args.run_id)


if __name__ == "__main__":
    main()
