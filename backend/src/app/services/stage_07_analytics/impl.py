"""Stage 07 Analytics - Main Implementation (Python-based KNIME alternative)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import polars as pl

from .dq_engine import run_dq_analysis
from .clustering_engine import run_clustering
from .anomaly_engine import run_anomaly_detection
from .correlation_engine import run_correlation_analysis
from .forecast_engine import run_forecast


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Python Analytics Engine - بديل كامل لـ KNIME workflows.
    
    يطبق جميع التحليلات تلقائياً:
    1. Data Quality Analysis (55+ rules)
    2. K-Means Clustering
    3. Anomaly Detection (Isolation Forest)
    4. Correlation Matrix
    5. Time Series Forecast
    
    المخرجات متوافقة 100% مع KNIME outputs لضمان عمل Stage 08.
    """
    
    print(f"\n{'='*60}")
    print(f"[Stage 07 Analytics] Starting Python Analytics Engine")
    print(f"Run ID: {run_id}")
    print(f"{'='*60}\n")
    
    # تحضير المجلدات
    artifacts_root = Path(config.get("artifacts_root", "artifacts")).expanduser().resolve()
    base = artifacts_root / run_id
    
    analytics_root = base / "phase_07_analytics"
    profile_dir = analytics_root / "profile"
    outputs_dir = analytics_root / "outputs"
    
    for directory in [analytics_root, profile_dir, outputs_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    
    # قراءة features من Stage 06
    features_path = Path(inputs["features"]).expanduser().resolve()
    if not features_path.exists():
        raise FileNotFoundError(f"Features file not found: {features_path}")
    
    print(f"[Stage 07 Analytics] Loading features from: {features_path}")
    df = pl.read_parquet(features_path)
    print(f"[Stage 07 Analytics] Loaded {df.shape[0]:,} rows × {df.shape[1]} columns\n")
    
    # حفظ نسخة محلية من البيانات
    data_path = analytics_root / "data.parquet"
    df.write_parquet(data_path)
    
    # نسخ ملفات إضافية (schema, kpi_map, profile files)
    _copy_support_files(base, analytics_root, profile_dir, inputs, config)
    
    # تشغيل جميع التحليلات
    results: Dict[str, Any] = {}
    
    # 1. Data Quality Analysis
    print("[Stage 07 Analytics] Running Data Quality Analysis...")
    try:
        dq_config = config.get("dq", {})
        dq_result = run_dq_analysis(df, outputs_dir, dq_config)
        results["dq"] = dq_result
        print(f"  ✓ DQ Analysis completed: {dq_result['summary']}")
    except Exception as e:
        print(f"  ✗ DQ Analysis failed: {e}")
        results["dq"] = {"status": "failed", "error": str(e)}
    
    # 2. Clustering
    print("\n[Stage 07 Analytics] Running K-Means Clustering...")
    try:
        clustering_config = config.get("clustering", {})
        cluster_result = run_clustering(df, outputs_dir, clustering_config)
        results["clustering"] = cluster_result
        if cluster_result["status"] == "completed":
            print(f"  ✓ Clustering completed: {cluster_result['summary']}")
        else:
            print(f"  ⊘ Clustering skipped: {cluster_result.get('reason', 'unknown')}")
    except Exception as e:
        print(f"  ✗ Clustering failed: {e}")
        results["clustering"] = {"status": "failed", "error": str(e)}
    
    # 3. Anomaly Detection
    print("\n[Stage 07 Analytics] Running Anomaly Detection...")
    try:
        anomaly_config = config.get("anomaly", {})
        anomaly_result = run_anomaly_detection(df, outputs_dir, anomaly_config)
        results["anomalies"] = anomaly_result
        if anomaly_result["status"] == "completed":
            print(f"  ✓ Anomaly Detection completed: {anomaly_result['summary']}")
        else:
            print(f"  ⊘ Anomaly Detection skipped: {anomaly_result.get('reason', 'unknown')}")
    except Exception as e:
        print(f"  ✗ Anomaly Detection failed: {e}")
        results["anomalies"] = {"status": "failed", "error": str(e)}
    
    # 4. Correlation Analysis
    print("\n[Stage 07 Analytics] Running Correlation Analysis...")
    try:
        corr_config = config.get("correlation", {})
        corr_result = run_correlation_analysis(df, outputs_dir, corr_config)
        results["correlation"] = corr_result
        if corr_result["status"] == "completed":
            print(f"  ✓ Correlation Analysis completed: {corr_result['summary']}")
        else:
            print(f"  ⊘ Correlation Analysis skipped: {corr_result.get('reason', 'unknown')}")
    except Exception as e:
        print(f"  ✗ Correlation Analysis failed: {e}")
        results["correlation"] = {"status": "failed", "error": str(e)}
    
    # 5. Forecasting (إذا توفر عمود زمني)
    print("\n[Stage 07 Analytics] Running Time Series Forecast...")
    try:
        forecast_config = config.get("forecast", {})
        forecast_result = run_forecast(df, outputs_dir, forecast_config)
        results["forecast"] = forecast_result
        if forecast_result["status"] == "completed":
            print(f"  ✓ Forecast completed: {forecast_result['summary']}")
        else:
            print(f"  ⊘ Forecast skipped: {forecast_result.get('reason', 'unknown')}")
    except Exception as e:
        print(f"  ✗ Forecast failed: {e}")
        results["forecast"] = {"status": "failed", "error": str(e)}
    
    # إنشاء analytics_summary.json
    completed_analyses = [k for k, v in results.items() if v.get("status") == "completed"]
    failed_analyses = [k for k, v in results.items() if v.get("status") == "failed"]
    skipped_analyses = [k for k, v in results.items() if v.get("status") == "skipped"]
    
    summary = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "python_analytics",
        "total_rows": df.shape[0],
        "total_columns": df.shape[1],
        "analyses_completed": completed_analyses,
        "analyses_failed": failed_analyses,
        "analyses_skipped": skipped_analyses,
        "results": {
            k: v.get("summary", v.get("reason", "unknown")) 
            for k, v in results.items()
        }
    }
    
    summary_path = profile_dir / "analytics_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    print(f"\n{'='*60}")
    print(f"[Stage 07 Analytics] Summary:")
    print(f"  ✓ Completed: {len(completed_analyses)}")
    print(f"  ✗ Failed: {len(failed_analyses)}")
    print(f"  ⊘ Skipped: {len(skipped_analyses)}")
    print(f"{'='*60}\n")
    
    return {
        "run_id": run_id,
        "status": "SUCCESS",
        "engine": "python_analytics",
        "outputs": {
            "analytics_root": analytics_root.as_posix(),
            "profile_dir": profile_dir.as_posix(),
            "outputs_dir": outputs_dir.as_posix(),
            "data_file": data_path.as_posix()
        },
        "summary": summary
    }


