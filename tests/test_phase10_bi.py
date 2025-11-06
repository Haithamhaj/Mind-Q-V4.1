from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, cast

import polars as pl  # type: ignore
import pytest
import yaml
from fastapi.testclient import TestClient

import backend.src.app.services.pipeline_api.app as pipeline_app_module
from phases.phase10_bi import impl as phase10_impl  # type: ignore

app = pipeline_app_module.app
_run_phase10 = getattr(pipeline_app_module, "_run_phase10")


def _write_parquet(path: Path, rows: list[dict[str, object]]) -> None:
    table = pl.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.write_parquet(path.as_posix())


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture()
def prepared_artifacts(tmp_path: Path) -> tuple[str, Path]:
    artifacts_root = tmp_path / "artifacts"
    run_id = "demo_run"
    stage09 = artifacts_root / run_id / "stage_09_business_validation"
    stage08 = artifacts_root / run_id / "stage_08_insights"
    (stage09 / "bi_tiles").mkdir(parents=True, exist_ok=True)
    stage08.mkdir(parents=True, exist_ok=True)

    _write_parquet(
        stage09 / "bi_feed.parquet",
        [
            {
                "entity_id": "ORD-1",
                "ts": datetime(2025, 10, 15, 12, 0),
                "ORIGIN": "RUH",
                "DESTINATION": "JED",
                "RECEIVER_MODE": "COD",
                "STATUS": "Delivered",
                "COD_AMOUNT": 25.0,
                "kpi_orders_cnt": 1,
                "kpi_cod_total": 25.0,
                "kpi_cod_avg": 25.0,
                "kpi_cod_rate": 1.0,
                "eff_effect_size": 0.2,
                "eff_confidence": 0.8,
                "eff_coverage_p90": 0.9,
                "eff_stability_time_pct": 0.7,
                "eff_stability_segment_pct": 0.6,
                "eff_simpson_flag": 0,
                "eff_small_n_flag": 0,
                "decision": "APPROVE",
                "explain_key": "abc123",
                "row_deeplink": "https://example.com",
                "locale": "ar",
                "currency": "SAR",
                "time_grain": "day",
                "scenario_id": "baseline",
            }
        ],
    )

    _write_parquet(
        stage09 / "row_decisions.parquet",
        [{"entity_id": "ORD-1", "decision": "APPROVE", "rules_hit_ids": ["status_enum"], "suggested_fix": "", "severity": "INFO"}],
    )
    _write_parquet(
        stage09 / "benchmarks.parquet",
        [{"DESTINATION": "JED", "STATUS": "Delivered", "orders_cnt": 10, "cod_avg": 23.0, "cod_avg_p50": 20.0, "cod_avg_p90": 30.0}],
    )
    _write_parquet(
        stage09 / "segment_insights.parquet",
        [{"segment_key": "COD|JED", "effect_size": 0.18, "effect_confidence": 0.75, "n": 25, "coverage": 0.4, "period_start": "2025-10-01", "period_end": "2025-10-15"}],
    )
    _write_parquet(
        stage09 / "bi_tiles" / "day.parquet",
        [{"dt": "2025-10-15", "orders": 10}],
    )

    _write_json(
        stage09 / "validation_report.json",
        {
            "kpi_recalc": [
                {"name": "orders_cnt", "recomputed": 1},
                {"name": "cod_total", "recomputed": 25.0},
            ],
            "perf": {"approve_pct": 1.0, "exec_seconds": 0.5, "reject_pct": 0.0, "rows": 1},
            "provenance": {"currency": "SAR", "timezone": "Asia/Riyadh"},
            "unit_currency_meta": {"currency": "SAR"},
            "gate": {"status": "PASS", "reasons": []},
        },
    )
    _write_json(stage09 / "metrics.json", {"rows": 1, "approve_pct": 1.0})

    _write_json(
        stage08 / "insights_report.json",
        {
            "run_id": run_id,
            "generated_at": "2025-10-15T12:00:00Z",
            "timezone": "Asia/Riyadh",
            "summary": {"official_count": 1, "exploratory_count": 0, "n_rows": 1, "max_strength": 0.2},
            "insights": [
                {
                    "kpi": "COD_AMOUNT",
                    "feature": "WEIGHT",
                    "strength": 0.2,
                    "confidence": 0.8,
                    "coverage": 0.5,
                    "bucket": "HIGH",
                    "segment": "Global",
                    "direction": "positive",
                    "window": "2025-10-01/2025-10-15",
                }
            ],
        },
    )
    _write_json(
        stage08 / "insights_candidates.json",
        {
            "run_id": run_id,
            "generated_at": "2025-10-15T12:00:00Z",
            "candidates": [
                {
                    "kpi": "COD_AMOUNT",
                    "feature": "WEIGHT",
                    "metric": "pearson_r",
                    "effect": 0.12,
                    "strength": 0.12,
                    "direction": "positive",
                    "n": 1,
                    "coverage": 1.0,
                    "confidence": 0.7,
                    "bucket": "MEDIUM",
                    "stability_score": 0.9,
                    "low_signal": False,
                    "source": "phase08",
                    "notes": ["demo"],
                }
            ],
        },
    )

    return run_id, artifacts_root


def test_bi_builder_creates_semantic(prepared_artifacts: tuple[str, Path]) -> None:
    run_id, artifacts_root = prepared_artifacts

    result = phase10_impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})

    stage10_root = artifacts_root / run_id / "stage_10_bi"
    semantic_path = stage10_root / "semantic" / "metrics.yaml"
    marts_dir = stage10_root / "marts"

    assert result["status"] == "READY"
    assert semantic_path.exists()
    assert any(marts_dir.glob("*.parquet"))

    metrics_payload: Dict[str, Any] = yaml.safe_load(semantic_path.read_text(encoding="utf-8"))  # type: ignore[assignment]
    assert isinstance(metrics_payload, dict)
    metrics_list_raw = metrics_payload.get("metrics") or []
    assert isinstance(metrics_list_raw, list)
    metrics_list: List[Dict[str, Any]] = [
        cast(Dict[str, Any], metric)
        for metric in cast(List[Any], metrics_list_raw)
        if isinstance(metric, dict)
    ]
    assert metrics_list
    assert any(metric.get("id") == "orders_daily" for metric in metrics_list)


def test_run_phase10_with_generated_assets(prepared_artifacts: tuple[str, Path]) -> None:
    run_id, artifacts_root = prepared_artifacts
    config = {"artifacts_root": artifacts_root.as_posix()}

    # builder invoked inside _run_phase10
    response = _run_phase10(run_id, config)

    assert response["status"] == "READY"
    assert "semantic" in response
    assert "marts" in response and response["marts"]


def test_run_phase10_without_artifacts_root(
    prepared_artifacts: tuple[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, artifacts_root = prepared_artifacts
    monkeypatch.chdir(artifacts_root.parent)

    response = _run_phase10(run_id, {})

    semantic_path = artifacts_root / run_id / "stage_10_bi" / "semantic" / "metrics.yaml"
    assert semantic_path.exists()
    assert response["status"] == "READY"
    assert response["artifacts_root"] == artifacts_root.resolve().as_posix()

def test_bi_metric_endpoint(prepared_artifacts: tuple[str, Path]) -> None:
    run_id, artifacts_root = prepared_artifacts
    _run_phase10(run_id, {"artifacts_root": artifacts_root.as_posix()})
    client = TestClient(app)

    response = client.get(
        f"/v1/bi/{run_id}/metrics/orders_daily",
        params={"artifacts_root": artifacts_root.as_posix()},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["metric"]["id"] == "orders_daily"
    assert payload["data"]
