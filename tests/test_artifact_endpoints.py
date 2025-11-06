from __future__ import annotations

from pathlib import Path
from typing import Tuple

import json
import pytest
from fastapi.testclient import TestClient

from backend.src.app.services.pipeline_api.app import app


@pytest.fixture()
def artifacts_structure(tmp_path: Path) -> Tuple[Path, str, str]:
    root = tmp_path / "artifacts"
    run_id = "run_demo_001"
    stage_dir = root / run_id / "stage_01_ingestion"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "raw.parquet").write_bytes(b"PAR1")
    sample_json = stage_dir / "meta_ingestion.json"
    sample_json.write_text(json.dumps({"rows": 5, "columns": 3}, indent=2), encoding="utf-8")
    return root, run_id, sample_json.relative_to(root).as_posix()


def test_list_runs_and_artifacts(artifacts_structure: Tuple[Path, str, str]) -> None:
    artifacts_root, run_id, sample_path = artifacts_structure
    client = TestClient(app)

    runs_response = client.get("/v1/runs", params={"artifacts_root": artifacts_root.as_posix()})
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["runs"]
    assert any(item["run_id"] == run_id for item in runs_payload["runs"])

    artifacts_response = client.get(
        f"/v1/runs/{run_id}/artifacts", params={"artifacts_root": artifacts_root.as_posix()}
    )
    assert artifacts_response.status_code == 200
    artifacts_payload = artifacts_response.json()
    assert artifacts_payload["run_id"] == run_id
    all_files = [file for phase in artifacts_payload["phases"] for file in phase["files"]]
    assert any(file["path"] == sample_path for file in all_files)

    content_response = client.get(
        f"/v1/runs/{run_id}/artifacts/content",
        params={"artifacts_root": artifacts_root.as_posix(), "path": sample_path},
    )
    assert content_response.status_code == 200
    content_payload = content_response.json()
    assert content_payload["content_type"] == "json"
    assert content_payload["content"]["rows"] == 5
