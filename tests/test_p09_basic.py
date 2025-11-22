from __future__ import annotations

import json
import pickle
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

pl = pytest.importorskip("polars")  # type: ignore

from tests.p09_utils import load_impl, seed_rag_bundle, write_stage_artifacts


class CatalogDummyModel:
    def predict_proba(self, X):
        return [[0.0, 0.7] for _ in range(len(X))]


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
    assert (out_dir / "gate.json").exists()
    assert (out_dir / "diagnostics.json").exists()
    health_path = artifacts_root / "system_health.json"
    assert health_path.exists()
    health_payload = json.loads(health_path.read_text(encoding="utf-8"))
    assert any(event.get("type") == "ingestion_latency" for event in health_payload.get("events", []))


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


def test_p09_reports_nzv_impact(tmp_path: Path) -> None:
    run_id = "run_nzv"
    artifacts_root = write_stage_artifacts(
        tmp_path,
        run_id,
        n_rows=8,
        nzv_low_variance=["RECEIVER_MODE"],
        nzv_high_imbalance=["STATUS"],
    )
    impl = load_impl()
    impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})
    out_dir = artifacts_root / run_id / "stage_09_business_validation"
    validation = json.loads((out_dir / "validation_report.json").read_text(encoding="utf-8"))
    impact = validation.get("nzv_impact", {})
    assert any(entry.get("name") == "RECEIVER_MODE" for entry in impact.get("low_variance_ignored_columns", []))
    assert any(entry.get("name") == "STATUS" for entry in impact.get("high_imbalance_included_columns", []))
    data_health = json.loads((out_dir / "data_health.json").read_text(encoding="utf-8"))
    assert data_health.get("nzv_impact")
    gate_payload = json.loads((out_dir / "gate.json").read_text(encoding="utf-8"))
    assert gate_payload.get("nzv_impact", {}).get("low_variance_ignored_columns")
    diagnostics_payload = json.loads((out_dir / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics_payload.get("nzv_impact", {}).get("high_imbalance_included_columns")


def test_p09_inference_uses_model_catalog(tmp_path: Path) -> None:
    run_id = "run_model"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=4)
    model_path = tmp_path / "dummy_model.pkl"

    with model_path.open("wb") as handle:
        pickle.dump(CatalogDummyModel(), handle)

    catalog_path = tmp_path / "models_catalog.yml"
    catalog_payload = {
        "models": {
            "sla_breach": {
                "version": "vtest",
                "path": model_path.as_posix(),
                "target": "will_breach_sla_4h",
                "features": ["COD_AMOUNT"],
            }
        }
    }
    catalog_path.write_text(yaml.safe_dump(catalog_payload), encoding="utf-8")

    impl = load_impl()
    result = impl.run(
        run_id,
        {},
        {"artifacts_root": artifacts_root.as_posix(), "models_catalog": catalog_path.as_posix()},
    )
    out_dir = artifacts_root / run_id / "stage_09_business_validation"
    predictions_path = out_dir / "sla_breach_predictions.json"
    assert predictions_path.exists()


def test_p09_rule_failures_include_sla_clause(tmp_path: Path) -> None:
    run_id = "run_sla_clause"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=6)
    rules_dir = tmp_path / "rules_override"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rule_payload = [
        {
            "rule_id": "sla_delivery_within_12h",
            "level": "WARN",
            "type": "time_window",
            "metadata": {
                "start_column": "PICKUP_DATE",
                "end_column": "DELIVERY_DATE",
                "window_days": 0.5,
                "kpi_code": "SLA_ACHIEVED",
            },
            "message": "SLA breach detected",
        }
    ]
    (rules_dir / "sla_rules.yaml").write_text(yaml.safe_dump(rule_payload), encoding="utf-8")
    seed_rag_bundle(artifacts_root, run_id, client_id="CLIENT_001")
    impl = load_impl()
    result = impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix(), "rules_dir": rules_dir.as_posix()})
    assert result["status"] in {"WARN", "STOP", "PASS"}
    out_dir = artifacts_root / run_id / "stage_09_business_validation"
    validation = json.loads((out_dir / "validation_report.json").read_text(encoding="utf-8"))
    failures = validation.get("rule_failures", [])
    clause = next((entry.get("sla_clause") for entry in failures if entry.get("rule_id") == "sla_delivery_within_12h"), None)
    assert clause and clause.get("raw_text")
    data_health = json.loads((out_dir / "data_health.json").read_text(encoding="utf-8"))
    assert data_health.get("rag_context", {}).get("status") in {"OK", "PARTIAL", "UNAVAILABLE"}


def test_p09_missing_model_catalog_warns_and_skips_scores(tmp_path: Path) -> None:
    run_id = "run_model_missing"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=3)
    catalog_path = tmp_path / "missing_catalog.yml"
    impl = load_impl()
    result = impl.run(
        run_id,
        {},
        {"artifacts_root": artifacts_root.as_posix(), "models_catalog": catalog_path.as_posix()},
    )
    assert result["status"] == "PASS"
    out_dir = artifacts_root / run_id / "stage_09_business_validation"
    feed_path = out_dir / "bi_feed.parquet"
    feed_df = pl.read_parquet(feed_path.as_posix())
    assert "sla_breach_score" not in feed_df.columns
    predictions_path = out_dir / "sla_breach_predictions.json"
    assert not predictions_path.exists()
    validation = json.loads((out_dir / "validation_report.json").read_text(encoding="utf-8"))
    reasons = validation.get("gate", {}).get("reasons", [])
    assert any("sla_breach model not available" in reason for reason in reasons)
