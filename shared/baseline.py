from __future__ import annotations

import json
import json
from pathlib import Path
from typing import Any, Dict, Optional


def baseline_path(artifacts_root: Path | str, run_id: str) -> Path:
    return Path(artifacts_root) / run_id / "baselines.json"


def load(artifacts_root: Path | str, run_id: str) -> Dict[str, Any]:
    path = baseline_path(artifacts_root, run_id)
    if not path.exists():
        raise FileNotFoundError(f"baseline file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def enforce_row_guard(
    *,
    expected: Optional[int],
    actual: int,
    phase: str,
    out_dir: Path,
    reason: str = "row_count_mismatch",
    force: bool = False,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if not force and (expected is None or expected == actual):
        return
    payload = {
        "phase": phase,
        "n_in": int(expected) if expected is not None else None,
        "n_out": int(actual),
        "reason": reason,
    }
    (out_dir / "shape_mismatch.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(1)


__all__ = ["baseline_path", "enforce_row_guard", "load"]
