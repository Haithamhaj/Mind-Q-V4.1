from __future__ import annotations

import argparse
import json
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List

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


ingest = _load_phase_impl("01_ingestion")  # type: ignore


def _emit_json(payload: Any) -> None:
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 01 ingestion against a local file")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier")
    parser.add_argument("--input", required=True, help="Path to input CSV/Parquet file")
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Root directory for pipeline artifacts (default: artifacts)",
    )
    parser.add_argument(
        "--min-file-size",
        type=int,
        default=100 * 1024,
        help="Minimum file size in bytes required for ingestion (default: 102400)",
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=10,
        help="Minimum number of rows required after ingestion (default: 10)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    print(f"[P01] using input file: {input_path}")
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    cfg: Dict[str, Any] = {
        "artifacts_root": artifacts_root.as_posix(),
        "ingestion": {
            "min_file_size_bytes": int(args.min_file_size),
            "min_rows": int(args.min_rows),
        },
    }
    inputs: Dict[str, Any] = {"files": [input_path.as_posix()]}
    result: Dict[str, Any] = ingest.run(args.run_id, inputs, cfg)  # type: ignore[assignment]
    _emit_json(result)
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
