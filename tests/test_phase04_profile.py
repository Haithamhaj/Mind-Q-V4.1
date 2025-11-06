from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = BACKEND_ROOT / "phases" / "04_profile" / "impl.py"
spec = importlib.util.spec_from_file_location("stage04_impl", MODULE_PATH)
assert spec and spec.loader
stage04_impl = importlib.util.module_from_spec(spec)
sys.modules.setdefault("stage04_impl", stage04_impl)
spec.loader.exec_module(stage04_impl)  # type: ignore[arg-type]
stage04_run = stage04_impl.run


@pytest.mark.skipif(pd is None, reason="pandas is required for profiling stage test")
def test_stage04_generates_expected_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = "run-profile"
    artifacts_root = tmp_path
    stage01_dir = artifacts_root / run_id / "stage_01_ingestion"
    stage03_dir = artifacts_root / run_id / "stage_03_schema" / "semantic"
    stage01_dir.mkdir(parents=True, exist_ok=True)
    stage03_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        {
            "order_id": ["A001", "A002", "A003", "A004"],
            "cod_amount": [120.5, 98.3, 75.0, 120.5],
            "status": ["Delivered", "Delivered", "In Transit", "Delivered"],
        }
    )
    raw_path = stage01_dir / "raw.parquet"
    df.to_parquet(raw_path, index=False)

    terminology_payload = {
        "columns": [
            {
                "column_id": "order_id",
                "original_name": "order_id",
                "display": {"en": "Order ID"},
                "description": {"en": "Identifier"},
            },
            {
                "column_id": "cod_amount",
                "original_name": "cod_amount",
                "display": {"en": "COD Amount"},
                "description": {"en": "Cash on delivery"},
            },
        ]
    }
    (stage03_dir / "terminology.json").write_text(json.dumps(terminology_payload), encoding="utf-8")
    (stage03_dir / "aliases.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")

    result = stage04_run(
        run_id,
        inputs={"raw": raw_path.as_posix()},
        config={"artifacts_root": artifacts_root.as_posix()},
    )

    outputs = result["outputs"]
    profile_path = Path(outputs["profile"])
    summary_path = Path(outputs["summary"])
    distribution_path = Path(outputs["distribution"])
    enriched_path = Path(outputs["terminology_enriched"])

    assert profile_path.exists()
    assert summary_path.exists()
    assert distribution_path.exists()
    assert enriched_path.exists()

    profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile_payload["run_id"] == run_id
    assert len(profile_payload["columns"]) == len(df.columns)

    summary = pd.read_parquet(summary_path)
    assert set(summary["column"]) == {"order_id", "cod_amount", "status"}
    assert "null_fraction" in summary.columns

    enriched_payload = json.loads(enriched_path.read_text(encoding="utf-8"))
    cod_entry = next(item for item in enriched_payload["columns"] if item["column_id"] == "cod_amount")
    assert "profile" in cod_entry
