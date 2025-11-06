from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.app.services.stage_08_insights import impl  # noqa: E402


def _configure_stdio() -> None:
    if not os.environ.get("PYTHONUTF8"):
        os.environ["PYTHONUTF8"] = "1"
    if hasattr(sys.stdout, "reconfigure"):
        cast(Any, sys.stdout).reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        cast(Any, sys.stderr).reconfigure(encoding="utf-8")
    if platform.system() == "Windows":  # pragma: no cover - defensive
        try:
            subprocess.run(["chcp", "65001"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Stage 08 Insights pipeline")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier")
    parser.add_argument("--artifacts-root", default="artifacts", help="Root artifacts directory (default: artifacts)")
    parser.add_argument("--correlations", help="Override path to correlations.json")
    parser.add_argument("--redundancy", help="Override path to redundancy.json")
    parser.add_argument("--features", help="Override path to features.parquet")
    parser.add_argument("--text-profile", help="Optional path to text_profile.json")
    parser.add_argument("--sentiment", help="Optional path to sentiment_features.parquet")
    parser.add_argument("--config-json", help="Optional JSON string with Stage 08 overrides")
    return parser


def resolve_inputs(args: argparse.Namespace, artifacts_root: Path) -> Dict[str, Any]:
    base = artifacts_root / args.run_id
    correlations_default = base / "stage_07_correlations" / "correlations_kpi.json"
    if not correlations_default.exists():
        correlations_default = base / "stage_07_correlations" / "correlations.json"
    defaults = {
        "correlations": correlations_default,
        "redundancy": base / "stage_07_correlations" / "redundancy.json",
        "features": base / "stage_06_feature_eng" / "features.parquet",
        "text_profile": base / "stage_03_5_textops" / "text_profile.json",
        "sentiment": base / "stage_03_5_textops" / "sentiment_features.parquet",
    }
    overrides = {
        "correlations": args.correlations,
        "redundancy": args.redundancy,
        "features": args.features,
        "text_profile": args.text_profile,
        "sentiment": args.sentiment,
    }
    resolved: Dict[str, Any] = {}
    for key, default in defaults.items():
        override = overrides.get(key)
        resolved[key] = override if override else default.as_posix()
    return resolved


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    inputs = resolve_inputs(args, artifacts_root)
    config = {"artifacts_root": artifacts_root.as_posix()}
    if args.config_json:
        config.update(json.loads(args.config_json))

    result = impl.run(args.run_id, inputs, config)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
