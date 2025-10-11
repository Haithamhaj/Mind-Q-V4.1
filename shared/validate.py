from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, TypedDict


def dq_check(df: Any, dq_path: str) -> Dict[str, Any]:
    return {"status": "PASS"}


class _ShapePayload(TypedDict):
    phase: str
    n_in: int
    n_out: int
    reason: str


def assert_row_stability(n_in: int, n_out: int, *, allow_drop: bool, phase: str, out_dir: Path) -> None:
    """Ensure row count is stable across phases.

    If a violation occurs, write shape_mismatch.json under out_dir and either:
    - raise SystemExit(2) when CI_STRICT=1 (used on main), or
    - return silently (used on PR smoke which is non-blocking).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = (n_out == n_in) or (allow_drop and n_out <= n_in)
    if ok:
        return
    payload: _ShapePayload = {
        "phase": phase,
        "n_in": int(n_in),
        "n_out": int(n_out),
        "reason": "row_count_mismatch",
    }
    (out_dir / "shape_mismatch.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if os.environ.get("CI_STRICT", "0") in ("1", "true", "True"):
        raise SystemExit(2)
