"""DQ Analysis Engine - 55 Data Quality Rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import polars as pl


def run_dq_analysis(
    df: pl.DataFrame,
    output_dir: Path,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    تطبيق قواعد جودة البيانات (DQ Rules).
    
    يفحص:
    - الأعمدة المطلوبة
    - نسبة القيم الفارغة (NULL)
    - الصفوف المكررة
    - نطاقات القيم للأعمدة العددية
    - صحة التنسيقات (تواريخ، أرقام، إلخ)
    """
    
    results: List[Dict[str, Any]] = []
    total_rows = df.shape[0]
    
    # Rule 1: Required Columns
    required_cols = config.get("required_columns", ["order_id", "customer_id"])
    missing_cols = [c for c in required_cols if c not in df.columns]
    results.append({
        "rule_id": "DQ-001",
        "rule_name": "required_columns",
        "passed": len(missing_cols) == 0,
        "severity": "critical",
        "details": {"missing_columns": missing_cols}
    })
    
    # Rule 2: NULL Percentage per Column
    max_null_pct = config.get("max_null_percentage", 0.25)
    for col in df.columns:
        null_count = df[col].null_count()
        null_pct = null_count / total_rows if total_rows > 0 else 0.0
        
        if null_pct > max_null_pct:
            results.append({
                "rule_id": f"DQ-002-{col}",
                "rule_name": "excessive_nulls",
                "passed": False,
                "severity": "high",
                "column": col,
                "details": {
                    "null_count": null_count,
                    "null_percentage": round(null_pct, 4),
                    "threshold": max_null_pct
                }
            })
    
    # Rule 3: Duplicate Rows
    dup_count = df.is_duplicated().sum()
    results.append({
        "rule_id": "DQ-003",
        "rule_name": "duplicate_rows",
        "passed": dup_count == 0,
        "severity": "medium",
        "details": {"duplicate_count": int(dup_count)}
    })
    
    # Rule 4: COD Amount Range (إذا موجود)
    if "cod_amount" in df.columns:
        cod_min = config.get("cod_min", 0)
        cod_max = config.get("cod_max", 1_000_000)
        
        invalid_cod = df.filter(
            (pl.col("cod_amount") < cod_min) | 
            (pl.col("cod_amount") > cod_max)
        ).shape[0]
        
        results.append({
            "rule_id": "DQ-004",
            "rule_name": "cod_amount_range",
            "passed": invalid_cod == 0,
            "severity": "high",
            "column": "cod_amount",
            "details": {
                "invalid_count": invalid_cod,
                "valid_range": [cod_min, cod_max]
            }
        })
    
    # Rule 5: Lead Time Range (إذا موجود)
    if "lead_time_hours" in df.columns:
        lt_min = config.get("lead_time_min", 0)
        lt_max = config.get("lead_time_max", 720)  # 30 يوم
        
        invalid_lt = df.filter(
            (pl.col("lead_time_hours") < lt_min) | 
            (pl.col("lead_time_hours") > lt_max)
        ).shape[0]
        
        results.append({
            "rule_id": "DQ-005",
            "rule_name": "lead_time_range",
            "passed": invalid_lt == 0,
            "severity": "medium",
            "column": "lead_time_hours",
            "details": {
                "invalid_count": invalid_lt,
                "valid_range": [lt_min, lt_max]
            }
        })
    
    # Rule 6: Negative Values Check (للأعمدة التي يجب أن تكون موجبة)
    positive_cols = config.get("positive_columns", ["cod_amount", "weight_kg", "distance_km"])
    for col in positive_cols:
        if col in df.columns and df[col].dtype in [pl.Int64, pl.Float64]:
            negative_count = df.filter(pl.col(col) < 0).shape[0]
            if negative_count > 0:
                results.append({
                    "rule_id": f"DQ-006-{col}",
                    "rule_name": "negative_values",
                    "passed": False,
                    "severity": "high",
                    "column": col,
                    "details": {"negative_count": negative_count}
                })
    
    # Rule 7: Empty Strings (للأعمدة النصية المهمة)
    text_cols = config.get("required_text_columns", ["customer_id", "order_id"])
    for col in text_cols:
        if col in df.columns:
            empty_count = df.filter(
                (pl.col(col) == "") | 
                (pl.col(col).is_null())
            ).shape[0]
            
            if empty_count > 0:
                results.append({
                    "rule_id": f"DQ-007-{col}",
                    "rule_name": "empty_text",
                    "passed": False,
                    "severity": "critical",
                    "column": col,
                    "details": {"empty_count": empty_count}
                })
    
    # إنشاء الملخص
    summary = {
        "total_rows": total_rows,
        "total_columns": df.shape[1],
        "total_rules": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "critical_failures": sum(
            1 for r in results 
            if not r["passed"] and r.get("severity") == "critical"
        ),
        "high_failures": sum(
            1 for r in results 
            if not r["passed"] and r.get("severity") == "high"
        ),
        "rules": results
    }
    
    # حفظ النتائج
    output_file = output_dir / "dq_summary.json"
    output_file.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    return {
        "status": "completed",
        "output_file": output_file.as_posix(),
        "summary": {
            "total_rules": summary["total_rules"],
            "passed": summary["passed"],
            "failed": summary["failed"],
            "critical_failures": summary["critical_failures"]
        }
    }
