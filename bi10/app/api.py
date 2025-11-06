from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

from .config import settings
from .semantic import load_semantic
from .query import conn_for, run_sql
from .llm_router import plan_chart

router = APIRouter(prefix="/api")


class QueryIn(BaseModel):
    run_id: str = settings.default_run_id
    sql: str


class DecideIn(BaseModel):
    run_id: str = settings.default_run_id
    question: str


@router.get("/meta")
def meta(run_id: str = settings.default_run_id) -> Dict[str, Any]:
    semantic = load_semantic(run_id, settings.artifacts_root)
    return {
        "timezone": settings.timezone,
        "currency": settings.currency,
        **semantic,
    }


@router.post("/query")
def query(payload: QueryIn) -> Dict[str, Any]:
    try:
        with conn_for(payload.run_id, settings.artifacts_root) as connection:
            rows = run_sql(connection, payload.sql)
        if not rows:
            raise HTTPException(status_code=422, detail="Query returned no rows")
        return {"rows": rows, "n": len(rows)}
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=422, detail=f"Query error: {exc}") from exc


@router.post("/llm/decide_chart")
def decide(payload: DecideIn) -> Dict[str, Any]:
    semantic = load_semantic(payload.run_id, settings.artifacts_root)
    plan = plan_chart(payload.question, semantic)
    try:
        with conn_for(payload.run_id, settings.artifacts_root) as connection:
            data = run_sql(connection, plan["sql"])
        if not data:
            raise HTTPException(status_code=422, detail="Planned SQL returned no rows")
        return {"plan": plan, "data": data}
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=422, detail=f"Planner/SQL error: {exc}") from exc


__all__ = ["router"]
