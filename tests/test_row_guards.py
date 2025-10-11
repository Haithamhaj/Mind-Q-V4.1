from __future__ import annotations
from pathlib import Path
from typing import Any, Dict

from phases._01_ingestion import impl as ingest  # type: ignore
from phases._02_quality import impl as quality  # type: ignore


def test_row_count_guard(tmp_path: Path) -> None:
    run_id = "guard01"
    data = Path("data/basic.csv").resolve()
    cfg: Dict[str, Any] = {"artifacts_root": str(tmp_path)}

    res1 = ingest.run(run_id, {"files": [data.as_posix()]}, cfg)
    raw = res1.get("outputs", {}).get("raw")
    assert raw, "ingestion should return raw parquet path"

    res2 = quality.run(run_id, {"raw": raw}, cfg)
    # Both stages should emit row_meta.json
    p1 = tmp_path / run_id / "stage_01_ingestion" / "row_meta.json"
    p2 = tmp_path / run_id / "stage_02_quality" / "row_meta.json"
    assert p1.exists()
    assert p2.exists()
