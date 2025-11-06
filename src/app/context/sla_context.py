from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import polars as pl  # type: ignore

JsonDict = Dict[str, Any]

STAGE_09_DIR = "stage_09_business_validation"
DEFAULT_CONTEXT_DIR = Path("artifacts") / "context"


def _read_json(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _tokenize(text: str) -> List[str]:
    return [token for token in re.split(r"\W+", text.lower()) if token]


def _score_text(query: str, content: str) -> float:
    if not query or not content:
        return 0.0
    q_tokens = set(_tokenize(query))
    c_tokens = set(_tokenize(content))
    if not q_tokens or not c_tokens:
        return SequenceMatcher(None, query.lower(), content.lower()).ratio()
    token_overlap = len(q_tokens & c_tokens) / max(len(q_tokens), 1)
    coverage = len(q_tokens & c_tokens) / max(len(c_tokens), 1)
    seq_ratio = SequenceMatcher(None, query.lower(), content.lower()).ratio()
    return float(token_overlap * 0.6 + coverage * 0.2 + seq_ratio * 0.2)


@dataclass(slots=True)
class ContextEntry:
    entry_id: str
    run_id: str
    type: str
    title: str
    content: str
    metadata: JsonDict

    def to_json(self) -> JsonDict:
        return {
            "entry_id": self.entry_id,
            "run_id": self.run_id,
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
        }


def _entry_id(run_id: str, suffix: str, index: int) -> str:
    return f"{run_id}:{suffix}:{index:03d}"


def _format_number(value: Optional[float]) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    if abs(value) >= 1:
        return f"{value:,.2f}"
    return f"{value:.4f}"


def _build_sla_entries(run_id: str, summary: JsonDict) -> List[ContextEntry]:
    results = summary.get("results") or []
    entries: List[ContextEntry] = []
    for idx, item in enumerate(results):
        title = f"SLA term: {item.get('kpi', 'unknown')}"
        metadata = {
            "kpi": item.get("kpi"),
            "status": item.get("status"),
            "reason": item.get("reason"),
            "window": item.get("window"),
            "unit": item.get("unit"),
            "source": item.get("source"),
        }
        actual = item.get("actual")
        warn = item.get("warn")
        stop = item.get("stop")
        target = item.get("target")
        paragraph = (
            f"Run {run_id} SLA term '{item.get('kpi')}' is {item.get('status', 'UNKNOWN')}. "
            f"Actual value: {_format_number(actual)}; "
            f"target: {_format_number(target)}; warn threshold: {_format_number(warn)}; "
            f"stop threshold: {_format_number(stop)}. Reason: {item.get('reason') or 'n/a'}."
        )
        notes = item.get("notes") or []
        if notes:
            paragraph += f" Notes: {' | '.join(str(note) for note in notes)}."
        entries.append(
            ContextEntry(
                entry_id=_entry_id(run_id, "sla", idx),
                run_id=run_id,
                type="sla_term",
                title=title,
                content=paragraph,
                metadata=metadata,
            )
        )
    if not entries and summary:
        entries.append(
            ContextEntry(
                entry_id=_entry_id(run_id, "sla", 0),
                run_id=run_id,
                type="sla_term",
                title="SLA summary",
                content="No explicit SLA terms were detected for this run, but a summary file is present.",
                metadata={"notes": summary.get("notes", [])},
            )
        )
    return entries


def _build_gate_entries(run_id: str, validation_report: JsonDict) -> List[ContextEntry]:
    gate = validation_report.get("gate") or {}
    gate_status = gate.get("status", "UNKNOWN")
    gate_reasons = gate.get("reasons") or []
    payload = validation_report.get("perf") or {}
    kpis = validation_report.get("kpi_recalc") or []
    entries: List[ContextEntry] = []
    content = (
        f"Validation gate status for run {run_id} is {gate_status}. "
        f"Reasons: {', '.join(gate_reasons) if gate_reasons else 'None recorded'}."
    )
    if payload:
        metrics = ", ".join(f"{key}: {_format_number(value)}" for key, value in payload.items())
        content += f" Performance metrics: {metrics}."
    if kpis:
        deltas = []
        for item in kpis:
            name = item.get("name")
            rel = item.get("rel_delta_pct")
            if rel is None:
                continue
            deltas.append(f"{name}: {rel:.2f}% change")
        if deltas:
            content += " KPI deltas: " + "; ".join(deltas) + "."
    entries.append(
        ContextEntry(
            entry_id=_entry_id(run_id, "gate", 0),
            run_id=run_id,
            type="validation_gate",
            title="Validation gate overview",
            content=content,
            metadata={"gate_status": gate_status, "gate_reasons": gate_reasons},
        )
    )
    return entries


def _build_story_entries(run_id: str, story_payload: JsonDict) -> List[ContextEntry]:
    items = story_payload.get("items") or []
    entries: List[ContextEntry] = []
    for idx, item in enumerate(items):
        title = item.get("title") or f"Story card {idx + 1}"
        summary = item.get("summary") or ""
        details = item.get("details") or []
        content = f"{title}: {summary}"
        if details:
            content += " Details: " + " | ".join(str(detail) for detail in details)
        entries.append(
            ContextEntry(
                entry_id=_entry_id(run_id, "story", idx),
                run_id=run_id,
                type="story",
                title=title,
                content=content,
                metadata={"tags": item.get("tags"), "confidence": item.get("confidence")},
            )
        )
    return entries


def _build_segment_entries(run_id: str, stage_dir: Path) -> List[ContextEntry]:
    segment_path = stage_dir / "segment_insights.parquet"
    if not segment_path.exists():
        return []
    try:
        df = pl.read_parquet(segment_path.as_posix())
    except Exception:
        return []
    entries: List[ContextEntry] = []
    limited = df.head(5)
    for idx, row in enumerate(limited.iter_rows(named=True)):
        segment = row.get("segment") or row.get("SEGMENT") or f"segment_{idx + 1}"
        kpi = row.get("kpi") or row.get("KPI")
        value = row.get("value") or row.get("VALUE")
        content = f"Segment insight '{segment}' for run {run_id} relates to KPI '{kpi}' with value {_format_number(value)}."
        metadata = _json_safe(row)
        if not isinstance(metadata, dict):
            metadata = {"value": metadata}
        entries.append(
            ContextEntry(
                entry_id=_entry_id(run_id, "segment", idx),
                run_id=run_id,
                type="segment_insight",
                title=f"Segment: {segment}",
                content=content,
                metadata=metadata,  # type: ignore[assignment]
            )
        )
    return entries


def build_sla_context(
    run_id: str,
    *,
    artifacts_root: Path,
    output_dir: Optional[Path] = None,
) -> Tuple[Path, Path]:
    stage_dir = artifacts_root / run_id / STAGE_09_DIR
    summary = _read_json(stage_dir / "sla_summary.json")
    validation_report = _read_json(stage_dir / "validation_report.json")
    story_payload = _read_json(stage_dir / "story_ops.json")
    notes = summary.get("notes") if isinstance(summary, dict) else None

    entries: List[ContextEntry] = []
    entries.extend(_build_sla_entries(run_id, summary))
    if validation_report:
        entries.extend(_build_gate_entries(run_id, validation_report))
    if story_payload:
        entries.extend(_build_story_entries(run_id, story_payload))
    entries.extend(_build_segment_entries(run_id, stage_dir))

    if not entries:
        entries.append(
            ContextEntry(
                entry_id=_entry_id(run_id, "placeholder", 0),
                run_id=run_id,
                type="info",
                title="No SLA context",
                content="No SLA or validation context was available for this run.",
                metadata={},
            )
        )

    context_dir = (output_dir / run_id) if output_dir else (DEFAULT_CONTEXT_DIR / run_id)
    context_dir.mkdir(parents=True, exist_ok=True)

    context_path = context_dir / f"{run_id}_sla.jsonl"
    with context_path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry.to_json(), ensure_ascii=False) + "\n")

    manifest_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entries": len(entries),
        "notes": notes or [],
        "sources": {
            "sla_summary": (stage_dir / "sla_summary.json").as_posix(),
            "validation_report": (stage_dir / "validation_report.json").as_posix(),
            "story_ops": (stage_dir / "story_ops.json").as_posix(),
            "segment_insights": (stage_dir / "segment_insights.parquet").as_posix(),
        },
    }
    manifest_path = context_dir / f"{run_id}_manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return context_path, manifest_path


