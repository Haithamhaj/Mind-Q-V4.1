from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from backend.src.app.services.stage_07_timeseries import impl as stage07_timeseries

try:  # pragma: no cover - optional dependency under test
    from statsforecast import StatsForecast  # type: ignore
    from statsforecast.models import AutoETS  # type: ignore
except Exception:  # pragma: no cover - dependency guard
    StatsForecast = None
    AutoETS = None


@pytest.mark.skipif(StatsForecast is None or AutoETS is None, reason="StatsForecast is not installed")
def test_stage07_templates_include_method(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    horizon = 7
    segments = ["series_a", "series_b"]
    base_dates = pd.date_range("2024-01-01", periods=60, freq="D")
    records: List[Dict[str, Any]] = []
    for idx, segment in enumerate(segments):
        noise = np.random.default_rng(idx).normal(0, 0.1, size=len(base_dates))
        values = 20 + idx * 2 + np.sin(np.linspace(0, 4 * np.pi, len(base_dates))) + noise
        for ts, value in zip(base_dates, values):
            records.append({"segment": segment, "timestamp": ts, "value": value})

    frame = pd.DataFrame(records)
    data_path = tmp_path / "timeseries.parquet"
    frame.to_parquet(data_path)

    monkeypatch.setenv("USE_EXT_FORECAST_TEMPLATES", "1")
    result = stage07_timeseries.run(
        "run-forecast",
        {
            "timeseries_path": data_path.as_posix(),
            "horizon": horizon,
            "segment_column": "segment",
            "timestamp_column": "timestamp",
            "value_column": "value",
        },
        {"artifacts_root": tmp_path.as_posix()},
    )

    assert result["method"] in {"baseline", "adapter"}
    templates_path = Path(result["outputs"]["forecast_templates"])
    payload = json.loads(templates_path.read_text(encoding="utf-8"))
    assert payload["method"] == result["method"]
    assert payload["rows"] == horizon * len(segments)

    forecasts = payload["forecasts"]
    assert len(forecasts) == horizon * len(segments)
    assert {entry["segment"] for entry in forecasts} == set(segments)

    log_path = Path(result["outputs"]["logs"])
    log_lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(entry.get("event") == "forecast_templates" and entry.get("method") == result["method"] for entry in log_lines)