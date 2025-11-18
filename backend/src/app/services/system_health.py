from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class SystemHealth:
    """Passive collector for pipeline health metrics."""

    artifacts_root: Path
    events: List[Dict[str, object]] = field(default_factory=list)

    def log_llm_cost(self, run_id: str, amount_usd: float) -> None:
        self.events.append(
            {
                "type": "llm_cost",
                "run_id": str(run_id),
                "amount_usd": float(amount_usd),
            }
        )

    def log_ingestion_latency(self, run_id: str, rows: int, minutes_per_1m: float) -> None:
        self.events.append(
            {
                "type": "ingestion_latency",
                "run_id": str(run_id),
                "rows": int(rows),
                "minutes_per_1m": float(minutes_per_1m),
            }
        )

    def log_cache_metrics(self, run_id: str, hit_rate: float) -> None:
        self.events.append(
            {
                "type": "cache_metrics",
                "run_id": str(run_id),
                "hit_rate": float(hit_rate),
            }
        )

    def emit_report(self, *, extra: Optional[Dict[str, object]] = None) -> Path:
        payload: Dict[str, object] = {"events": self.events}
        if extra:
            payload["extra"] = extra
        out_path = self.artifacts_root / "system_health.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return out_path
