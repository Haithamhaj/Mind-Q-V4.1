from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
from pathlib import Path

router = APIRouter(prefix="/api/bi", tags=["bi"])

ARTIFACTS_ROOT_DEFAULT = Path("artifacts")

def _resolve_artifacts_root(artifacts_root: Optional[str]) -> Path:
    if artifacts_root and artifacts_root.strip():
        return Path(artifacts_root).expanduser().resolve()
    return ARTIFACTS_ROOT_DEFAULT.expanduser().resolve()

@router.get("/runs")
async def list_bi_runs(artifacts_root: Optional[str] = None):
    raise HTTPException(status_code=501, detail="Use /v1/runs endpoint instead")

@router.get("/orders")
async def get_orders_dataset(run=None, artifacts_root=None):
    """Return orders dataset for BI visualization"""
    if not run or not run.strip():
        raise HTTPException(status_code=400, detail="run parameter is required")
    
    root = _resolve_artifacts_root(artifacts_root)
    run_dir = root / run
    
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run '{run}' not found")
    
    # Serve pre-exported JSON file
    json_file = run_dir / "stage_10_bi" / "datasets" / "fact_business.json"
    
    if not json_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"BI dataset JSON not found. Please re-run Phase 10."
        )
    
    # Return file directly - NO Pydantic serialization!
    return FileResponse(
        path=json_file,
        media_type="application/json",
        filename="bi_data.json"
    )
