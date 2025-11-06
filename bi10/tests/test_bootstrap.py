from __future__ import annotations

import pytest

from bi10.app.bootstrap import preflight


def test_preflight(monkeypatch, tmp_path):
    run_id = "demo"
    base = tmp_path / run_id / "stage_10_bi"
    mart_dir = base / "marts"
    semantic_dir = base / "semantic"
    mart_dir.mkdir(parents=True, exist_ok=True)
    semantic_dir.mkdir(parents=True, exist_ok=True)

    fact = mart_dir / "fact_shipments.parquet"
    fact.write_bytes(b"PAR1")  # dummy file; duckdb not invoked here

    (semantic_dir / "metrics.yaml").write_text(
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
    sql: "SELECT 1"
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr("bi10.app.config.settings.artifacts_root", tmp_path.as_posix())
    monkeypatch.setattr("bi10.app.config.settings.default_run_id", run_id)

    preflight(run_id)


def test_preflight_missing(monkeypatch, tmp_path):
    run_id = "demo"
    base = tmp_path / run_id / "stage_10_bi"
    semantic_dir = base / "semantic"
    semantic_dir.mkdir(parents=True, exist_ok=True)
    (semantic_dir / "metrics.yaml").write_text(
        """
timezone: Asia/Riyadh
currency: SAR
marts:
  - id: shipments
    files: ["missing.parquet"]
metrics:
  - id: sla_pct
    name: "SLA%"
    mart: shipments
    sql: "SELECT 1"
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr("bi10.app.config.settings.artifacts_root", tmp_path.as_posix())
    monkeypatch.setattr("bi10.app.config.settings.default_run_id", run_id)

    with pytest.raises(SystemExit):
        preflight(run_id)
