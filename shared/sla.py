from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# Optional imports are deferred to keep runtime dependencies light.

TABULAR_EXTENSIONS = {".csv", ".tsv", ".psv", ".xls", ".xlsx", ".xlsm", ".xlsb", ".ods"}
TEXT_EXTENSIONS = {".txt", ".md", ".rtf"}
HTML_EXTENSIONS = {".html", ".htm"}
PDF_EXTENSIONS = {".pdf"}
DOC_EXTENSIONS = {".docx"}

DEFAULT_MAX_TABLE_ROWS = 200


@dataclass(slots=True)
class SLATerm:
    kpi: str
    direction: str = "gte"
    target: Optional[float] = None
    warn: Optional[float] = None
    stop: Optional[float] = None
    window: Optional[str] = None
    unit: Optional[str] = None
    source: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


@dataclass(slots=True)
class SLATermResult:
    term: SLATerm
    actual: Optional[float]
    status: str
    reason: str


@dataclass(slots=True)
class SLABundle:
    run_id: str
    manifest_path: Optional[Path]
    entries: List[Dict[str, Any]] = field(default_factory=list)
    terms: List[SLATerm] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class _PlainHTMLExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:  # pragma: no cover - tiny helper
        text = data.strip()
        if text:
            self._chunks.append(text)

    def text(self) -> str:
        return "\n".join(self._chunks)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _media_type(path: Path) -> str:
    guess, _ = mimetypes.guess_type(path.as_posix())
    return guess or "application/octet-stream"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value != value:  # NaN check
            return ""
    return str(value)


def _frame_to_table(name: str, frame: "pd.DataFrame", *, max_rows: int) -> Dict[str, Any]:  # type: ignore[name-defined]
    import pandas as pd  # local import to avoid mandatory dependency at module import

    sample = frame.head(max_rows).copy()
    sample = sample.fillna("")
    rows: List[Dict[str, Any]] = []
    for _, row in sample.iterrows():
        rows.append({str(col): _safe_str(row[col]) for col in sample.columns})
    return {
        "name": name,
        "row_count": int(len(frame)),
        "columns": [str(col) for col in frame.columns],
        "sample_rows": rows,
    }


def _parse_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value != value:  # NaN
            return None
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    # Remove common operators and symbols.
    text = text.replace(",", "")
    text = re.sub(r"(?i)\b(?:>=|<=|>|<|eq|lte|gte|percent|pct)\b", "", text)
    percent = "%" in text
    cleaned = re.sub(r"[^0-9\.\-]", "", text)
    if not cleaned:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    if percent and number > 1:
        return number / 100.0
    return number


