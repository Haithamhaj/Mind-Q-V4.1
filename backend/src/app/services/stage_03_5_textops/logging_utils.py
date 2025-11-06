from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Sequence

from zoneinfo import ZoneInfo


@dataclass
class Timer:
    label: str
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float | None = None

    def stop(self) -> float:
        if self.finished_at is None:
            self.finished_at = time.monotonic()
        return self.finished_at - self.started_at


def utcnow_iso(tz_name: str | None = None) -> str:
    tz = ZoneInfo(tz_name) if tz_name else timezone.utc
    return datetime.now(tz).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, entries: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False))
            fh.write("\n")


def append_log(logs: List[dict[str, Any]], event: str, **fields: Any) -> None:
    logs.append({"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields})


def artefact_manifest(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"artifacts": list(entries)}


__all__ = [
    "Timer",
    "utcnow_iso",
    "sha256_file",
    "write_json",
    "write_jsonl",
    "append_log",
    "artefact_manifest",
]
