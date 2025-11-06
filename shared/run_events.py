from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SENSITIVE_KEY_TOKENS = ("key", "token", "secret", "password", "credential")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalise_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalise_value(v) for v in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if any(token in lowered for token in SENSITIVE_KEY_TOKENS):
                redacted[key] = "***"
            else:
                redacted[key] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def sanitise_payload(payload: Any) -> Any:
    return _redact_sensitive(_normalise_value(payload))


def derive_phase_identity(module_path: str) -> Tuple[str, str]:
    """
    Returns (phase_id, stage_directory_name) for a given module path.
    """
    if not module_path:
        raise ValueError("module_path is required to derive phase identity")
    parts = module_path.split(".")
    if len(parts) < 2:
        segment = module_path
    else:
        segment = parts[-2]

    if segment.startswith("stage_"):
        phase_id = segment[len("stage_") :]
        phase_id_clean = phase_id.lstrip("_")
        stage_dir = segment
    elif segment.startswith("phase"):
        phase_id = segment[len("phase") :]
        phase_id_clean = phase_id.lstrip("_")
        stage_dir = f"stage_{phase_id_clean}"
    else:
        phase_id = segment
        phase_id_clean = phase_id.lstrip("_")
        stage_dir = f"stage_{phase_id_clean}"

    return phase_id_clean, stage_dir


def _events_path(base: Path) -> Path:
    return base / "events.jsonl"


def _meta_path(base: Path) -> Path:
    return base / "meta.json"


@dataclass
class PhaseRunRecorder:
    artifacts_root: Path
    run_id: str
    phase_id: str
    stage_dir: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.phase_dir = self.artifacts_root / self.run_id / self.stage_dir
        self.phase_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = _events_path(self.phase_dir)
        self._meta_path = _meta_path(self.phase_dir)
        self.started_at = _utc_now_iso()
        self._started_monotonic = time.perf_counter()
        self._finalised = False
        self._inputs_snapshot = sanitise_payload(self.inputs)
        self._config_snapshot = sanitise_payload(self.config)
        self.log_event(
            "phase_start",
            payload={
                "inputs": self._inputs_snapshot,
                "config": self._config_snapshot,
            },
        )

    def __enter__(self) -> "PhaseRunRecorder":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is not None:
            self.record_failure(exc)
        return False

    def log_event(
        self,
        event: str,
        *,
        message: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        level: str = "info",
    ) -> None:
        record = {
            "ts": _utc_now_iso(),
            "run_id": self.run_id,
            "phase_id": self.phase_id,
            "event": event,
            "level": level,
            "message": message,
            "payload": sanitise_payload(payload) if payload is not None else None,
        }
        with self._events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    def finalise(
        self,
        status: str,
        *,
        outputs: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self._finalised:
            return
        duration_ms = int((time.perf_counter() - self._started_monotonic) * 1000)
        finished_at = _utc_now_iso()

        payload = {
            "status": status,
            "outputs": sanitise_payload(outputs or {}),
            "metrics": sanitise_payload(metrics or {}),
            "context": sanitise_payload(context or {}),
            "duration_ms": duration_ms,
        }
        self.log_event("phase_end", payload=payload)

        meta = {
            "phase_id": self.phase_id,
            "stage_directory": self.stage_dir,
            "run_id": self.run_id,
            "status": status,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "inputs": self._inputs_snapshot,
            "config": self._config_snapshot,
            "outputs": payload["outputs"],
            "metrics": payload["metrics"],
            "context": payload["context"],
        }
        self._meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        self._finalised = True

    def record_failure(self, exc: BaseException) -> None:
        if self._finalised:
            return
        duration_ms = int((time.perf_counter() - self._started_monotonic) * 1000)
        finished_at = _utc_now_iso()
        message = f"{exc.__class__.__name__}: {exc}"
        self.log_event(
            "phase_error",
            level="error",
            payload={"exception": message, "duration_ms": duration_ms},
        )
        meta = {
            "phase_id": self.phase_id,
            "stage_directory": self.stage_dir,
            "run_id": self.run_id,
            "status": "FAIL",
            "started_at": self.started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "inputs": self._inputs_snapshot,
            "config": self._config_snapshot,
            "error": message,
        }
        self._meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        self._finalised = True


def append_event(
    artifacts_root: Path,
    run_id: str,
    stage_dir: str,
    phase_id: str,
    event: str,
    *,
    message: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    level: str = "info",
) -> None:
    base = artifacts_root / run_id / stage_dir
    base.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": _utc_now_iso(),
        "run_id": run_id,
        "phase_id": phase_id,
        "event": event,
        "level": level,
        "message": message,
        "payload": sanitise_payload(payload) if payload is not None else None,
    }
    with _events_path(base).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False))
        handle.write("\n")


__all__ = [
    "PhaseRunRecorder",
    "derive_phase_identity",
    "append_event",
    "sanitise_payload",
]


def load_phase_events(artifacts_root: Path, run_id: str, stage_dir: str) -> List[Dict[str, Any]]:
    path = _events_path(artifacts_root / run_id / stage_dir)
    if not path.exists():
        return []
    events: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                events.append(record)
    return events


def load_phase_meta(artifacts_root: Path, run_id: str, stage_dir: str) -> Optional[Dict[str, Any]]:
    path = _meta_path(artifacts_root / run_id / stage_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return None
    except json.JSONDecodeError:
        return None


__all__.extend(["load_phase_events", "load_phase_meta"])
