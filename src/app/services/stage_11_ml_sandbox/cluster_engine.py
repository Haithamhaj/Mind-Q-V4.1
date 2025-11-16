from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import joblib  # type: ignore
import numpy as np
import polars as pl  # type: ignore
from sklearn.cluster import KMeans  # type: ignore
from sklearn.preprocessing import StandardScaler  # type: ignore

BASE_FILENAME = "ml_base_orders.parquet"
CLUSTER_FILENAME = "client_clusters.parquet"
MODEL_FILENAME = "cluster_model.joblib"
METADATA_FILENAME = "cluster_metadata.json"
MIN_SHIPMENTS_FOR_CLUSTER = 5
KMEANS_RANDOM_STATE = 42

FEATURE_COLUMNS: List[str] = [
    "shipments_count",
    "avg_delivery_time_hours",
    "rto_rate",
    "sla_breach_rate",
    "avg_cod_amount",
    "total_cod_amount",
    "avg_weight_kg",
    "cod_share",
    "avg_pieces",
]


def _aggregate_features(base_df: pl.DataFrame) -> pl.DataFrame:
    bool_as_float = lambda name: pl.col(name).cast(pl.Float64, strict=False)  # noqa: E731
    return (
        base_df.group_by("client_id")
        .agg(
            [
                pl.len().alias("shipments_count"),
                pl.col("delivery_time_hours").mean().alias("avg_delivery_time_hours"),
                bool_as_float("is_rto").mean().alias("rto_rate"),
                bool_as_float("sla_breach").mean().alias("sla_breach_rate"),
                pl.col("cod_amount").mean().alias("avg_cod_amount"),
                pl.col("cod_amount").sum().alias("total_cod_amount"),
                pl.col("weight_kg").mean().alias("avg_weight_kg"),
                bool_as_float("is_cod").mean().alias("cod_share"),
                pl.col("pieces").mean().alias("avg_pieces"),
            ]
        )
        .sort("client_id")
    )


def _feature_matrix(df: pl.DataFrame) -> np.ndarray:
    if df.is_empty():
        return np.empty((0, len(FEATURE_COLUMNS)), dtype="float64")
    filled = df.select(
        [pl.col(column).cast(pl.Float64, strict=False).fill_null(0.0).alias(column) for column in FEATURE_COLUMNS]
    )
    return filled.to_numpy()


def _ensure_stage_dir(output_dir: str) -> Path:
    stage_dir = Path(output_dir).expanduser().resolve()
    stage_dir.mkdir(parents=True, exist_ok=True)
    return stage_dir


def run_client_clustering(run_id: str, output_dir: str, n_clusters: int = 5) -> Dict[str, object]:
    """
    Aggregate client-level KPIs and run clustering to derive behavior segments.
    """

    stage_dir = _ensure_stage_dir(output_dir)
    base_path = stage_dir / BASE_FILENAME
    if not base_path.exists():
        raise FileNotFoundError(f"ML base table not found for run {run_id}: {base_path}")

    base_df = pl.read_parquet(base_path.as_posix())
    if base_df.is_empty():
        client_df = pl.DataFrame(
            {"client_id": [], "cluster_id": [], **{col: [] for col in FEATURE_COLUMNS}}
        )
        cluster_path = stage_dir / CLUSTER_FILENAME
        client_df.write_parquet(cluster_path.as_posix())
        metadata = {
            "run_id": run_id,
            "n_clients_total": 0,
            "n_clients_clustered": 0,
            "n_clients_unclustered": 0,
            "n_clusters": n_clusters,
            "features_used": FEATURE_COLUMNS,
            "min_shipments": MIN_SHIPMENTS_FOR_CLUSTER,
            "model_trained": False,
            "output_path": cluster_path.as_posix(),
            "base_table": base_path.as_posix(),
        }
        (stage_dir / METADATA_FILENAME).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        joblib.dump(
            {"scaler": None, "model": None, "feature_names": FEATURE_COLUMNS, "min_shipments": MIN_SHIPMENTS_FOR_CLUSTER},
            stage_dir / MODEL_FILENAME,
        )
        return metadata

    client_features = _aggregate_features(base_df)
    eligible = client_features.filter(pl.col("shipments_count") >= MIN_SHIPMENTS_FOR_CLUSTER)
    ineligible = client_features.filter(pl.col("shipments_count") < MIN_SHIPMENTS_FOR_CLUSTER)
    eligible_count = eligible.height

    trained = eligible_count >= max(n_clusters, 2)

    if trained:
        matrix = _feature_matrix(eligible)
        scaler = StandardScaler()
        scaled = scaler.fit_transform(matrix)
        model = KMeans(n_clusters=n_clusters, random_state=KMEANS_RANDOM_STATE, n_init=10)
        labels = model.fit_predict(scaled)
        labels_series = pl.Series("cluster_id", labels.tolist(), dtype=pl.Int32)
        eligible_clustered = eligible.with_columns(labels_series)
        unclustered = ineligible.with_columns(pl.lit(-1).alias("cluster_id"))
        combined = pl.concat([eligible_clustered, unclustered], how="vertical")
    else:
        scaler = None
        model = None
        combined = client_features.with_columns(pl.lit(-1).alias("cluster_id"))

    combined = combined.sort("client_id")
    cluster_path = stage_dir / CLUSTER_FILENAME
    combined.write_parquet(cluster_path.as_posix())

    model_payload = {
        "scaler": scaler,
        "model": model,
        "feature_names": FEATURE_COLUMNS,
        "min_shipments": MIN_SHIPMENTS_FOR_CLUSTER,
    }
    joblib.dump(model_payload, stage_dir / MODEL_FILENAME)

    clustered_clients = combined.filter(pl.col("cluster_id") >= 0).height
    unclustered_clients = combined.filter(pl.col("cluster_id") < 0).height
    cluster_sizes = (
        combined.filter(pl.col("cluster_id") >= 0)
        .group_by("cluster_id")
        .len()
        .sort("cluster_id")
        .to_dict(as_series=False)
        if trained
        else {}
    )

    metadata = {
        "run_id": run_id,
        "n_clusters": n_clusters if trained else 0,
        "n_clients_total": combined.height,
        "n_clients_clustered": clustered_clients,
        "n_clients_unclustered": unclustered_clients,
        "features_used": FEATURE_COLUMNS,
        "min_shipments": MIN_SHIPMENTS_FOR_CLUSTER,
        "model_trained": trained,
        "cluster_sizes": cluster_sizes,
        "output_path": cluster_path.as_posix(),
        "base_table": base_path.as_posix(),
    }
    (stage_dir / METADATA_FILENAME).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata
