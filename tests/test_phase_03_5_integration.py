from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from zoneinfo import ZoneInfo

from backend.src.app.services.stage_03_5_textops import impl


@pytest.mark.integration
def test_phase_03_5_integration(tmp_path: Path) -> None:
    run_id = "run_textops"
    artifacts_root = tmp_path / "artifacts"
    shipments_dir = tmp_path / "raw" / "shipments"
    stage03_dir = artifacts_root / run_id / "stage_03"
    shipments_dir.mkdir(parents=True, exist_ok=True)
    stage03_dir.mkdir(parents=True, exist_ok=True)

    tz = ZoneInfo("Asia/Riyadh")
    rows = []
    base_time = datetime(2024, 1, 1, 8, 0, tzinfo=tz)
    for idx in range(10_000):
        rows.append(
            (
                f"AWB-{idx:06d}",
                "Great service" if idx % 2 == 0 else "سيء جدا",
                "شكرا لكم" if idx % 3 == 0 else "التأخير سيء",
                base_time + timedelta(minutes=idx),
                "Riyadh _ District _ Street",
                "+966555000000",
                "Jeddah _ District _ Street",
                "+966555111111",
            )
        )
    shipments_frame = pl.DataFrame(
        rows,
        schema={
            "AWB_NO": pl.Utf8,
            "item_desc": pl.Utf8,
            "customer_note": pl.Utf8,
            "created_at": pl.Datetime(time_zone="Asia/Riyadh"),
            "SENDER ADDRESS": pl.Utf8,
            "SENDER PHONE": pl.Utf8,
            "RECEIVER ADDRESS": pl.Utf8,
            "RECEIVER PHONE": pl.Utf8,
        },
        orient="row",
    )
    shipments_path = shipments_dir / "shipments.parquet"
    shipments_frame.write_parquet(shipments_path.as_posix())

    domain_dict_path = stage03_dir / "domain_dict.json"
    domain_dict_path.write_text(
        json.dumps(
            {
                "stopwords_ar": ["من", "على", "الى"],
                "stopwords_en": ["the", "and", "or"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    text_catalog_path = stage03_dir / "text_columns_catalog.json"
    text_catalog_path.write_text(
        json.dumps({"text_columns": ["item_desc", "customer_note"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    config_payload = {
        "version": "1.0",
        "seed": 42,
        "timezone": "Asia/Riyadh",
        "inputs": {
            "shipments_path": shipments_path.as_posix(),
            "docs_path": str(tmp_path / "raw" / "docs"),
            "notes_path": str(tmp_path / "raw" / "notes"),
        },
        "sources": {
            "domain_dict": domain_dict_path.as_posix(),
            "text_catalog": text_catalog_path.as_posix(),
            "kpi_map": "config/kpi_map.yaml",
            "dim_keys": "config/dim_keys.yaml",
        },
    }
    config_path = tmp_path / "textops_test.yaml"
    config_path.write_text(json.dumps(config_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg = {
        "artifacts_root": artifacts_root.as_posix(),
        "config_path": config_path.as_posix(),
    }

    result = impl.run(run_id, inputs={}, config=cfg)
    assert result["status"] in {"PASS", "WARN"}

    phase_dir = artifacts_root / run_id / "stage_03_5_textops"
    sentiment_path = phase_dir / "sentiment_features.parquet"
    vectors_path = phase_dir / "svd_components.parquet"
    profile_path = phase_dir / "text_profile.json"
    ready_flag = phase_dir / "_READY.OK"
    structured_path = phase_dir / "structured_fields.parquet"

    assert sentiment_path.exists()
    assert vectors_path.exists()
    assert profile_path.exists()
    assert ready_flag.exists()
    assert structured_path.exists()

    sentiment_df = pl.read_parquet(sentiment_path.as_posix())
    vectors_df = pl.read_parquet(vectors_path.as_posix())
    structured_df = pl.read_parquet(structured_path.as_posix())

    assert sentiment_df.height == 10_000
    assert vectors_df.height == 10_000
    assert "AWB_NO" in sentiment_df.columns
    assert "AWB_NO" in vectors_df.columns
    assert "AWB_NO" in structured_df.columns
    assert "sender_phone_structured" in structured_df.columns
    assert "receiver_phone_structured" in structured_df.columns

    joined = sentiment_df.join(vectors_df, on="AWB_NO", how="inner")
    assert joined.height == sentiment_df.height

    report_payload = json.loads((phase_dir / "textops_report.json").read_text(encoding="utf-8"))
    assert report_payload["coverage_pct"] >= 50
    findings_payload = json.loads((phase_dir / "quality_findings.json").read_text(encoding="utf-8"))
    assert "warnings" in findings_payload
