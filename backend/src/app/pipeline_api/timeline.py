from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.phase_manifest import PhaseDefinition, PhaseResource, iter_phase_definitions
from shared.run_events import load_phase_events, load_phase_meta


def _stage_directory_for_phase(phase_id: str) -> str:
    phase = phase_id.lstrip("_")
    return phase if phase.startswith("stage_") else f"stage_{phase}"


def _serialise_resource(resource: PhaseResource) -> Dict[str, Any]:
    return {
        "id": resource.id,
        "name": asdict(resource.name),
        "description": asdict(resource.description),
    }


def _serialise_definition(definition: PhaseDefinition) -> Dict[str, Any]:
    return {
        "id": definition.id,
        "name": asdict(definition.name),
        "description": asdict(definition.description),
        "expected_inputs": [_serialise_resource(item) for item in definition.expected_inputs],
        "expected_outputs": list(definition.expected_outputs),
        "key_checks": list(definition.key_checks),
        "common_failures": list(definition.common_failures),
        "learning_resources": [
            {"title": item.title, "url": item.url} for item in definition.learning_resources
        ],
    }


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def build_run_timeline(run_id: str, artifacts_root: Path) -> Dict[str, Any]:
    phases_payload: List[Dict[str, Any]] = []
    status_counts: Dict[str, int] = {}
    earliest_start: Optional[datetime] = None
    latest_finish: Optional[datetime] = None
    phases_with_errors: List[str] = []
    phases_with_warnings: List[str] = []

    for definition in iter_phase_definitions():
        stage_dir_guess = _stage_directory_for_phase(definition.id)
        meta = load_phase_meta(artifacts_root, run_id, stage_dir_guess)
        stage_dir = meta.get("stage_directory") if isinstance(meta, dict) else stage_dir_guess
        stage_dir_str = str(stage_dir) if stage_dir else stage_dir_guess
        events = load_phase_events(artifacts_root, run_id, stage_dir_str)
        status = "NOT_RUN"
        if isinstance(meta, dict):
            status = str(meta.get("status", "UNKNOWN")) or "UNKNOWN"
            started = _parse_timestamp(meta.get("started_at"))
            finished = _parse_timestamp(meta.get("finished_at"))
            if started and (earliest_start is None or started < earliest_start):
                earliest_start = started
            if finished and (latest_finish is None or finished > latest_finish):
                latest_finish = finished
            if status.upper() == "FAIL":
                phases_with_errors.append(definition.id)
            elif status.upper() not in ("PASS", "SUCCESS"):
                phases_with_warnings.append(definition.id)
        else:
            # Look for warning/error events even when meta missing
            if any(event.get("event") == "phase_error" for event in events):
                status = "FAIL"
                phases_with_errors.append(definition.id)
            elif events:
                status = "UNKNOWN"

        status_counts[status] = status_counts.get(status, 0) + 1

        phase_entry = {
            "id": definition.id,
            "stage_directory": stage_dir_str,
            "definition": _serialise_definition(definition),
            "meta": meta,
            "events": events,
        }
        phases_payload.append(phase_entry)

    summary: Dict[str, Any] = {
        "status_counts": status_counts,
        "phases_with_errors": phases_with_errors,
        "phases_with_warnings": phases_with_warnings,
    }
    if earliest_start:
        summary["started_at"] = earliest_start.isoformat()
    if latest_finish:
        summary["finished_at"] = latest_finish.isoformat()
    if earliest_start and latest_finish:
        summary["duration_seconds"] = (latest_finish - earliest_start).total_seconds()

    return {
        "run_id": run_id,
        "artifacts_root": artifacts_root.as_posix(),
        "summary": summary,
        "phases": phases_payload,
    }
