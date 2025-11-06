"""Clustering Engine - K-Means Customer/Shipment Segmentation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import polars as pl


def run_clustering(
    df: pl.DataFrame,
    output_dir: Path,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    تجزئة العملاء/الشحنات باستخدام K-Means.
    
    يقوم بـ:
    - اختيار الميزات العددية المناسبة
    - تطبيع البيانات
    - تطبيق K-Means clustering
    - حساب إحصائيات كل cluster
    """
    
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        import numpy as np
    except ImportError:
        return {
            "status": "skipped",
            "reason": "scikit-learn not installed (pip install scikit-learn)"
        }
    
    # اختيار الميزات
    default_features = ["lead_time_hours", "cod_amount", "weight_kg", "distance_km"]
    feature_cols = config.get("features", default_features)
    available_cols = [c for c in feature_cols if c in df.columns]
    
    if len(available_cols) < 2:
        return {
            "status": "skipped",
            "reason": f"insufficient_features (need 2+, found {len(available_cols)})"
        }
    
    # تحضير البيانات (ملء القيم الفارغة بـ 0)
    df_clean = df.select(available_cols).fill_null(0)
    X = df_clean.to_numpy()
    
    # تطبيع البيانات
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # K-Means
    n_clusters = config.get("n_clusters", 4)
    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=42,
        n_init=10,
        max_iter=300
    )
    labels = kmeans.fit_predict(X_scaled)
    
    # إضافة cluster_id للـ DataFrame الأصلي
    df_with_clusters = df.with_columns([
        pl.Series("cluster_id", labels, dtype=pl.Int64)
    ])
    
    # حساب إحصائيات كل cluster
    cluster_stats: List[Dict[str, Any]] = []
    
    for i in range(n_clusters):
        cluster_df = df_with_clusters.filter(pl.col("cluster_id") == i)
        cluster_size = cluster_df.shape[0]
        
        stats: Dict[str, Any] = {
            "cluster_id": i,
            "size": cluster_size,
            "percentage": round(cluster_size / df.shape[0] * 100, 2),
        }
        
        # حساب المتوسطات للميزات المستخدمة
        for col in available_cols:
            if col in cluster_df.columns:
                mean_val = cluster_df[col].mean()
                stats[f"avg_{col}"] = round(float(mean_val), 2) if mean_val is not None else None
        
        cluster_stats.append(stats)
    
    # ترتيب clusters حسب الحجم
    cluster_stats.sort(key=lambda x: x["size"], reverse=True)
    
    # حساب Silhouette Score (إذا ممكن)
    silhouette_score = None
    try:
        from sklearn.metrics import silhouette_score as calc_silhouette
        if len(set(labels)) > 1 and len(labels) > n_clusters:
            silhouette_score = float(calc_silhouette(X_scaled, labels))
    except Exception:
        pass
    
    # إنشاء الملخص
    summary = {
        "n_clusters": n_clusters,
        "features_used": available_cols,
        "total_rows": df.shape[0],
        "silhouette_score": round(silhouette_score, 3) if silhouette_score else None,
        "clusters": cluster_stats
    }
    
    # حفظ الملخص
    summary_file = output_dir / "cluster_summary.json"
    summary_file.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    # حفظ التسميات (cluster assignments)
    assignments_file = output_dir / "cluster_assignments.parquet"
    df_with_clusters.write_parquet(assignments_file)
    
    return {
        "status": "completed",
        "output_files": {
            "summary": summary_file.as_posix(),
            "assignments": assignments_file.as_posix()
        },
        "summary": {
            "n_clusters": n_clusters,
            "silhouette_score": summary["silhouette_score"]
        }
    }