def _parse_direction(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if any(marker in text for marker in ("<=", "<", "max", "less")):
        return "lte"
    if any(marker in text for marker in (">=", ">", "min", "greater")):
        return "gte"
    return None


def _normalise_bullet_text(text: str) -> str:
    cleaned = text.replace("•", " ").replace("●", " ").replace("○", " ").replace("■", " ").replace("▪", " ")
    cleaned = cleaned.replace("\u2028", " ").replace("\u2029", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _infer_document_title(source_path: Path, text_summary: Optional[str]) -> str:
    if text_summary:
        for line in text_summary.splitlines():
            candidate = _normalise_bullet_text(line)
            candidate = re.sub(r"^[\d\.\)\-_:]+", "", candidate).strip()
            if len(candidate) >= 8:
                return candidate
    fallback = re.sub(r"[_\-]+", " ", source_path.stem).strip()
    return fallback or source_path.name


def _infer_terms(table: "pd.DataFrame", table_name: str) -> List[SLATerm]:  # type: ignore[name-defined]
    import pandas as pd

    if table.empty:
        return []

    candidates = [str(col).strip().lower() for col in table.columns]
    metric_key: Optional[str] = None
    for column, lowered in zip(table.columns, candidates):
        if any(marker in lowered for marker in ("kpi", "metric", "indicator", "name")):
            metric_key = column
            break
    if metric_key is None:
        if len(table.columns) > 0:
            metric_key = table.columns[0]
        else:
            return []

    terms: List[SLATerm] = []
    for idx, (_index, row) in enumerate(table.iterrows()):
        metric_raw = row.get(metric_key)
        metric_name = _safe_str(metric_raw).strip()
        if not metric_name:
            continue
        term = SLATerm(kpi=metric_name, source={"table": table_name, "row_index": int(idx)})
        term.raw["metric"] = metric_raw
        for column, lowered in zip(table.columns, candidates):
            value = row.get(column)
            if value is None or (isinstance(value, float) and value != value):
                continue
            text_value = _safe_str(value)
            lower_text = text_value.lower()
            term.raw[str(column)] = text_value
            if any(marker in lowered for marker in ("warn", "warning", "yellow")):
                parsed = _parse_numeric(value)
                if parsed is not None:
                    term.warn = parsed
                continue
            if any(marker in lowered for marker in ("stop", "red", "critical", "breach")):
                parsed = _parse_numeric(value)
                if parsed is not None:
                    term.stop = parsed
                continue
            if any(marker in lowered for marker in ("target", "goal", "threshold", "expected")):
                parsed = _parse_numeric(value)
                if parsed is not None:
                    term.target = parsed
                continue
            if any(marker in lowered for marker in ("window", "period", "span")):
                term.window = text_value
                continue
            if "unit" in lowered or "currency" in lowered:
                term.unit = text_value
                continue
            if "direction" in lowered or "sense" in lowered:
                parsed_direction = _parse_direction(text_value)
                if parsed_direction:
                    term.direction = parsed_direction
                continue
            if "comparison" in lowered and not term.direction:
                parsed_direction = _parse_direction(text_value)
                if parsed_direction:
                    term.direction = parsed_direction
                continue
            if "notes" in lowered or "comment" in lowered:
                term.notes.append(text_value)
        if term.warn is None and term.target is not None:
            term.warn = term.target
        if term.direction not in {"gte", "lte"}:
            inferred = _parse_direction(term.raw.get("direction"))
            term.direction = inferred or "gte"
        if term.warn is None and term.stop is None and term.target is None:
            continue
        terms.append(term)
    return terms


def _extract_tabular(
    path: Path,
    *,
    max_rows: int,
) -> Tuple[List[Dict[str, Any]], List[SLATerm], List[str]]:
    try:
        import pandas as pd
    except Exception as exc:  # pragma: no cover - optional dependency missing
        return [], [], [f"pandas_not_available::{exc}"]

    suffix = path.suffix.lower()
    tables: List[Dict[str, Any]] = []
    terms: List[SLATerm] = []
    notes: List[str] = []
    try:
        if suffix in {".csv", ".tsv", ".psv"}:
            sep = "," if suffix == ".csv" else "\t" if suffix == ".tsv" else "|"
            frame = pd.read_csv(path, dtype=object, sep=sep)
            tables.append(_frame_to_table(path.name, frame, max_rows=max_rows))
            terms.extend(_infer_terms(frame, path.name))
        elif suffix in {".xls", ".xlsx", ".xlsm", ".xlsb", ".ods"}:
            book = pd.read_excel(path, sheet_name=None, dtype=object)
            for sheet_name, frame in book.items():
                table_name = f"{path.name}::{sheet_name}"
                tables.append(_frame_to_table(table_name, frame, max_rows=max_rows))
                terms.extend(_infer_terms(frame, table_name))
        else:  # pragma: no cover - defensive
            notes.append(f"tabular_format_unsupported::{suffix}")
    except Exception as exc:  # pragma: no cover - pragmatic fallback
        notes.append(f"tabular_parse_error::{exc}")
    return tables, terms, notes


def _extract_pdf_text(path: Path) -> Tuple[Optional[str], List[str]]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        return None, [f"pypdf_unavailable::{exc}"]
    try:
        reader = PdfReader(path.as_posix())
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        return text or None, []
    except Exception as exc:  # pragma: no cover - defensive
        return None, [f"pdf_extract_error::{exc}"]


def _extract_docx_text(path: Path) -> Tuple[Optional[str], List[str]]:
    try:
        from zipfile import ZipFile
        from xml.etree import ElementTree
    except Exception as exc:  # pragma: no cover - defensive
        return None, [f"docx_extract_error::{exc}"]

    try:
        with ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
        tree = ElementTree.fromstring(xml)
        texts: List[str] = []
        for node in tree.iter():
            if node.text:
                fragment = node.text.strip()
                if fragment:
                    texts.append(fragment)
        return ("\n".join(texts).strip() or None), []
    except Exception as exc:  # pragma: no cover - defensive
        return None, [f"docx_extract_error::{exc}"]


def _extract_html_text(path: Path) -> Tuple[Optional[str], List[str]]:
    parser = _PlainHTMLExtractor()
    try:
        parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
        text = parser.text().strip()
        return text or None, []
    except Exception as exc:  # pragma: no cover - defensive
        return None, [f"html_extract_error::{exc}"]


def _extract_plain_text(path: Path) -> Tuple[Optional[str], List[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        return text or None, []
    except Exception as exc:  # pragma: no cover - defensive
        return None, [f"text_extract_error::{exc}"]


def _truncate_text(text: Optional[str], limit: int = 4000) -> Optional[str]:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def process_sla_file(
    source_path: Path,
    *,
    run_id: str,
    storage_dir: Path,
    processed_dir: Path,
    max_rows: int = DEFAULT_MAX_TABLE_ROWS,
) -> Dict[str, Any]:
    storage_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    digest = _hash_file(source_path)
    suffix = source_path.suffix.lower()
    digest_prefix = digest[:10]
    stem = source_path.stem
    if stem.endswith(digest_prefix):
        normalized_name = f"{stem}{suffix}"
    else:
        normalized_name = f"{stem}_{digest_prefix}{suffix}"
    stored_path = storage_dir / normalized_name
    if not stored_path.exists():
        shutil.copy2(source_path, stored_path)

    media_type = _media_type(stored_path)
    size_bytes = stored_path.stat().st_size

    tables: List[Dict[str, Any]] = []
    terms: List[SLATerm] = []
    notes: List[str] = []
    text_summary: Optional[str] = None

    if suffix in TABULAR_EXTENSIONS:
        tables, terms, table_notes = _extract_tabular(stored_path, max_rows=max_rows)
        notes.extend(table_notes)
    elif suffix in PDF_EXTENSIONS:
        text_summary, extract_notes = _extract_pdf_text(stored_path)
        notes.extend(extract_notes)
    elif suffix in DOC_EXTENSIONS:
        text_summary, extract_notes = _extract_docx_text(stored_path)
        notes.extend(extract_notes)
    elif suffix in HTML_EXTENSIONS:
        text_summary, extract_notes = _extract_html_text(stored_path)
        notes.extend(extract_notes)
    elif suffix in TEXT_EXTENSIONS:
        text_summary, extract_notes = _extract_plain_text(stored_path)
        notes.extend(extract_notes)
    else:
        text_summary, extract_notes = _extract_plain_text(stored_path)
        notes.extend(extract_notes or [f"format_fallback::{suffix}"])

    # Attempt to infer terms from unstructured text if needed.
    if not terms and text_summary:
        inferred_terms = _infer_terms_from_text(text_summary)
        terms.extend(inferred_terms)

    normalized_json_path = processed_dir / f"{normalized_name}.json"
    document_id = normalized_name
    document_path = normalized_json_path.as_posix()
    document_title = _infer_document_title(source_path, text_summary)

    for term in terms:
        term.source.setdefault("document_id", document_id)
        term.source.setdefault("document_path", document_path)
        term.source.setdefault("document_title", document_title)
        term.source.setdefault("document_sha", digest)

    normalized_payload = {
        "run_id": run_id,
        "created_at": _now_iso(),
        "source": stored_path.as_posix(),
        "original_name": source_path.name,
        "media_type": media_type,
        "size_bytes": size_bytes,
        "sha256": digest,
        "text_excerpt": _truncate_text(text_summary),
        "tables": tables,
        "notes": notes,
        "terms": [term_to_dict(term) for term in terms],
        "document_id": document_id,
        "title": document_title,
    }

    normalized_json_path.write_text(json.dumps(normalized_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "source_path": source_path.as_posix(),
        "stored_path": stored_path.as_posix(),
        "normalized_path": document_path,
        "media_type": media_type,
        "size_bytes": size_bytes,
        "sha256": digest,
        "terms": [term_to_dict(term) for term in terms],
        "notes": notes,
        "document_id": document_id,
        "title": document_title,
    }


def _infer_terms_from_text(text: str) -> List[SLATerm]:
    terms: List[SLATerm] = []
    pattern = re.compile(r"(?P<kpi>[A-Za-z0-9_\s\-]+?)\s*[:\-]\s*(?P<body>.+)")
    for raw_line in text.splitlines():
        cleaned_line = _normalise_bullet_text(raw_line)
        if not cleaned_line:
            continue
        match = pattern.match(cleaned_line)
        if not match:
            continue
        raw_kpi = match.group("kpi").strip()
        kpi = re.sub(r"^[\d\.\)\-_:]+", "", raw_kpi).strip()
        if len(kpi) < 3:
            continue
        body_raw = match.group("body").strip()
        body = _normalise_bullet_text(body_raw)
        if not body:
            continue
        term = SLATerm(kpi=kpi, notes=[body])
        value_matches = list(
            re.finditer(
                r"([0-9]+(?:\.[0-9]+)?)\s*(%|percent|٪|hours?|hrs?|h|days?|d|minutes?|mins?|m)?",
                body,
                re.IGNORECASE,
            )
        )
        numeric_values: List[Optional[float]] = []
        units: List[Optional[str]] = []
        for value_match in value_matches:
            numeric_values.append(_parse_numeric(value_match.group(1)))
            unit = value_match.group(2)
            units.append(unit.lower() if unit else None)
        numeric_values = [value for value in numeric_values if value is not None]
        if numeric_values:
            term.target = numeric_values[0]
            if len(numeric_values) > 1:
                term.warn = numeric_values[1]
            if len(numeric_values) > 2:
                term.stop = numeric_values[2]
            if units and units[0]:
                unit = units[0]
                if unit in {"%", "percent", "٪"}:
                    term.unit = "%"
                elif unit in {"hours", "hour", "hrs", "hr", "h"}:
                    term.unit = "hours"
                elif unit in {"days", "day", "d"}:
                    term.unit = "days"
                elif unit in {"minutes", "minute", "mins", "min", "m"}:
                    term.unit = "minutes"
        direction = _parse_direction(body)
        if direction:
            term.direction = direction
        terms.append(term)
    return terms


def term_to_dict(term: SLATerm) -> Dict[str, Any]:
    payload = asdict(term)
    payload["kpi"] = term.kpi
    return payload


def term_from_dict(payload: Mapping[str, Any]) -> SLATerm:
    return SLATerm(
        kpi=str(payload.get("kpi", "")),
        direction=str(payload.get("direction", "gte")),
        target=payload.get("target"),
        warn=payload.get("warn"),
        stop=payload.get("stop"),
        window=payload.get("window"),
        unit=payload.get("unit"),
        source=dict(payload.get("source", {})),
        raw=dict(payload.get("raw", {})),
        notes=list(payload.get("notes", [])),
    )


def load_bundle(manifest_path: Path) -> SLABundle:
    if not manifest_path.exists():
        return SLABundle(run_id=manifest_path.parent.parent.name, manifest_path=None)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - defensive
        return SLABundle(run_id=manifest_path.parent.parent.name, manifest_path=manifest_path, notes=["manifest_parse_error"])
    entries = payload.get("entries") or []
    terms: List[SLATerm] = []
    for entry in entries:
        for term_payload in entry.get("terms", []):
            try:
                terms.append(term_from_dict(term_payload))
            except Exception:
                continue
    notes = list(payload.get("notes") or [])
    return SLABundle(
        run_id=str(payload.get("run_id", manifest_path.parent.parent.name)),
        manifest_path=manifest_path,
        entries=entries,
        terms=terms,
        notes=notes,
    )


def _align_threshold(actual: Optional[float], threshold: Optional[float]) -> Optional[float]:
    if actual is None or threshold is None:
        return threshold
    if actual <= 1.0 and threshold > 1.0:
        return threshold / 100.0
    return threshold


def evaluate_terms(terms: Sequence[SLATerm], metrics: Mapping[str, float]) -> List[SLATermResult]:
    lookup = {key.lower(): value for key, value in metrics.items()}
    results: List[SLATermResult] = []
    for term in terms:
        key = term.kpi.lower()
        actual = lookup.get(key)
        target = _align_threshold(actual, term.target)
        warn = _align_threshold(actual, term.warn)
        stop = _align_threshold(actual, term.stop)
        status = "PASS"
        reason = "sla_pass"
        if actual is None:
            status = "WARN"
            reason = "metric_missing"
        else:
            if term.direction == "lte":
                if stop is not None and actual > stop:
                    status = "STOP"
                    reason = "above_stop"
                elif warn is not None and actual > warn:
                    status = "WARN"
                    reason = "above_warn"
                elif target is not None and actual > target:
                    status = "WARN"
                    reason = "above_target"
            else:
                if stop is not None and actual < stop:
                    status = "STOP"
                    reason = "below_stop"
                elif warn is not None and actual < warn:
                    status = "WARN"
                    reason = "below_warn"
                elif target is not None and actual < target:
                    status = "WARN"
                    reason = "below_target"
        results.append(SLATermResult(term=term, actual=actual, status=status, reason=reason))
    return results


def term_result_to_dict(result: SLATermResult) -> Dict[str, Any]:
    payload = {
        "kpi": result.term.kpi,
        "direction": result.term.direction,
        "target": result.term.target,
        "warn": result.term.warn,
        "stop": result.term.stop,
        "window": result.term.window,
        "unit": result.term.unit,
        "status": result.status,
        "reason": result.reason,
        "actual": result.actual,
        "source": result.term.source,
        "raw": result.term.raw,
        "notes": result.term.notes,
    }
    return payload


__all__ = [
    "SLATerm",
    "SLATermResult",
    "SLABundle",
    "process_sla_file",
    "load_bundle",
    "evaluate_terms",
    "term_to_dict",
    "term_from_dict",
    "term_result_to_dict",
]
