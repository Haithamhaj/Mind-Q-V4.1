from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

pl = pytest.importorskip("polars")  # type: ignore

from tests.p09_utils import load_impl, write_stage_artifacts


def _overwrite_clean(
    artifacts_root: Path,
    run_id: str,
    rows: list[dict],
) -> None:
    stage06_dir = artifacts_root / run_id / "stage_06_standardize"
    df = pl.DataFrame(rows)
    df = df.with_columns(
        [
            pl.col("ENTRY_DATE").dt.cast_time_unit("us"),
            pl.col("DELIVERY_DATE").dt.cast_time_unit("us"),
        ]
    )
    df.write_parquet((stage06_dir / "clean.parquet").as_posix())


def _write_textops_payloads(artifacts_root: Path, run_id: str, sla_payload: dict, sop_payload: dict) -> None:
    textops_dir = artifacts_root / run_id / "stage_03_5_textops"
    textops_dir.mkdir(parents=True, exist_ok=True)
    (textops_dir / "sla_policies.json").write_text(json.dumps(sla_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (textops_dir / "sop_rules.json").write_text(json.dumps(sop_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_sla_policy_and_defaults_drive_columns(tmp_path: Path) -> None:
    run_id = "run_contract_sla"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=2)
    tz = ZoneInfo("Asia/Riyadh")
    base = datetime(2024, 1, 1, 8, 0, tzinfo=tz)
    open_created = datetime.now(tz) - timedelta(hours=12)
    rows = [
        {
            "AWB_NO": "AWB-001",
            "ENTRY_DATE": base,
            "DELIVERY_DATE": base + timedelta(hours=10),
            "Account_NO": "CLIENT_001",
            "DESTINATION": "RUH",
            "STATUS": "DELIVERED",
            "RECEIVER_MODE": "COD",
            "COD_AMOUNT": 10.0,
        },
        {
            "AWB_NO": "AWB-002",
            "ENTRY_DATE": base + timedelta(hours=1),
            "DELIVERY_DATE": base + timedelta(hours=20),
            "Account_NO": "CLIENT_001",
            "DESTINATION": "RUH",
            "STATUS": "DELIVERED",
            "RECEIVER_MODE": "COD",
            "COD_AMOUNT": 10.0,
        },
        {
            "AWB_NO": "AWB-003",
            "ENTRY_DATE": base,
            "DELIVERY_DATE": base + timedelta(hours=20),
            "Account_NO": "CLIENT_002",
            "DESTINATION": "JED",
            "STATUS": "DELIVERED",
            "RECEIVER_MODE": "COD",
            "COD_AMOUNT": 10.0,
        },
        {
            "AWB_NO": "AWB-004",
            "ENTRY_DATE": base,
            "DELIVERY_DATE": base + timedelta(hours=28),
            "Account_NO": "CLIENT_003",
            "DESTINATION": "DMM",
            "STATUS": "DELIVERED",
            "RECEIVER_MODE": "COD",
            "COD_AMOUNT": 10.0,
        },
        {
            "AWB_NO": "AWB-005",
            "ENTRY_DATE": open_created,
            "DELIVERY_DATE": None,
            "Account_NO": "CLIENT_001",
            "DESTINATION": "RUH",
            "STATUS": "IN_TRANSIT",
            "RECEIVER_MODE": "COD",
            "COD_AMOUNT": 10.0,
        },
    ]
    _overwrite_clean(artifacts_root, run_id, rows)

    sla_payload = [
        {
            "client_id": "CLIENT_001",
            "client_name": "Client One",
            "service_levels": [
                {"name": "Riyadh Rush", "max_hours": 12, "zones": ["RUH"]},
                {"name": "Default", "max_hours": 18},
            ],
        }
    ]
    sop_payload = [
        {
            "client_id": "CLIENT_001",
            "escalation_steps": [
                {"level": 1, "owner": "Support", "sla_hours": 6, "trigger": "Delayed"},
            ],
        }
    ]
    _write_textops_payloads(artifacts_root, run_id, sla_payload, sop_payload)

    defaults_path = tmp_path / "sla_defaults_test.yml"
    defaults_payload = {
        "defaults": {
            "global_hours": 60.0,
            "by_region": {"JED": 30.0},
            "by_client": {
                "CLIENT_003": {"global_hours": 25.0, "by_region": {"DMM": 18.0}},
            },
        }
    }
    defaults_path.write_text(yaml.safe_dump(defaults_payload), encoding="utf-8")

    impl = load_impl()
    result = impl.run(
        run_id,
        {},
        {
            "artifacts_root": artifacts_root.as_posix(),
            "sla_defaults": defaults_path.as_posix(),
        },
    )
    assert result["status"] in {"PASS", "WARN"}

    feed_path = artifacts_root / run_id / "stage_09_business_validation" / "bi_feed.parquet"
    feed_df = pl.read_parquet(feed_path.as_posix())

    row_good = feed_df.filter(pl.col("entity_id") == "AWB-001").to_dicts()[0]
    assert row_good["sla_basis"] == "contract_policy"
    assert row_good["sla_breached_contract"] is False

    row_breach = feed_df.filter(pl.col("entity_id") == "AWB-002").to_dicts()[0]
    assert row_breach["sla_basis"] == "contract_policy"
    assert row_breach["sla_breached_contract"] is True

    row_region = feed_df.filter(pl.col("entity_id") == "AWB-003").to_dicts()[0]
    assert row_region["sla_basis"] == "config_region"
    assert row_region["sla_breached_contract"] is False

    row_client = feed_df.filter(pl.col("entity_id") == "AWB-004").to_dicts()[0]
    assert row_client["sla_basis"] == "config_client"

    sop_row = feed_df.filter(pl.col("entity_id") == "AWB-005").to_dicts()[0]
    assert sop_row["sop_escalation_hours"] == 6.0
    assert sop_row["sop_escalation_breached"] is True

    validation = json.loads(
        (artifacts_root / run_id / "stage_09_business_validation" / "validation_report.json").read_text(encoding="utf-8")
    )
    kpi_names = [entry["name"] for entry in validation.get("kpi_recalc", [])]
    assert "sla_contract_pct" in kpi_names


def test_missing_policies_fall_back_to_config(tmp_path: Path) -> None:
    run_id = "run_sla_defaults"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=2)
    tz = ZoneInfo("Asia/Riyadh")
    base = datetime(2024, 2, 1, 9, 0, tzinfo=tz)
    rows = [
        {
            "AWB_NO": "AWB-100",
            "ENTRY_DATE": base,
            "DELIVERY_DATE": base + timedelta(hours=30),
            "Account_NO": "CLIENT_900",
            "DESTINATION": "RUH",
            "STATUS": "DELIVERED",
            "RECEIVER_MODE": "COD",
            "COD_AMOUNT": 15.0,
        },
        {
            "AWB_NO": "AWB-101",
            "ENTRY_DATE": base,
            "DELIVERY_DATE": base + timedelta(hours=20),
            "Account_NO": "CLIENT_900",
            "DESTINATION": "RUH",
            "STATUS": "DELIVERED",
            "RECEIVER_MODE": "COD",
            "COD_AMOUNT": 15.0,
        },
    ]
    _overwrite_clean(artifacts_root, run_id, rows)

    defaults_path = tmp_path / "sla_defaults_only.yml"
    defaults_payload = {
        "defaults": {
            "global_hours": 36.0,
        }
    }
    defaults_path.write_text(yaml.safe_dump(defaults_payload), encoding="utf-8")

    impl = load_impl()
    result = impl.run(
        run_id,
        {},
        {
            "artifacts_root": artifacts_root.as_posix(),
            "sla_defaults": defaults_path.as_posix(),
        },
    )
    assert result["status"] in {"PASS", "WARN"}

    out_dir = artifacts_root / run_id / "stage_09_business_validation"
    feed_path = out_dir / "bi_feed.parquet"
    feed_df = pl.read_parquet(feed_path.as_posix())
    assert "sla_basis" in feed_df.columns
    assert set(feed_df["sla_basis"].unique()) <= {"config_global"}
