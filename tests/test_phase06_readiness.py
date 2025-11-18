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
import pytest


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
            sys.modules.setdefault(spec.name, module)
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
    awb = [f"AWB-{i:06d}" for i in range(n)]
    sender_phone = [f"055500{i:04d}" for i in range(n)]
    receiver_phone = [f"055511{i:04d}" for i in range(n)]
    sender_address = ["Riyadh _ District _ Street 10" for _ in range(n)]
    receiver_address = ["Jeddah _ District _ Street 5" for _ in range(n)]
    df = pd.DataFrame(
        {
            "AWB_NO": awb,
            "feature_constant": 1,
            "feature_numeric1": np.arange(n, dtype=float),
            "feature_numeric2": np.arange(n, dtype=float) * 1.01,
            "order_id": [f"ORD-{i:04d}" for i in range(n)],
            "main_ts": dates,
            "future_ts": dates + pd.Timedelta(days=2),
            "COD_AMOUNT": cod_amount,
            "WEIGHT_KG": weight,
            "SENDER PHONE": sender_phone,
            "RECEIVER PHONE": receiver_phone,
            "SENDER ADDRESS": sender_address,
            "RECEIVER ADDRESS": receiver_address,
        }
    )
    return df


def _write_stage05_nzv(
    artifacts_root: Path,
    run_id: str,
    *,
    n_rows: int,
    columns_payload: list[dict[str, Any]],
    summary_payload: dict[str, Any],
) -> None:
    stage05_dir = artifacts_root / run_id / "stage_05_missing"
    stage05_dir.mkdir(parents=True, exist_ok=True)
    summary_path = stage05_dir / "summary.json"
    summary_wrapper = {
        "imputed_columns": [],
        "indicator_columns": [],
        "model_exclusions": [],
        "nzv_summary": summary_payload,
    }
    summary_path.write_text(json.dumps(summary_wrapper, ensure_ascii=False, indent=2), encoding="utf-8")
    nzv_payload = {
        "run_id": run_id,
        "n_rows": n_rows,
        "columns": columns_payload,
        "nzv_summary": summary_payload,
    }
    (stage05_dir / "nzv_summaries.json").write_text(json.dumps(nzv_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_phase06_and_readiness_artifacts(tmp_path: Path) -> None:
    run_id = "testrun"
    artifacts_root = tmp_path / "artifacts"
    raw_path = tmp_path / "raw.parquet"
    df = _build_dataset()
    df.to_parquet(raw_path, index=False)

    _write_baseline(artifacts_root, run_id, len(df), len(df.columns))

    structured_dir = artifacts_root / run_id / "stage_03_5_textops"
    structured_dir.mkdir(parents=True, exist_ok=True)
    structured_payload = {
        "AWB_NO": df["AWB_NO"],
        "sender_phone_structured": ["0555000000"] * len(df),
        "receiver_phone_structured": ["0555110000"] * len(df),
        "sender_address_components": [json.dumps(["Riyadh", "District", "Street"], ensure_ascii=False)] * len(df),
        "receiver_address_components": [json.dumps(["Jeddah", "District", "Street"], ensure_ascii=False)] * len(df),
    }
    pd.DataFrame(structured_payload).to_parquet((structured_dir / "structured_fields.parquet").as_posix(), index=False)

    cfg = {"artifacts_root": artifacts_root.as_posix()}
    std_result = standardize.run(run_id, {"raw": raw_path.as_posix()}, cfg)  # type: ignore[arg-type]
    outputs = std_result["outputs"]
    features_pre = Path(outputs["features_pre"])
    features_curated = Path(outputs["features_curated"])
    assert features_pre.exists()
    assert features_curated.exists()
    clean_df = pd.read_parquet(Path(outputs["clean"]))
    assert "SENDER_PHONE" in clean_df.columns
    assert clean_df["SENDER_PHONE"].str.startswith("+966").any()
    assert "sender_address_sans_valid" in clean_df.columns
    assert clean_df["sender_address_sans_valid"].dropna().all()

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
    feature_flags_path = readiness_dir / "feature_flags.json"
    assert feature_flags_path.exists()
    feature_flags = json.loads(feature_flags_path.read_text(encoding="utf-8"))
    assert any(flag.get("flag") == "confounded_risk" for flag in feature_flags)
    assert any(flag.get("flag") == "unstable_feature" for flag in feature_flags)
    report = json.loads((readiness_dir / "readiness_report.json").read_text(encoding="utf-8"))
    key_stats = report["key_stats"]
    assert key_stats["nzv_count"] >= 1
    assert key_stats["psi_columns_evaluated"] >= 1
    assert report["gate"]["status"] in {"WARN", "STOP"}


def test_standardize_report_includes_nzv_metadata(tmp_path: Path) -> None:
    run_id = "nzvstd"
    artifacts_root = tmp_path / "artifacts"
    raw_path = tmp_path / "raw.parquet"
    df = pd.DataFrame(
        {
            "STATUS FLAG": ["ON_TIME"] * 24 + ["DELAYED"],
            "variable_field": list(range(25)),
        }
    )
    df.to_parquet(raw_path, index=False)

    _write_baseline(artifacts_root, run_id, len(df), len(df.columns))

    stage05_dir = artifacts_root / run_id / "stage_05_missing"
    stage05_dir.mkdir(parents=True, exist_ok=True)
    nzv_payload = {
        "run_id": run_id,
        "n_rows": len(df),
        "columns": [
            {
                "name": "STATUS FLAG",
                "n_valid": len(df),
                "missing_pct": 0.0,
                "unique_count": 2,
                "dominant_value": "ON_TIME",
                "dominant_pct": 24 / 25,
                "top_values": [{"value": "ON_TIME", "pct": 24 / 25}, {"value": "DELAYED", "pct": 1 / 25}],
                "nzv_category": "near_zero_variance",
                "is_nzv": True,
                "nzv_reason": "dominant_pct>=0.95,max_unique<=5",
            },
            {
                "name": "variable_field",
                "n_valid": len(df),
                "missing_pct": 0.0,
                "unique_count": len(df),
                "dominant_value": 0,
                "dominant_pct": 1 / len(df),
                "top_values": [],
                "nzv_category": "normal",
                "is_nzv": False,
                "nzv_reason": "no_threshold_matched",
            },
        ],
        "nzv_summary": {
            "n_nzv_columns": 1,
            "n_constant_like": 0,
            "n_high_imbalance": 0,
            "n_total_columns": 2,
            "nzv_ratio": 0.5,
        },
    }
    (stage05_dir / "nzv_summaries.json").write_text(json.dumps(nzv_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg = {"artifacts_root": artifacts_root.as_posix()}
    standardize.run(run_id, {"raw": raw_path.as_posix()}, cfg)  # type: ignore[arg-type]

    report_path = artifacts_root / run_id / "stage_06_standardize" / "standardize_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["nzv_summary"] == nzv_payload["nzv_summary"]
    assert report["nzv_summaries_path"].endswith("nzv_summaries.json")
    columns_meta = report["columns"]
    assert "STATUS_FLAG" in columns_meta
    status_meta = columns_meta["STATUS_FLAG"]
    assert status_meta["original_name"] == "STATUS FLAG"
    assert status_meta["is_nzv"] is True
    assert status_meta["usage_hint"] == "context_only"
    assert status_meta["nzv_category"] == "near_zero_variance"
    assert status_meta["nzv_dominant_value"] == "ON_TIME"
    assert status_meta["dtype_before"]
    assert status_meta["dtype_after"]

    normal_meta = columns_meta["variable_field"]
    assert not normal_meta.get("is_nzv")
    assert "usage_hint" not in normal_meta


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


def test_readiness_nzv_adjustment_pass(tmp_path: Path) -> None:
    run_id = "nzvpass"
    artifacts_root = tmp_path / "artifacts"
    raw_path = tmp_path / "raw.parquet"
    n = 80
    rng = np.random.default_rng(314)
    df = pd.DataFrame(
        {
            "META_FIELD": ["STATIC"] * n,
            "metric_one": rng.normal(size=n),
            "metric_two": rng.normal(size=n),
            "main_ts": pd.date_range("2025-02-01", periods=n, freq="H"),
        }
    )
    df.to_parquet(raw_path, index=False)
    _write_baseline(artifacts_root, run_id, len(df), len(df.columns))

    summary_payload = {
        "n_nzv_columns": 1,
        "n_constant_like": 1,
        "n_high_imbalance": 0,
        "n_total_columns": len(df.columns),
        "nzv_ratio": 1 / len(df.columns),
    }
    columns_payload = [
        {
            "name": "META_FIELD",
            "n_valid": len(df),
            "missing_pct": 0.0,
            "unique_count": 1,
            "dominant_value": "STATIC",
            "dominant_pct": 1.0,
            "top_values": [{"value": "STATIC", "pct": 1.0}],
            "nzv_category": "near_zero_variance",
            "is_nzv": True,
            "nzv_reason": "dominant_pct>=0.95,max_unique<=5",
        }
    ]
    _write_stage05_nzv(artifacts_root, run_id, n_rows=len(df), columns_payload=columns_payload, summary_payload=summary_payload)

    cfg = {"artifacts_root": artifacts_root.as_posix()}
    std_result = standardize.run(run_id, {"raw": raw_path.as_posix()}, cfg)  # type: ignore[arg-type]
    outputs = std_result["outputs"]
    feature_dir = artifacts_root / run_id / "stage_06_feature_eng"
    (feature_dir / "feature_spec.json").write_text(json.dumps({"main_ts": "main_ts"}, ensure_ascii=False, indent=2), encoding="utf-8")
    feat_result = feature_eng.run(  # type: ignore[arg-type]
        run_id,
        {"raw": outputs["features_curated"], "features_pre": outputs["features_pre"]},
        cfg,
    )
    readiness.run(run_id, {"raw": feat_result["outputs"]["features"]}, cfg)  # type: ignore[arg-type]

    readiness_dir = artifacts_root / run_id / "stage_07_readiness"
    report = json.loads((readiness_dir / "readiness_report.json").read_text(encoding="utf-8"))
    assert report["gate"]["status"] == "PASS"
    assert report["nzv_summary"]["n_nzv_columns"] == 1
    assert report["critical_nzv_columns"] == []
    assert report.get("nzv_notes")
    diagnostics_payload = json.loads((readiness_dir / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics_payload["summary"]["nzv_ratio"] == pytest.approx(summary_payload["nzv_ratio"])


def test_readiness_warn_with_critical_nzv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_id = "nzvcritical"
    artifacts_root = tmp_path / "artifacts"
    raw_path = tmp_path / "raw.parquet"
    n = 60
    rng = np.random.default_rng(90210)
    df = pd.DataFrame(
        {
            "COD_AMOUNT": [100.0] * n,
            "metric_one": rng.normal(size=n),
            "metric_two": rng.normal(size=n),
            "main_ts": pd.date_range("2025-03-01", periods=n, freq="H"),
        }
    )
    df.to_parquet(raw_path, index=False)
    _write_baseline(artifacts_root, run_id, len(df), len(df.columns))

    summary_payload = {
        "n_nzv_columns": 1,
        "n_constant_like": 1,
        "n_high_imbalance": 0,
        "n_total_columns": len(df.columns),
        "nzv_ratio": 1 / len(df.columns),
    }
    columns_payload = [
        {
            "name": "COD_AMOUNT",
            "n_valid": len(df),
            "missing_pct": 0.0,
            "unique_count": 1,
            "dominant_value": 100.0,
            "dominant_pct": 1.0,
            "top_values": [{"value": 100.0, "pct": 1.0}],
            "nzv_category": "near_zero_variance",
            "is_nzv": True,
            "nzv_reason": "dominant_pct>=0.95,max_unique<=5",
        }
    ]
    _write_stage05_nzv(artifacts_root, run_id, n_rows=len(df), columns_payload=columns_payload, summary_payload=summary_payload)

    critical_file = tmp_path / "critical.yaml"
    critical_file.write_text(json.dumps({"critical_columns": ["COD_AMOUNT"]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(readiness, "CRITICAL_COLUMNS_PATH", critical_file)

    cfg = {"artifacts_root": artifacts_root.as_posix()}
    std_result = standardize.run(run_id, {"raw": raw_path.as_posix()}, cfg)  # type: ignore[arg-type]
    outputs = std_result["outputs"]
    feature_dir = artifacts_root / run_id / "stage_06_feature_eng"
    (feature_dir / "feature_spec.json").write_text(json.dumps({"main_ts": "main_ts"}, ensure_ascii=False, indent=2), encoding="utf-8")
    feat_result = feature_eng.run(  # type: ignore[arg-type]
        run_id,
        {"raw": outputs["features_curated"], "features_pre": outputs["features_pre"]},
        cfg,
    )
    readiness.run(run_id, {"raw": feat_result["outputs"]["features"]}, cfg)  # type: ignore[arg-type]

    readiness_dir = artifacts_root / run_id / "stage_07_readiness"
    report = json.loads((readiness_dir / "readiness_report.json").read_text(encoding="utf-8"))
    assert report["gate"]["status"] == "WARN"
    assert "critical_nzv_columns" in report["gate"]["reasons"]
    assert report["critical_nzv_columns"] == ["COD_AMOUNT"]
    assert any("critical" in note.lower() for note in report.get("nzv_notes", []))
    diagnostics_payload = json.loads((readiness_dir / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics_payload["summary"]["critical_nzv_columns"] == ["COD_AMOUNT"]
