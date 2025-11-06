from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from typing import Any, Dict

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_phase03():
    base = PROJECT_ROOT / "phases" / "03_schema" / "impl.py"
    spec = importlib.util.spec_from_file_location("phases.03_schema.impl", base.as_posix())
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load phase 03 implementation")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "phases.03_schema"
    spec.loader.exec_module(module)
    return module


schema_mod = _load_phase03()


def _write_baseline(root: Path, run_id: str, df: pd.DataFrame) -> None:
    payload = {
        "run_id": run_id,
        "n_rows": len(df),
        "n_cols": len(df.columns),
    }
    path = root / run_id / "baselines.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_phase(tmp_path: Path, run_id: str, df: pd.DataFrame, terminology_enabled: bool = False) -> Dict[str, Any]:
    raw_path = tmp_path / f"{run_id}_raw.parquet"
    df.to_parquet(raw_path, index=False)
    _write_baseline(tmp_path, run_id, df)
    config: Dict[str, Any] = {
        "artifacts_root": str(tmp_path),
        "terminology": {"enabled": terminology_enabled},
    }
    return schema_mod.run(run_id, {"raw": raw_path.as_posix()}, config)


def test_schema_stage_outputs_all_files(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "ORDER_ID": ["o1", "o2", "o3"],
            "REGION": ["Riyadh", "Jeddah", "Dammam"],
            "WEIGHT": [10.5, 11.0, 9.7],
        }
    )

    result = _run_phase(tmp_path, "run_schema", df, terminology_enabled=False)
    outputs = result["outputs"]

    expected_keys = {"raw", "schema", "terminology", "aliases", "glossary", "terminology_logs"}
    assert expected_keys.issubset(outputs.keys())

    for key in ["schema", "terminology", "aliases", "glossary", "terminology_logs"]:
        path = Path(outputs[key])
        assert path.exists(), f"{key} file should exist"
