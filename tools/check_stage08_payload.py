#!/usr/bin/env python3
"""Validate Stage 08 sample payloads against the published schema."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts/bi/story_v1.1.schema.json"
FIXTURE_GLOBS = ("stage_08_run_*", "stage_08_small_sample", "stage_08_large_sample")
ALLOWED_EXTRAS = {"context"}


def _load_schema_keys() -> set[str]:
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Stage 08 schema not found: {SCHEMA_PATH}")
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    props = payload.get("properties") if isinstance(payload, dict) else None
    if not isinstance(props, dict):
        return set(ALLOWED_EXTRAS)
    return set(props.keys()) | ALLOWED_EXTRAS


def _iter_fixture_payloads() -> Dict[Path, Dict[str, Any]]:
    fixtures: Dict[Path, Dict[str, Any]] = {}
    for pattern in FIXTURE_GLOBS:
        for directory in Path.cwd().glob(pattern):
            insights_file = directory / "insights_report.json"
            if insights_file.exists():
                try:
                    fixtures[insights_file] = json.loads(insights_file.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    fixtures[insights_file] = {}
    return fixtures


def main() -> int:
    allowed_keys = _load_schema_keys()
    fixtures = _iter_fixture_payloads()
    violations: list[str] = []
    for path, payload in fixtures.items():
        if not isinstance(payload, dict):
            continue
        for key in payload.keys():
            if key not in allowed_keys:
                violations.append(f"{path}: unexpected top-level key '{key}'")
    if violations:
        for entry in violations:
            print(entry)
        print("Stage 08 payload check failed: update schema/tests or allowlist.")
        return 1
    print("Stage 08 payload check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
