from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

import pandas as pd  # type: ignore

from backend.src.app.services.stage_07_knime_bridge import impl as knime_bridge


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_knime_bridge_generates_layer2_candidate(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    run_id = "testrun"
    stage075 = artifacts_root / run_id / "stage_07_5_feature_report"
    variance_payload: Dict[str, Any] = {
        "generated_at": "2025-10-27T12:00:00Z",
        "columns": [
            {"column": "COD_AMOUNT", "variance": 12.5, "mean": 42.1, "count": 100},
        ],
    }
    comparative_payload: Dict[str, Any] = {
        "generated_at": "2025-10-27T12:00:00Z",
        "metric": "COD_AMOUNT",
        "dimensions": [
            {
                "dimension": "REGION",
                "top": [
                    {"value": "Riyadh", "mean": 180.0, "delta": 25.0, "delta_pct": 0.16, "n": 40},
                ],
            }
        ],
    }
    heatmap_payload: Dict[str, Any] = {
        "generated_at": "2025-10-27T12:00:00Z",
        "metric": "COD_AMOUNT",
        "agg": "mean",
        "x": "REGION",
        "y": "SEGMENT",
        "matrix": [
            {"x": "Riyadh", "y": "VIP", "value": 210.0, "n": 12},
        ],
    }
    _write_json(stage075 / "variance_analysis.json", variance_payload)
    _write_json(stage075 / "comparative_summary.json", comparative_payload)
    _write_json(stage075 / "heatmap_matrix.json", heatmap_payload)

    features_dir = artifacts_root / run_id / "stage_06_feature_eng"
    features_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"COD_AMOUNT": [100, 120, 140], "REGION": ["Riyadh", "Jeddah", "Riyadh"]})
    features_path = features_dir / "features.parquet"
    df.to_parquet(features_path, index=False)

    inputs = {
        "features": features_path.as_posix(),
    }
    config = {
        "artifacts_root": artifacts_root.as_posix(),
        "mode": "auto",
        "enable_knime_stub": True,
    }

    result = knime_bridge.run(run_id, inputs, config)

    profile_dir = artifacts_root / run_id / "phase_07_knime" / "profile"
    candidate_path = profile_dir / "layer2_candidate.json"
    assert candidate_path.exists()
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == run_id
    assert payload["variance"]["columns"][0]["column"] == "COD_AMOUNT"
    assert payload["comparative"]["metric"] == "COD_AMOUNT"
    assert payload["heatmap"]["metric"] == "COD_AMOUNT"
    assert "layer2_candidate" in result["outputs"]

    analytics_dir = artifacts_root / run_id / "phase_07_analytics"
    assert analytics_dir.exists()
    summary_file = analytics_dir / "profile" / "analytics_summary.json"
    assert summary_file.exists()
    knime_outputs_dir = artifacts_root / run_id / "phase_07_knime" / "outputs"
    assert knime_outputs_dir.exists()
    assert result["metrics"].get("python_analytics") in {"SUCCESS", "skipped"}
