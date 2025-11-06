from __future__ import annotations

from fastapi.testclient import TestClient

from bi10.app.main import app


def test_meta_ok(monkeypatch, tmp_path):
    # setup minimal semantic file
    run_id = "test_run"
    semantic_dir = tmp_path / run_id / "stage_10_bi" / "semantic"
    semantic_dir.mkdir(parents=True, exist_ok=True)
    metrics_yaml = semantic_dir / "metrics.yaml"
    metrics_yaml.write_text(
        """
timezone: Asia/Riyadh
currency: SAR
marts:
  - id: shipments
    files: ["fact_shipments.parquet"]
metrics:
  - id: sla_pct
    name: "SLA%"
    mart: shipments
    sql: "SELECT '2025-01-01' AS dt, 95.0 AS val"
    default_chart: line
    cap: 1000
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr("bi10.app.config.settings.artifacts_root", tmp_path.as_posix())
    monkeypatch.setattr("bi10.app.config.settings.default_run_id", run_id)

    client = TestClient(app)
    response = client.get("/api/meta")
    assert response.status_code == 200
    payload = response.json()
    assert payload["timezone"] == "Asia/Riyadh"
    assert "metrics" in payload
