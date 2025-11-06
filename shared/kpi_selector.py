from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.agents.llm_adapter import invoke_model
from shared.llm_prompts import compose_system_prompt

DEFAULT_PROVIDER = os.getenv("SCHEMA_KPI_LLM_PROVIDER") or os.getenv("RAW_METRICS_LLM_PROVIDER", "openai")
DEFAULT_MODEL = os.getenv("SCHEMA_KPI_LLM_MODEL") or os.getenv("RAW_METRICS_LLM_MODEL", "gpt-4o-mini")

NEGATIVE_PATTERNS = {"id", "identifier", "created_at", "creation_time", "updated_at", "timestamp", "hash"}


def _is_negative_column(column_id: str, entry: Mapping[str, Any]) -> bool:
    candidate = column_id.lower()
    if any(token in candidate for token in NEGATIVE_PATTERNS):
        return True
    dtype = entry.get("dtype")
    if dtype and "datetime" in str(dtype).lower():
        return True
    return False


def _build_system_prompt() -> str:
    return compose_system_prompt(
        [
            "قيّم كل عمود لتحديد إن كان مؤشر أداء تنفيذي في اللوجستيات (الخدمة، العمليات، التكلفة، الإيرادات، تجربة العميل، الجودة). "
            "أعد JSON وفق المخطط:\n"
            "{\n"
            '  \"candidates\": [\n'
            "    {\n"
            '      \"column_id\": \"...\",\n'
            '      \"is_kpi\": true|false,\n'
            '      \"priority\": \"high\"|\"medium\"|\"low\",\n'
            '      \"business_dimension\": \"Service\"|\"Operations\"|\"Cost\"|\"Revenue\"|\"Experience\"|\"Quality\",\n'
            '      \"recommended_formula\": \"...\",\n'
            '      \"rationale_en\": \"...\",\n'
            '      \"rationale_ar\": \"...\",\n'
            '      \"confidence\": 0.0-1.0\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "لا تُصنف الأعمدة الزمنية أو المعرفات كمؤشرات أداء.",
        ],
        enforce_data_scope=True,
    )


def _build_user_prompt(entries: Sequence[Mapping[str, Any]]) -> str:
    payload = {"columns": entries}
    return (
        "Evaluate each column and determine if it should be tracked as a KPI for a logistics organization. "
        "Use conservative judgement; only mark `is_kpi=true` for metrics that impact business outcomes. "
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


@dataclass
class KpiCandidate:
    column_id: str
    is_kpi: bool
    priority: str
    business_dimension: str
    recommended_formula: str
    rationale_en: str
    rationale_ar: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column_id": self.column_id,
            "is_kpi": self.is_kpi,
            "priority": self.priority,
            "business_dimension": self.business_dimension,
            "recommended_formula": self.recommended_formula,
            "rationale_en": self.rationale_en,
            "rationale_ar": self.rationale_ar,
            "confidence": self.confidence,
        }


def _parse_response(content: str, fallback_columns: Sequence[str]) -> List[KpiCandidate]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        payload = {}
    candidates = []
    items = payload.get("candidates") if isinstance(payload, Mapping) else None
    if not isinstance(items, list):
        items = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        column_id = str(item.get("column_id") or "").strip()
        if not column_id or column_id in seen:
            continue
        seen.add(column_id)
        try:
            confidence_val = float(item.get("confidence", 0.6))
        except (TypeError, ValueError):
            confidence_val = 0.6
        candidates.append(
            KpiCandidate(
                column_id=column_id,
                is_kpi=bool(item.get("is_kpi", False)),
                priority=str(item.get("priority") or "low"),
                business_dimension=str(item.get("business_dimension") or "Operations"),
                recommended_formula=str(item.get("recommended_formula") or ""),
                rationale_en=str(item.get("rationale_en") or ""),
                rationale_ar=str(item.get("rationale_ar") or ""),
                confidence=max(0.0, min(confidence_val, 1.0)),
            )
        )
    for column_id in fallback_columns:
        if column_id not in seen:
            candidates.append(
                KpiCandidate(
                    column_id=column_id,
                    is_kpi=False,
                    priority="low",
                    business_dimension="Operations",
                    recommended_formula="",
                    rationale_en="Auto-classified as non-KPI due to heuristics.",
                    rationale_ar="تم تصنيف العمود تلقائيًا كغير مؤشر أداء.",
                    confidence=0.5,
                )
            )
    return candidates


def select_kpi_candidates(
    terminology_entries: Sequence[Mapping[str, Any]],
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 900,
) -> Dict[str, Any]:
    provider = provider or DEFAULT_PROVIDER
    model = model or DEFAULT_MODEL

    eligible_entries: List[Mapping[str, Any]] = []
    fallback_columns: List[str] = []
    for entry in terminology_entries:
        column_id = str(entry.get("column_id") or "").strip()
        if not column_id:
            continue
        if _is_negative_column(column_id, entry):
            fallback_columns.append(column_id)
            continue
        eligible_entries.append(entry)
        fallback_columns.append(column_id)

    if not eligible_entries:
        return {"provider": provider, "model": model, "candidates": [], "selected": 0, "total": 0}

    try:
        response = invoke_model(
            provider=provider,
            model=model,
            system_prompt=_build_system_prompt(),
            user_prompt=_build_user_prompt(eligible_entries),
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
            timeout=90,
        )
        candidates = _parse_response(response.content, fallback_columns)
        return {
            "provider": provider,
            "model": model,
            "candidates": [candidate.to_dict() for candidate in candidates],
            "selected": sum(1 for candidate in candidates if candidate.is_kpi),
            "total": len(candidates),
        }
    except RuntimeError as exc:  # pragma: no cover - credential/network issues
        fallback_candidates = [
            KpiCandidate(
                column_id=column_id,
                is_kpi=False,
                priority="low",
                business_dimension="Operations",
                recommended_formula="",
                rationale_en=f"LLM disabled: {exc}",
                rationale_ar="تم إيقاف توصيف KPI مؤقتًا لعدم توفر خدمة LLM.",
                confidence=0.0,
            ).to_dict()
            for column_id in fallback_columns
        ]
        return {
            "provider": provider,
            "model": model,
            "candidates": fallback_candidates,
            "error": str(exc),
            "selected": 0,
            "total": len(fallback_candidates),
        }
