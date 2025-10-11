from __future__ import annotations
from typing import Any, Dict
import os, json

try:
    import polars as pl  # type: ignore
except Exception:
    pl = None  # type: ignore


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    artifacts_root = str((config or {}).get("artifacts_root", "artifacts"))
    out_dir = os.path.join(artifacts_root, run_id, "stage_06_feature_eng")
    os.makedirs(out_dir, exist_ok=True)
    raw = (inputs or {}).get("raw") or (inputs or {}).get("raw_uri")
    n_rows = 0
    if pl and isinstance(raw, str) and os.path.exists(raw):
        try:
            df = pl.read_parquet(raw)
            n_rows = int(df.height)
        except Exception:
            n_rows = 0
    with open(os.path.join(out_dir, "row_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"phase": "06F", "n_rows": n_rows, "source": raw}, f)
    return {
        "run_id": run_id,
        "status": "PASS",
        "outputs": {"raw": raw},
        "metrics": {"n_rows": n_rows},
        "logs_uri": os.path.join(out_dir, "logs.jsonl"),
    }
