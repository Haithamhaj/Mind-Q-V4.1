from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_phase_impl() -> Any:
    phase_dir = PROJECT_ROOT / "phases" / "09_business_validation" / "impl.py"
    if not phase_dir.exists():
        raise FileNotFoundError(f"Unable to locate phase implementation: {phase_dir}")
    spec = importlib.util.spec_from_file_location("phase09_business_validation", phase_dir.as_posix())
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load Phase 09 implementation module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _configure_stdio() -> None:
    if not os.environ.get("PYTHONUTF8"):
        os.environ["PYTHONUTF8"] = "1"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    if platform.system() == "Windows":  # pragma: no cover - defensive
        try:
            subprocess.run(["chcp", "65001"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 09 Business Validation and BI handoff")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier")
    parser.add_argument("--artifacts-root", default="artifacts", help="Root artifacts directory (default: artifacts)")
    parser.add_argument("--clean", help="Override path to stage 06 clean parquet")
    parser.add_argument("--insights", help="Override path to stage 08 insights report")
    parser.add_argument("--rules", help="Directory containing YAML rule definitions")
    parser.add_argument("--kpi-cfg", dest="kpi_cfg", help="Path to KPI catalog YAML")
    parser.add_argument("--bi-cfg", dest="bi_cfg", help="Path to BI contract YAML")
    parser.add_argument("--what-if", dest="what_if", help="Optional what-if configuration YAML")
    parser.add_argument("--channel", help="Override BI channel (canary|prod)")
    parser.add_argument("--explain-url-template", dest="explain_url_template", help="Explain deeplink template with {entity_id}")
    return parser


def resolve_inputs(args: argparse.Namespace) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key in ("clean", "insights", "rules", "kpi_cfg", "bi_cfg", "what_if"):
        value = getattr(args, key, None)
        if value:
            payload[key] = value
    return payload


def resolve_config(args: argparse.Namespace) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"artifacts_root": args.artifacts_root}
    if args.channel:
        payload["channel"] = args.channel
    if args.explain_url_template:
        payload["explain_url_template"] = args.explain_url_template
    return payload


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    inputs = resolve_inputs(args)
    config = resolve_config(args)
    phase_impl = _load_phase_impl()
    result = phase_impl.run(args.run_id, inputs, config)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return int(result.get("exit_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
