from fastapi import APIRouter, HTTPException, Response
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

@router.get("/orders", response_model=None)
async def get_orders_dataset(run: str | None = None, artifacts_root: str | None = None):
    """Return orders dataset for BI visualization"""
    print(f"🔥🔥🔥 /api/bi/orders called! run={run}")
    # Test FileResponse with simple file first
    from pathlib import Path as P
    test_file = P("/tmp/test_simple.json")
    print(f"🔥🔥🔥 Returning FileResponse: {test_file.exists()}")
    return FileResponse(path=test_file, media_type="application/json")
