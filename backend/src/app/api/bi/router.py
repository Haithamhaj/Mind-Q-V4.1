from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
from pathlib import Path
import duckdb
import json
import io

router = APIRouter(prefix="/api/bi", tags=["bi"])

ARTIFACTS_ROOT_DEFAULT = Path("artifacts")

def _resolve_artifacts_root(artifacts_root: Optional[str]) -> Path:
    if artifacts_root and artifacts_root.strip():
        return Path(artifacts_root).expanduser().resolve()
    return ARTIFACTS_ROOT_DEFAULT.expanduser().resolve()

@router.get("/runs")
async def list_bi_runs(artifacts_root: Optional[str] = None):
    raise HTTPException(status_code=501, detail="Use /v1/runs endpoint instead")

@router.get("/test")
async def test_simple():
    """Simple test endpoint"""
    import json
    return StreamingResponse(
        io.BytesIO(json.dumps({"status": "ok", "test": 123}).encode('utf-8')),
        media_type="application/json"
    )

@router.get("/orders")
async def get_orders_dataset(
    run: Optional[str] = None,
    artifacts_root: Optional[str] = None,
    limit: Optional[int] = Query(default=5000, le=10000)
):
    """
    Return orders dataset for BI visualization.
    Reads from stage_10_bi/marts/fact_business.parquet
    """
    if not run or not run.strip():
        raise HTTPException(status_code=400, detail="run parameter is required")
    
    root = _resolve_artifacts_root(artifacts_root)
    run_dir = root / run
    
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run '{run}' not found in artifacts")
    
    # Use fact_business.parquet (main BI mart)
    fact_business_path = run_dir / "stage_10_bi" / "marts" / "fact_business.parquet"
    
    if not fact_business_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"BI dataset not found for run '{run}'. Please ensure Phase 10 (BI Builder) has been executed."
        )
    
    try:
        # Use DuckDB to query parquet file with NaN/Inf handling
        import polars as pl
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Reading parquet from: {fact_business_path}")
        # Read with Polars first to handle special float values
        df = pl.read_parquet(fact_business_path)
        logger.info(f"Read {df.height} rows, {len(df.columns)} columns")
        
        # Get total rows before limiting
        total_rows = df.height
        
        # Apply limit
        if limit and limit > 0:
            df = df.head(limit)
        
        # Clean NaN and infinite values - replace with None for JSON compatibility
        df = df.with_columns([
            pl.when(pl.col(pl.Float64).is_nan() | pl.col(pl.Float64).is_infinite())
              .then(None)
              .otherwise(pl.col(pl.Float64))
              .name.keep()
        ])
        
        df = df.with_columns([
            pl.when(pl.col(pl.Float32).is_nan() | pl.col(pl.Float32).is_infinite())
              .then(None)
              .otherwise(pl.col(pl.Float32))
              .name.keep()
        ])
        
        # Get column names
        columns = df.columns
        
        # Convert to dicts - now safe after NaN/Inf cleanup
        logger.info("Converting to dicts...")
        rows = df.to_dicts()
        logger.info(f"Converted {len(rows)} rows to dicts")
        
        logger.info("Creating response_data dict...")
        response_data = {
            "run": run,
            "artifacts_root": root.as_posix(),
            "data_source": "fact_business",
            "row_count": int(len(rows)),  # Ensure Python int
            "total_rows": int(total_rows),  # Convert Polars int to Python int
            "columns": list(columns),  # Ensure Python list
            "rows": rows
        }
        
        # Use StreamingResponse to bypass all FastAPI serialization
        logger.info("Serializing to JSON...")
        json_str = json.dumps(response_data, ensure_ascii=False, default=str)
        logger.info(f"JSON string length: {len(json_str)}")
        
        logger.info("Creating StreamingResponse...")
        stream_resp = StreamingResponse(
            io.BytesIO(json_str.encode('utf-8')),
            media_type="application/json"
        )
        logger.info("Returning StreamingResponse")
        return stream_resp
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read orders dataset: {str(e)}"
        )
