from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np  # type: ignore
import polars as pl  # type: ignore

from src.agents.llm_adapter import LLMResponse, invoke_model  # type: ignore

from .config_schema import TextOpsConfig


@dataclass(slots=True)
class RagBundle:
    segments: pl.DataFrame
    embeddings: Optional[np.ndarray]
    vector_ids: Optional[np.ndarray]
    embed_fn: Optional[Callable[[Sequence[str]], np.ndarray]]
    top_k: int
    max_context_chars: int


def _empty_rules_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "rule_id": pl.Utf8,
            "partner_id": pl.Utf8,
            "metric": pl.Utf8,
            "operator": pl.Utf8,
            "value": pl.Utf8,
            "unit": pl.Utf8,
            "scope": pl.Utf8,
            "valid_from": pl.Utf8,
            "valid_to": pl.Utf8,
            "source_doc_id": pl.Utf8,
            "citation_segment_ids": pl.List(pl.Int64),
        }
    )


def _empty_sop_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "sop_id": pl.Utf8,
            "step_no": pl.Int64,
            "actor": pl.Utf8,
            "action": pl.Utf8,
            "condition": pl.Utf8,
            "expected_output": pl.Utf8,
            "source_doc_id": pl.Utf8,
            "citation_segment_ids": pl.List(pl.Int64),
        }
    )


def _empty_profile_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "services": pl.List(pl.Utf8),
            "cities": pl.List(pl.Utf8),
            "working_hours": pl.Utf8,
            "cod_policy": pl.Utf8,
            "notes": pl.Utf8,
            "citations": pl.List(pl.Int64),
        }
    )


def _empty_contacts_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "person_name": pl.Utf8,
            "role": pl.Utf8,
            "contact": pl.Utf8,
            "channel": pl.Utf8,
            "availability_window": pl.Utf8,
            "citations": pl.List(pl.Int64),
        }
    )


