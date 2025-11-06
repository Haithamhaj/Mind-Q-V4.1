from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any

import importlib.util
import numpy as np
import pandas as pd


def _load_phase_impl(phase_dir: str):
    base = Path(__file__).resolve().parents[1] / "phases"
    candidates = [
        base / phase_dir / "impl.py",
        base / f"_{phase_dir}" / "impl.py",
    ]
    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location(f"phase_{phase_dir.replace('/', '_')}", path.as_posix())
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(f"Unable to locate implementation for phase directory '{phase_dir}'")


standardize = _load_phase_impl("06_standardize")
feature_eng = _load_phase_impl("06_feature_eng")
readiness = _load_phase_impl("07_readiness")


def _write_baseline(artifacts_root: Path, run_id: str, n_rows: int, n_cols: int) -> None:
    payload: Dict[str, Any] = {
        "run_id": run_id,
        "n_rows": n_rows,
        "n_cols": n_cols,
        "schema_hash": "testhash",
        "source_fingerprint": [],
    }
    baseline_path = artifacts_root / run_id / "baselines.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_dataset() -> pd.DataFrame:
    n = 120
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    cod_amount = np.concatenate([np.full(60, 10.0), np.full(60, 120.0)])
    weight = np.concatenate([np.full(60, 1.0), np.full(60, 5.0)])
    df = pd.DataFrame(
        {
            "feature_constant": 1,
            "feature_numeric1": np.arange(n, dtype=float),
            "feature_numeric2": np.arange(n, dtype=float) * 1.01,
            "order_id": [f"ORD-{i:04d}" for i in range(n)],
            "main_ts": dates,
            "future_ts": dates + pd.Timedelta(days=2),
            "COD_AMOUNT": cod_amount,
            "WEIGHT_KG": weight,
        }
    )
    return df


