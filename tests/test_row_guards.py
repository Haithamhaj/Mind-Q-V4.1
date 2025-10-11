from __future__ import annotations
from pathlib import Path
from typing import Any, Dict

from phases._01_ingestion import impl as ingest  # type: ignore
from phases._02_quality import impl as quality  # type: ignore
from shared import validate  # type: ignore
import json
import pytest


def test_row_count_guard(tmp_path: Path) -> None:
    run_id = "guard01"
    data = Path("data/basic.csv").resolve()
    cfg: Dict[str, Any] = {"artifacts_root": str(tmp_path)}

    res1: Dict[str, Any] = ingest.run(run_id, {"files": [data.as_posix()]}, cfg)  # type: ignore[assignment]
    raw = res1.get("outputs", {}).get("raw")  # type: ignore[assignment]
    assert raw, "ingestion should return raw parquet path"

    _ = quality.run(run_id, {"raw": raw}, cfg)  # type: ignore[call-arg]
    # Both stages should emit row_meta.json
    p1 = tmp_path / run_id / "stage_01_ingestion" / "row_meta.json"
    p2 = tmp_path / run_id / "stage_02_quality" / "row_meta.json"
    assert p1.exists()
    assert p2.exists()


@pytest.mark.parametrize("phase_dir", [
    "03_schema",
    "04_profile",
    "05_missing",
    "06_standardize",
    "06_feature_eng",
    "07_readiness",
])
def test_stub_phases_write_row_meta(tmp_path: Path, phase_dir: str) -> None:
    # Use ingestion to produce raw, then import phase module dynamically
    run_id = "guard02"
    data = Path("data/basic.csv").resolve()
    cfg: Dict[str, Any] = {"artifacts_root": str(tmp_path)}
    res1 = ingest.run(run_id, {"files": [data.as_posix()]}, cfg)  # type: ignore[assignment]
    raw = res1.get("outputs", {}).get("raw")  # type: ignore[assignment]
    assert raw
    import importlib
    mod = importlib.import_module(f"phases.{phase_dir}.impl")
    res = mod.run(run_id, {"raw": raw}, cfg)
    assert isinstance(res, dict)
    out = tmp_path / run_id / f"stage_{phase_dir.split('_',1)[0]}_{phase_dir.split('_',1)[1]}" / "row_meta.json"
    assert out.exists()


def test_guard_writes_mismatch(tmp_path: Path) -> None:
    out_dir = tmp_path / "stage_test"
    validate.assert_row_stability(n_in=10, n_out=9, allow_drop=False, phase="XX", out_dir=out_dir)
    f = out_dir / "shape_mismatch.json"
    assert f.exists()
    payload = json.loads(f.read_text(encoding="utf-8"))
    assert payload.get("n_in") == 10 and payload.get("n_out") == 9
