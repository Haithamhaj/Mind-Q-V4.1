#!/usr/bin/env python3
"""Capture /api/bi payloads using the Python-only pipeline outputs."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.app.api import bi  # noqa: E402  (import after sys.path tweak)

DEFAULT_OUTPUT = Path("tmp/bi_payloads_python")


async def _collect(run_id: str, limit: int) -> Dict[str, Any]:
    orders = await bi.get_orders(run=run_id, limit=limit)
    metrics = await bi.get_metrics(run=run_id)
    intelligence = await bi.get_intelligence(run=run_id)
    return {"orders": orders, "metrics": metrics, "intelligence": intelligence}


def _write_payload(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump BI payloads for a given run id")
    parser.add_argument("--run-id", default="run-latest", help="Pipeline run id (default: run-latest)")
    parser.add_argument("--limit", type=int, default=5000, help="Row limit for orders payload")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory where JSON payloads will be written",
    )
    args = parser.parse_args()

    payloads = asyncio.run(_collect(args.run_id, args.limit))

    summary = {
        "orders": {
            "rows": len(payloads["orders"].get("rows", [])),
            "columns": payloads["orders"].get("columns"),
            "source": payloads["orders"].get("source"),
        },
        "metrics": {
            "metrics_count": len(payloads["metrics"].get("metrics", [])),
            "catalog_keys": list(payloads["metrics"].keys()),
        },
        "intelligence": {
            "items": len(payloads["intelligence"].get("items", [])),
            "sections": [key for key in payloads["intelligence"].keys() if key != "items"],
        },
    }

    for name, payload in payloads.items():
        _write_payload(args.output / f"{name}.json", payload)
    _write_payload(args.output / "summary.json", summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
