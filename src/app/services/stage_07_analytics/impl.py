from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import polars as pl  # type: ignore
import polars.selectors as cs  # type: ignore

RUN_TS_KEY = "generated_at"
SEGMENT_CANDIDATES: Sequence[str] = (
    "client_id",
    "CLIENT_ID",
    "Account_NO",
    "ACCOUNT_NO",
    "DESTINATION",
    "DESTINATION_CITY",
    "city",
    "CITY",
    "ZONE",
)
ID_CANDIDATES: Sequence[str] = (
    "order_id",
    "ORDER_ID",
    "entity_id",
    "shipment_id",
    "AWB_NO",
)
VALUE_CANDIDATES: Sequence[str] = (
    "cod_amount",
    "COD_AMOUNT",
    "kpi_cod_avg",
    "lead_time_hours",
    "weight_kg",
    "ON_WEIGHT",
)


def _ensure_dirs(artifacts_root: Path, run_id: str) -> Dict[str, Path]:
    analytics_root = artifacts_root / run_id / "phase_07_analytics"
    profile_dir = analytics_root / "profile"
    outputs_dir = analytics_root / "outputs"
    analytics_root.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return {"root": analytics_root, "profile": profile_dir, "outputs": outputs_dir}


def _resolve_features_path(inputs: Dict[str, Any]) -> Path:
    features = inputs.get("features")
    if not features:
        raise ValueError("Stage 07 analytics requires `features` input from Stage 06.")
    path = Path(str(features)).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Stage 06 features not found: {path}")
    return path


def _load_dataset(path: Path) -> pl.DataFrame:
    if path.suffix.lower() == ".csv":
        return pl.read_csv(path.as_posix())
    return pl.read_parquet(path.as_posix())


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _numeric_columns(df: pl.DataFrame) -> List[str]:
    numeric_df = df.select(cs.numeric())
    return list(numeric_df.columns)


def _pick_column(candidates: Sequence[str], available: Sequence[str]) -> Optional[str]:
    lookup = set(available)
    for name in candidates:
        if name in lookup:
            return name
    return None


def _pick_categorical_column(df: pl.DataFrame) -> Optional[str]:
    candidate = _pick_column(SEGMENT_CANDIDATES, df.columns)
    if candidate:
        return candidate
    for name, dtype in df.schema.items():
        if dtype == pl.Utf8:
            unique = df.select(pl.col(name).n_unique()).item()
            if 1 < unique <= 50:
                return name
    return None


def _pick_metric_column(df: pl.DataFrame) -> Optional[str]:
    candidate = _pick_column(VALUE_CANDIDATES, df.columns)
    if candidate:
        return candidate
    numeric_cols = _numeric_columns(df)
    return numeric_cols[0] if numeric_cols else None


def _build_dq_summary(df: pl.DataFrame, run_id: str) -> Dict[str, Any]:
    n_rows = df.height
    n_cols = df.width
    total_cells = max(1, n_rows * n_cols)
    null_total = 0
    for column in df.columns:
        nulls = df.select(pl.col(column).is_null().sum()).item()
        null_total += int(nulls or 0)
    null_ratio = round((null_total / total_cells) * 100, 2)
    rules = [
        {
            "rule_id": "row_count_positive",
            "rule_name": "Dataset contains rows",
            "passed": n_rows > 0,
            "severity": "LOW" if n_rows > 0 else "HIGH",
            "details": {"rows": n_rows},
        },
        {
            "rule_id": "null_coverage_control",
            "rule_name": "Overall null coverage under 50%",
            "passed": null_ratio < 50.0,
            "severity": "MEDIUM",
            "details": {"null_pct": null_ratio},
        },
    ]
    failed = sum(1 for rule in rules if not rule["passed"])
    return {
        "run_id": run_id,
        RUN_TS_KEY: datetime.now(timezone.utc).isoformat(),
        "total_rows": n_rows,
        "total_columns": n_cols,
        "total_rules": len(rules),
        "passed": len(rules) - failed,
        "failed": failed,
        "critical_failures": 0 if failed == 0 else failed,
        "high_failures": 0,
        "rules": rules,
    }


def _build_correlation_payload(df: pl.DataFrame) -> Dict[str, Any]:
    numeric_cols = _numeric_columns(df)
    if len(numeric_cols) < 2:
        return {"top_correlations": [], RUN_TS_KEY: datetime.now(timezone.utc).isoformat()}
    numeric_df = df.select(numeric_cols)
    corr_matrix = numeric_df.corr()
    matrix = corr_matrix.to_numpy().tolist()
    correlations: List[Dict[str, Any]] = []
    for i, col_a in enumerate(numeric_cols):
        for j in range(i + 1, len(numeric_cols)):
            col_b = numeric_cols[j]
            corr_value = matrix[i][j]
            if corr_value is None:
                continue
            correlations.append(
                {
                    "col1": col_a,
                    "col2": col_b,
                    "correlation": round(float(corr_value), 4),
                    "abs_correlation": abs(float(corr_value)),
                    "direction": "positive" if corr_value >= 0 else "negative",
                }
            )
    correlations.sort(key=lambda entry: entry["abs_correlation"], reverse=True)
    return {
        RUN_TS_KEY: datetime.now(timezone.utc).isoformat(),
        "top_correlations": correlations[:25],
        "total_pairs": len(correlations),
    }


