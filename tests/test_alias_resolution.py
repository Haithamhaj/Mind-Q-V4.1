from __future__ import annotations

import json
from pathlib import Path

import polars as pl  # type: ignore

from backend.src.app.services.business_validation import OPS_ALIAS_CANDIDATES, _prepare_ops  # type: ignore


def test_prepare_ops_resolves_aliases(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    run_id = "demo"
    (artifacts_root / run_id / "stage_06_standardize").mkdir(parents=True, exist_ok=True)
    report_path = artifacts_root / run_id / "stage_06_standardize" / "standardize_report.json"
    report_path.write_text(
        json.dumps(
            {
                "column_renames": {
                    "RECEIVER MODE": "RECEIVER_MODE",
                    "DELIVER DATE": "DELIVER_DATE",
                    "status": "STATUS",
                }
            }
        ),
        encoding="utf-8",
    )

    df = pl.DataFrame(
        {
            "ENTRY_DATE": ["2025-10-01T08:00:00"],
            "DELIVER DATE": ["2025-10-02T12:00:00"],
            "RECEIVER MODE": ["COD"],
            "COD": [150.0],
            "status": ["Delivered"],
        }
    )

    prepared, picks = _prepare_ops(df, artifacts_root, run_id)

    assert picks["created_ts"] == "ENTRY_DATE"
    assert picks["delivered_ts"] == "DELIVER_DATE"
    assert picks["receiver_mode"] == "RECEIVER_MODE"
    assert picks["cod_amount"] in {"COD", "COD_AMOUNT"}
    assert prepared["ts_created"].dtype.time_zone == "Asia/Riyadh"
    assert prepared["ts_delivered"].dtype.time_zone == "Asia/Riyadh"
    assert "lead_time_hours" in prepared.columns
