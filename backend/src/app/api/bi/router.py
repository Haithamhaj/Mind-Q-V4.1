from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/bi", tags=["bi"])

@router.get("/runs")
async def list_bi_runs(artifacts_root: Optional[str] = None) -> Dict[str, Any]:
    raise HTTPException(status_code=501, detail="Use /v1/runs endpoint instead")