def _copy_support_files(
    base: Path,
    analytics_root: Path,
    profile_dir: Path,
    inputs: Dict[str, Any],
    config: Dict[str, Any]
) -> None:
    """نسخ الملفات الداعمة (schema, kpi_map, profile files)."""
    
    # Schema (من Stage 03 أو contracts/)
    schema_path = None
    if "schema" in inputs:
        schema_path = Path(inputs["schema"])
    
    if not schema_path or not schema_path.exists():
        # محاولة من stage_03
        stage03_schema = base / "stage_03_schema" / "schema_v1.json"
        if stage03_schema.exists():
            schema_path = stage03_schema
        else:
            # fallback: contracts/schema.json
            from pathlib import Path as P
            backend_root = P(__file__).resolve().parents[4]
            contracts_schema = backend_root / "contracts" / "schema.json"
            if contracts_schema.exists():
                schema_path = contracts_schema
    
    if schema_path and schema_path.exists():
        shutil.copy2(schema_path, analytics_root / "schema.json")
    
    # KPI Map
    kpi_path = None
    if "kpis" in inputs:
        kpi_path = Path(inputs["kpis"])
    
    if not kpi_path or not kpi_path.exists():
        from pathlib import Path as P
        backend_root = P(__file__).resolve().parents[4]
        contracts_kpi = backend_root / "contracts" / "kpis.yml"
        if contracts_kpi.exists():
            kpi_path = contracts_kpi
    
    if kpi_path and kpi_path.exists():
        shutil.copy2(kpi_path, analytics_root / "kpi_map.yml")
    
    # Profile files من Stage 07
    profile_files = {
        "readiness_report": "readiness_report.json",
        "decision_manifest": "decision_manifest.json",
        "feature_report": "feature_report.json"
    }
    
    for key, filename in profile_files.items():
        if key in inputs:
            src = Path(inputs[key])
            if src.exists():
                shutil.copy2(src, profile_dir / filename)
    
    # layer2_candidate من Stage 07.5 (إذا موجود)
    stage075_dir = base / "stage_07_5_feature_report"
    if stage075_dir.exists():
        _build_layer2_candidate(stage075_dir, profile_dir, base.name)


def _build_layer2_candidate(
    stage075_dir: Path,
    dest_dir: Path,
    run_id: str
) -> None:
    """بناء layer2_candidate.json من مخرجات Stage 07.5."""
    
    variance_path = stage075_dir / "variance_analysis.json"
    comparative_path = stage075_dir / "comparative_summary.json"
    heatmap_path = stage075_dir / "heatmap_matrix.json"
    
    def _load_json(p: Path) -> Any:
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    
    variance = _load_json(variance_path)
    comparative = _load_json(comparative_path)
    heatmap = _load_json(heatmap_path)
    
    if not any([variance, comparative, heatmap]):
        return
    
    layer2 = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "variance": variance_path.as_posix() if variance_path.exists() else None,
            "comparative": comparative_path.as_posix() if comparative_path.exists() else None,
            "heatmap": heatmap_path.as_posix() if heatmap_path.exists() else None
        },
        "variance": variance,
        "comparative": comparative,
        "heatmap": heatmap
    }
    
    output_path = dest_dir / "layer2_candidate.json"
    output_path.write_text(
        json.dumps(layer2, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
