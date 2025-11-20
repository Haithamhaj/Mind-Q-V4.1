from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
from fastapi.testclient import TestClient

from backend.src.app.services.pipeline_api.app import app


def _prepare_artifacts(tmp_path: Path) -> tuple[str, Path]:
    run_id = "run-test-bridge"
    artifacts_root = tmp_path / "artifacts"
    fact_dir = artifacts_root / run_id / "stage_10_bi" / "marts"
    fact_dir.mkdir(parents=True, exist_ok=True)
    fact_path = fact_dir / "fact_business.parquet"
    pl.DataFrame(
        {
            "entity_id": ["e1", "e2", "e3"],
            "ts": [
                datetime(2025, 1, 1, tzinfo=timezone.utc),
                datetime(2025, 1, 2, tzinfo=timezone.utc),
                datetime(2025, 1, 3, tzinfo=timezone.utc),
            ],
            "locale": ["Riyadh", "Jeddah", "Riyadh"],
            "CARRIER": ["SMSA", "Aramex", "SMSA"],
            "kpi_rto_pct": [0.1, 0.2, 0.3],
            "kpi_cod_rate": [0.4, 0.5, 0.6],
            "sla_breached_contract": [True, False, True],
            "orders_cnt": [10, 20, 5],
        }
    ).write_parquet(fact_path)

    insights_dir = artifacts_root / run_id / "stage_08_insights"
    insights_dir.mkdir(parents=True, exist_ok=True)
    (insights_dir / "story_ops.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "ins-1",
                        "title": "Investigate Riyadh RTO spike",
                        "what_we_see": "RTO is trending up for SMSA in Riyadh.",
                        "priority": "High",
                        "deep_dive_filters": {"city": "Riyadh", "carrier": "SMSA"},
                    },
                    {
                        "id": "ins-2",
                        "title": "LLM error",
                        "what_we_see": {"code": "llm_error", "message": "fallback text"},
                        "priority": "Medium",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (insights_dir / "insights_report.json").write_text(
        json.dumps({"nzv_impact": {"demotion_note": "3 columns demoted"}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_id, artifacts_root


client = TestClient(app)


def test_v2_table_endpoint_filters(tmp_path):
    run_id, artifacts_root = _prepare_artifacts(tmp_path)
    response = client.get(
        "/api/v2/bi/table",
        params={
            "run_id": run_id,
            "city": "Riyadh",
            "date_from": "2025-01-02",
            "artifacts_root": artifacts_root.as_posix(),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"], "Expected at least one filtered row"
    assert all(row["locale"] == "Riyadh" for row in payload["rows"])
    assert any(col["field"] == "orders_cnt" for col in payload["columns"])


def test_v2_heatmap_endpoint(tmp_path):
    run_id, artifacts_root = _prepare_artifacts(tmp_path)
    response = client.get(
        "/api/v2/bi/heatmap",
        params={"run_id": run_id, "kpi": "rto_rate", "artifacts_root": artifacts_root.as_posix()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["x_labels"] and payload["y_labels"]
    assert payload["data"]
    for row in payload["data"]:
        assert len(row) == 3


def test_v2_insights_feed(tmp_path):
    run_id, artifacts_root = _prepare_artifacts(tmp_path)
    response = client.get(
        "/api/v2/ml/insights/feed",
        params={"run_id": run_id, "artifacts_root": artifacts_root.as_posix()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["id"] == "ins-1"
    assert payload[0]["deep_dive_filters"]["city"] == "Riyadh"
    assert payload[1]["demotion_note"] == "3 columns demoted"
