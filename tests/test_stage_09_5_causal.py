from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import sys

TEST_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = TEST_DIR.parent
SRC_PATH = BACKEND_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
PROJECT_ROOT = BACKEND_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import types

if "polars" not in sys.modules:
    import pandas as _pd

    class _StubDataFrame:
        def __init__(self, rows=None):
            if rows is None:
                self._df = _pd.DataFrame()
            elif isinstance(rows, _pd.DataFrame):
                self._df = rows.copy()
            else:
                self._df = _pd.DataFrame(rows)
            self.schema = {col: None for col in self._df.columns}
            self.columns = list(self._df.columns)

        def is_empty(self) -> bool:
            return self._df.empty

        def select(self, columns):
            if isinstance(columns, list):
                return _StubDataFrame(self._df[columns])
            return self

        def with_columns(self, columns):
            return self

        def write_parquet(self, path):
            self._df.to_parquet(path)

        def to_pandas(self):
            return self._df.copy()

    def _stub_series(name, values, dtype=None):
        return _pd.Series(values, name=name)

    stub = types.ModuleType("polars")
    stub.DataFrame = lambda rows=None: _StubDataFrame(rows)
    stub.Series = _stub_series
    stub.Utf8 = stub.Float64 = stub.Int64 = stub.Boolean = object()
    stub.read_parquet = lambda path: _StubDataFrame(_pd.read_parquet(path))
    sys.modules["polars"] = stub

import numpy as np
import pandas as pd
import pytest

from app.services.stage_09_5_causal_inference import impl
from app.services.stage_09_5_causal_inference.estimate import EstimationOutputs
from backend.phases.phase10_bi.impl import include_causal_advisory


def _make_dataset(size: int = 1800) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    flags = rng.integers(0, 2, size=size)
    return pd.DataFrame(
        {
            "express_lane_flag": flags,
            "delivery_success_rate": np.clip(0.6 + 0.1 * flags + rng.normal(0, 0.05, size=size), 0, 1),
            "ORIGIN": rng.choice(["RUH", "JED", "DMM"], size=size),
            "DESTINATION": rng.choice(["MED", "JED", "KWI"], size=size),
            "vehicle_type": rng.choice(["van", "bike"], size=size),
            "courier_tenure_months": rng.integers(1, 36, size=size),
            "delivery_window": rng.choice(["morning", "afternoon", "evening"], size=size),
            "package_category": rng.choice(["cod", "prepaid"], size=size),
            "weather_score_bucket": rng.choice(["low", "medium", "high"], size=size),
            "hub_handling_time_bucket": rng.choice(["<15", "15-30", ">30"], size=size),
        }
    )


def _prepare_stage09(tmp_path: Path, run_id: str, df: pd.DataFrame) -> Path:
    stage09_dir = tmp_path / run_id / "stage_09_business_validation"
    stage09_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(stage09_dir / "bi_feed.parquet", index=False)
    return stage09_dir


@pytest.mark.asyncio
async def test_skip_when_flag_off_or_no_problem(monkeypatch):
    monkeypatch.delenv("MINDQ_ENABLE_CAUSAL", raising=False)
    result = await impl.run("any-run", "logistics_delivery")
    assert result["skipped"] is True

    monkeypatch.setenv("MINDQ_ENABLE_CAUSAL", "true")
    result = await impl.run("any-run", "")
    assert result["skipped"] is True


@pytest.mark.asyncio
async def test_preconditions_missing_cols(monkeypatch, tmp_path):
    run_id = "missing-columns"
    monkeypatch.setenv("MINDQ_ENABLE_CAUSAL", "true")
    monkeypatch.setattr(impl, "ARTIFACT_ROOT_CANDIDATES", [tmp_path])

    df = pd.DataFrame(
        {
            "express_lane_flag": [0, 1, 0, 1],
            "delivery_success_rate": [0.7, 0.75, 0.8, 0.9],
        }
    )
    _prepare_stage09(tmp_path, run_id, df)

    with pytest.raises(ValueError):
        await impl.run(run_id, "logistics_delivery")


@pytest.mark.asyncio
async def test_overlap_check(monkeypatch, tmp_path):
    run_id = "overlap-fail"
    monkeypatch.setenv("MINDQ_ENABLE_CAUSAL", "true")
    monkeypatch.setattr(impl, "ARTIFACT_ROOT_CANDIDATES", [tmp_path])
    _prepare_stage09(tmp_path, run_id, _make_dataset())

    def fake_propensity(df: pd.DataFrame, treatment: str, features: Any):
        half = len(df) // 2
        scores = np.concatenate([np.zeros(half), np.ones(len(df) - half)])
        return pd.Series(scores, index=df.index, name="propensity_score")

    class DummyModel:
        def __init__(self):
            self.identity = "dummy"

    estimation = EstimationOutputs(
        ate=0.12,
        cate_mean=0.18,
        cate_series=pd.Series([0.2, 0.15]),
        cate_segments=[{"segment": "delivery_window=morning", "n": 20, "effect": 0.2}],
        method_baseline="stub",
        method_advanced="stub",
        baseline_estimate=object(),
    )

    monkeypatch.setattr(impl, "estimate_propensity", fake_propensity)
    monkeypatch.setattr(impl, "build_and_export", lambda config, out_dir: {"png": out_dir.joinpath("dag.png").as_posix()})
    monkeypatch.setattr(impl, "identify_estimand", lambda df, cfg: (DummyModel(), object(), ["overlap", "backdoor"]))
    monkeypatch.setattr(impl, "run_estimators", lambda model, estimand, df, cfg: estimation)
    monkeypatch.setattr(
        impl,
        "run_refuters",
        lambda model, est, methods: {"tests": [{"name": m, "status": "PASSED"} for m in methods], "passed_count": 3, "supported": True},
    )

    result = await impl.run(run_id, "logistics_delivery")
    assert result["status"] == "UNSUPPORTED"
    assert result["propensity_summary"]["min"] == 0.0
    assert result["propensity_summary"]["max"] == 1.0


