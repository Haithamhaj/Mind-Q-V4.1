from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Tuple

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.api import bi


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture()
def intelligence_fixture(tmp_path: Path, monkeypatch) -> Tuple[TestClient, str]:
    artifacts_root = tmp_path / "artifacts"
    run_id = "run_layer3_demo"
    stage08 = artifacts_root / run_id / "stage_08_insights"
    stage08.mkdir(parents=True, exist_ok=True)

    insights_payload = {
        "run_id": run_id,
        "generated_at": "2025-10-27T12:00:00Z",
        "insights": [
            {
                "kpi": "COD_AMOUNT",
                "relation": "COD_AMOUNT <-> REGION",
                "strength": 0.68,
                "direction": "positive",
                "coverage": 0.55,
                "confidence": 0.74,
                "bucket": "HIGH",
            },
            {
                "kpi": "SLA",
                "relation": "SLA <-> CARRIER",
                "strength": -0.42,
                "direction": "negative",
                "coverage": 0.48,
                "confidence": 0.63,
                "bucket": "MEDIUM",
            },
        ],
    }
    _write_json(stage08 / "insights_report.json", insights_payload)

    diagnostics_payload = {
        "anomalies": {
            "metric": "COD_AMOUNT",
            "records": [
                {"REGION": "Riyadh", "_n": 120, "_m": 210.0, "_s": 12.0, "z_score": 3.2},
                {"REGION": "Jeddah", "_n": 80, "_m": 90.0, "_s": 8.0, "z_score": -3.6},
            ],
        }
    }
    _write_json(stage08 / "diagnostics.json", diagnostics_payload)
    _write_json(stage08 / "story_ops.json", {"items": []})
    _write_json(stage08 / "gate.json", {"status": "PASS"})

    time_stats = pd.DataFrame(
        {
            "time_bucket": [
                "2025-10-20",
                "2025-10-21",
                "2025-10-22",
                "2025-10-23",
            ],
            "n": [100, 120, 160, 150],
            "share": [0.2, 0.25, 0.33, 0.30],
        }
    )
    time_stats.to_parquet(stage08 / "time_stats.parquet", index=False)

    knime_profile = artifacts_root / run_id / "phase_07_knime" / "profile"
    knime_profile.mkdir(parents=True, exist_ok=True)
    _write_json(knime_profile.parent / "run_meta.json", {"run_id": run_id, "prompt": {"mode": "auto"}})
    _write_json(
        knime_profile / "layer2_candidate.json",
        {
            "run_id": run_id,
            "variance": {"columns": [{"column": "COD_AMOUNT", "variance": 12.5}]},
        },
    )

    def _iter_override():
        yield artifacts_root

    monkeypatch.setattr(bi, "_iter_artifact_roots", _iter_override)
    monkeypatch.setattr(bi, "_resolve_run", lambda run: (artifacts_root / run) if (artifacts_root / run).exists() else None)
    assert bi._resolve_run(run_id) is not None

    app = FastAPI()
    app.include_router(bi.router)
    client = TestClient(app)
    return client, run_id


def test_get_intelligence_payload(intelligence_fixture: Tuple[TestClient, str]) -> None:
    client, run_id = intelligence_fixture
    response = client.get("/api/bi/intelligence", params={"run": run_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"] == run_id
    assert payload["network"]["nodes"]
    assert payload["sankey"]["links"]
    assert payload["anomalies"]["series"]
    assert payload["predictive"]["series"]
    assert payload["knime"]["files"]
