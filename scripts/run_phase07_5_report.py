from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_phase_impl(phase_dir: str):
    base = PROJECT_ROOT / "phases"
    candidates = [
        base / phase_dir / "impl.py",
        base / f"_{phase_dir}" / "impl.py",
    ]
    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location(f"phase_{phase_dir.replace('/', '_')}", path.as_posix())
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(f"Unable to locate implementation for phase directory '{phase_dir}'")


feature_report = _load_phase_impl("07_5_feature_report")  # type: ignore


def _emit_json(payload: Any) -> None:
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _configure_io() -> None:
    if not os.environ.get("PYTHONUTF8"):
        os.environ["PYTHONUTF8"] = "1"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        if platform.system() == "Windows":
            subprocess.run(["chcp", "65001"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Stage 07.5 feature profiling report")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier")
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Root directory for pipeline artifacts (default: artifacts)",
    )
    parser.add_argument(
        "--features-path",
        help="Override path to Stage 06 features parquet (default resolves from artifacts)",
    )
    parser.add_argument(
        "--decision-manifest",
        help="Override path to decision_manifest.json (default resolves from Stage 07 readiness)",
    )
    parser.add_argument("--focus-cols", help="Optional comma separated column list for focused profiling")
    parser.add_argument("--exclude-cols", help="Optional comma separated column list to exclude from report")
    parser.add_argument("--top-k", type=int, default=20, help="Top categories to include for categorical columns (default: 20)")
    parser.add_argument("--tz", default="Asia/Riyadh", help="Timezone for temporal profiling (default: Asia/Riyadh)")
    return parser.parse_args()


def resolve_paths(run_id: str, artifacts_root: Path, args: argparse.Namespace) -> tuple[Path, Path, Path]:
    features = Path(args.features_path).expanduser().resolve() if args.features_path else artifacts_root / run_id / "stage_06_feature_eng" / "features.parquet"
    decision = Path(args.decision_manifest).expanduser().resolve() if args.decision_manifest else artifacts_root / run_id / "stage_07_readiness" / "decision_manifest.json"
    spec = artifacts_root / run_id / "stage_06_feature_eng" / "feature_spec.json"
    return features, decision, spec


def main() -> int:
    _configure_io()
    args = parse_args()
    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    features_path, decision_path, feature_spec_path = resolve_paths(args.run_id, artifacts_root, args)

    inputs = {
        "features": features_path.as_posix(),
        "decision_manifest": decision_path.as_posix(),
        "feature_spec": feature_spec_path.as_posix(),
    }
    cfg = {
        "artifacts_root": artifacts_root.as_posix(),
        "focus_cols": args.focus_cols,
        "exclude_cols": args.exclude_cols,
        "top_k": args.top_k,
        "tz": args.tz,
    }
    result = feature_report.run(args.run_id, inputs, cfg)  # type: ignore[arg-type]
    _emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
