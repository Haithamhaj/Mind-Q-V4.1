from __future__ import annotations

import json
from pathlib import Path

import polars as pl  # type: ignore

from src.app.services.stage_07_analytics import run as run_stage07_analytics


def _sample_features() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "order_id": [f"ORD-{idx}" for idx in range(1, 11)],
            "DESTINATION": ["RUH", "RUH", "JED", "JED", "JED", "DMM", "DMM", "RUH", "MED", "JED"],
            "COD_AMOUNT": [100, 120, 80, 450, 30, 60, 65, 90, 20, 15],
            "weight_kg": [1.2, 1.5, 3.0, 7.5, 0.5, 0.8, 0.9, 1.1, 2.2, 1.8],
            "lead_time_hours": [24, 26, 30, 72, 20, 18, 22, 28, 60, 25],
        }
    )


def test_stage07_analytics_generates_outputs(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    features_path = tmp_path / "features.parquet"
    _sample_features().write_parquet(features_path.as_posix())

    inputs = {"features": features_path.as_posix()}
    config = {"artifacts_root": artifacts_root.as_posix()}
    result = run_stage07_analytics("demo-run", inputs, config)

    assert result["status"] == "READY"
    outputs_dir = artifacts_root / "demo-run" / "phase_07_analytics" / "outputs"
    expected_files = [
        "dq_summary.json",
        "correlation_matrix.json",
        "cluster_summary.json",
        "anomalies.json",
    ]
    for filename in expected_files:
        path = outputs_dir / filename
        assert path.exists(), f"{filename} missing"

    cluster_payload = json.loads((outputs_dir / "cluster_summary.json").read_text(encoding="utf-8"))
    assert cluster_payload["clusters"]
    assert cluster_payload["segment_column"] == "DESTINATION"

    anomalies_payload = json.loads((outputs_dir / "anomalies.json").read_text(encoding="utf-8"))
    assert anomalies_payload["top_anomalies"]

    profile_summary = artifacts_root / "demo-run" / "phase_07_analytics" / "profile" / "analytics_summary.json"
    assert profile_summary.exists()
