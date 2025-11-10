#!/usr/bin/env python3
"""Ensure runtime modules do not import from `phases.*` directly."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOW_TOP_LEVEL = {"tests", "compat"}
SKIP_DIRS = {"node_modules", ".venv", "attachments", "attached_assets"}
PATTERN = re.compile(r"^\s*from\s+phases\.")


def _should_skip(path: Path) -> bool:
    parts = path.relative_to(ROOT).parts
    if not parts:
        return False
    if parts[0] in SKIP_DIRS:
        return True
    if parts[0].startswith('.'):
        return True
    return False


def main() -> int:
    failures: list[str] = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if _should_skip(path):
            continue
        top = rel.parts[0]
        if top in ALLOW_TOP_LEVEL:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in PATTERN.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            failures.append(f"{rel.as_posix()}:{line}: forbidden import '{match.group(0).strip()}'")
    if failures:
        for entry in failures:
            print(entry)
        print("Phases import policy failed. Only tests/compat may import from phases.*", file=sys.stderr)
        return 1
    print("Phases import policy: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
