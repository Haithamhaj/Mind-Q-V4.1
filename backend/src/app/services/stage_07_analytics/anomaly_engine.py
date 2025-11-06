"""Anomaly Detection Engine - Isolation Forest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import polars as pl


def run_anomaly_detection(
    df: pl.DataFrame,
    output_dir: Path,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    كشف الشذوذ باستخدام Isolation Forest.
    
    يقوم بـ:
    - اختيار الميزات العددية
    - تطبيق Isolation Forest
    - استخراج أهم 20 حالة شاذة
    - حفظ النتائج مع scores
    """
    
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return {
            "status": "skipped",
            "reason": "scikit-learn not installed"
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
    
    # تحضير البيانات
    df_clean = df.select(available_cols).fill_null(0)
    X = df_clean.to_numpy()
    
    # Isolation Forest
    contamination = config.get("contamination", 0.05)  # 5% شذوذ افتراضي
    iso_forest = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
        max_samples='auto'
    )
    
    # التنبؤ (-1 = anomaly, 1 = normal)
    predictions = iso_forest.fit_predict(X)
    scores = iso_forest.score_samples(X)  # أقل score = أكثر شذوذاً
    
    # إضافة النتائج للـ DataFrame
    df_with_anomalies = df.with_columns([
        pl.Series("is_anomaly", predictions == -1, dtype=pl.Boolean),
        pl.Series("anomaly_score", scores, dtype=pl.Float64)
    ])
    
    # استخراج الشذوذات فقط
    anomalies_df = df_with_anomalies.filter(pl.col("is_anomaly"))
    
    # ترتيب حسب الـ score (الأسوأ أولاً)
    top_n = config.get("top_n", 20)
    top_anomalies = anomalies_df.sort("anomaly_score").head(top_n)
    
    # تحويل لـ JSON
    anomalies_list: List[Dict[str, Any]] = []
    
    for row in top_anomalies.iter_rows(named=True):
        anomaly_record: Dict[str, Any] = {
            "anomaly_score": round(float(row["anomaly_score"]), 4),
        }
        
        # إضافة معرّفات (order_id, customer_id, etc)
        for id_col in ["order_id", "customer_id", "shipment_id"]:
            if id_col in row:
                anomaly_record[id_col] = row[id_col]
        
        # إضافة الميزات المستخدمة
        anomaly_record["features"] = {
            col: round(float(row[col]), 2) if row[col] is not None else None
            for col in available_cols
            if col in row
        }
        
        anomalies_list.append(anomaly_record)
    
    # إنشاء الملخص
    total_anomalies = int(anomalies_df.shape[0])
    summary = {
        "total_anomalies": total_anomalies,
        "contamination_rate": contamination,
        "percentage": round(total_anomalies / df.shape[0] * 100, 2) if df.shape[0] > 0 else 0,
        "features_used": available_cols,
        "top_anomalies": anomalies_list
    }
    
    # حفظ النتائج
    output_file = output_dir / "anomalies.json"
    output_file.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    return {
        "status": "completed",
        "output_file": output_file.as_posix(),
        "summary": {
            "total_anomalies": total_anomalies,
            "contamination_rate": contamination
        }
    }
