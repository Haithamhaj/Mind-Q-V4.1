"""Correlation Analysis Engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import polars as pl


def run_correlation_analysis(
    df: pl.DataFrame,
    output_dir: Path,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    حساب مصفوفة الارتباطات بين الأعمدة العددية.
    
    يقوم بـ:
    - استخراج جميع الأعمدة العددية
    - حساب Pearson correlation لكل زوج
    - الاحتفاظ بالارتباطات القوية فقط (|r| >= threshold)
    - ترتيب حسب القوة
    """
    
    # استخراج الأعمدة العددية
    numeric_cols = [
        c for c in df.columns 
        if df[c].dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]
    ]
    
    if len(numeric_cols) < 2:
        return {
            "status": "skipped",
            "reason": f"insufficient_numeric_columns (need 2+, found {len(numeric_cols)})"
        }
    
    # حد أدنى لقوة الارتباط
    threshold = config.get("min_correlation", 0.25)
    
    # حساب الارتباطات
    correlations: List[Dict[str, Any]] = []
    
    for i, col1 in enumerate(numeric_cols):
        for col2 in numeric_cols[i + 1:]:
            try:
                # Polars correlation (Pearson)
                corr_result = df.select([
                    pl.corr(col1, col2).alias("corr")
                ])
                
                corr_val = corr_result.item()
                
                if corr_val is not None and abs(corr_val) >= threshold:
                    # تحديد قوة الارتباط
                    abs_corr = abs(corr_val)
                    if abs_corr >= 0.7:
                        strength = "strong"
                    elif abs_corr >= 0.5:
                        strength = "moderate"
                    else:
                        strength = "weak"
                    
                    # تحديد الاتجاه
                    direction = "positive" if corr_val > 0 else "negative"
                    
                    correlations.append({
                        "col1": col1,
                        "col2": col2,
                        "correlation": round(float(corr_val), 4),
                        "abs_correlation": round(abs_corr, 4),
                        "strength": strength,
                        "direction": direction
                    })
            
            except Exception:
                # تخطي إذا فشل الحساب (مثلاً كل القيم null)
                continue
    
    # ترتيب حسب القوة (absolute correlation)
    correlations.sort(key=lambda x: x["abs_correlation"], reverse=True)
    
    # أخذ أعلى N ارتباط
    top_n = config.get("top_n", 15)
    top_correlations = correlations[:top_n]
    
    # إنشاء الملخص
    summary = {
        "total_pairs_analyzed": len(numeric_cols) * (len(numeric_cols) - 1) // 2,
        "significant_correlations": len(correlations),
        "threshold": threshold,
        "numeric_columns": numeric_cols,
        "strong_correlations": sum(1 for c in correlations if c["strength"] == "strong"),
        "moderate_correlations": sum(1 for c in correlations if c["strength"] == "moderate"),
        "weak_correlations": sum(1 for c in correlations if c["strength"] == "weak"),
        "top_correlations": top_correlations
    }
    
    # حفظ النتائج
    output_file = output_dir / "correlation_matrix.json"
    output_file.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    return {
        "status": "completed",
        "output_file": output_file.as_posix(),
        "summary": {
            "total_pairs": summary["total_pairs_analyzed"],
            "significant": summary["significant_correlations"],
            "strong": summary["strong_correlations"]
        }
    }
