from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

_CAPTURE_GROUP = "value"
_SUPPORTED_SUFFIXES = {".txt", ".text", ".md", ".rtf", ".pdf"}

DEFAULT_PATTERNS: Mapping[str, Sequence[str]] = {
    "awb_number": (
        r"\b(?:AWB|Air\s*Waybill|Waybill)\s*(?:Number|No\.?|#|:)?\s*(?P<value>[A-Z0-9-]{8,})",
        r"\b(?P<value>\d{8,})\b",
    ),
    "invoice_number": (
        r"\bInvoice\s*(?:Number|No\.?|#|:)?\s*(?P<value>[A-Z0-9-]{4,})",
        r"\bINV[-\s]?(?P<value>[A-Z0-9]{3,})\b",
    ),
    "shipment_date": (
        r"\b(?:Date|Shipment\s*Date)\s*(?:Number|No\.?|#|:)?\s*(?P<value>\d{2}[/-]\d{2}[/-]\d{2,4})",
        r"\b(?P<value>\d{4}[/-]\d{2}[/-]\d{2})\b",
    ),
    "reference": (
        r"\b(?:Reference|Ref)\s*(?:Number|No\.?|#|:)?\s*(?P<value>[A-Z0-9-]{5,})",
    ),
}


class DocumentExtractionError(RuntimeError):
    """Raised when a document cannot be processed."""


def _normalise_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text)
    return collapsed.strip()


def _extract_text_from_pdf(path: Path) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    try:  # pragma: no cover - optional dependency
        from pdfminer.high_level import extract_text  # type: ignore

        text = extract_text(path.as_posix())
        return text or "", warnings
    except ImportError as exc:  # pragma: no cover - optional dependency
        warnings.append(f"pdfminer is not installed: {exc}")
    except Exception as exc:  # pragma: no cover - optional dependency
        warnings.append(f"Failed to read {path.name} with pdfminer: {exc}")
    return "", warnings


def _read_document(path: Path) -> Tuple[str, List[str]]:
    suffix = path.suffix.lower()
    warnings: List[str] = []
    try:
        if suffix == ".pdf":
            return _extract_text_from_pdf(path)
        if suffix in {".txt", ".text", ".md", ".rtf"}:
            return path.read_text(encoding="utf-8"), warnings
        text = path.read_text(encoding="utf-8")
        warnings.append(f"Unsupported extension {suffix}; treated as text")
        return text, warnings
    except UnicodeDecodeError:
        fallback = path.read_text(encoding="utf-8", errors="ignore")
        warnings.append(f"Unicode errors reading {path.name}; partial content used")
        return fallback, warnings
    except Exception as exc:
        warnings.append(f"Failed to read {path.name}: {exc}")
        return "", warnings


def _compile_patterns(patterns: Mapping[str, Sequence[str]]) -> Dict[str, List[re.Pattern[str]]]:
    compiled: Dict[str, List[re.Pattern[str]]] = {}
    for field, variants in patterns.items():
        compiled[field] = [re.compile(expr, flags=re.IGNORECASE) for expr in variants]
    return compiled


def _match_fields(text: str, compiled: Mapping[str, Sequence[re.Pattern[str]]]) -> Dict[str, Dict[str, Optional[str]]]:
    results: Dict[str, Dict[str, Optional[str]]] = {}
    for field, regexes in compiled.items():
        value: Optional[str] = None
        chosen_pattern: Optional[str] = None
        confidence = 0.0
        for regex in regexes:
            match = regex.search(text)
            if not match:
                continue
            chosen_pattern = regex.pattern
            if _CAPTURE_GROUP in match.groupdict():
                value = match.group(_CAPTURE_GROUP)
            else:
                value = match.group(0)
            confidence = 0.7
            break
        results[field] = {
            "value": value,
            "confidence": confidence,
            "method": "regex",
            "pattern": chosen_pattern,
        }
    return results


def extract_fields_from_document(
    path: Path,
    *,
    patterns: Optional[Mapping[str, Sequence[str]]] = None,
) -> Tuple[Dict[str, object], List[str]]:
    if not path.exists():
        raise DocumentExtractionError(f"Document not found: {path}")

    text, warnings = _read_document(path)
    if not text.strip():
        warnings.append(f"No readable text detected in {path.name}")
        return {"document": path.name, "fields": {}}, warnings

    compiled = _compile_patterns(patterns or DEFAULT_PATTERNS)
    fields = _match_fields(_normalise_text(text), compiled)
    return {"document": path.name, "fields": fields}, warnings


def extract_fields_from_directory(
    root: Path,
    *,
    patterns: Optional[Mapping[str, Sequence[str]]] = None,
    glob: Optional[Iterable[str]] = None,
) -> Tuple[Dict[str, object], List[str]]:
    if not root.exists():
        raise DocumentExtractionError(f"Documents root does not exist: {root}")

    patterns = patterns or DEFAULT_PATTERNS
    warnings: List[str] = []
    documents: List[Dict[str, object]] = []

    matchers = tuple(glob or ["**/*"])
    candidates: List[Path] = []
    for matcher in matchers:
        candidates.extend(sorted(root.glob(matcher)))

    for path in sorted({p for p in candidates if p.is_file()}):
        if path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        doc_payload, doc_warnings = extract_fields_from_document(path, patterns=patterns)
        documents.append(doc_payload)
        warnings.extend(doc_warnings)

    payload: Dict[str, object] = {
        "documents": documents,
        "patterns": {field: list(exprs) for field, exprs in patterns.items()},
    }
    if warnings:
        logger.debug("Document extraction emitted %d warnings", len(warnings))
    return payload, warnings