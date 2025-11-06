from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = (PROJECT_ROOT / "contracts" / "impute" / "policy.yml").resolve()


def _load_phase05():
    base = PROJECT_ROOT / "phases" / "05_missing" / "impl.py"
    spec = importlib.util.spec_from_file_location("phase_05_missing_impl", base.as_posix())
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load phase 05 implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


missing_mod = _load_phase05()


def _write_baseline(root: Path, run_id: str, n_rows: int, n_cols: int) -> None:
    payload = {
        "run_id": run_id,
        "n_rows": n_rows,
        "n_cols": n_cols,
        "schema_hash": "stub",
        "source_fingerprint": [],
    }
    path = root / run_id / "baselines.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_phase(
    tmp_path: Path,
    run_id: str,
    df: pd.DataFrame,
    policy_path: Path | None = None,
    strategy: str | None = None,
) -> Dict[str, Any]:
    data_path = tmp_path / f"{run_id}_raw.parquet"
    df.to_parquet(data_path, index=False)
    _write_baseline(tmp_path, run_id, len(df), len(df.columns))
    cfg: Dict[str, Any] = {
        "artifacts_root": str(tmp_path),
        "missing": {
            "policy_path": str((policy_path or DEFAULT_POLICY).resolve()),
        },
    }
    if strategy:
        cfg["missing"]["strategy_override"] = strategy
    res = missing_mod.run(run_id, {"raw": data_path.as_posix()}, cfg)
    return res


def _run_cli_phase(
    tmp_path: Path,
    run_id: str,
    raw_path: Path,
    policy_path: Path,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        "scripts/run_phase05.py",
        "--run-id",
        run_id,
        "--artifacts-root",
        str(tmp_path),
        "--raw-path",
        raw_path.as_posix(),
        "--policy",
        str(policy_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)


def test_autoplan_builds_and_applies(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "City": ["Riyadh", "Riyadh", "Jeddah", "Jeddah", "Jeddah"],
            "Carrier": ["C1", "C1", "C2", "C2", "C2"],
            "ServiceType": ["A", "A", "B", "B", "B"],
            "COD_AMOUNT": [100.0, np.nan, 50.0, np.nan, 60.0],
            "CATEGORY": ["Food", None, "Tech", "Tech", None],
            "LATITUDE": [np.nan, np.nan, 24.0, 24.1, np.nan],
            "LONGITUDE": [np.nan, np.nan, 46.0, 46.1, np.nan],
            "order_id": ["o1", "o1", "o2", "o2", "o2"],
            "account_id": ["a1", "a1", "a2", "a2", "a2"],
        }
    )
    res = _run_phase(tmp_path, "auto01", df)
    stage_dir = tmp_path / "auto01" / "stage_05_missing"
    assert (stage_dir / "imputation_plan.json").exists()
    metrics = json.loads((stage_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["plan_source"] == "auto"
    assert metrics["tz_applied"] == "Asia/Riyadh"
    assert metrics["group_valid_min_rows"] == 500
    out_df = pd.read_parquet(res["outputs"]["raw"])
    assert "cod_amount__is_missing" in out_df.columns
    assert out_df["COD_AMOUNT"].isna().sum() == 0


def test_groupwise_then_median(tmp_path: Path) -> None:
    rows = []
    missing_per_group = 100
    rows_per_group = 650
    for city, carrier, base_value in [("Riyadh", "CarrierA", 10.0), ("Jeddah", "CarrierB", 20.0)]:
        for idx in range(rows_per_group):
            value = base_value
            if idx < missing_per_group:
                value = np.nan
            rows.append(
                {
                    "City": city,
                    "Carrier": carrier,
                    "ServiceType": "Express",
                    "COD_AMOUNT": value,
                    "row_id": idx,
                }
            )
    df = pd.DataFrame(rows)
    res = _run_phase(tmp_path, "group01", df)
    out_df = pd.read_parquet(res["outputs"]["raw"])
    ri_fill = out_df[(out_df["City"] == "Riyadh") & (out_df["row_id"] < missing_per_group)]["COD_AMOUNT"].unique()
    jd_fill = out_df[(out_df["City"] == "Jeddah") & (out_df["row_id"] < missing_per_group)]["COD_AMOUNT"].unique()
    assert set(ri_fill) == {10.0}
    assert set(jd_fill) == {20.0}


def test_geo_indicator_only(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "City": ["Riyadh", "Riyadh"],
            "Carrier": ["C1", "C1"],
            "ServiceType": ["A", "A"],
            "LATITUDE": [np.nan, np.nan],
            "LONGITUDE": [np.nan, 46.5],
        }
    )
    res = _run_phase(tmp_path, "geo01", df)
    out_df = pd.read_parquet(res["outputs"]["raw"])
    assert out_df["LATITUDE"].isna().sum() == 2
    assert "latitude__is_missing" in out_df.columns
    assert "longitude__is_missing" in out_df.columns


def test_geo_high_missing_imputed(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "City": ["Riyadh", "Riyadh", "Jeddah", "Jeddah", "Jeddah", "Dammam", "Dammam", "Dammam"],
            "Carrier": ["C1", "C1", "C2", "C2", "C2", "C3", "C3", "C3"],
            "ServiceType": ["A", "A", "B", "B", "B", "C", "C", "C"],
            "LATITUDE": [np.nan, np.nan, np.nan, 24.3, np.nan, np.nan, 24.7, np.nan],
            "LONGITUDE": [np.nan, 46.5, np.nan, 46.6, np.nan, np.nan, 46.8, np.nan],
        }
    )
    res = _run_phase(tmp_path, "geo_high", df)
    out_df = pd.read_parquet(res["outputs"]["raw"])
    assert out_df["LATITUDE"].isna().sum() == 0
    assert out_df["LONGITUDE"].isna().sum() == 0
    plan = json.loads((tmp_path / "geo_high" / "stage_05_missing" / "imputation_plan.json").read_text(encoding="utf-8"))
    lat_entry = next(item for item in plan["policies"] if item["feature"] == "LATITUDE")
    lon_entry = next(item for item in plan["policies"] if item["feature"] == "LONGITUDE")
    assert lat_entry["action"] == "impute"
    assert lon_entry["action"] == "impute"


