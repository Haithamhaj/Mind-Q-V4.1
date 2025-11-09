from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

pl = pytest.importorskip("polars")  # type: ignore

from tests.p09_utils import load_impl, write_stage_artifacts


def test_p09_basic(tmp_path: Path) -> None:
    run_id = "run_basic"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=6)
    impl = load_impl()
    result = impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})

    assert result["status"] == "PASS"
    out_dir = artifacts_root / run_id / "stage_09_business_validation"

    feed_path = out_dir / "bi_feed.parquet"
    assert feed_path.exists()
    feed_df = pl.read_parquet(feed_path.as_posix())
    required_cols = [
        "entity_id",
        "ts",
        "kpi_orders_cnt",
        "kpi_cod_total",
        "eff_effect_size",
        "eff_confidence",
        "eff_stability_time_pct",
        "decision",
        "explain_key",
        "locale",
        "currency",
    ]
    for column in required_cols:
        assert column in feed_df.columns

    whitelist_path = out_dir / "bi_whitelist.jsonl"
    assert whitelist_path.exists()
    whitelist_records = [json.loads(line) for line in whitelist_path.read_text(encoding="utf-8").strip().splitlines()]
    assert whitelist_records, "whitelist should contain approved rows"
    assert all(record["decision"] == "APPROVE" for record in whitelist_records)

    validation_path = out_dir / "validation_report.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    assert validation["gate"]["status"] == "PASS"
    assert validation["bi_hints"]["time_grain"] == "day"
    assert validation["provenance"]["bi_contract_id"] == "default"

    targets_path = out_dir / "targets.json"
    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    assert "cod_rate" in targets


def test_p09_warn_on_low_signal(tmp_path: Path) -> None:
    run_id = "run_low_signal"
    insights_override = {
        "run_id": run_id,
        "generated_at": datetime.now(ZoneInfo("Asia/Riyadh")).isoformat(),
        "summary": {"official_count": 0, "exploratory_count": 1, "n_rows": 6},
        "insights": [],
    }
    gate_override = {
        "status": "WARN",
        "counts": {"all": 1, "emitted": 0},
        "reasons": ["Only low-signal fallback candidates were available; treat insights as exploratory."],
        "diag": {"preflight": {"status": "PASS", "reasons": []}},
        "low_signal_candidates": 1,
    }
    diagnostics_override = {
        "run_id": run_id,
        "time_window_days": 60,
        "counts": {"features": 0, "segments_used": 0, "pairs_tested": 0, "low_signal": 1, "nzv_override": 0},
        "coverage": {},
        "effect": {},
        "confidence": {},
        "stability": {},
        "flags": {},
        "warnings": ["Low-signal fallback candidates present; treat as exploratory signals."],
        "sampling": {"enabled": False, "population_rows": 6, "sampled_rows": 6},
        "coverage_report": {"threshold": 0.9, "rows": 6, "total_columns": 0, "kept": [], "dropped": []},
        "notes": ["All signals are associative, not causal."],
    }
    artifacts_root = write_stage_artifacts(
        tmp_path,
        run_id,
        insights_override=insights_override,
        gate_override=gate_override,
        diagnostics_override=diagnostics_override,
        include_effect_metrics=False,
    )
    impl = load_impl()
    result = impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})
    assert result["status"] == "WARN"
    out_dir = artifacts_root / run_id / "stage_09_business_validation"
    validation = json.loads((out_dir / "validation_report.json").read_text(encoding="utf-8"))
    assert validation["gate"]["status"] == "WARN"
    assert any("low-signal" in reason.lower() for reason in validation["gate"].get("reasons", []))


def test_p09_textops_context(tmp_path: Path) -> None:
    run_id = "run_textops"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=8)
    textops_dir = artifacts_root / run_id / "stage_03_5_textops"
    textops_dir.mkdir(parents=True, exist_ok=True)
    profile_payload = {
        "columns": {
            "NOTES": {
                "top_tokens": [{"t": "delay", "c": 4}, {"t": "damage", "c": 2}],
            }
        }
    }
    (textops_dir / "text_profile.json").write_text(json.dumps(profile_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    sentiment_df = pl.DataFrame({"sentiment_score": [0.5, -0.6, -0.4, 0.2]})
    sentiment_df.write_parquet((textops_dir / "sentiment_features.parquet").as_posix())
    (textops_dir / "quality_findings.json").write_text(json.dumps({"warnings": ["Customers mention delays"]}, ensure_ascii=False, indent=2), encoding="utf-8")

    impl = load_impl()
    impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})

    data_health = json.loads((artifacts_root / run_id / "stage_09_business_validation" / "data_health.json").read_text(encoding="utf-8"))
    assert data_health.get("text_ops", {}).get("top_tokens")

    ops_actions = json.loads((artifacts_root / run_id / "stage_09_business_validation" / "ops_actions.json").read_text(encoding="utf-8"))
    assert any(action.get("entity_id") == "textops::sentiment" for action in ops_actions)
