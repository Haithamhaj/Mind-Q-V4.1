from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = BACKEND_ROOT / "phases" / "05_missing" / "impl.py"
spec = importlib.util.spec_from_file_location("stage05_impl", MODULE_PATH)
assert spec and spec.loader
stage05_impl = importlib.util.module_from_spec(spec)
sys.modules.setdefault("stage05_impl", stage05_impl)
spec.loader.exec_module(stage05_impl)  # type: ignore[arg-type]
stage05_run = stage05_impl.run


@pytest.mark.skipif(pd is None, reason="pandas is required for missing data stage test")
def test_stage05_generates_expected_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_id = "run-missing"
    artifacts_root = tmp_path
    stage05_dir = artifacts_root / run_id / "stage_05_missing"

    # Build minimal Stage 01 artifacts
    stage01_dir = artifacts_root / run_id / "stage_01_ingestion"
    stage01_dir.mkdir(parents=True, exist_ok=True)
    missing_summary = [
        {"column": "value", "missing_pct": 0.5, "missing": 2, "blank": 0, "dtype": "numeric"},
        {"column": "category", "missing_pct": 0.25, "missing": 1, "blank": 0, "dtype": "categorical"},
    ]
    (stage01_dir / "missing_summary.json").write_text(json.dumps(missing_summary), encoding="utf-8")

    df = pd.DataFrame(
        {
            "value": [1.0, None, 3.5, None],
            "category": ["A", "B", None, "A"],
            "latitude": [24.7, None, 24.6, None],
            "longitude": [46.7, None, 46.8, None],
        }
    )
    raw_path = stage01_dir / "raw.parquet"
    df.to_parquet(raw_path, index=False)

    # Avoid baseline dependency
    monkeypatch.setattr("stage05_impl.baseline_utils.load", lambda artifacts, run: {})

    result = stage05_run(
        run_id,
        inputs={"raw": raw_path.as_posix()},
        config={"artifacts_root": artifacts_root.as_posix()},
    )

    outputs = result["outputs"]
    imputed_path = Path(outputs["imputed"])
    report_path = Path(outputs["imputation_report"])
    psi_path = Path(outputs["psi_summary"])

    assert imputed_path.exists()
    assert report_path.exists()
    assert psi_path.exists()

    imputed_df = pd.read_parquet(imputed_path)
    assert len(imputed_df) == len(df)

    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["run_id"] == run_id
    assert "summary" in report_payload

    psi_payload = json.loads(psi_path.read_text(encoding="utf-8"))
    assert "evaluated" in psi_payload

    nzv_path = Path(outputs["nzv_summaries"])
    assert nzv_path.exists()
    nzv_payload = json.loads(nzv_path.read_text(encoding="utf-8"))
    assert nzv_payload["run_id"] == run_id
    assert "columns" in nzv_payload and isinstance(nzv_payload["columns"], list)

    summary_path = stage05_dir / "summary.json"
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    nzv_summary = summary_payload.get("nzv_summary")
    assert isinstance(nzv_summary, dict)
    assert set(nzv_summary.keys()) == {"n_nzv_columns", "n_constant_like", "n_high_imbalance", "n_total_columns", "nzv_ratio"}


@pytest.mark.skipif(pd is None, reason="pandas is required for missing data stage test")
def test_stage05_emits_nzv_categories(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_id = "run-nzv"
    artifacts_root = tmp_path
    stage01_dir = artifacts_root / run_id / "stage_01_ingestion"
    stage01_dir.mkdir(parents=True, exist_ok=True)

    columns = ["constant_col", "near_zero_col", "high_imb_col", "normal_col"]
    missing_summary = [
        {"column": name, "missing_pct": 0.0, "missing": 0, "blank": 0, "dtype": "string"} for name in columns
    ]
    (stage01_dir / "missing_summary.json").write_text(json.dumps(missing_summary), encoding="utf-8")

    n_rows = 100
    data = {
        "constant_col": ["A"] * n_rows,
        "near_zero_col": ["X"] * 96 + ["Y"] * 4,
        "high_imb_col": ["H"] * 90 + ["L"] * 10,
        "normal_col": list(range(n_rows)),
    }
    df = pd.DataFrame(data)
    raw_path = stage01_dir / "raw.parquet"
    df.to_parquet(raw_path, index=False)

    monkeypatch.setattr("stage05_impl.baseline_utils.load", lambda artifacts, run: {})

    result = stage05_run(
        run_id,
        inputs={"raw": raw_path.as_posix()},
        config={"artifacts_root": artifacts_root.as_posix()},
    )
    outputs = result["outputs"]
    stage05_dir = artifacts_root / run_id / "stage_05_missing"
    nzv_path = Path(outputs["nzv_summaries"])
    assert nzv_path.exists()

    payload = json.loads(nzv_path.read_text(encoding="utf-8"))
    columns_payload = {entry["name"]: entry for entry in payload["columns"]}

    assert columns_payload["constant_col"]["nzv_category"] == "constant_like"
    assert columns_payload["constant_col"]["is_nzv"] is True
    assert columns_payload["near_zero_col"]["nzv_category"] == "near_zero_variance"
    assert columns_payload["near_zero_col"]["is_nzv"] is True
    assert columns_payload["high_imb_col"]["nzv_category"] == "high_imbalance"
    assert columns_payload["high_imb_col"]["is_nzv"] is False
    assert columns_payload["normal_col"]["nzv_category"] == "normal"
    assert columns_payload["normal_col"]["is_nzv"] is False

    summary_payload = json.loads((stage05_dir / "summary.json").read_text(encoding="utf-8"))
    nzv_summary = summary_payload["nzv_summary"]
    assert nzv_summary["n_constant_like"] >= 1
    assert nzv_summary["n_high_imbalance"] >= 1
    assert nzv_summary["n_nzv_columns"] == 2
    assert nzv_summary["n_total_columns"] == len(columns)
    assert math.isclose(
        nzv_summary["nzv_ratio"],
        nzv_summary["n_nzv_columns"] / nzv_summary["n_total_columns"],
    )