@pytest.mark.asyncio
async def test_artifacts_written(monkeypatch, tmp_path):
    run_id = "artifact-pass"
    monkeypatch.setenv("MINDQ_ENABLE_CAUSAL", "true")
    monkeypatch.setattr(impl, "ARTIFACT_ROOT_CANDIDATES", [tmp_path])
    df = _make_dataset()
    _prepare_stage09(tmp_path, run_id, df)

    def fake_dag(config, out_dir):
        path = out_dir / "causal_dag.png"
        out_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fakepng")
        return {"png": path.as_posix()}

    class DummyModel:
        def refute_estimate(self, estimate, method_name: str):
            return type("R", (), {"refutation_result": "Not refuted", "p_value": 0.5, "new_effect": 0.1})

    estimation = EstimationOutputs(
        ate=0.1,
        cate_mean=0.15,
        cate_series=pd.Series([0.11, 0.18]),
        cate_segments=[{"segment": "package_category=cod", "n": 100, "effect": 0.2}],
        method_baseline="stub",
        method_advanced="stub",
        baseline_estimate=object(),
    )

    monkeypatch.setattr(impl, "build_and_export", fake_dag)
    monkeypatch.setattr(impl, "identify_estimand", lambda df, cfg: (DummyModel(), object(), ["overlap", "backdoor"]))
    monkeypatch.setattr(impl, "estimate_propensity", lambda df, treatment, features: pd.Series([0.4] * len(df)))
    monkeypatch.setattr(impl, "run_estimators", lambda model, estimand, df, cfg: estimation)
    monkeypatch.setattr(
        impl,
        "run_refuters",
        lambda model, est, methods: {"tests": [{"name": m, "status": "PASSED"} for m in methods], "passed_count": 3, "supported": True},
    )

    result = await impl.run(run_id, "logistics_delivery")
    stage_dir = tmp_path / run_id / "stage_09_5_causal"
    assert result["status"] == "SUPPORTED"
    for name in (
        "causal_insights.json",
        "causal_summary.json",
        "refutation_report.json",
        "causal_recommendations.json",
        "causal_config_used.yml",
        "logs.jsonl",
    ):
        assert (stage_dir / name).exists()


def test_status_supported_gate(monkeypatch, tmp_path):
    artifacts_root = tmp_path
    run_id = "gate"
    stage_dir = artifacts_root / run_id / "stage_09_5_causal"
    stage_dir.mkdir(parents=True, exist_ok=True)
    insights = {
        "advisory_only": True,
        "status": "UNSUPPORTED",
        "problem_name": "logistics_delivery",
        "effect": {"ATE": None, "CATE_mean": None},
    }
    (stage_dir / "causal_insights.json").write_text(json.dumps(insights), encoding="utf-8")
    marts_dir = artifacts_root / run_id / "stage_10_bi" / "marts"
    marts_dir.mkdir(parents=True, exist_ok=True)

    created = include_causal_advisory(run_id, artifacts_root, marts_dir)
    assert created is None
    assert not (marts_dir / "fact_causal_effects.parquet").exists()


def test_include_causal_advisory_supported(monkeypatch, tmp_path):
    artifacts_root = tmp_path
    run_id = "supported"
    stage_dir = artifacts_root / run_id / "stage_09_5_causal"
    stage_dir.mkdir(parents=True, exist_ok=True)
    insights = {
        "advisory_only": True,
        "status": "SUPPORTED",
        "problem_name": "logistics_delivery",
        "n": 50,
        "effect": {"ATE": 0.12, "CATE_mean": 0.18},
        "method_baseline": "stub",
        "method_advanced": "stub",
        "CATE_by_segment": [{"segment": "delivery_window=morning", "n": 10, "effect": 0.3}],
    }
    (stage_dir / "causal_insights.json").write_text(json.dumps(insights), encoding="utf-8")
    recommendations = {
        "items": [{"segment": "delivery_window=morning", "priority": "HIGH"}],
    }
    (stage_dir / "causal_recommendations.json").write_text(json.dumps(recommendations), encoding="utf-8")
    marts_dir = artifacts_root / run_id / "stage_10_bi" / "marts"
    marts_dir.mkdir(parents=True, exist_ok=True)

    created = include_causal_advisory(run_id, artifacts_root, marts_dir)
    assert created is not None
    assert created.exists()
    df = pd.read_parquet(created)
    assert not df.empty
    assert set(df["estimate_type"].unique()) <= {"ATE", "CATE"}
