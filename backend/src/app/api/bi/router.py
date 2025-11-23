from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional
from pathlib import Path
import json

router = APIRouter(prefix="/api/bi", tags=["bi"])

ARTIFACTS_ROOT_DEFAULT = Path("artifacts")

def _resolve_artifacts_root(artifacts_root: Optional[str]) -> Path:
    if artifacts_root and artifacts_root.strip():
        return Path(artifacts_root).expanduser().resolve()
    return ARTIFACTS_ROOT_DEFAULT.expanduser().resolve()

def _resolve_run_id(run: Optional[str]) -> str:
    """Default to smoke-test-02 if no run provided"""
    return run if run else "smoke-test-02"

def _load_json_file(path: Path) -> dict:
    """Load JSON file or return empty dict"""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

@router.get("/runs")
async def list_bi_runs(artifacts_root: Optional[str] = None):
    raise HTTPException(status_code=501, detail="Use /v1/runs endpoint instead")

@router.get("/orders", response_model=None)
async def get_orders_dataset(run: str | None = None, artifacts_root: str | None = None):
    """Return orders dataset for BI visualization"""
    from fastapi.responses import FileResponse
    from pathlib import Path

    run_id = _resolve_run_id(run)
    
    root = _resolve_artifacts_root(artifacts_root)
    json_file = root / run_id / "stage_10_bi" / "datasets" / "fact_business.json"
    
    if not json_file.exists():
        parquet_file = root / run_id / "stage_10_bi" / "marts" / "fact_business.parquet"
        if parquet_file.exists():
             return FileResponse(path=parquet_file, media_type="application/octet-stream")
        
        print(f"❌ File not found: {json_file}")
        raise HTTPException(status_code=404, detail=f"Dataset not found for run {run_id}")
    
    print(f"✅ Serving file: {json_file}")
    return FileResponse(path=json_file, media_type="application/json")

@router.get("/metrics")
async def get_bi_metrics(run: Optional[str] = None, artifacts_root: Optional[str] = None):
    """Return metrics catalog"""
    run_id = _resolve_run_id(run)
    root = _resolve_artifacts_root(artifacts_root)
    
    metrics_file = root / run_id / "stage_10_bi" / "semantic" / "metrics.json"
    data = _load_json_file(metrics_file)
    
    return JSONResponse(content=data if data else [])

@router.get("/dimensions")
async def get_bi_dimensions(run: Optional[str] = None, artifacts_root: Optional[str] = None):
    """Return dimensions catalog"""
    run_id = _resolve_run_id(run)
    root = _resolve_artifacts_root(artifacts_root)
    
    dims_file = root / run_id / "stage_10_bi" / "semantic" / "dimensions.json"
    data = _load_json_file(dims_file)
    
    return JSONResponse(content=data if data else {"date": [], "numeric": [], "categorical": [], "bool": []})

@router.get("/insights")
async def get_bi_insights(run: Optional[str] = None, artifacts_root: Optional[str] = None):
    """Return insights"""
    run_id = _resolve_run_id(run)
    root = _resolve_artifacts_root(artifacts_root)
    
    insights_file = root / run_id / "stage_08_insights" / "insights_report.json"
    data = _load_json_file(insights_file)
    
    return JSONResponse(content=data if data else {"insights": []})

@router.get("/correlations")
async def get_bi_correlations(run: Optional[str] = None, top: Optional[int] = 50, artifacts_root: Optional[str] = None):
    """Return correlations"""
    run_id = _resolve_run_id(run)
    root = _resolve_artifacts_root(artifacts_root)
    
    corr_file = root / run_id / "stage_07_7_business_correlations" / "correlations_business.json"
    data = _load_json_file(corr_file)
    
    if not data:
        return JSONResponse(content={
            "numeric": [],
            "datetime": [],
            "business": {"numeric_numeric": [], "numeric_categorical": [], "categorical_categorical": []},
            "run": run_id,
            "artifacts_root": None,
            "top": top
        })
    
    return JSONResponse(content=data)

@router.get("/intelligence")
async def get_bi_intelligence(run: Optional[str] = None, artifacts_root: Optional[str] = None):
    """Return Layer 3 intelligence"""
    run_id = _resolve_run_id(run)
    root = _resolve_artifacts_root(artifacts_root)
    
    intel_file = root / run_id / "stage_10_bi" / "intelligence" / "layer3.json"
    data = _load_json_file(intel_file)
    
    return JSONResponse(content=data if data else {})

@router.get("/knime-data")
async def get_knime_data(run: Optional[str] = None, limit: Optional[int] = 250, offset: Optional[int] = 0, artifacts_root: Optional[str] = None):
    """Return KNIME bridge data"""
    run_id = _resolve_run_id(run)
    root = _resolve_artifacts_root(artifacts_root)
    
    knime_file = root / run_id / "stage_07_knime_bridge" / "knime_snapshot.json"
    data = _load_json_file(knime_file)
    
    if not data:
        return JSONResponse(content={"run": run_id, "columns": [], "rows": [], "total_rows": 0, "limit": limit, "offset": offset})
    
    return JSONResponse(content=data)

@router.get("/knime-report")
async def get_knime_report(run: Optional[str] = None, artifacts_root: Optional[str] = None):
    """Return KNIME report"""
    run_id = _resolve_run_id(run)
    root = _resolve_artifacts_root(artifacts_root)
    
    report_file = root / run_id / "stage_07_knime_bridge" / "knime_report.json"
    data = _load_json_file(report_file)
    
    return JSONResponse(content=data if data else {})

@router.get("/kpi-catalog")
async def get_kpi_catalog(run: Optional[str] = None, artifacts_root: Optional[str] = None):
    """Return KPI catalog"""
    run_id = _resolve_run_id(run)
    root = _resolve_artifacts_root(artifacts_root)
    
    catalog_file = root / run_id / "stage_10_bi" / "semantic" / "kpi_catalog.json"
    data = _load_json_file(catalog_file)
    
    return JSONResponse(content=data if data else {})
