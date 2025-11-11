from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend.src.app.pipeline_api import app

client = TestClient(app)


def _write_terminology(root: Path, run_id: str) -> None:
    semantic_dir = root / run_id / "stage_03_schema" / "semantic"
    semantic_dir.mkdir(parents=True, exist_ok=True)
    terminology: Dict[str, Any] = {
        "run_id": run_id,
        "columns": [
            {
                "column_id": "cod_amount",
                "original_name": "COD_AMOUNT",
                "display": {"en": "COD Amount", "ar": "مبلغ الدفع عند الاستلام"},
                "description": {"en": "Amount collected", "ar": "المبلغ المحصل"},
                "synonyms": {"en": ["cod"], "ar": ["الدفع نقداً"]},
                "tags": ["metric"],
                "is_kpi": True,
                "kpi_links": ["total_cod"],
                "value_examples": ["100", "200"],
                "dtype": "float64",
                "null_fraction": 0.05,
                "unique_count": 120,
            }
        ],
    }
    (semantic_dir / "terminology.json").write_text(json.dumps(terminology, ensure_ascii=False, indent=2), encoding="utf-8")
    (semantic_dir / "aliases.json").write_text(json.dumps({"cod": "cod_amount"}, ensure_ascii=False, indent=2), encoding="utf-8")
    (semantic_dir / "column_glossary.json").write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
    (semantic_dir / "terminology_logs.jsonl").write_text("", encoding="utf-8")


def test_schema_terminology_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = "run-terminology"
    artifacts_root = tmp_path
    (artifacts_root / run_id).mkdir(parents=True, exist_ok=True)
    _write_terminology(artifacts_root, run_id)

    monkeypatch.setenv("ARTIFACTS_ROOT", artifacts_root.as_posix())

    response = client.get(f"/v1/runs/{run_id}/schema/terminology")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["terminology"]["columns"][0]["column_id"] == "cod_amount"

    response_flat = client.get(f"/v1/runs/{run_id}/schema/terminology?format=flat")
    assert response_flat.status_code == 200
    flat_payload = response_flat.json()
    assert flat_payload["records"][0]["column_id"] == "cod_amount"
