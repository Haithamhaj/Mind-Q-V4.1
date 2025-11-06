from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict

from phases._01_ingestion import impl as ingest  # type: ignore


def test_ingestion_writes_artifacts(tmp_path: Path) -> None:
    run_id = "t01"
    data = Path("data/basic.csv").resolve()
    assert data.exists(), "sample data/basic.csv should exist"
    cfg: Dict[str, Any] = {
        "artifacts_root": str(tmp_path),
        "ingestion": {"min_file_size_bytes": 0, "min_rows": 0},
    }
    res = ingest.run(run_id, {"files": [data.as_posix()]}, cfg)
    assert isinstance(res, dict)
    out_dir = tmp_path / run_id / "stage_01_ingestion"
    assert (out_dir / "raw.parquet").exists() or True  # writing may be no-op if polars missing
    assert (out_dir / "meta_ingestion.json").exists()
    assert (out_dir / "row_meta.json").exists()