def test_phase06_and_readiness_artifacts(tmp_path: Path) -> None:
    run_id = "testrun"
    artifacts_root = tmp_path / "artifacts"
    raw_path = tmp_path / "raw.parquet"
    df = _build_dataset()
    df.to_parquet(raw_path, index=False)

    _write_baseline(artifacts_root, run_id, len(df), len(df.columns))

    cfg = {"artifacts_root": artifacts_root.as_posix()}
    std_result = standardize.run(run_id, {"raw": raw_path.as_posix()}, cfg)  # type: ignore[arg-type]
    outputs = std_result["outputs"]
    features_pre = Path(outputs["features_pre"])
    features_curated = Path(outputs["features_curated"])
    assert features_pre.exists()
    assert features_curated.exists()

    feature_dir = artifacts_root / run_id / "stage_06_feature_eng"
    feature_spec = {"main_ts": "main_ts", "business_event_ts": "future_ts"}
    (feature_dir / "feature_spec.json").write_text(json.dumps(feature_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    feat_result = feature_eng.run(  # type: ignore[arg-type]
        run_id,
        {"raw": features_curated.as_posix(), "features_pre": features_pre.as_posix()},
        cfg,
    )
    final_features = Path(feat_result["outputs"]["features"])
    assert final_features.exists()

    readiness_result = readiness.run(  # type: ignore[arg-type]
        run_id,
        {"raw": final_features.as_posix()},
        cfg,
    )
    readiness_dir = artifacts_root / run_id / "stage_07_readiness"
    assert (readiness_dir / "redundancy.json").exists()
    assert (readiness_dir / "correlations.json").exists()
    assert (readiness_dir / "leakage_scan.json").exists()
    assert (readiness_dir / "stability.json").exists()
    report = json.loads((readiness_dir / "readiness_report.json").read_text(encoding="utf-8"))
    key_stats = report["key_stats"]
    assert key_stats["nzv_count"] >= 1
    assert key_stats["psi_columns_evaluated"] >= 1
    assert report["gate"]["status"] in {"WARN", "STOP"}


def test_decider_feature_counts(tmp_path: Path) -> None:
    run_id = "testrun"
    artifacts_root = tmp_path / "artifacts"
    raw_path = tmp_path / "raw.parquet"
    df = _build_dataset()
    df.to_parquet(raw_path, index=False)

    _write_baseline(artifacts_root, run_id, len(df), len(df.columns))

    cfg = {"artifacts_root": artifacts_root.as_posix()}
    std_result = standardize.run(run_id, {"raw": raw_path.as_posix()}, cfg)  # type: ignore[arg-type]
    outputs = std_result["outputs"]
    features_pre = Path(outputs["features_pre"])
    features_curated = Path(outputs["features_curated"])

    feature_dir = artifacts_root / run_id / "stage_06_feature_eng"
    feature_spec = {"main_ts": "main_ts", "business_event_ts": "future_ts"}
    (feature_dir / "feature_spec.json").write_text(json.dumps(feature_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    feat_result = feature_eng.run(  # type: ignore[arg-type]
        run_id,
        {"raw": features_curated.as_posix(), "features_pre": features_pre.as_posix()},
        cfg,
    )
    final_features = Path(feat_result["outputs"]["features"])

    readiness.run(run_id, {"raw": final_features.as_posix()}, cfg)  # type: ignore[arg-type]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT := Path(__file__).resolve().parents[1])
    script = PROJECT_ROOT / "scripts" / "run_phase07_decider.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--run-id", run_id, "--artifacts-root", artifacts_root.as_posix()],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    lines = [line for line in completed.stdout.strip().splitlines() if line]
    assert any(line.startswith("[DECISION]") for line in lines)
    json_start = next((idx for idx, line in enumerate(lines) if line.startswith("{")), None)
    assert json_start is not None
    json_payload = "\n".join(lines[json_start:])
    summary = json.loads(json_payload)
    assert summary["drop"] >= 1
    assert summary["review"] >= 1
    assert summary["keep"] + summary["drop"] + summary["review"] == len(summary["keep_features"]) + len(summary["drop_features"]) + len(summary["review_features"])
    assert not (artifacts_root / run_id / "stage_07_readiness" / "decision_sanity.json").exists()


def test_correlation_sampling_handles_large_numeric(tmp_path: Path) -> None:
    run_id = "largecorr"
    artifacts_root = tmp_path / "artifacts"
    rows = 50
    base = np.arange(rows, dtype=float)
    data = {f"num_{i:03d}": base + i for i in range(305)}
    data["main_ts"] = pd.date_range("2025-01-01", periods=rows, freq="D")
    data["COD_AMOUNT"] = np.linspace(10, 20, num=rows)
    df = pd.DataFrame(data)
    raw_path = tmp_path / "raw_large.parquet"
    df.to_parquet(raw_path, index=False)

    _write_baseline(artifacts_root, run_id, len(df), len(df.columns))
    cfg = {"artifacts_root": artifacts_root.as_posix()}
    std_result = standardize.run(run_id, {"raw": raw_path.as_posix()}, cfg)  # type: ignore[arg-type]
    outputs = std_result["outputs"]
    feature_dir = artifacts_root / run_id / "stage_06_feature_eng"
    (feature_dir / "feature_spec.json").write_text(json.dumps({"main_ts": "main_ts"}, ensure_ascii=False, indent=2), encoding="utf-8")

    feature_eng.run(  # type: ignore[arg-type]
        run_id,
        {"raw": outputs["features_curated"], "features_pre": outputs["features_pre"]},
        cfg,
    )
    final_features = feature_dir / "features.parquet"
    readiness.run(run_id, {"raw": final_features.as_posix()}, cfg)  # type: ignore[arg-type]
    corr_payload = json.loads((artifacts_root / run_id / "stage_07_readiness" / "correlations.json").read_text(encoding="utf-8"))
    assert isinstance(corr_payload, list)
    assert len(corr_payload) <= 50
