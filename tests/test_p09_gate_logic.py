from __future__ import annotations

import json
from pathlib import Path

import pytest

pl = pytest.importorskip("polars")  # type: ignore

from tests.p09_utils import load_impl, write_stage_artifacts


def _run_phase(run_id: str, artifacts_root: Path) -> dict:
    impl = load_impl()
    return impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})


def test_p09_gate_logic_stop(tmp_path: Path) -> None:
    run_id = "run_stop"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=4)
    clean_path = artifacts_root / run_id / "stage_06_standardize" / "clean.parquet"
    df = pl.read_parquet(clean_path.as_posix())
    df = df.with_columns(pl.when(pl.arange(0, pl.len()) == 0).then(pl.lit(-5.0)).otherwise(pl.col("COD_AMOUNT")).alias("COD_AMOUNT"))
    df.write_parquet(clean_path.as_posix())

    result = _run_phase(run_id, artifacts_root)
    assert result["status"] == "STOP"
    assert result["exit_code"] == 3


def test_p09_gate_logic_warn(tmp_path: Path) -> None:
    run_id = "run_warn"
    artifacts_root = write_stage_artifacts(
        tmp_path,
        run_id,
        n_rows=5,
        status_cycle=["UNKNOWN"],
        include_effect_metrics=False,
    )
    result = _run_phase(run_id, artifacts_root)
    assert result["status"] == "WARN"
    assert result["exit_code"] == 2
    out_dir = artifacts_root / run_id / "stage_09_business_validation"
    validation = json.loads((out_dir / "validation_report.json").read_text(encoding="utf-8"))
    assert any("missing_insights" in reason or "status_enum" in reason for reason in validation["gate"]["reasons"])
    assert any(reason.startswith("kpi_guard") for reason in validation["gate"]["reasons"])
