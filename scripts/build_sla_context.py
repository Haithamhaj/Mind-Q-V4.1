from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.context.sla_context import build_sla_context  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SLA context bundles for LLM retrieval.")
    parser.add_argument("--run-id", action="append", dest="run_ids", required=True, help="Run identifier to process (can be passed multiple times).")
    parser.add_argument("--artifacts-root", default="artifacts", help="Root directory where pipeline artifacts are stored.")
    parser.add_argument("--output-dir", default=None, help="Optional directory override for context output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None

    results: List[dict] = []
    for run_id in args.run_ids:
        context_path, manifest_path = build_sla_context(run_id, artifacts_root=artifacts_root, output_dir=output_dir)
        results.append({"run_id": run_id, "context": context_path.as_posix(), "manifest": manifest_path.as_posix()})

    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
