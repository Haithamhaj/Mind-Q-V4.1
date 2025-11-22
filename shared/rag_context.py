from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import polars as pl  # type: ignore

RAG_STAGE_DIR = "stage_03_5_textops"
CLIENT_KEYS = ("client_id", "partner_id", "account_no", "account_id")
KPI_KEYWORDS = ("SLA", "ON_TIME", "DELIVERY", "RTO", "OTIF", "LEAD_TIME", "TAT")


def _safe_read_parquet(path: Path) -> Optional[pl.DataFrame]:
    if not path.exists():
        return None
    try:
        return pl.read_parquet(path.as_posix())
    except Exception:
        return None


def _normalise_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalise_kpi(value: Optional[str]) -> Optional[str]:
    text = _normalise_text(value)
    if not text:
        return None
    return text.upper()


def _normalise_client(value: Optional[str]) -> Optional[str]:
    text = _normalise_text(value)
    if not text:
        return None
    return text.upper()


def _infer_doc_type(name: Optional[str]) -> str:
    if not name:
        return "DOC"
    lowered = str(name).lower()
    for keyword in ("sla", "service"):
        if keyword in lowered:
            return "SLA"
    for keyword in ("sop", "procedure"):
        if keyword in lowered:
            return "SOP"
    if "profile" in lowered:
        return "PROFILE"
    if "contract" in lowered:
        return "CONTRACT"
    return "DOC"


def _format_rule_fallback(rule: Mapping[str, Any]) -> str:
    metric = rule.get("metric") or "metric"
    operator = rule.get("operator") or ""
    value = rule.get("value") or ""
    scope = rule.get("scope")
    unit = rule.get("unit") or ""
    text = f"{metric} {operator} {value} {unit}".strip()
    if scope:
        text = f"{text} (scope: {scope})"
    return text


def _segment_lookup(frame: Optional[pl.DataFrame]) -> Dict[int, Dict[str, Any]]:
    if frame is None or frame.is_empty():
        return {}
    lookup: Dict[int, Dict[str, Any]] = {}
    for row in frame.iter_rows(named=True):
        segment_id = row.get("segment_id")
        if segment_id is None:
            continue
        lookup[int(segment_id)] = {
            "text": row.get("text"),
            "source": row.get("source"),
            "source_key": row.get("source_key"),
        }
    return lookup


def _extract_citations(raw: Any) -> List[int]:
    if not isinstance(raw, Sequence):
        return []
    ids: List[int] = []
    for value in raw:
        if value is None:
            continue
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return ids


def _parse_dim_keys(raw: Any) -> Mapping[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, Mapping):
        return raw
    try:
        parsed = json.loads(str(raw))
        if isinstance(parsed, Mapping):
            return parsed
    except Exception:
        return {}
    return {}


