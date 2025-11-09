from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence

import pytest
from zoneinfo import ZoneInfo

pl = pytest.importorskip("polars")  # type: ignore


def _build_rows(
    n_rows: int,
    *,
    cod_values: Optional[Sequence[float]] = None,
    status_cycle: Optional[Sequence[str]] = None,
    receiver_modes: Optional[Sequence[str]] = None,
) -> List[dict]:
    tz = ZoneInfo("Asia/Riyadh")
    rows: List[dict] = []
    status_cycle = status_cycle or ("DELIVERED", "IN_TRANSIT", "DELIVERED", "RETURNED")
    receiver_modes = receiver_modes or ("COD", "PREPAID")
    cod_values = cod_values or (10.0, 0.0, 25.5, 5.0)
    for idx in range(n_rows):
        pickup = datetime(2024, 1, 1, 8, 0, tzinfo=tz) + timedelta(days=idx)
        delivery = pickup + timedelta(days=idx % 3)
        rows.append(
            {
                "AWB_NO": f"AWB{idx+1:05d}",
                "ORIGIN": "DMM" if idx % 2 == 0 else "RUH",
                "DESTINATION": "RUH" if idx % 2 == 0 else "JED",
                "RECEIVER_MODE": receiver_modes[idx % len(receiver_modes)],
                "STATUS": status_cycle[idx % len(status_cycle)],
                "COD_AMOUNT": cod_values[idx % len(cod_values)],
                "PICKUP_DATE": pickup,
                "DELIVERY_DATE": delivery,
            }
        )
    return rows


def write_stage_artifacts(
    tmp_path: Path,
    run_id: str,
    *,
    n_rows: int = 6,
    cod_values: Optional[Sequence[float]] = None,
    status_cycle: Optional[Sequence[str]] = None,
    receiver_modes: Optional[Sequence[str]] = None,
    include_effect_metrics: bool = True,
    insights_override: Optional[Dict[str, Any]] = None,
    gate_override: Optional[Dict[str, Any]] = None,
    diagnostics_override: Optional[Dict[str, Any]] = None,
) -> Path:
    artifacts_root = tmp_path / "artifacts"
    stage06_dir = artifacts_root / run_id / "stage_06_standardize"
    stage08_dir = artifacts_root / run_id / "stage_08_insights"
    stage06_dir.mkdir(parents=True, exist_ok=True)
    stage08_dir.mkdir(parents=True, exist_ok=True)

    rows = _build_rows(
        n_rows,
        cod_values=cod_values,
        status_cycle=status_cycle,
        receiver_modes=receiver_modes,
    )
    clean_df = pl.DataFrame(rows, orient="row")
    clean_df = clean_df.with_columns(pl.col("PICKUP_DATE").dt.cast_time_unit("us"))
    clean_df.write_parquet((stage06_dir / "clean.parquet").as_posix())

    if insights_override is not None:
        insights_payload = insights_override
    else:
        insights_payload = {
            "run_id": run_id,
            "generated_at": datetime.now(ZoneInfo("Asia/Riyadh")).isoformat(),
            "summary": {
                "official_count": 2,
                "exploratory_count": 1,
                "n_rows": n_rows,
                "max_strength": 0.8,
                "max_confidence": 0.9,
            },
            "diagnostics": {},
            "insights": [
                {
                    "segment": "DESTINATION=RUH",
                    "strength": 0.45,
                    "confidence": 0.72,
                    "coverage": 0.8,
                    "n": n_rows // 2,
                    "window": "2024-01-01 -> 2024-01-14",
                    "relation": "DESTINATION -> DELIVERY",
                    "kpi": "DELIVERED",
                    "direction": "positive",
                    "stability_score": 0.75,
                    "bucket": "HIGH",
                    "evidence": ["stage07_source:stage07_correlations"],
                    "source": "stage07_correlations",
                    "low_signal": False,
                    "nzv_override": False,
                }
            ],
        }
        if include_effect_metrics:
            insights_payload["diagnostics"] = {
                "effect": {"max_abs": 0.62, "median_abs": 0.38},
                "confidence": {"max": 0.91, "p50": 0.72},
                "coverage": {"p90": 0.84, "median": 0.66},
                "stability": {"time": 0.88, "segment": 0.81},
                "flags": {"simpson": False, "small_n": False},
            }

    gate_payload = gate_override or {
        "status": "PASS",
        "counts": {"all": len(insights_payload.get("insights", [])), "emitted": len(insights_payload.get("insights", []))},
        "reasons": [],
        "diag": {"preflight": {"status": "PASS", "reasons": []}},
        "low_signal_candidates": 0,
    }
    diagnostics_payload = diagnostics_override or {
        "run_id": run_id,
        "time_window_days": 60,
        "counts": {"features": 1, "segments_used": 1, "pairs_tested": len(insights_payload.get("insights", [])), "low_signal": 0, "nzv_override": 0},
        "coverage": {},
        "effect": {},
        "confidence": {},
        "stability": {},
        "flags": {},
        "warnings": [],
        "sampling": {"enabled": False, "population_rows": n_rows, "sampled_rows": n_rows},
        "coverage_report": {"threshold": 0.9, "rows": n_rows, "total_columns": 0, "kept": [], "dropped": []},
        "notes": ["All signals are associative, not causal."],
    }
    quality_report_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(ZoneInfo("Asia/Riyadh")).isoformat(),
        "threshold": 0.9,
        "rows": n_rows,
        "excluded_columns": [],
    }

    (stage08_dir / "insights_report.json").write_text(json.dumps(insights_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (stage08_dir / "gate.json").write_text(json.dumps(gate_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (stage08_dir / "diagnostics.json").write_text(json.dumps(diagnostics_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (stage08_dir / "quality_report.json").write_text(json.dumps(quality_report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (stage08_dir / "insights_candidates.json").write_text(json.dumps({"candidates": insights_payload.get("insights", [])}, ensure_ascii=False, indent=2), encoding="utf-8")

    return artifacts_root


def load_impl():
    import importlib
    import sys

    project_root = Path(__file__).resolve().parents[1]
    root_str = project_root.as_posix()
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return importlib.import_module("phases.09_business_validation.impl")


def load_models():
    import importlib
    import sys

    project_root = Path(__file__).resolve().parents[1]
    root_str = project_root.as_posix()
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return importlib.import_module("phases.09_business_validation.models")
