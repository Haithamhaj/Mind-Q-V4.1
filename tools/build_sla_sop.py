from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence, cast

from backend.src.app.services.sla_sop import (
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_SOP_ROOT,
    build_expectations_payload,
    discover_sop_documents,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract SLA SOP expectations using an LLM.")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier.")
    parser.add_argument(
        "--artifacts-root",
        default="backend/artifacts",
        help="Directory where stage_10_bi outputs should be written.",
    )
    parser.add_argument("--sop-root", default=str(DEFAULT_SOP_ROOT), help="Root directory that contains SOP files.")
    parser.add_argument("--provider", default=DEFAULT_LLM_PROVIDER, help="LLM provider to use.")
    parser.add_argument("--model", default=DEFAULT_LLM_MODEL, help="LLM model identifier to use.")
    parser.add_argument("--temperature", type=float, default=0.1, help="Sampling temperature for the LLM call.")
    parser.add_argument("--max-tokens", type=int, default=1200, help="Maximum tokens for each extraction call.")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional explicit output JSON path. Defaults to <artifacts-root>/<run-id>/stage_10_bi/semantic/sop_expectations.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_id: str = args.run_id
    sop_root = Path(args.sop_root)
    artifacts_root = Path(args.artifacts_root)

    documents = discover_sop_documents(run_id, roots=[sop_root / run_id, sop_root / "common"])
    if not documents:
        print(f"[sop-extractor] no documents found under {sop_root} for run {run_id}")
        return

    payload = build_expectations_payload(
        documents,
        provider=args.provider,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    target_path = (
        Path(args.output)
        if args.output
        else artifacts_root / run_id / "stage_10_bi" / "semantic" / "sop_expectations.json"
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    expectations = payload.get("expectations")
    if isinstance(expectations, Sequence):
        expectation_count = len(cast(Sequence[Any], expectations))
    else:
        expectation_count = 0
    print(f"[sop-extractor] wrote {target_path} ({expectation_count} expectations)")


if __name__ == "__main__":
    main()
