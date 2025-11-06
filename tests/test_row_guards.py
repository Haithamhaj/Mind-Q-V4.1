from __future__ import annotations
from pathlib import Path
from typing import Any, Dict

import importlib.util
from shared import validate  # type: ignore
import json
import pytest


def _load_phase_impl(phase_dir: str):
    base = Path(__file__).resolve().parents[1] / "phases"
    candidates = [
        base / phase_dir / "impl.py",
        base / f"_{phase_dir}" / "impl.py",
    ]
    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location(f"phase_{phase_dir}", path.as_posix())
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(f"Unable to locate implementation for phase directory '{phase_dir}'")


ingest = _load_phase_impl("01_ingestion")
quality = _load_phase_impl("02_quality")


def _write_baseline(artifacts_root: Path, run_id: str, metrics: Dict[str, Any]) -> None:
    payload = {
        "run_id": run_id,
        "n_rows": metrics.get("n_rows"),
        "n_cols": metrics.get("n_cols"),
        "schema_hash": "stub-hash",
        "source_fingerprint": [],
    }
    path = artifacts_root / run_id / "baselines.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_row_count_guard(tmp_path: Path) -> None:
    run_id = "guard01"
    data = Path("data/basic.csv").resolve()
    cfg: Dict[str, Any] = {
        "artifacts_root": str(tmp_path),
        "ingestion": {"min_file_size_bytes": 0, "min_rows": 0},
    }

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
    cfg: Dict[str, Any] = {
        "artifacts_root": str(tmp_path),
        "ingestion": {"min_file_size_bytes": 0, "min_rows": 0},
    }
    res1 = ingest.run(run_id, {"files": [data.as_posix()]}, cfg)  # type: ignore[assignment]
    raw = res1.get("outputs", {}).get("raw")  # type: ignore[assignment]
    metrics = res1.get("metrics") or {}
    _write_baseline(Path(cfg["artifacts_root"]), run_id, metrics)
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
