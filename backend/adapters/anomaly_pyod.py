from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, MutableMapping, Sequence

import numpy as np
import polars as pl


@dataclass(frozen=True)
class AnomalyAdapterResult:
    records: List[Dict[str, object]]
    meta: Mapping[str, object]


def score_kpi_anomalies(
    frame: pl.DataFrame,
    *,
    group_by: Sequence[str],
    metric: str,
    contamination: float = 0.05,
    min_groups: int = 3,
) -> AnomalyAdapterResult:
    """Score KPI anomalies using PyOD IsolationForest."""
    if metric not in frame.columns:
        raise ValueError(f"metric column '{metric}' not present in feature frame")

    groups = [col for col in group_by if col in frame.columns]
    if not groups:
        raise ValueError("at least one grouping column is required for anomaly adapter")

    aggregated = (
        frame.group_by(groups)
        .agg(
            [
                pl.col(metric).count().alias("_n"),
                pl.col(metric).mean().alias("_m"),
                pl.col(metric).std().fill_null(0.0).alias("_s"),
            ]
        )
        .sort(groups)
    )

    if aggregated.height < min_groups:
        raise ValueError("insufficient aggregated groups for anomaly adapter")

    stats = aggregated.select(["_m", "_s", "_n"]).to_numpy()
    stats = np.nan_to_num(stats, nan=0.0, posinf=0.0, neginf=0.0)

    try:
        from pyod.models.iforest import IForest  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("pyod>=1.1.0 is required for anomaly adapter") from exc

    contamination = float(min(max(contamination, 1e-3), 0.5))
    model = IForest(contamination=contamination, random_state=42)
    model.fit(stats)

    decision_scores = model.decision_function(stats)
    proba = model.predict_proba(stats)[:, 1]
    labels = model.predict(stats)

    if not labels.any():
        top_k = min(5, len(proba))
        threshold = np.partition(proba, -top_k)[-top_k]
        labels = (proba >= threshold).astype(int)

    z_mean = float(aggregated["_m"].mean())
    z_std = float(aggregated["_m"].std()) or 1.0

    enriched = aggregated.with_columns(
        ((pl.col("_m") - z_mean) / z_std).alias("z_score").cast(pl.Float64),
        pl.Series("anomaly_score", proba).cast(pl.Float64),
        pl.Series("decision_score", decision_scores).cast(pl.Float64),
        pl.Series("adapter_label", labels).cast(pl.Int64),
    )

    selected = enriched.filter(pl.col("adapter_label") == 1).drop("adapter_label")
    records: List[Dict[str, object]] = []
    for row in selected.iter_rows(named=True):
        payload: MutableMapping[str, object] = {}
        for key, value in row.items():
            if isinstance(value, (np.generic,)):
                payload[key] = value.item()
            else:
                payload[key] = value
        records.append(dict(payload))

    records.sort(key=lambda item: float(item.get("anomaly_score", 0.0)), reverse=True)

    meta: Dict[str, object] = {
        "model": "pyod.IForest",
        "contamination": contamination,
        "n_groups": int(aggregated.height),
        "selected": len(records),
    }
    return AnomalyAdapterResult(records=records, meta=meta)
