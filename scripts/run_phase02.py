from __future__ import annotations

import argparse
import json
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict

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


quality = _load_phase_impl("02_quality")  # type: ignore


def _emit_json(payload: Any) -> None:
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 02 quality checks")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier")
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Root directory for pipeline artifacts (default: artifacts)",
    )
    parser.add_argument(
        "--raw-path",
        help="Override path to raw parquet (defaults to stage_01_ingestion/raw.parquet)",
    )
    return parser.parse_args()


def resolve_raw_path(run_id: str, artifacts_root: Path, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return artifacts_root / run_id / "stage_01_ingestion" / "raw.parquet"


def main() -> int:
    args = parse_args()
    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    raw_path = resolve_raw_path(args.run_id, artifacts_root, args.raw_path)
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw parquet not found: {raw_path}")

    cfg: Dict[str, Any] = {"artifacts_root": artifacts_root.as_posix()}
    inputs: Dict[str, Any] = {"raw": raw_path.as_posix()}
    result: Dict[str, Any] = quality.run(args.run_id, inputs, cfg)  # type: ignore[assignment]
    _emit_json(result)
    return 0 if result.get("status") != "STOP" else 1


if __name__ == "__main__":
    raise SystemExit(main())