def test_high_missing_exclude(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "City": ["Riyadh"] * 100,
            "Carrier": ["C1"] * 100,
            "ServiceType": ["A"] * 100,
            "RareFeature": [None] * 97 + ["value", "value", "value"],
        }
    )
    _run_phase(tmp_path, "exclude01", df)
    plan = json.loads((tmp_path / "exclude01" / "stage_05_missing" / "imputation_plan.json").read_text(encoding="utf-8"))
    rare_entry = next(item for item in plan["policies"] if item["feature"] == "RareFeature")
    assert rare_entry["action"] == "drop_for_model_only"


def test_gates_psi_stop(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy_override.yml"
    policy_path.write_text(
        """numeric:
  strategy: groupwise_then_median
  winsor_limits: [0.05, 0.95]
  group_keys: ["City","Carrier","ServiceType"]
  group_valid_min_rows: 10
categorical:
  strategy: mode_with_unknown
time_aware:
  enable: false
geo:
  columns: []
high_missing_exclude_threshold: 0.95
gates:
  psi_warn: 0.0
  psi_stop: 0.0
  psi_keys: ["COD_AMOUNT"]
""",
        encoding="utf-8",
    )
    values = [10.0] * 180 + [20.0] * 20
    df = pd.DataFrame(
        {
            "City": ["Riyadh"] * 200,
            "Carrier": ["C1"] * 200,
            "ServiceType": ["A"] * 200,
            "COD_AMOUNT": values,
        }
    )
    df.loc[df.index[:40], "COD_AMOUNT"] = np.nan
    res = _run_phase(tmp_path, "gate01", df, policy_path=policy_path)
    assert res["status"] == "STOP"
    metrics = json.loads((tmp_path / "gate01" / "stage_05_missing" / "metrics.json").read_text(encoding="utf-8"))
    assert "psi_stop" in metrics["gating_reasons"]


def test_psi_keys_gating(tmp_path: Path) -> None:
    run_id = "psi_warn"
    artifacts_root = tmp_path
    stage01 = artifacts_root / run_id / "stage_01_ingestion"
    stage01.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        {
            "City": ["Riyadh"] * 100,
            "Carrier": ["C1"] * 100,
            "ServiceType": ["A"] * 100,
            "COD_AMOUNT": [100.0] * 25 + [200.0] * 25 + [np.nan] * 50,
            "WEIGHT": [1.0] * 100,
            "DELIVERY_DAYS": [2.0] * 100,
        }
    )
    raw_path = stage01 / "raw.parquet"
    df.to_parquet(raw_path, index=False)
    _write_baseline(artifacts_root, run_id, len(df), len(df.columns))
    plan_dir = artifacts_root / run_id / "stage_05_missing"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_payload = {
        "policies": [
            {
                "feature": "COD_AMOUNT",
                "dtype": "numeric",
                "action": "impute",
                "strategy": "median",
                "params": {"missing_pct": 0.5, "group_valid_min_rows": 500},
                "indicator": "cod_amount__is_missing",
                "fill_value": 0,
            }
        ],
        "gates": {"psi_warn": 0.0, "psi_stop": 10.0, "psi_keys": ["COD_AMOUNT"]},
        "model_exclusions": [],
    }
    (plan_dir / "imputation_plan.json").write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    result = _run_cli_phase(tmp_path, run_id, raw_path, DEFAULT_POLICY)
    assert "[MISSING] WARN" in result.stdout
    metrics = json.loads((plan_dir / "metrics.json").read_text(encoding="utf-8"))
    warn_features = [entry["feature"] for entry in metrics["psi"]["warn"]]
    assert "COD_AMOUNT" in warn_features


