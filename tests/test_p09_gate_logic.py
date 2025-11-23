from __future__ import annotations

import json
from pathlib import Path

import pytest

pl = pytest.importorskip("polars")  # type: ignore

from tests.p09_utils import load_impl, write_stage_artifacts


@pytest.fixture(autouse=True)
def _strict_lab_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDQ_BUSINESS_MODE", "strict_lab")


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
    gate_payload = json.loads((artifacts_root / run_id / "stage_09_business_validation" / "gate.json").read_text(encoding="utf-8"))
    assert gate_payload["data_gate_status"] == "STOP"


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
    gate_payload = json.loads((out_dir / "gate.json").read_text(encoding="utf-8"))
    assert gate_payload["business_gate_status"] in {"OK", "ALERT"}


def test_p09_business_mode_allows_sla(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_id = "run_business"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=6)
    impl = load_impl()
    monkeypatch.setattr(impl, "_evaluate_sla_terms", lambda *args, **kwargs: ([], ["sla::breach"], []))
    monkeypatch.setenv("MINDQ_BUSINESS_MODE", "business_first")
    result = impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})
    assert result["status"] == "PASS"
    gate_payload = json.loads((artifacts_root / run_id / "stage_09_business_validation" / "gate.json").read_text(encoding="utf-8"))
    assert gate_payload["business_gate_status"] == "CRITICAL_ALERT"
    assert gate_payload["data_gate_status"] == "PASS"
    monkeypatch.delenv("MINDQ_BUSINESS_MODE", raising=False)
