from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl  # type: ignore
from src.app.services.stage_11_ml_sandbox.base_extractor import build_ml_base_table
from src.app.services.stage_11_ml_sandbox.cluster_engine import run_client_clustering

from tests.stage11_utils import write_fact_business


def _cluster_fact_rows() -> list[dict[str, object]]:
    tz = ZoneInfo("Asia/Riyadh")
    base = datetime(2025, 2, 1, 9, 0, tzinfo=tz)
    rows: list[dict[str, object]] = []

    def _row(entity_suffix: str, client: str, carrier: str, hours: float, cod_amount: float, on_time: bool, rto: bool) -> dict[str, object]:
        created = base + timedelta(hours=int(entity_suffix) * 2)
        delivered = created + timedelta(hours=hours)
        return {
            "entity_id": f"{client}-ORD-{entity_suffix}",
            "Account_NO": client,
            "FORWARD_COMPANY": carrier,
            "ORIGIN": "Riyadh",
            "DESTINATION": "Jeddah",
            "DESTINATION_HUB": "Hub-Cluster",
            "AREA_STREET": "Zone-X",
            "SENDER_NAME": f"Sender {client}",
            "RECEIVER_NAME": f"Receiver {client}",
            "STATUS": "Delivered" if not rto else "RTO",
            "3PLSTATUS": "Delivered",
            "3PL_Last_Status": "Dropoff",
            "RECEIVER_MODE": "COD",
            "row_deeplink": "https://bi.mindq/orders/demo",
            "COD_AMOUNT": cod_amount,
            "ON_WEIGHT": 5.0,
            "ON_PIECES": 1.0,
            "D_ATTEMPT": 1,
            "CALL_ATTEMPT": 0,
            "kpi_sla_pct": 0.9,
            "kpi_rto_pct": 0.05,
            "kpi_cod_rate": 0.6,
            "ts_created": created,
            "ts_delivered": delivered,
            "SCHEDULE_DATE": created + timedelta(days=1),
            "lead_time_hours": hours,
            "on_time": on_time,
            "rto_flag": rto,
            "is_cod": True,
        }

    for idx in range(5):
        rows.append(_row(str(idx), "C1", "Carrier-A", 18.0, 150.0, True, False))
    for idx in range(5):
        rows.append(_row(str(idx + 5), "C2", "Carrier-B", 72.0, 500.0, False, True))
    for idx in range(2):
        rows.append(_row(str(idx + 10), "C3", "Carrier-C", 24.0, 80.0, True, False))
    return rows


def test_client_clustering_builds_artifacts(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    run_id = "demo-stage11-cluster"
    write_fact_business(artifacts_root, run_id, _cluster_fact_rows())

    stage11_dir = artifacts_root / run_id / "stage_11_ml_sandbox"
    build_ml_base_table(run_id, stage11_dir.as_posix())
    metadata = run_client_clustering(run_id, stage11_dir.as_posix(), n_clusters=2)

    cluster_path = stage11_dir / "client_clusters.parquet"
    model_path = stage11_dir / "cluster_model.joblib"
    metadata_path = stage11_dir / "cluster_metadata.json"

    assert cluster_path.exists()
    assert model_path.exists()
    assert metadata_path.exists()
    assert metadata["model_trained"] is True
    assert metadata["n_clients_total"] == 3
    assert metadata["n_clients_clustered"] == 2
    assert metadata["n_clients_unclustered"] == 1

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["features_used"]  # sanity check it records schema

    df = pl.read_parquet(cluster_path.as_posix())
    assert sorted(df["client_id"]) == ["C1", "C2", "C3"]
    non_negative_clusters = {int(value) for value in df["cluster_id"] if int(value) >= 0}
    assert len(non_negative_clusters) == 2
    assert df.filter(pl.col("client_id") == "C3").select("cluster_id").item() == -1
