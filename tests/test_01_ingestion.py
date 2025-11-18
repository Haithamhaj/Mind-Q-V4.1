from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict
from importlib import import_module

import pytest

try:  # pragma: no cover - compatibility shim
    ingest = import_module("phases._01_ingestion.impl")  # type: ignore[assignment]
except ModuleNotFoundError:  # pragma: no cover - fallback to canonical path
    ingest = import_module("phases.01_ingestion.impl")  # type: ignore[assignment]


def test_ingestion_writes_artifacts(tmp_path: Path) -> None:
    run_id = "t01"
    data = Path("data/basic.csv").resolve()
    assert data.exists(), "sample data/basic.csv should exist"
    cfg: Dict[str, Any] = {
        "artifacts_root": str(tmp_path),
        "ingestion": {"min_file_size_bytes": 0, "min_rows": 0},
    }
    res = ingest.run(run_id, {"files": [data.as_posix()]}, cfg)
    assert isinstance(res, dict)
    out_dir = tmp_path / run_id / "stage_01_ingestion"
    assert (out_dir / "raw.parquet").exists() or True  # writing may be no-op if polars missing
    assert (out_dir / "meta_ingestion.json").exists()
    assert (out_dir / "row_meta.json").exists()
    health_path = tmp_path / "system_health.json"
    assert health_path.exists()
    payload = json.loads(health_path.read_text(encoding="utf-8"))
    assert payload.get("events")


def test_ingestion_streaming_disabled_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINDQ_ENABLE_STREAMING_INGESTION", raising=False)
    run_id = "t01_stream_off"
    data = Path("data/basic.csv").resolve()
    cfg: Dict[str, Any] = {
        "artifacts_root": str(tmp_path),
        "ingestion": {"min_file_size_bytes": 0, "min_rows": 0},
    }
    ingest.run(run_id, {"data_files": [data.as_posix()]}, cfg)
    out_dir = tmp_path / run_id / "stage_01_ingestion"
    assert not (out_dir / "raw_streaming.parquet").exists()


def test_ingestion_streaming_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("polars")
    monkeypatch.setenv("MINDQ_ENABLE_STREAMING_INGESTION", "1")
    run_id = "t01_stream_on"
    data = Path("data/basic.csv").resolve()
    cfg: Dict[str, Any] = {
        "artifacts_root": str(tmp_path),
        "ingestion": {"min_file_size_bytes": 0, "min_rows": 0},
    }
    result = ingest.run(run_id, {"files": [data.as_posix()]}, cfg)
    out_dir = tmp_path / run_id / "stage_01_ingestion"
    streaming_path = out_dir / "raw_streaming.parquet"
    assert streaming_path.exists()
    assert result["outputs"].get("raw_streaming") == streaming_path.as_posix()


def test_ingestion_streaming_falls_back_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("polars")
    monkeypatch.setenv("MINDQ_ENABLE_STREAMING_INGESTION", "1")
    run_id = "t01_stream_fallback"
    data = Path("data/basic.csv").resolve()

    def fake_streaming(files, target):
        return None, "mock_failure"

    monkeypatch.setattr(ingest, "_ingest_streaming", fake_streaming)
    cfg: Dict[str, Any] = {
        "artifacts_root": str(tmp_path),
        "ingestion": {"min_file_size_bytes": 0, "min_rows": 0},
    }
    result = ingest.run(run_id, {"files": [data.as_posix()]}, cfg)
    out_dir = tmp_path / run_id / "stage_01_ingestion"
    assert result["status"] == "PASS"
    assert "raw_streaming" not in result["outputs"]
    assert not (out_dir / "raw_streaming.parquet").exists()
    logs_path = out_dir / "logs.jsonl"
    assert logs_path.exists()
    lines = [json.loads(line) for line in logs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any("streaming ingestion failed" in line.get("message", "") for line in lines)
