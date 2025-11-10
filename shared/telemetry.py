from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


def current_mem_mb() -> float:
    return 0.0


def _telemetry_dir(root: Path | str) -> Path:
    return Path(root).expanduser().resolve() / "_telemetry"


def snapshot_threshold(
    metric: str,
    value: float,
    artifacts_root: Path | str,
    *,
    details: Optional[Dict[str, Any]] = None,
) -> Optional[float]:
    """Persist the latest threshold value and return the prior reading if any."""

    telemetry_dir = _telemetry_dir(artifacts_root)
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    path = telemetry_dir / "thresholds.jsonl"

    previous: Optional[float] = None
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("metric") == metric:
                raw_value = payload.get("value")
                try:
                    previous = float(raw_value)
                except (TypeError, ValueError):
                    previous = None
                else:
                    break

    entry = {
        "timestamp": time.time(),
        "metric": metric,
        "value": float(value),
        "details": details or {},
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return previous


__all__ = ["current_mem_mb", "snapshot_threshold"]
