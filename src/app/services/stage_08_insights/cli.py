from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from . import impl


def _configure_stdio() -> None:
    if not os.environ.get("PYTHONUTF8"):
        os.environ["PYTHONUTF8"] = "1"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage 08 — Insights & Aggregations")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier")
    parser.add_argument("--artifacts-root", default="artifacts", help="Root directory for artifacts (default: artifacts)")
    parser.add_argument("--correlations", help="Override path to correlations.json")
    parser.add_argument("--redundancy", help="Override path to redundancy.json")
    parser.add_argument("--features", help="Override path to features.parquet")
    parser.add_argument("--text-profile", help="Optional override for text_profile.json")
    parser.add_argument("--sentiment", help="Optional override for sentiment_features.parquet")
    parser.add_argument("--config", help="Optional JSON string with additional configuration overrides")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    overrides: Dict[str, Any] = {}
    if args.config:
        overrides = json.loads(args.config)
    input_paths: Dict[str, Any] = {
        key: value
        for key, value in {
            "correlations": args.correlations,
            "redundancy": args.redundancy,
            "features": args.features,
            "text_profile": args.text_profile,
            "sentiment": args.sentiment,
        }.items()
        if value
    }
    config = {"artifacts_root": args.artifacts_root, **overrides}
    result = impl.run(args.run_id, input_paths, config)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
