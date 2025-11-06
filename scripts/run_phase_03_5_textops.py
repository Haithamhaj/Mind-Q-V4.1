from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

from backend.src.app.services.stage_03_5_textops import run as run_textops  # noqa: E402


def _load_dotenv() -> None:
    if load_dotenv is None:
        return
    candidates = [
        PROJECT_ROOT / "backend" / ".env",
        PROJECT_ROOT / ".env",
        Path.cwd() / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate)

def _emit_json(payload: Any) -> None:
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 03.5 TextOps")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier")
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Root directory for pipeline artifacts (default: artifacts)",
    )
    parser.add_argument(
        "--config",
        default="config/textops.yaml",
        help="Path to TextOps runtime configuration YAML",
    )
    parser.add_argument("--shipments", help="Override glob for shipments parquet files")
    parser.add_argument("--domain-dict", help="Override path to Phase 03 domain_dict.json")
    parser.add_argument("--text-catalog", help="Override path to Phase 03 text catalog JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()

    cfg: Dict[str, Any] = {
        "artifacts_root": artifacts_root.as_posix(),
        "config_path": config_path.as_posix(),
    }
    inputs: Dict[str, Any] = {}
    if args.shipments:
        inputs["shipments"] = args.shipments
    if args.domain_dict:
        inputs["domain_dict"] = args.domain_dict
    if args.text_catalog:
        inputs["text_catalog"] = args.text_catalog

    result = run_textops(args.run_id, inputs, cfg)
    _emit_json(result)
    return 0 if result.get("status") != "STOP" else 1


if __name__ == "__main__":
    raise SystemExit(main())

