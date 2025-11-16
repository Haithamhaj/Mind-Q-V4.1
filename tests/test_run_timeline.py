from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
import importlib

pipeline_app_module = importlib.import_module("backend.src.app.services.pipeline_api.app")
pipeline_timeline_module = importlib.import_module("backend.src.app.services.pipeline_api.timeline")
from shared.phase_manifest import load_phase_manifest

build_run_timeline = getattr(pipeline_timeline_module, "build_run_timeline")
_purge_run_history = getattr(pipeline_app_module, "_purge_run_history")


def test_phase_manifest_contains_expected_entries():
    manifest = load_phase_manifest()
    # Ensure newly documented sub-phases are present
    for phase_id in [
        "03_schema",
        "06_feature_eng",
        "07_5_feature_report",
        "07_6_llm_summary",
        "07_7_business_correlations",
        "07_knime_bridge",
        "10_bi",
    ]:
        assert phase_id in manifest, f"Phase {phase_id} missing from manifest"
        definition = manifest[phase_id]
        assert definition.name.en, f"Phase {phase_id} should have English title"
        assert definition.description.ar, f"Phase {phase_id} should have Arabic description"


def test_build_run_timeline(tmp_path: Path):
    run_id = "run-demo"
    artifacts_root = tmp_path
    stage_dir = artifacts_root / run_id / "stage_03_schema"
    stage_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    finished_at = started_at + timedelta(seconds=2)

    meta_payload: Dict[str, Any] = {
        "phase_id": "03_schema",
        "stage_directory": "stage_03_schema",
        "run_id": run_id,
        "status": "PASS",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_ms": 1234,
        "inputs": {"raw": "artifacts/run-demo/stage_01_ingestion/raw.parquet"},
        "config": {"terminology": {"provider": "openai"}},
        "outputs": {"schema": "artifacts/run-demo/stage_03_schema/schema_v1.json"},
        "metrics": {"n_rows": 100},
        "context": {"terminology": {"columns": 5}},
    }
    (stage_dir / "meta.json").write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    events: List[Dict[str, Any]] = [
        {
            "ts": started_at.isoformat(),
            "run_id": run_id,
            "phase_id": "03_schema",
            "event": "phase_start",
            "level": "info",
            "message": None,
            "payload": {"inputs": {"raw": "artifacts/run-demo/stage_01_ingestion/raw.parquet"}},
        },
        {
            "ts": finished_at.isoformat(),
            "run_id": run_id,
            "phase_id": "03_schema",
            "event": "phase_end",
            "level": "info",
            "message": None,
            "payload": {"status": "PASS", "duration_ms": 1234},
        },
    ]
    events_path = stage_dir / "events.jsonl"
    with events_path.open("w", encoding="utf-8") as handle:
        for record in events:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    llm_metrics = {
        "provider": "openai",
        "model": "gpt-4o",
        "tokens_in": 123,
        "tokens_out": 456,
        "cost_estimate": 0.78,
    }
    (stage_dir / "metrics.json").write_text(json.dumps(llm_metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    timeline = build_run_timeline(run_id, artifacts_root)
    assert timeline["run_id"] == run_id
    summary = timeline["summary"]
    assert summary["status_counts"]["PASS"] >= 1
    llm_summary = summary["llm_usage"]
    assert llm_summary["total_tokens_in"] == 123
    assert llm_summary["total_tokens_out"] == 456
    assert llm_summary["phases"]
    phase_entries = [phase for phase in timeline["phases"] if phase["id"] == "03_schema"]
    assert phase_entries, "Timeline should include 03_schema entry"
    phase_entry = phase_entries[0]
    assert phase_entry["meta"]["status"] == "PASS"
    assert len(phase_entry["events"]) == 2
    assert phase_entry["llm"]["tokens_in"] == 123


def test_purge_run_history(tmp_path: Path):
    root = tmp_path
    keep = root / "run-keep"
    keep.mkdir()
    latest = root / "run-latest"
    latest.mkdir()
    old = root / "run-old"
    old.mkdir()

    _purge_run_history("run-keep", root, force=True)

    assert keep.exists()
    assert latest.exists()
    assert not old.exists()
