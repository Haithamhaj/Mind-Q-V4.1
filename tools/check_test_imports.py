#!/usr/bin/env python3
"""CI guard to ensure tests do not rely on deprecated import paths."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("phases._09_business_validation", re.compile(r"from\s+phases\._09_business_validation\s+import", re.MULTILINE)),
    ("pipeline.PipelineRequest", re.compile(r"from\s+pipeline\s+import\s+PipelineRequest", re.MULTILINE)),
    ("fastapi_app", re.compile(r"fastapi_app")),
)


def main() -> int:
    failures: list[str] = []
    for path in TESTS_DIR.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                failures.append(f"{path.relative_to(ROOT)}:{line}: found forbidden pattern '{label}'")
    if failures:
        for entry in failures:
            print(entry)
        print("Deprecated test imports detected. See matches above.", file=sys.stderr)
        return 1
    print("Test import guard: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
