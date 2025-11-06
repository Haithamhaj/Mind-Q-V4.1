from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from openai import OpenAI, OpenAIError  # type: ignore
from pydantic import BaseModel, Field

from app.context.sla_context import ContextEntry, load_context_entries, search_context  # type: ignore


class ContextReference(BaseModel):
    entry_id: str
    title: str
    score: float = Field(ge=0.0, le=1.0)
    content: str
    metadata: Dict[str, Any]


class ChatRequest(BaseModel):
    run_id: str
    question: str
    top_k: int = Field(default=5, ge=1, le=10)
    customer_id: Optional[str] = Field(default=None, description="Optional customer identifier for downstream filtering.")


class ChatResponse(BaseModel):
    answer: str
    model: str
    references: List[ContextReference]
    usage: Dict[str, Any]


class SLAContextProvider:
    def __init__(self, context_root: Path) -> None:
        self.context_root = context_root
        self._cache: Dict[str, Tuple[float, List[ContextEntry]]] = {}

    def load(self, run_id: str) -> List[ContextEntry]:
        context_dir = self.context_root
        context_path = context_dir / run_id / f"{run_id}_sla.jsonl"
        if not context_path.exists():
            raise FileNotFoundError(f"SLA context not found for run {run_id} (run the build_sla_context script first)")

        mtime = context_path.stat().st_mtime
        cached = self._cache.get(run_id)
        if cached and cached[0] == mtime:
            return cached[1]

        entries = load_context_entries(context_dir, run_id)
        self._cache[run_id] = (mtime, entries)
        return entries


def _truncate(text: str, limit: int = 400) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _compose_context_block(pairs: List[Tuple[ContextEntry, float]]) -> str:
    blocks = []
    for entry, score in pairs:
        blocks.append(f"[{entry.entry_id}] {entry.content}")
    return "\n\n".join(blocks)


def _system_prompt() -> str:
    return (
        "أنت مساعد تحليلي خبير في اتفاقيات مستوى الخدمة (SLA) وتحليلات BI الخاصة بالعملاء. "
        "اعتمد فقط على المعلومات المقدمة في قسم السياق. "
        "اشرح الاستنتاجات بوضوح، واذكر معرف كل مرجع (entry_id) يدعم إجابتك. "
        "إذا لم تتوفر بيانات كافية، صرّح بذلك بدلاً من التخمين."
    )


def _user_prompt(question: str, context_block: str) -> str:
    return (
        f"السؤال:\n{question}\n\n"
        "السياق:\n"
        f"{context_block}\n\n"
        "التعليمات:\n"
        "- لخّص حالة البنود ذات الصلة.\n"
        "- وضّح القيم الفعلية مقابل الحدود المستهدفة.\n"
        "- إذا ذُكرت تحذيرات أو أسباب STOP فاشرحها.\n"
        "- أشر إلى معرف المرجع بين أقواس مربعة، مثل [run123:sla:001]."
    )


def _initialise_openai() -> Optional[OpenAI]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("OPENAI_BASE_URL")
    return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)


def _call_llm(client: OpenAI, model: str, system_prompt: str, user_prompt: str) -> Tuple[str, Dict[str, Any]]:
    response = client.chat.completions.create(
        model=model,
        temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    message = response.choices[0].message.content if response.choices else ""
    usage = response.usage.model_dump() if hasattr(response, "usage") else {}
    return message or "", usage


def _fallback_answer(question: str, references: List[ContextReference]) -> str:
    if not references:
        return (
            "لم أجد سجلات SLA لهذه العملية. تأكد من تشغيل بناء السياق عبر سكربت build_sla_context "
            "أو راجع فريق البيانات للحصول على مزيد من التفاصيل."
        )
    bullets = [f"- {ref.title}: {ref.content}" for ref in references]
    return (
        "لا يتوفر اتصال بالـ LLM حاليًا، لكن إليك أبرز البنود المرتبطة بسؤالك:\n"
        + "\n".join(bullets)
    )


def _log_interaction(log_dir: Path, payload: Dict[str, Any]) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "chat_sessions.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


app = FastAPI(title="SLA Chat Service", version="1.0.0", description="LLM gateway for SLA and BI context.")

CONTEXT_ROOT = Path(os.getenv("SLA_CONTEXT_ROOT", "artifacts/context")).expanduser()
context_provider = SLAContextProvider(CONTEXT_ROOT)
openai_client = _initialise_openai()
openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


@app.get("/healthz")
def healthcheck() -> JSONResponse:
    status = "ok" if CONTEXT_ROOT.exists() else "context_missing"
    return JSONResponse({"status": status, "context_root": CONTEXT_ROOT.as_posix()})


@app.post("/v1/sla/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        entries = context_provider.load(request.run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    ranked = search_context(request.question, entries, top_k=request.top_k)
    references = [
        ContextReference(
            entry_id=entry.entry_id,
            title=entry.title,
            score=round(score, 6),
            content=_truncate(entry.content, 400),
            metadata=entry.metadata,
        )
        for entry, score in ranked
    ]

    context_block = _compose_context_block(ranked)
    system_prompt = _system_prompt()
    user_prompt = _user_prompt(request.question, context_block)

    answer: str
    usage: Dict[str, Any] = {}
    if openai_client is not None:
        try:
            answer, usage = _call_llm(openai_client, openai_model, system_prompt, user_prompt)
        except OpenAIError as exc:
            answer = _fallback_answer(request.question, references)
            usage = {"error": str(exc)}
    else:
        answer = _fallback_answer(request.question, references)
        usage = {"warning": "OPENAI_API_KEY not configured; returned fallback response."}

    log_payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": request.run_id,
        "question": request.question,
        "references": [ref.entry_id for ref in references],
        "usage": usage,
    }
    _log_interaction(CONTEXT_ROOT / request.run_id / "logs", log_payload)

    return ChatResponse(answer=answer, model=openai_model, references=references, usage=usage)


__all__ = ["app"]