def load_context_entries(context_dir: Path, run_id: str) -> List[ContextEntry]:
    context_path = context_dir / run_id / f"{run_id}_sla.jsonl"
    if not context_path.exists():
        raise FileNotFoundError(f"SLA context not found for run {run_id}: {context_path}")
    entries: List[ContextEntry] = []
    with context_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            meta = payload.get("metadata")
            if not isinstance(meta, dict):
                meta = {} if meta is None else {"value": meta}
            entries.append(
                ContextEntry(
                    entry_id=payload.get("entry_id"),
                    run_id=payload.get("run_id"),
                    type=payload.get("type"),
                    title=payload.get("title"),
                    content=payload.get("content"),
                    metadata=meta,
                )
            )
    return entries


def search_context(
    query: str,
    entries: Sequence[ContextEntry],
    *,
    top_k: int = 5,
    allowed_types: Optional[Iterable[str]] = None,
) -> List[Tuple[ContextEntry, float]]:
    filtered: Sequence[ContextEntry]
    if allowed_types:
        allowed_set = set(allowed_types)
        filtered = [entry for entry in entries if entry.type in allowed_set]
    else:
        filtered = entries

    scored = [(entry, _score_text(query, entry.content)) for entry in filtered]
    ranked = sorted(scored, key=lambda pair: pair[1], reverse=True)
    return [item for item in ranked if item[1] > 0.0][:top_k]


__all__ = [
    "ContextEntry",
    "build_sla_context",
    "load_context_entries",
    "search_context",
]
def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, type(None), bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(val) for val in value]
    return str(value)
