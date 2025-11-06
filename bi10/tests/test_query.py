from __future__ import annotations

import pyarrow as pa  # type: ignore
import pyarrow.parquet as pq  # type: ignore
from fastapi.testclient import TestClient

from bi10.app.main import app


def _write_parquet(path, rows):
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path.as_posix())


def test_query_limit(monkeypatch, tmp_path):
    run_id = "test_run"
    base = tmp_path / run_id / "stage_10_bi"
    mart_dir = base / "marts"
    mart_dir.mkdir(parents=True, exist_ok=True)
    fact_path = mart_dir / "fact_shipments.parquet"
    rows = [{"range": idx, "val": 1.0} for idx in range(200)]
    _write_parquet(fact_path, rows)

    semantic_dir = base / "semantic"
    semantic_dir.mkdir(parents=True, exist_ok=True)
    (semantic_dir / "metrics.yaml").write_text(
        """
timezone: Asia/Riyadh
currency: SAR
marts:
  - id: shipments
    files: ["fact_shipments.parquet"]
metrics:
  - id: val_avg
    name: "Val Avg"
    mart: shipments
    sql: "SELECT range AS dt, val FROM fact_shipments"
    default_chart: line
    cap: 50
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr("bi10.app.config.settings.artifacts_root", tmp_path.as_posix())
    monkeypatch.setattr("bi10.app.config.settings.default_run_id", run_id)

    client = TestClient(app)
    response = client.post("/api/query", json={"sql": "SELECT range AS dt, val FROM fact_shipments"})
    assert response.status_code == 200
    data = response.json()
    assert data["n"] == 200
