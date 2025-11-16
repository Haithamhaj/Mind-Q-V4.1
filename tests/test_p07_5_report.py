from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

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


feature_report = _load_phase_impl("07_5_feature_report")


def _build_dataset() -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=40, freq="D")
    amount = np.linspace(10, 100, num=40)
    rng = np.random.default_rng(123)
    carrier = rng.choice(["A", "B"], size=40)
    emails = [f"user{i}@example.com" for i in range(40)]
    emails[5] = None
    return pd.DataFrame(
        {
            "amount": amount,
            "carrier": carrier,
            "created_at": dates,
            "customer_email": emails,
        }
    )


def _write_manifest(path: Path, keep: list[str]) -> None:
    payload: Dict[str, Any] = {
        "keep": keep,
        "drop": [],
        "review": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_nzv_artifacts(
    artifacts_root: Path,
    run_id: str,
    *,
    column_name: str,
    n_rows: int,
    dominant_value: Any,
    dominant_pct: float,
) -> None:
    stage05_dir = artifacts_root / run_id / "stage_05_missing"
    stage05_dir.mkdir(parents=True, exist_ok=True)
    nzv_entry = {
        "name": column_name,
        "n_valid": n_rows,
        "missing_pct": 0.0,
        "unique_count": 1,
        "dominant_value": dominant_value,
        "dominant_pct": dominant_pct,
        "top_values": [{"value": dominant_value, "pct": dominant_pct}],
        "nzv_category": "near_zero_variance",
        "is_nzv": True,
        "nzv_reason": "dominant_pct>=0.95,max_unique<=5",
    }
    summary_payload = {
        "imputed_columns": [],
        "indicator_columns": [],
        "model_exclusions": [],
        "nzv_summary": {
            "n_nzv_columns": 1,
            "n_constant_like": 1,
            "n_high_imbalance": 0,
            "n_total_columns": 1,
            "nzv_ratio": 1.0,
        },
    }
    (stage05_dir / "summary.json").write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    nzv_payload = {"run_id": run_id, "n_rows": n_rows, "columns": [nzv_entry], "nzv_summary": summary_payload["nzv_summary"]}
    (stage05_dir / "nzv_summaries.json").write_text(json.dumps(nzv_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    stage06_dir = artifacts_root / run_id / "stage_06_standardize"
    stage06_dir.mkdir(parents=True, exist_ok=True)
    standardize_payload = {
        "columns": {
            column_name: {
                "original_name": column_name,
                "standardized_name": column_name,
                "dtype_before": "string",
                "dtype_after": "string",
                "is_nzv": True,
                "nzv_category": "near_zero_variance",
                "nzv_reason": "dominant_pct>=0.95,max_unique<=5",
                "nzv_dominant_value": dominant_value,
                "nzv_dominant_pct": dominant_pct,
            }
        },
        "nzv_summary": summary_payload["nzv_summary"],
    }
    (stage06_dir / "standardize_report.json").write_text(json.dumps(standardize_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_stage_07_5_generates_profiles(tmp_path: Path) -> None:
    run_id = "testrun"
    artifacts_root = tmp_path / "artifacts"
    features_dir = artifacts_root / run_id / "stage_06_feature_eng"
    readiness_dir = artifacts_root / run_id / "stage_07_readiness"
    features_dir.mkdir(parents=True, exist_ok=True)
    readiness_dir.mkdir(parents=True, exist_ok=True)

    df = _build_dataset()
    features_path = features_dir / "features.parquet"
    df.to_parquet(features_path, index=False)

    _seed_nzv_artifacts(
        artifacts_root,
        run_id,
        column_name="carrier",
        n_rows=len(df),
        dominant_value="A",
        dominant_pct=0.95,
    )

    manifest_path = readiness_dir / "decision_manifest.json"
    keep_cols = ["amount", "carrier", "created_at", "customer_email"]
    _write_manifest(manifest_path, keep_cols)

    feature_spec = {"main_ts": "created_at"}
    (features_dir / "feature_spec.json").write_text(json.dumps(feature_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg = {
        "artifacts_root": artifacts_root.as_posix(),
        "focus_cols": ["amount", "carrier", "created_at", "customer_email"],
        "top_k": 5,
        "tz": "Asia/Riyadh",
        "layer2_metric": "amount",
        "comparative_dimensions": ["carrier"],
        "layer2_min_group": 1,
        "layer2_top_n": 3,
        "layer2_heatmap": {"metric": "amount", "x": "carrier", "y": "customer_email", "max_x": 5, "max_y": 5, "agg": "mean"},
    }
    inputs = {
        "features": features_path.as_posix(),
        "decision_manifest": manifest_path.as_posix(),
        "feature_spec": (features_dir / "feature_spec.json").as_posix(),
    }

    feature_report.run(run_id, inputs, cfg)  # type: ignore[arg-type]

    output_dir = artifacts_root / run_id / "stage_07_5_feature_report"
    report_path = output_dir / "report.json"
    focus_path = output_dir / "focus_report.json"
    metrics_path = output_dir / "metrics.json"
    logs_path = output_dir / "logs.jsonl"

    assert report_path.exists()
    assert (output_dir / "report.md").exists()
    assert focus_path.exists()
    assert metrics_path.exists()
    assert logs_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    summary = report["summary"]
    assert summary["n_rows"] == len(df)
    assert summary["n_cols_reported"] == 3

    amount_profile = report["columns"]["amount"]
    assert amount_profile["stats_numeric"] is not None
    assert "std" in amount_profile["stats_numeric"]
    assert amount_profile["flags"]["has_outliers"] in {True, False}

    created_profile = report["columns"]["created_at"]
    assert created_profile["time_profile"] is not None
    time_profile = created_profile["time_profile"]
    assert time_profile.get("by_month") != []

    email_profile = report["columns"]["customer_email"]
    top_categories = email_profile["top_categories"]
    assert top_categories is not None
    assert all(item["value"] in {"<REDACTED>", "<MISSING>"} for item in top_categories)

    with logs_path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
    assert any('"step": "profile_column"' in line for line in lines)

    low_variance_fields = report.get("low_variance_fields") or []
    assert any(field["name"] == "carrier" for field in low_variance_fields)
    assert "carrier" not in report["columns"]

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["n_rows"] == len(df)
    assert metrics["n_cols_reported"] == 3
    assert metrics["provider"] == "local"

    variance_path = output_dir / "variance_analysis.json"
    assert variance_path.exists()
    variance_payload = json.loads(variance_path.read_text(encoding="utf-8"))
    assert variance_payload["columns"]
    assert any(entry["column"] == "amount" for entry in variance_payload["columns"])

    comparative_path = output_dir / "comparative_summary.json"
    assert comparative_path.exists()
    comparative_payload = json.loads(comparative_path.read_text(encoding="utf-8"))
    assert comparative_payload["metric"] == "amount"
    assert comparative_payload["dimensions"]
    first_dimension = comparative_payload["dimensions"][0]
    assert "top" in first_dimension and first_dimension["top"]

    heatmap_path = output_dir / "heatmap_matrix.json"
    if heatmap_path.exists():
        heatmap_payload = json.loads(heatmap_path.read_text(encoding="utf-8"))
        assert heatmap_payload["metric"] == "amount"
        assert heatmap_payload["matrix"]
        assert {"x", "y", "value"}.issubset(heatmap_payload["matrix"][0].keys())


def test_stage_07_5_handles_empty_keep_list(tmp_path: Path) -> None:
    run_id = "fallbackrun"
    artifacts_root = tmp_path / "artifacts"
    features_dir = artifacts_root / run_id / "stage_06_feature_eng"
    readiness_dir = artifacts_root / run_id / "stage_07_readiness"
    features_dir.mkdir(parents=True, exist_ok=True)
    readiness_dir.mkdir(parents=True, exist_ok=True)

    df = _build_dataset()
    features_path = features_dir / "features.parquet"
    df.to_parquet(features_path, index=False)

    manifest_path = readiness_dir / "decision_manifest.json"
    manifest_path.write_text(json.dumps({"run_id": run_id, "entries": []}, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg = {
        "artifacts_root": artifacts_root.as_posix(),
        "fallback_max_cols": 2,
        "exclude_cols": [],
        "focus_cols": [],
    }
    inputs = {
        "features": features_path.as_posix(),
        "decision_manifest": manifest_path.as_posix(),
    }

    feature_report.run(run_id, inputs, cfg)  # type: ignore[arg-type]

    report_path = artifacts_root / run_id / "stage_07_5_feature_report" / "report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    summary = report["summary"]
    assert summary["n_cols_reported"] == 2
    assert list(report["columns"].keys())

    logs_path = artifacts_root / run_id / "stage_07_5_feature_report" / "logs.jsonl"
    assert logs_path.exists()
    with logs_path.open("r", encoding="utf-8") as handle:
        assert any("fallback_keep" in line for line in handle)
