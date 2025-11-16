"""Forecasting Engine - Simple Time Series Forecast."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import polars as pl


def run_forecast(
    df: pl.DataFrame,
    output_dir: Path,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    توقعات زمنية بسيطة باستخدام المتوسط المتحرك.
    
    يقوم بـ:
    - البحث عن عمود التاريخ
    - تجميع البيانات حسب اليوم
    - حساب المتوسط المتحرك
    - توقع الأيام القادمة
    """
    
    # البحث عن عمود التاريخ
    date_col: Optional[str] = None
    for col in ["order_date", "entry_date", "created_at", "ts", "date"]:
        if col in df.columns:
            date_col = col
            break
    
    if not date_col:
        return {
            "status": "skipped",
            "reason": "no_date_column_found"
        }
    
    try:
        # تحويل لـ date إذا لم يكن
        df_with_date = df.with_columns([
            pl.col(date_col).cast(pl.Date).alias("forecast_date")
        ])
    except Exception:
        return {
            "status": "skipped",
            "reason": f"cannot_parse_date_column: {date_col}"
        }
    
    # تجميع حسب التاريخ
    daily_counts = (
        df_with_date
        .group_by("forecast_date")
        .agg([
            pl.len().alias("order_count"),
            pl.col("cod_amount").sum().alias("total_cod") if "cod_amount" in df.columns else pl.lit(0).alias("total_cod")
        ])
        .sort("forecast_date")
    )
    
    if daily_counts.shape[0] < 7:
        return {
            "status": "skipped",
            "reason": "insufficient_data (need at least 7 days)"
        }
    
    # حساب المتوسط المتحرك لـ 7 أيام
    window_size = config.get("window_size", 7)
    daily_counts = daily_counts.with_columns([
        pl.col("order_count").rolling_mean(window_size=window_size).alias("ma_orders"),
        pl.col("total_cod").rolling_mean(window_size=window_size).alias("ma_cod")
    ])
    
    # استخراج آخر قيمة للمتوسط المتحرك
    last_row = daily_counts.tail(1)
    last_ma_orders = last_row["ma_orders"].item()
    last_ma_cod = last_row["ma_cod"].item()
    
    # توقع الأيام القادمة (بسيط: نفس المتوسط)
    horizon_days = config.get("horizon_days", 3)
    forecast_list = []
    
    for day in range(1, horizon_days + 1):
        forecast_list.append({
            "day": day,
            "predicted_orders": round(float(last_ma_orders), 2) if last_ma_orders else 0,
            "predicted_cod": round(float(last_ma_cod), 2) if last_ma_cod else 0
        })
    
    # إنشاء الملخص
    summary = {
        "date_column": date_col,
        "window_size": window_size,
        "horizon_days": horizon_days,
        "historical_days": daily_counts.shape[0],
        "last_moving_average": {
            "orders": round(float(last_ma_orders), 2) if last_ma_orders else 0,
            "cod": round(float(last_ma_cod), 2) if last_ma_cod else 0
        },
        "forecast": forecast_list
    }
    
    # حفظ البيانات التاريخية مع المتوسطات
    forecast_file = output_dir / "forecast.parquet"
    daily_counts.write_parquet(forecast_file)
    
    # حفظ الملخص كـ JSON
    summary_file = output_dir / "forecast_summary.json"
    summary_file.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    return {
        "status": "completed",
        "output_files": {
            "data": forecast_file.as_posix(),
            "summary": summary_file.as_posix()
        },
        "summary": {
            "horizon_days": horizon_days,
            "predicted_orders": summary["last_moving_average"]["orders"]
        }
    }
