"""Stage 07 timeseries forecast template builder."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import pandas as pd  # type: ignore

try:  # pragma: no cover - optional adapter dependency
    from statsforecast import StatsForecast  # type: ignore
    from statsforecast.models import AutoETS  # type: ignore
except Exception:  # pragma: no cover - dependency guard
    StatsForecast = None
    AutoETS = None


FLAG_TRUE_VALUES = {"1", "true", "yes", "on", "t", "y"}


@dataclass(slots=True)
class SeriesSpec:
    segment_column: str
    timestamp_column: str
    value_column: str
    frequency: Optional[str]
    horizon: int


def _is_flag_enabled(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and value.strip().lower() in FLAG_TRUE_VALUES)


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        candidate = int(float(value))
        return candidate if candidate > 0 else default
    except (TypeError, ValueError):
        return default


def _resolve_spec(inputs: Mapping[str, Any], config: Mapping[str, Any]) -> SeriesSpec:
    segment_column = str(inputs.get("segment_column") or config.get("segment_column") or "segment")
    timestamp_column = str(inputs.get("timestamp_column") or config.get("timestamp_column") or "timestamp")
    value_column = str(inputs.get("value_column") or config.get("value_column") or "value")
    frequency_raw = inputs.get("frequency") or config.get("frequency")
    frequency = str(frequency_raw) if frequency_raw else None
    horizon = _coerce_positive_int(inputs.get("horizon") or config.get("horizon"), 7)
    return SeriesSpec(
        segment_column=segment_column,
        timestamp_column=timestamp_column,
        value_column=value_column,
        frequency=frequency,
        horizon=horizon,
    )


def _load_frame(inputs: Mapping[str, Any], spec: SeriesSpec) -> pd.DataFrame:
    frame: Optional[pd.DataFrame]
    path_value = inputs.get("timeseries_path") or inputs.get("data_path") or inputs.get("frame_path")
    if path_value:
        path = Path(str(path_value)).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"timeseries payload not found: {path}")
        if path.suffix.lower() in {".parquet", ".pq"}:
            frame = pd.read_parquet(path)
        else:
            frame = pd.read_csv(path)
    else:
        payload = inputs.get("timeseries") or inputs.get("data") or inputs.get("frame")
        if isinstance(payload, pd.DataFrame):
            frame = payload.copy()
        elif isinstance(payload, Iterable):
            frame = pd.DataFrame(payload)
        else:
            raise KeyError("timeseries payload is required via 'timeseries_path' or 'timeseries'")

    required = {spec.segment_column, spec.timestamp_column, spec.value_column}
    missing = required.difference(frame.columns)
    if missing:
        raise KeyError(f"timeseries payload missing columns: {sorted(missing)}")

    cleaned = frame.copy()
    cleaned[spec.segment_column] = cleaned[spec.segment_column].astype(str)
    cleaned[spec.timestamp_column] = pd.to_datetime(cleaned[spec.timestamp_column], utc=True, errors="coerce")
    cleaned[spec.value_column] = pd.to_numeric(cleaned[spec.value_column], errors="coerce")
    cleaned = cleaned.dropna(subset=[spec.segment_column, spec.timestamp_column, spec.value_column])
    if cleaned.empty:
        raise ValueError("timeseries payload is empty after cleaning")
    return cleaned.sort_values([spec.segment_column, spec.timestamp_column]).reset_index(drop=True)


def _infer_frequency(frame: pd.DataFrame, spec: SeriesSpec) -> str:
    if spec.frequency:
        return spec.frequency
    for _, group in frame.groupby(spec.segment_column):
        if len(group) < 3:
            continue
        freq = pd.infer_freq(group[spec.timestamp_column])
        if freq:
            return str(freq)
    return "D"


def _season_length_for(freq: str, horizon: int) -> int:
    lookup = {
        "H": 24,
        "D": 7,
        "W": 4,
        "M": 12,
        "Q": 4,
        "Y": 1,
    }
    key = freq.upper() if freq else "D"
    return max(1, lookup.get(key[0], horizon))


def _generate_future_dates(last_ts: pd.Timestamp, freq: str, horizon: int) -> List[pd.Timestamp]:
    offset = pd.tseries.frequencies.to_offset(freq)
    start = last_ts + offset
    return list(pd.date_range(start=start, periods=horizon, freq=freq))


def _baseline_value(group: pd.DataFrame, spec: SeriesSpec) -> float:
    tail = group[spec.value_column].tail(5)
    candidate = tail.mean()
    if pd.isna(candidate):
        candidate = tail.dropna().iloc[-1]
    return float(candidate)


def _build_baseline_forecasts(frame: pd.DataFrame, spec: SeriesSpec, freq: str) -> List[Dict[str, Any]]:
    forecasts: List[Dict[str, Any]] = []
    for segment, group in frame.groupby(spec.segment_column):
        last_row = group.iloc[-1]
        last_ts = pd.Timestamp(last_row[spec.timestamp_column])
        future_dates = _generate_future_dates(last_ts, freq, spec.horizon)
        value = _baseline_value(group, spec)
        for ts in future_dates:
            forecasts.append(
                {
                    "segment": str(segment),
                    "timestamp": pd.Timestamp(ts).isoformat(),
                    "value": value,
                }
            )
    return forecasts


def _build_adapter_forecasts(frame: pd.DataFrame, spec: SeriesSpec, freq: str) -> List[Dict[str, Any]]:
    if StatsForecast is None or AutoETS is None:
        raise RuntimeError("StatsForecast adapter unavailable")
    sf_frame = frame.rename(
        columns={
            spec.segment_column: "unique_id",
            spec.timestamp_column: "ds",
            spec.value_column: "y",
        }
    )
    sf_frame["ds"] = pd.to_datetime(sf_frame["ds"], utc=True)
    model = StatsForecast(models=[AutoETS(season_length=_season_length_for(freq, spec.horizon))], freq=freq, n_jobs=1)
    forecast = model.forecast(df=sf_frame, h=spec.horizon)
    value_columns = [col for col in forecast.columns if col not in {"unique_id", "ds"}]
    if not value_columns:
        raise RuntimeError("StatsForecast returned no prediction columns")
    target = value_columns[0]
    results: List[Dict[str, Any]] = []
    for row in forecast.itertuples(index=False):
        ts = pd.Timestamp(getattr(row, "ds")).isoformat()
        results.append(
            {
                "segment": str(getattr(row, "unique_id")),
                "timestamp": ts,
                "value": float(getattr(row, target)),
            }
        )
    return results


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_logs(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def run(run_id: str, inputs: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
    spec = _resolve_spec(inputs, config)
    frame = _load_frame(inputs, spec)
    freq = _infer_frequency(frame, spec)
    artifacts_root = Path(config.get("artifacts_root", "artifacts")).expanduser().resolve()
    out_dir = artifacts_root / run_id / "stage_07_timeseries"
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline = _build_baseline_forecasts(frame, spec, freq)
    forecasts = baseline
    method = "baseline"
    logs: List[Dict[str, Any]] = []

    if _is_flag_enabled("USE_EXT_FORECAST_TEMPLATES"):
        try:
            adapter = _build_adapter_forecasts(frame, spec, freq)
            if adapter:
                forecasts = adapter
                method = "adapter"
        except Exception as exc:  # pragma: no cover - adapter failure guard
            logs.append({"event": "forecast_adapter_warning", "message": str(exc)})
            forecasts = baseline
            method = "baseline"

    forecasts.sort(key=lambda item: (item["segment"], item["timestamp"]))
    segments = sorted({item["segment"] for item in forecasts})
    horizon = spec.horizon
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "horizon": horizon,
        "segments": len(segments),
        "frequency": freq,
        "rows": len(forecasts),
        "columns": {
            "segment": spec.segment_column,
            "timestamp": spec.timestamp_column,
            "value": spec.value_column,
        },
        "forecasts": forecasts,
    }

    templates_path = out_dir / "forecast_templates.json"
    _write_json(templates_path, payload)

    logs.append({"event": "forecast_templates", "method": method, "horizon": horizon, "segments": len(segments)})
    log_path = out_dir / "logs.jsonl"
    _write_logs(log_path, logs)

    outputs = {
        "forecast_templates": templates_path.as_posix(),
        "logs": log_path.as_posix(),
    }
    status = "PASS" if forecasts else "WARN"
    metrics = {"rows": len(forecasts), "segments": len(segments), "horizon": horizon, "frequency": freq}
    return {"run_id": run_id, "status": status, "method": method, "outputs": outputs, "metrics": metrics}
