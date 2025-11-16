from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl  # type: ignore
import pytest

from src.app.services.stage_11_ml_sandbox.base_extractor import build_ml_base_table

from tests.stage11_utils import write_fact_business


def _sample_fact_rows() -> list[dict[str, object]]:
    tz = ZoneInfo("Asia/Riyadh")
    base = datetime(2025, 1, 1, 8, 0, tzinfo=tz)
    rows: list[dict[str, object]] = []
    for idx, client in enumerate(("C1", "C2")):
        created = base + timedelta(hours=idx * 2)
        delivered = created + timedelta(hours=12 + idx)
        rows.append(
            {
                "entity_id": f"{client}-ORD-{idx}",
                "Account_NO": client,
                "FORWARD_COMPANY": f"CARRIER-{client}",
                "ORIGIN": "Riyadh",
                "DESTINATION": "Jeddah" if client == "C1" else "Dammam",
                "DESTINATION_HUB": "Hub-A" if client == "C1" else "Hub-B",
                "AREA_STREET": f"Zone-{idx}",
                "SENDER_NAME": f"Store {client}",
                "RECEIVER_NAME": f"Customer {client}",
                "STATUS": "Delivered",
                "3PLSTATUS": "Delivered",
                "3PL_Last_Status": "Dropoff",
                "RECEIVER_MODE": "COD",
                "row_deeplink": "https://bi.mindq/orders/demo",
                "COD_AMOUNT": 100.0 + (idx * 5),
                "ON_WEIGHT": 3.5 + idx,
                "ON_PIECES": 1 + idx,
                "D_ATTEMPT": 1,
                "CALL_ATTEMPT": 0,
                "kpi_sla_pct": 0.95,
                "kpi_rto_pct": 0.02,
                "kpi_cod_rate": 0.8,
                "ts_created": created,
                "ts_delivered": delivered,
                "SCHEDULE_DATE": created + timedelta(days=1),
                "lead_time_hours": float((delivered - created).total_seconds() / 3600),
                "on_time": True,
                "rto_flag": False,
                "is_cod": True,
            }
        )
    return rows


def test_build_ml_base_table_creates_expected_schema(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    run_id = "demo-stage11"
    write_fact_business(artifacts_root, run_id, _sample_fact_rows())

    stage11_dir = artifacts_root / run_id / "stage_11_ml_sandbox"
    metadata = build_ml_base_table(run_id, stage11_dir.as_posix())

    output_path = stage11_dir / "ml_base_orders.parquet"
    assert output_path.exists()
    assert metadata["row_count"] == 2
    assert metadata["column_count"] >= 20

    df = pl.read_parquet(output_path.as_posix())
    assert {"shipment_id", "client_id", "city", "delivery_time_hours", "sla_breach"} <= set(df.columns)
    record = df.filter(pl.col("shipment_id") == "C1-ORD-0").to_dicts()[0]
    assert record["client_id"] == "C1"
    assert pytest.approx(record["delivery_time_hours"], rel=1e-3) == 12.0
    assert record["sla_breach"] is False
    assert record["city"] == "Jeddah"