@dataclass
class RagClauseLookup:
    source: str = "stage_03_5_rag"
    status: str = "UNAVAILABLE"
    available: bool = False
    top_k: int = 3
    warnings: List[str] = field(default_factory=list)
    _clauses: Dict[Tuple[Optional[str], str], List[Dict[str, Any]]] = field(default_factory=dict)
    _global: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    _clients: set[str] = field(default_factory=set)

    def add_clause(self, client_id: Optional[str], kpi_aliases: Sequence[str], clause: Dict[str, Any]) -> None:
        aliases = {_normalise_kpi(alias) for alias in kpi_aliases if _normalise_kpi(alias)}
        if not aliases:
            return
        client_norm = _normalise_client(client_id)
        if client_norm:
            self._clients.add(client_norm)
        for alias in aliases:
            key = (client_norm, alias)
            bucket = self._clauses.setdefault(key, [])
            if len(bucket) < self.top_k:
                bucket.append(clause)
            global_bucket = self._global.setdefault(alias, [])
            if len(global_bucket) < self.top_k:
                global_bucket.append(clause)

    def lookup(self, *, kpi_code: Optional[str], client_id: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.available:
            return []
        alias = _normalise_kpi(kpi_code)
        if not alias:
            return []
        limit = limit or self.top_k
        client_norm = _normalise_client(client_id)
        candidates: List[Dict[str, Any]] = []
        if client_norm:
            candidates.extend(self._clauses.get((client_norm, alias), []))
        if not candidates:
            candidates.extend(self._global.get(alias, []))
        if not candidates:
            # attempt fuzzy match by keyword if direct lookup failed
            if any(keyword in alias for keyword in KPI_KEYWORDS):
                for key_alias, bucket in self._global.items():
                    if key_alias.startswith(alias) or alias in key_alias:
                        candidates.extend(bucket)
                        break
        return [dict(item) for item in candidates[:limit]]

    @property
    def clauses_indexed(self) -> int:
        return sum(len(entries) for entries in self._global.values())

    @property
    def clients_indexed(self) -> int:
        return len(self._clients)


def load_rag_clause_lookup(artifacts_root: Path, run_id: str, *, top_k: int = 3) -> RagClauseLookup:
    lookup = RagClauseLookup(top_k=top_k)
    base = artifacts_root / run_id / RAG_STAGE_DIR
    if not base.exists():
        lookup.warnings.append(f"rag_missing_dir::{base.as_posix()}")
        return lookup

    rules_path = base / "rules_sla_llm.parquet"
    links_path = base / "kpi_links.parquet"
    segments_path = base / "doc_segments.parquet"

    rules_df = _safe_read_parquet(rules_path)
    links_df = _safe_read_parquet(links_path)
    segments_df = _safe_read_parquet(segments_path)

    parts_loaded = []
    if rules_df is not None and not rules_df.is_empty():
        parts_loaded.append("rules")
    else:
        lookup.warnings.append(f"rag_rules_missing::{rules_path.as_posix()}")
    if links_df is not None and not links_df.is_empty():
        parts_loaded.append("links")
    else:
        lookup.warnings.append(f"rag_links_missing::{links_path.as_posix()}")
    if segments_df is not None and segments_df.is_empty():
        segments_df = None

    if len(parts_loaded) < 2:
        lookup.status = "PARTIAL" if parts_loaded else "UNAVAILABLE"
        return lookup

    lookup.status = "OK"
    lookup.available = True
    segment_lookup = _segment_lookup(segments_df)
    rules_map: Dict[str, Mapping[str, Any]] = {}
    for row in rules_df.iter_rows(named=True):
        rule_id = row.get("rule_id")
        if not isinstance(rule_id, str):
            continue
        rules_map[rule_id] = row

    sorted_links = links_df.sort("link_confidence", descending=True) if "link_confidence" in links_df.columns else links_df
    for row in sorted_links.iter_rows(named=True):
        rule_id = row.get("entity_id")
        kpi_id = row.get("kpi_id")
        if not isinstance(rule_id, str) or not isinstance(kpi_id, str):
            continue
        rule = rules_map.get(rule_id)
        if not rule:
            continue
        dims = _parse_dim_keys(row.get("dim_keys"))
        client_id = None
        for key in CLIENT_KEYS:
            if dims.get(key):
                client_id = str(dims[key])
                break
        if client_id is None and rule.get("partner_id"):
            client_id = str(rule.get("partner_id"))
        citations = _extract_citations(rule.get("citation_segment_ids"))
        text_parts: List[str] = []
        doc_name: Optional[str] = None
        doc_type: Optional[str] = None
        for segment_id in citations[: top_k * 2]:
            segment = segment_lookup.get(segment_id)
            if not segment:
                continue
            snippet = _normalise_text(segment.get("text"))
            if snippet:
                text_parts.append(snippet)
            if not doc_name:
                doc_name = segment.get("source_key") or segment.get("source")
                doc_type = _infer_doc_type(segment.get("source"))
        if not text_parts:
            text_parts.append(_format_rule_fallback(rule))
        if not doc_name:
            doc_name = rule.get("source_doc_id") or rule.get("metric") or rule_id
        payload = {
            "document_name": Path(str(doc_name)).name if doc_name else str(doc_name),
            "document_type": doc_type or _infer_doc_type(str(doc_name)),
            "clause_id": rule_id,
            "page": None,
            "raw_text": "\n\n".join(text_parts).strip(),
        }
        aliases = [kpi_id, rule.get("metric")]
        lookup.add_clause(client_id, aliases, payload)

    if not lookup.clauses_indexed:
        lookup.status = "PARTIAL"
    return lookup


__all__ = ["RagClauseLookup", "load_rag_clause_lookup"]