def _normalise(vec: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vec, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vec / norms


def _collect_context(question: str, rag: RagBundle) -> Tuple[str, List[int]]:
    if rag.embeddings is not None and rag.embed_fn is not None and rag.vector_ids is not None and rag.embeddings.size:
        question_vec = rag.embed_fn([question])
        if question_vec.size == 0:
            return "", []
        question_vec = _normalise(question_vec.astype(np.float32))
        scores = np.dot(rag.embeddings, question_vec[0])
        top_indices = np.argsort(scores)[::-1][: rag.top_k]
        index_list = [int(idx) for idx in top_indices.tolist()]
        if isinstance(rag.segments, pl.DataFrame):
            selected = (
                rag.segments.with_row_count("__idx")
                .filter(pl.col("__idx").is_in(index_list))
                .drop("__idx")
            )
        elif hasattr(rag.segments, "iloc"):
            selected = rag.segments.iloc[index_list]
        else:
            selected = rag.segments.head(len(index_list))
    else:
        limit = min(rag.top_k, rag.segments.height)
        selected = rag.segments.head(limit)

    context_parts: List[str] = []
    citations: List[int] = []
    current_len = 0
    for row in selected.iter_rows(named=True):
        segment_id = int(row.get("segment_id", len(citations)))
        text = str(row.get("text", "")).strip()
        if not text:
            continue
        snippet = f"[{segment_id}] {text}"
        proposed_len = current_len + len(snippet) + 1
        if proposed_len > rag.max_context_chars and context_parts:
            break
        context_parts.append(snippet)
        citations.append(segment_id)
        current_len = proposed_len
    return "\n".join(context_parts), citations


def _task_instructions(task: str, domain_dict: Mapping[str, Any]) -> Tuple[str, str]:
    base_system = (
        "You are an expert logistics analyst. Reply ONLY with valid JSON matching the requested schema. "
        "Do not include explanatory text."
    )
    if task == "extract_sla":
        aliases = ", ".join(domain_dict.get("kpi_aliases", [])) or "SLA"
        question = (
            "From the context identify explicit SLA rules. Return JSON with key 'rules' containing an array of "
            "objects {rule_id, partner_id, metric, operator, value, unit, scope, valid_from, valid_to, "
            "source_doc_id}. Missing fields should be null. Use operator symbols like >= or <=."
            f" Metric names should align with: {aliases}."
        )
        return base_system, question
    if task == "extract_sop":
        question = (
            "Extract Standard Operating Procedure steps. Return JSON with key 'sops' where each entry has "
            "sop_id and steps array [{step_no, actor, action, condition, expected_output, source_doc_id}]."
        )
        return base_system, question
    if task == "summarize":
        question = (
            "Produce company profile and contacts. Return JSON with keys 'profile' and 'contacts'. "
            "profile => {services[], cities[], working_hours, cod_policy, notes}. "
            "contacts => array of {person_name, role, contact, channel, availability}."
        )
        return base_system, question
    return base_system, "Summarise the context as JSON."


def _invoke_llm(
    *,
    task: str,
    cfg: TextOpsConfig,
    system_prompt: str,
    user_prompt: str,
) -> LLMResponse:
    return invoke_model(
        provider=cfg.llm.provider,
        model=cfg.llm.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=cfg.llm.max_tokens,
        temperature=cfg.llm.temperature,
        top_p=cfg.llm.top_p,
        timeout=cfg.llm.timeout_sec,
    )


def _ensure_json(content: str) -> Mapping[str, Any]:
    try:
        data = json.loads(content)
        if isinstance(data, Mapping):
            return data
    except json.JSONDecodeError:
        return {}
    return {}


def _build_rules_frame(payload: Mapping[str, Any], citations: List[int]) -> pl.DataFrame:
    rules = payload.get("rules", [])
    if not isinstance(rules, Sequence):
        return _empty_rules_frame()
    records: List[Dict[str, Any]] = []
    for idx, raw in enumerate(rules):
        if not isinstance(raw, Mapping):
            continue
        record = {
            "rule_id": str(raw.get("rule_id") or f"rule_{idx+1}"),
            "partner_id": raw.get("partner_id"),
            "metric": raw.get("metric"),
            "operator": raw.get("operator"),
            "value": raw.get("value"),
            "unit": raw.get("unit"),
            "scope": raw.get("scope"),
            "valid_from": raw.get("valid_from"),
            "valid_to": raw.get("valid_to"),
            "source_doc_id": raw.get("source_doc_id"),
            "citation_segment_ids": citations,
        }
        records.append(record)
    if not records:
        return _empty_rules_frame()
    return pl.DataFrame(records).with_columns(
        pl.col("citation_segment_ids").cast(pl.List(pl.Int64))
    )


def _build_sop_frame(payload: Mapping[str, Any], citations: List[int]) -> pl.DataFrame:
    sops = payload.get("sops", [])
    if not isinstance(sops, Sequence):
        return _empty_sop_frame()
    rows: List[Dict[str, Any]] = []
    for sop in sops:
        if not isinstance(sop, Mapping):
            continue
        sop_id = str(sop.get("sop_id") or "sop_1")
        steps = sop.get("steps", [])
        if not isinstance(steps, Sequence):
            continue
        for step in steps:
            if not isinstance(step, Mapping):
                continue
            rows.append(
                {
                    "sop_id": sop_id,
                    "step_no": step.get("step_no"),
                    "actor": step.get("actor"),
                    "action": step.get("action"),
                    "condition": step.get("condition"),
                    "expected_output": step.get("expected_output"),
                    "source_doc_id": step.get("source_doc_id"),
                    "citation_segment_ids": citations,
                }
            )
    if not rows:
        return _empty_sop_frame()
    return pl.DataFrame(rows).with_columns(
        pl.col("citation_segment_ids").cast(pl.List(pl.Int64))
    )


def _build_profile_frames(payload: Mapping[str, Any], citations: List[int]) -> Tuple[pl.DataFrame, pl.DataFrame]:
    profile_block = payload.get("profile") or {}
    if not isinstance(profile_block, Mapping):
        profile_block = {}
    profile_rows = [
        {
            "services": profile_block.get("services", []),
            "cities": profile_block.get("cities", []),
            "working_hours": profile_block.get("working_hours"),
            "cod_policy": profile_block.get("cod_policy"),
            "notes": profile_block.get("notes"),
            "citations": citations,
        }
    ] if profile_block else []
    profile_df = (
        _empty_profile_frame()
        if not profile_rows
        else pl.DataFrame(profile_rows).with_columns(
            pl.col("services").cast(pl.List(pl.Utf8)),
            pl.col("cities").cast(pl.List(pl.Utf8)),
            pl.col("citations").cast(pl.List(pl.Int64)),
        )
    )

    contacts = payload.get("contacts", [])
    rows: List[Dict[str, Any]] = []
    if isinstance(contacts, Sequence):
        for contact in contacts:
            if not isinstance(contact, Mapping):
                continue
            rows.append(
                {
                    "person_name": contact.get("person_name"),
                    "role": contact.get("role"),
                    "contact": contact.get("contact"),
                    "channel": contact.get("channel"),
                    "availability_window": contact.get("availability"),
                    "citations": citations,
                }
            )
    contacts_df = (
        _empty_contacts_frame()
        if not rows
        else pl.DataFrame(rows).with_columns(pl.col("citations").cast(pl.List(pl.Int64)))
    )
    return profile_df, contacts_df


def run_llm_tasks(
    run_id: str,
    cfg: TextOpsConfig,
    rag_bundle: Optional[RagBundle],
    domain_dict: Mapping[str, Any],
) -> Tuple[Dict[str, pl.DataFrame], List[Dict[str, Any]], List[Dict[str, str]]]:
    outputs = {
        "rules": _empty_rules_frame(),
        "sops": _empty_sop_frame(),
        "profile": _empty_profile_frame(),
        "contacts": _empty_contacts_frame(),
    }
    traces: List[Dict[str, Any]] = []
    warnings: List[Dict[str, str]] = []

    if not cfg.llm.tasks:
        return outputs, traces, warnings

    rag = rag_bundle or RagBundle(
        segments=pl.DataFrame(schema={"segment_id": pl.Int64, "text": pl.Utf8}),
        embeddings=None,
        vector_ids=None,
        embed_fn=None,
        top_k=cfg.rag.top_k,
        max_context_chars=cfg.rag.max_ctx_tokens,
    )

    for task in cfg.llm.tasks:
        system_prompt, question = _task_instructions(task, domain_dict)
        context, citations = _collect_context(question, rag)
        if not context:
            warnings.append({"code": f"llm_no_context_{task}", "message": "Insufficient context for LLM task."})
            continue
        user_prompt = (
            f"Run ID: {run_id}.\n"
            f"Context (with segment ids):\n{context}\n\n"
            f"Instructions: {question}"
        )
        try:
            response = _invoke_llm(task=task, cfg=cfg, system_prompt=system_prompt, user_prompt=user_prompt)
            payload = _ensure_json(response.content)
        except Exception as exc:  # pragma: no cover - network/LLM dependent
            warnings.append({"code": f"llm_error_{task}", "message": str(exc)})
            continue

        trace_entry = {
            "task": task,
            "provider": response.provider,
            "model": response.model,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "duration_s": response.duration_s,
            "citations": citations,
            "raw_response": response.content,
        }
        traces.append(trace_entry)

        if task == "extract_sla":
            outputs["rules"] = _build_rules_frame(payload, citations)
        elif task == "extract_sop":
            outputs["sops"] = _build_sop_frame(payload, citations)
        elif task == "summarize":
            profile_df, contacts_df = _build_profile_frames(payload, citations)
            outputs["profile"] = profile_df
            outputs["contacts"] = contacts_df

    return outputs, traces, warnings


__all__ = ["RagBundle", "run_llm_tasks"]