def test_groupwise_threshold_fallback(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "City": ["Riyadh"] * 50,
            "Carrier": ["C1"] * 50,
            "ServiceType": ["A"] * 50,
            "COD_AMOUNT": [np.nan] * 25 + [10.0] * 25,
        }
    )
    _run_phase(tmp_path, "fallback01", df)
    plan = json.loads((tmp_path / "fallback01" / "stage_05_missing" / "imputation_plan.json").read_text(encoding="utf-8"))
    cod_entry = next(item for item in plan["policies"] if item["feature"] == "COD_AMOUNT")
    assert cod_entry["params"].get("group_used") == "fallback_small_group"


def test_timeaware_no_future(tmp_path: Path) -> None:
    tz = ZoneInfo("Asia/Riyadh")
    future = datetime.now(tz) + pd.Timedelta(days=10)
    past = datetime.now(tz) - pd.Timedelta(days=5)
    df = pd.DataFrame(
        {
            "City": ["Riyadh"] * 6,
            "Carrier": ["C1"] * 6,
            "ServiceType": ["A"] * 6,
            "ENTRY_DATE": [past, past, future, np.nan, past, future],
            "order_id": ["o1", "o1", "o1", "o2", "o2", "o2"],
            "account_id": ["a1", "a1", "a1", "a2", "a2", "a2"],
        }
    )
    res = _run_phase(tmp_path, "timeaware01", df)
    metrics = json.loads((tmp_path / "timeaware01" / "stage_05_missing" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["tz_applied"] == "Asia/Riyadh"
    out_df = pd.read_parquet(res["outputs"]["raw"])
    entry_series = pd.to_datetime(out_df["ENTRY_DATE"], errors="coerce")
    assert not (entry_series.dropna() > datetime.now(tz)).any()


__all__ = ["missing_mod"]