def _build_cluster_payload(df: pl.DataFrame, segment_col: Optional[str], metric_col: Optional[str]) -> Dict[str, Any]:
    if not segment_col:
        return {"clusters": [], "segment_column": None, RUN_TS_KEY: datetime.now(timezone.utc).isoformat()}
    aggregations: List[pl.Expr] = [pl.len().alias("count")]
    if metric_col:
        aggregations.append(pl.col(metric_col).mean().alias("metric_avg"))
        aggregations.append(pl.col(metric_col).median().alias("metric_median"))
    grouped = (
        df.group_by(segment_col)
        .agg(aggregations)
        .sort("count", descending=True)
        .head(8)
    )
    total_rows = max(1, df.height)
    clusters: List[Dict[str, Any]] = []
    for idx, row in enumerate(grouped.to_dicts()):
        percentage = round((row["count"] / total_rows) * 100, 2)
        cluster_payload: Dict[str, Any] = {
            "cluster_id": idx + 1,
            "segment_value": row[segment_col],
            "count": row["count"],
            "percentage": percentage,
        }
        if metric_col:
            cluster_payload["metric_name"] = metric_col
            cluster_payload["metric_avg"] = row.get("metric_avg")
            cluster_payload["metric_median"] = row.get("metric_median")
        clusters.append(cluster_payload)
    return {
        RUN_TS_KEY: datetime.now(timezone.utc).isoformat(),
        "segment_column": segment_col,
        "clusters": clusters,
    }


def _build_anomalies_payload(
    df: pl.DataFrame, id_col: Optional[str], metric_col: Optional[str]
) -> Dict[str, Any]:
    if not (id_col and metric_col):
        return {"top_anomalies": [], RUN_TS_KEY: datetime.now(timezone.utc).isoformat()}
    metric_series = df.select(metric_col).to_series()
    mean = float(metric_series.mean() or 0)
    std = float(metric_series.std() or 0)
    if std == 0:
        std = max(1.0, mean * 0.1 or 1.0)
    threshold = mean + 2 * std
    anomaly_df = (
        df.filter(pl.col(metric_col).cast(pl.Float64) >= threshold)
        .select([id_col, metric_col])
        .sort(metric_col, descending=True)
        .head(5)
    )
    if anomaly_df.is_empty():
        anomaly_df = (
            df.select([id_col, metric_col])
            .sort(metric_col, descending=True)
            .head(5)
        )
    anomalies = [
        {
            "order_id": row.get(id_col),
            "metric_name": metric_col,
            "metric_value": row.get(metric_col),
            "features": {"z_score_threshold": threshold, "mean": mean},
        }
        for row in anomaly_df.to_dicts()
    ]
    return {RUN_TS_KEY: datetime.now(timezone.utc).isoformat(), "top_anomalies": anomalies}


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    artifacts_root = Path(config.get("artifacts_root", "artifacts")).expanduser().resolve()
    dirs = _ensure_dirs(artifacts_root, run_id)
    features_path = _resolve_features_path(inputs)

    df = _load_dataset(features_path)

    dq_summary = _build_dq_summary(df, run_id)
    segment_col = _pick_categorical_column(df)
    metric_col = _pick_metric_column(df)
    id_col = _pick_column(ID_CANDIDATES, df.columns) or segment_col

    correlation_payload = _build_correlation_payload(df)
    cluster_payload = _build_cluster_payload(df, segment_col, metric_col)
    anomalies_payload = _build_anomalies_payload(df, id_col, metric_col)

    dq_path = dirs["outputs"] / "dq_summary.json"
    corr_path = dirs["outputs"] / "correlation_matrix.json"
    cluster_path = dirs["outputs"] / "cluster_summary.json"
    anomalies_path = dirs["outputs"] / "anomalies.json"
    _write_json(dq_path, dq_summary)
    _write_json(corr_path, correlation_payload)
    _write_json(cluster_path, cluster_payload)
    _write_json(anomalies_path, anomalies_payload)

    analytics_summary = {
        "run_id": run_id,
        RUN_TS_KEY: datetime.now(timezone.utc).isoformat(),
        "dataset": features_path.as_posix(),
        "segment_column": segment_col,
        "metric_column": metric_col,
        "n_rows": df.height,
        "n_columns": df.width,
    }
    _write_json(dirs["profile"] / "analytics_summary.json", analytics_summary)

    outputs = {
        "dq_summary": dq_path.as_posix(),
        "correlation_matrix": corr_path.as_posix(),
        "cluster_summary": cluster_path.as_posix(),
        "anomalies": anomalies_path.as_posix(),
    }
    metrics = {
        "n_rows": df.height,
        "n_columns": df.width,
        "segment_column": segment_col,
        "metric_column": metric_col,
    }
    return {"run_id": run_id, "status": "READY", "outputs": outputs, "metrics": metrics}


# Public surface for importlib loader
__all__ = ["run"]
