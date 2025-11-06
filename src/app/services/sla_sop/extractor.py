from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence

from src.agents.llm_adapter import invoke_model
from shared.llm_prompts import compose_system_prompt

MODULE_PATH = Path(__file__).resolve()
BACKEND_ROOT = MODULE_PATH.parents[3]
PROJECT_ROOT = MODULE_PATH.parents[4]

DEFAULT_SOP_ROOT = BACKEND_ROOT / "contracts" / "sla_sops"
DEFAULT_LLM_PROVIDER = os.getenv("SLA_SOP_LLM_PROVIDER", os.getenv("RAW_METRICS_LLM_PROVIDER", "openai"))
DEFAULT_LLM_MODEL = os.getenv("SLA_SOP_LLM_MODEL", os.getenv("RAW_METRICS_LLM_MODEL", "gpt-4o-mini"))

TEXT_EXTENSIONS: Sequence[str] = (
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".yml",
    ".yaml",
    ".csv",
)  # Remaining formats will be skipped gracefully.


@dataclass
class SOPDocument:
    run_id: str
    path: Path
    title: str
    body: str
    source: str


@dataclass
class SOPExpectation:
    metric_id: str
    metric_name: Optional[str]
    target_value: Optional[float]
    target_unit: Optional[str]
    condition: Optional[str]
    timeframe: Optional[str]
    responsible_team: Optional[str]
    source_document: str
    citation: Optional[str]
    rationale: Optional[str]

    def to_dict(self) -> Mapping[str, Optional[str]]:
        payload = asdict(self)
        # Normalise floats that may come as strings in the LLM response.
        target_value = payload.get("target_value")
        if isinstance(target_value, str):
            try:
                payload["target_value"] = float(target_value)
            except ValueError:
                payload["target_value"] = None
        return payload


def _safe_read_text(path: Path) -> Optional[str]:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def discover_sop_documents(run_id: str, roots: Optional[Sequence[Path]] = None) -> List[SOPDocument]:
    search_roots: List[Path] = []
    if roots:
        search_roots.extend(roots)
    else:
        search_roots.append(DEFAULT_SOP_ROOT / run_id)
        search_roots.append(DEFAULT_SOP_ROOT / "common")
        search_roots.append(PROJECT_ROOT / "contracts" / "sla_sops" / run_id)
        search_roots.append(PROJECT_ROOT / "contracts" / "sla_sops" / "common")

    documents: List[SOPDocument] = []
    seen: set[str] = set()
    for root in search_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            key = path.as_posix()
            if key in seen:
                continue
            seen.add(key)
            text = _safe_read_text(path)
            if not text:
                continue
            documents.append(
                SOPDocument(
                    run_id=run_id,
                    path=path,
                    title=path.stem.replace("_", " ").title(),
                    body=text.strip(),
                    source=path.relative_to(PROJECT_ROOT).as_posix(),
                )
            )
    return documents


def _build_system_prompt() -> str:
    return compose_system_prompt(
        [
            "حوّل محتوى مستندات SOP إلى أهداف قابلة للقياس بشأن SLA. أعد JSON بالحقول:\n"
            "metric_id, metric_name, target_value, target_unit, timeframe, condition, responsible_team, citation, rationale.\n"
            "إذا لم يتوافر هدف رقمي واضح استخدم target_value=null مع ذكر السبب.",
        ],
        enforce_data_scope=True,
    )


def _build_user_prompt(document: SOPDocument) -> str:
    snippet = document.body
    if len(snippet) > 6000:
        snippet = snippet[:6000] + "\n... (truncated)"
    return (
        f"المستند: {document.title}\n"
        f"المسار: {document.source}\n"
        "النص:\n"
        f"{snippet}\n\n"
        "استخرج الأهداف الرقمية المتعلقة بمؤشرات SLA أو الجودة التشغيلية."
    )


def _parse_expectations(content: str, document: SOPDocument) -> List[SOPExpectation]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        # Try to wrap plain text into a single entry.
        return []

    expectations_block = []
    if isinstance(payload, Mapping):
        expectations_block = payload.get("expectations") or payload.get("items") or payload.get("targets") or []
    elif isinstance(payload, Sequence):
        expectations_block = payload

    expectations: List[SOPExpectation] = []
    for entry in expectations_block:
        if not isinstance(entry, Mapping):
            continue
        expectations.append(
            SOPExpectation(
                metric_id=str(entry.get("metric_id") or entry.get("id") or "").strip(),
                metric_name=str(entry.get("metric_name") or entry.get("name") or "").strip() or None,
                target_value=entry.get("target_value"),
                target_unit=str(entry.get("target_unit") or entry.get("unit") or "").strip() or None,
                condition=str(entry.get("condition") or entry.get("condition_text") or "").strip() or None,
                timeframe=str(entry.get("timeframe") or entry.get("frequency") or "").strip() or None,
                responsible_team=str(entry.get("responsible_team") or entry.get("owner") or "").strip() or None,
                source_document=document.source,
                citation=str(entry.get("citation") or entry.get("section") or "").strip() or None,
                rationale=str(entry.get("rationale") or entry.get("notes") or "").strip() or None,
            )
        )
    return expectations


def build_expectations_payload(
    documents: Iterable[SOPDocument],
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 1200,
) -> Mapping[str, object]:
    provider = provider or DEFAULT_LLM_PROVIDER
    model = model or DEFAULT_LLM_MODEL

    expectations: List[Mapping[str, object]] = []
    logs: List[Mapping[str, object]] = []

    for document in documents:
        user_prompt = _build_user_prompt(document)
        try:
            llm_response = invoke_model(
                provider=provider,
                model=model,
                system_prompt=_build_system_prompt(),
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9,
                timeout=90,
            )
            parsed = _parse_expectations(llm_response.content, document)
            expectations.extend(expectation.to_dict() for expectation in parsed if expectation.metric_id)
            logs.append(
                {
                    "document": document.source,
                    "tokens_in": llm_response.tokens_in,
                    "tokens_out": llm_response.tokens_out,
                    "cost_estimate": llm_response.cost_estimate,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive
            logs.append({"document": document.source, "error": str(exc)})

    return {
        "provider": provider,
        "model": model,
        "expectations": expectations,
        "documents": [asdict(doc) for doc in documents],
        "logs": logs,
    }
