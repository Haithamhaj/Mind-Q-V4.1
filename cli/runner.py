from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, cast
PHASES: List[tuple[str, str]] = [
    ("01_ingestion", "impl"),
    ("02_quality", "impl"),
    ("03_schema", "impl"),
    ("04_profile", "impl"),
    ("05_missing", "impl"),
    ("06_standardize", "impl"),
    ("06_feature_eng", "impl"),
    ("07_readiness", "impl"),
]


def _call_phase(phase_dir: str, module_name: str, run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    # Try normal import first
    try:
        mod = importlib.import_module(f"phases.{phase_dir}.{module_name}")
    except Exception:
        # Fallback to file-based import to support numeric directory names
        mod_path = Path("phases") / phase_dir / f"{module_name}.py"
        if not mod_path.exists() and phase_dir[0].isdigit():
            mod_path = Path("phases") / ("_" + phase_dir) / f"{module_name}.py"
        spec = importlib.util.spec_from_file_location(f"phase_{phase_dir}_{module_name}", mod_path.as_posix())
        if spec is None or spec.loader is None:
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod.run(run_id=run_id, inputs=inputs, config=config)


def flow(run_id: str) -> None:
    artifacts_root = "artifacts"
    data_csv = Path("data/basic.csv")
    fallback_csv = Path("data/header_offset.csv")
    input_files: List[str] = []
    if data_csv.exists():
        input_files = [str(data_csv.resolve())]
    elif fallback_csv.exists():
        input_files = [str(fallback_csv.resolve())]

    cfg: Dict[str, Any] = {"artifacts_root": artifacts_root, "ingestion": {"min_file_size_bytes": 0}}
    cur_inputs: Dict[str, Any] = {"files": input_files}

    results: List[Dict[str, Any]] = []
    for phase_dir, module in PHASES:
        try:
            res = _call_phase(phase_dir, module, run_id, cur_inputs, cfg)
            results.append({"phase": phase_dir, **res})
            raw = res.get("outputs", {}).get("raw")
            if raw:
                cur_inputs = {"files": [raw]}
        except Exception as exc:
            results.append({"phase": phase_dir, "status": "STOP", "error": str(exc)})
            break

    out = Path(artifacts_root) / run_id / "flow_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write summary expected by smoke consumers
    summary_dir = Path(artifacts_root) / run_id / "_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    phases_summary: List[Dict[str, Any]] = []
    for r in results:
        met_any = r.get("metrics") or {}
        met = cast(Dict[str, Any], met_any) if isinstance(met_any, dict) else {}
        n_val = met.get("n_rows")
        n_row_int = int(n_val) if isinstance(n_val, (int, float)) else None
        phases_summary.append({"phase": str(r.get("phase", "")), "status": r.get("status"), "n_rows": n_row_int})
    run_report: Dict[str, Any] = {"run_id": run_id, "phases": phases_summary}
    (summary_dir / "run_report.json").write_text(json.dumps(run_report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(prog="cli.runner")
    ap.add_argument("flow", help="run the default flow", nargs="?")
    ap.add_argument("--run-id", dest="run_id", default="demo")
    ns = ap.parse_args()
    flow(ns.run_id)


if __name__ == "__main__":
    main()
