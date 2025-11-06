from __future__ import annotations

import os
from typing import Dict, Optional

from fastapi import APIRouter

router = APIRouter(tags=["pipeline"])


@router.post("/v1/runs/{run_id}/phases/09_5_causal")
async def run_causal_optional(run_id: str, problem_name: Optional[str] = None) -> Dict[str, object]:
    from app.services.stage_09_5_causal_inference.impl import run as run_causal  # lazy import

    if not (os.getenv("MINDQ_ENABLE_CAUSAL", "false").lower() == "true" and problem_name):
        return {"skipped": True, "reason": "feature disabled or no problem name"}
    return await run_causal(run_id=run_id, problem_name=problem_name)
