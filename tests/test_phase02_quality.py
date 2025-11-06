from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_phase02():
    base = PROJECT_ROOT / "phases" / "02_quality" / "impl.py"
    spec = importlib.util.spec_from_file_location("phases.02_quality.impl", base.as_posix())
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load phase 02 implementation")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "phases.02_quality"
    spec.loader.exec_module(module)
    return module


schema_mod = _load_phase02()


def _write_baseline(root: Path, run_id: str, df: pd.DataFrame) -> None:
    payload = {
        "run_id": run_id,
        "n_rows": len(df),
        "n_cols": len(df.columns),
        "schema_hash": schema_mod._schema_hash(list(df.columns)),  # type: ignore[attr-defined]
    }
    path = root / run_id / "baselines.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_phase(tmp_path: Path, run_id: str, df: pd.DataFrame) -> Dict[str, Any]:
    raw_path = tmp_path / f"{run_id}_raw.parquet"
    df.to_parquet(raw_path, index=False)
    _write_baseline(tmp_path, run_id, df)
    cfg: Dict[str, Any] = {"artifacts_root": str(tmp_path)}
    result = schema_mod.run(run_id, {"raw": raw_path.as_posix()}, cfg)
    return result


def test_quality_stage_writes_overview_and_shape_guard(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "ORDER_ID": ["o1", "o2", "o3", "o4"],
            "WEIGHT": [10.0, 11.5, None, 9.8],
            "CREATED_AT": pd.date_range("2024-01-01", periods=4, tz="Asia/Riyadh"),
            "NOTES": ["ok", "مرحبا", None, "all good"],
        }
    )

    result = _run_phase(tmp_path, "run_quality", df)
    outputs = result["outputs"]

    overview_path = Path(outputs["quality_overview"])
    shape_path = Path(outputs["shape_guard"])
    assert overview_path.exists()
    assert shape_path.exists()

    overview = json.loads(overview_path.read_text(encoding="utf-8"))
    assert overview["issues_total"] >= 1
    shape = json.loads(shape_path.read_text(encoding="utf-8"))
    assert shape["rows"]["current"] == len(df)
