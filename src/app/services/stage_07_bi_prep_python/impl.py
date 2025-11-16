"""Stage 07 BI prep implemented entirely in Python (replaces the KNIME bridge)."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # Optional dependency used when summarizing parquet shapes
    import pyarrow.parquet as pq  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pq = None  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = PROJECT_ROOT / "backend"
ANALYTICS_MODULE = "backend.src.app.services.stage_07_analytics.impl"
EXPORT_SUFFIXES = {".csv", ".json", ".parquet"}
_MODE_CONFIG_KEYS: Tuple[str, ...] = ("bi_prep_mode", "mode", "knime_mode")
_MODE_ENV_KEYS: Tuple[str, ...] = (
    "MINDQ_BI_PREP_MODE",
    "BI_PREP_MODE",
    "MINDQ_KNIME_MODE",
    "KNIME_PIPELINE_MODE",
)


def _normalize_mode(value: Optional[Any]) -> str:
    if value is None:
        return "auto"
    text = str(value).strip().lower()
    if text in {"auto", "yes", "y", "1", "true", "enable", "enabled"}:
        return "auto"
    if text in {"skip", "no", "n", "0", "false", "disable", "disabled"}:
        return "skip"
    return "auto"


def _resolve_mode(config: Dict[str, Any]) -> str:
    for key in _MODE_CONFIG_KEYS:
        if key in config:
            return _normalize_mode(config[key])

    for env_key in _MODE_ENV_KEYS:
        env_value = os.getenv(env_key)
        if env_value:
            return _normalize_mode(env_value)

    if config.get("auto_approve") is True:
        return "auto"
    if config.get("auto_skip") is True:
        return "skip"
    return "auto"


def resolve_mode(config: Dict[str, Any]) -> str:
    """Public helper retained for backwards compatibility with the pipeline."""

    return _resolve_mode(config)


def _copy_file(src: Optional[Path], dest: Path) -> Optional[str]:
    if not src:
        return None
    try:
        src = src.expanduser().resolve()
    except FileNotFoundError:
        return None
    if not src.exists():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest.as_posix()


def _load_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    try:
        with path.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except Exception:
        return None


def _load_json_any(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parquet_overview(path: Path) -> Tuple[Optional[int], Optional[int]]:
    if pq is None or not path.exists():
        return None, None
    try:
        parquet_file = pq.ParquetFile(path.as_posix())
        rows = parquet_file.metadata.num_rows if parquet_file.metadata else None
        cols = len(parquet_file.schema.names)
        return rows, cols
    except Exception:
        return None, None


def _build_layer2_candidate(stage075_dir: Path, run_id: str) -> Dict[str, Any]:
    variance_path = stage075_dir / "variance_analysis.json"
    comparative_path = stage075_dir / "comparative_summary.json"
    heatmap_path = stage075_dir / "heatmap_matrix.json"

    variance_payload = _load_json_any(variance_path) if variance_path.exists() else None
    comparative_payload = _load_json_any(comparative_path) if comparative_path.exists() else None
    heatmap_payload = _load_json_any(heatmap_path) if heatmap_path.exists() else None

    generated_at = datetime.now(timezone.utc).isoformat()
    sources = {
        "variance": variance_path.as_posix() if variance_path.exists() else None,
        "comparative": comparative_path.as_posix() if comparative_path.exists() else None,
        "heatmap": heatmap_path.as_posix() if heatmap_path.exists() else None,
    }

    return {
        "run_id": run_id,
        "generated_at": generated_at,
        "sources": sources,
        "variance": variance_payload,
        "comparative": comparative_payload,
        "heatmap": heatmap_payload,
    }


def _safe_git_info() -> Tuple[Optional[str], Optional[str]]:
    sha: Optional[str] = None
    branch: Optional[str] = None
    try:
        sha = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL, text=True
            )
            .strip()
            or None
        )
    except Exception:
        sha = None
    try:
        branch = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL, text=True
            )
            .strip()
            or None
        )
    except Exception:
        branch = None
    return sha, branch


def _analytics_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "features",
        "schema",
        "kpis",
        "readiness_report",
        "decision_manifest",
        "feature_report",
    )
    payload: Dict[str, Any] = {}
    for key in keys:
        value = inputs.get(key)
        if value:
            payload[key] = value
    return payload


def _run_python_analytics(
    run_id: str,
    inputs: Dict[str, Any],
    config: Dict[str, Any],
    artifacts_root: Path,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        module = importlib.import_module(ANALYTICS_MODULE)
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"analytics_import_error: {exc}"

    run_fn = getattr(module, "run", None)
    if not callable(run_fn):  # pragma: no cover - defensive
        return None, "analytics_run_not_callable"

    analytics_inputs = _analytics_inputs(inputs)
    analytics_config = dict(config)
    analytics_config.setdefault("artifacts_root", artifacts_root.as_posix())
    try:
        result = run_fn(run_id, analytics_inputs, analytics_config)
    except Exception as exc:  # pragma: no cover - keep bridge resilient
        return None, f"analytics_execution_failed: {exc}"
    return result, None


def _copy_analytics_outputs(
    analytics_outputs_dir: Path,
    knime_outputs_dir: Path,
    transforms_dir: Path,
) -> Dict[str, str]:
    copied: Dict[str, str] = {}
    if not analytics_outputs_dir.exists():
        return copied
    for entry in analytics_outputs_dir.rglob("*"):
        if not entry.is_file():
            continue
        relative = entry.relative_to(analytics_outputs_dir)
        dest = knime_outputs_dir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, dest)
        copied[relative.as_posix()] = dest.as_posix()
        if entry.suffix.lower() in EXPORT_SUFFIXES:
            tx_dest = transforms_dir / relative
            tx_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, tx_dest)
    return copied


def _emit_dq_artifacts(dq_summary_path: Path, profile_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    if not dq_summary_path.exists():
        return None, None
    try:
        summary = json.loads(dq_summary_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None

    rules = summary.get("rules") or []
    normalized: List[Dict[str, Any]] = []
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        record: Dict[str, Any] = {
            "id": str(rule.get("rule_id") or f"rule_{idx+1}"),
            "title": rule.get("rule_name") or rule.get("rule_id"),
            "passed": bool(rule.get("passed", False)),
            "severity": rule.get("severity"),
            "status": "pass" if rule.get("passed") else "fail",
            "details": rule.get("details"),
        }
        if rule.get("column"):
            record["column"] = rule["column"]
        normalized.append(record)

    dq_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_rules": summary.get("total_rules"),
            "passed": summary.get("passed"),
            "failed": summary.get("failed"),
            "critical_failures": summary.get("critical_failures"),
            "high_failures": summary.get("high_failures"),
        },
        "results": normalized,
    }
    dq_report_path = profile_dir / "dq_report.json"
    dq_report_path.write_text(json.dumps(dq_report, ensure_ascii=False, indent=2), encoding="utf-8")

    coverage = {
        "summary": {
            "total_rows": summary.get("total_rows"),
            "total_columns": summary.get("total_columns"),
            "rules_evaluated": len(normalized),
            "rules_failed": summary.get("failed"),
            "critical_failures": summary.get("critical_failures"),
        }
    }
    coverage_path = profile_dir / "dq_coverage_summary.json"
    coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    return dq_report_path, coverage_path


def _bucket_from_strength(value: float) -> str:
    if value >= 0.7:
        return "HIGH"
    if value >= 0.5:
        return "MEDIUM"
    return "LOW"


def _emit_insights_artifact(
    correlation_path: Path,
    cluster_path: Path,
    anomalies_path: Path,
    profile_dir: Path,
) -> Path:
    insights: List[Dict[str, Any]] = []
    sources: Dict[str, Optional[str]] = {
        "correlations": correlation_path.as_posix() if correlation_path.exists() else None,
        "clusters": cluster_path.as_posix() if cluster_path.exists() else None,
        "anomalies": anomalies_path.as_posix() if anomalies_path.exists() else None,
    }

    if correlation_path.exists():
        try:
            corr_payload = json.loads(correlation_path.read_text(encoding="utf-8"))
        except Exception:
            corr_payload = {}
        for entry in corr_payload.get("top_correlations", [])[:20]:
            if not isinstance(entry, dict):
                continue
            abs_corr = float(entry.get("abs_correlation", 0) or 0.0)
            insights.append(
                {
                    "kpi": entry.get("col1"),
                    "feature": entry.get("col2"),
                    "strength": abs_corr,
                    "direction": entry.get("direction"),
                    "coverage": round(abs_corr * 100, 2),
                    "confidence": min(0.95, 0.6 + abs_corr * 0.4),
                    "bucket": _bucket_from_strength(abs_corr),
                    "source": "correlation",
                }
            )

    if cluster_path.exists():
        try:
            cluster_payload = json.loads(cluster_path.read_text(encoding="utf-8"))
        except Exception:
            cluster_payload = {}
        for cluster in cluster_payload.get("clusters", [])[:5]:
            if not isinstance(cluster, dict):
                continue
            insights.append(
                {
                    "kpi": "cluster",
                    "feature": f"cluster_{cluster.get('cluster_id')}",
                    "strength": float(cluster.get("percentage", 0)) / 100.0,
                    "direction": "positive",
                    "coverage": cluster.get("percentage"),
                    "confidence": 0.7,
                    "bucket": "MEDIUM",
                    "notes": {k: v for k, v in cluster.items() if k not in {"cluster_id", "percentage"}},
                    "source": "cluster",
                }
            )

    if anomalies_path.exists():
        try:
            anomalies_payload = json.loads(anomalies_path.read_text(encoding="utf-8"))
        except Exception:
            anomalies_payload = {}
        for record in anomalies_payload.get("top_anomalies", [])[:10]:
            if not isinstance(record, dict):
                continue
            insights.append(
                {
                    "kpi": "anomaly",
                    "feature": record.get("order_id") or record.get("customer_id") or "unknown",
                    "strength": 1.0,
                    "direction": "negative",
                    "coverage": 1,
                    "confidence": 0.65,
                    "bucket": "HIGH",
                    "notes": record.get("features"),
                    "source": "anomaly",
                }
            )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "insights": insights,
        "meta": {"sources": sources, "total_candidates": len(insights)},
    }
    insights_path = profile_dir / "insights_fdr.json"
    insights_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return insights_path


def _write_run_notes(
    profile_dir: Path,
    run_id: str,
    dataset_path: Path,
    analytics_status: str,
    data_rows: Optional[int],
) -> Path:
    lines = [
        f"# Stage 07 Python BI Prep :: {run_id}",
        "",
        "- Dataset: ``%s``" % dataset_path.as_posix(),
        f"- Rows inspected: {data_rows if data_rows is not None else 'unknown'}",
        f"- Analytics engine status: {analytics_status}",
        "",
        "This replaces the manual KNIME workflow and is generated automatically.",
    ]
    notes_path = profile_dir / "run_summary.md"
    notes_path.write_text("\n".join(lines), encoding="utf-8")
    return notes_path


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    artifacts_root = Path(config.get("artifacts_root", "artifacts")).expanduser().resolve()
    mode = _resolve_mode(config)

    if mode == "skip":
        return {
            "run_id": run_id,
            "status": "SKIP",
            "reason": "bi_prep_disabled",
            "meta": {"mode": mode},
        }

    features_path = Path(inputs["features"]).expanduser().resolve()
    if not features_path.exists():
        raise FileNotFoundError(f"Stage 06 features not found: {features_path}")

    layer1_path: Optional[Path] = None
    if inputs.get("layer1_dataset"):
        candidate = Path(str(inputs["layer1_dataset"])).expanduser()
        if candidate.exists():
            layer1_path = candidate.resolve()

    dataset_path = layer1_path or features_path

    schema_path = Path(inputs["schema"]).expanduser().resolve() if inputs.get("schema") else None
    kpis_path = Path(inputs["kpis"]).expanduser().resolve() if inputs.get("kpis") else None
    readiness_path = Path(inputs["readiness_report"]).expanduser().resolve() if inputs.get("readiness_report") else None
    decisions_path = Path(inputs["decision_manifest"]).expanduser().resolve() if inputs.get("decision_manifest") else None
    feature_report_path = Path(inputs["feature_report"]).expanduser().resolve() if inputs.get("feature_report") else None

    # Keep the historical phase_07_knime naming so /api/bi and legacy tooling keep working.
    bi_root = artifacts_root / run_id / "phase_07_knime"
    profile_dir = bi_root / "profile"
    outputs_dir = bi_root / "outputs"
    transforms_dir = bi_root / "transforms" / "analytics"
    stage_bridge_profile_dir = artifacts_root / run_id / "stage_07_knime_bridge" / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    transforms_dir.mkdir(parents=True, exist_ok=True)
    stage_bridge_profile_dir.mkdir(parents=True, exist_ok=True)

    copied: Dict[str, Optional[str]] = {}
    copied["data"] = _copy_file(dataset_path, bi_root / "data.parquet")
    if layer1_path and layer1_path.exists() and layer1_path != features_path:
        copied["features_original"] = _copy_file(features_path, bi_root / "features_original.parquet")

    data_rows, data_cols = _parquet_overview(dataset_path)

    if not schema_path or not schema_path.exists():
        schema_fallback = (artifacts_root / run_id / "stage_03_schema" / "schema_v1.json").expanduser()
        if schema_fallback.exists():
            schema_path = schema_fallback
        else:
            default_schema = PROJECT_ROOT / "contracts" / "schema.json"
            if default_schema.exists():
                schema_path = default_schema
    if schema_path and schema_path.exists():
        copied["schema"] = _copy_file(schema_path, bi_root / "schema.json")

    if not kpis_path or not kpis_path.exists():
        fallback_kpis = BACKEND_ROOT / "contracts" / "kpis.yml"
        if fallback_kpis.exists():
            kpis_path = fallback_kpis
    if kpis_path and kpis_path.exists():
        copied["kpi_map"] = _copy_file(kpis_path, bi_root / "kpi_map.yml")

    copied["readiness_report"] = _copy_file(readiness_path, profile_dir / "readiness_report.json")
    copied["decision_manifest"] = _copy_file(decisions_path, profile_dir / "decision_manifest.json")
    copied["feature_report"] = _copy_file(feature_report_path, profile_dir / "feature_report.json")

    readiness_payload = _load_json(readiness_path)
    gate_info = (readiness_payload or {}).get("gate") if isinstance(readiness_payload, dict) else None
    key_stats = (readiness_payload or {}).get("key_stats") if isinstance(readiness_payload, dict) else None
    gate_dict = gate_info if isinstance(gate_info, dict) else {}
    key_stats_dict = key_stats if isinstance(key_stats, dict) else {}

    now = datetime.now(timezone.utc).isoformat()
    git_sha, git_branch = _safe_git_info()

    run_meta: Dict[str, Any] = {
        "run_id": run_id,
        "created_at": now,
        "workflow": "python_bi_prep",
        "git_sha": git_sha,
        "git_branch": git_branch,
        "prompt": {"mode": mode, "approved": True, "timestamp": now},
        "inputs": {
            "dataset_source": dataset_path.as_posix(),
            "features_source": features_path.as_posix(),
            "layer1_dataset": layer1_path.as_posix() if layer1_path else None,
            "schema_source": schema_path.as_posix() if schema_path else None,
            "kpi_source": kpis_path.as_posix() if kpis_path else None,
        },
        "artifacts": {
            "input_dir": bi_root.as_posix() + "/",
            "data": copied.get("data"),
            "schema": copied.get("schema"),
            "kpi_map": copied.get("kpi_map"),
            "profile": profile_dir.as_posix() + "/",
        },
        "quality_gates": {
            "status": gate_dict.get("status"),
            "reasons": gate_dict.get("reasons"),
            "n_rows": key_stats_dict.get("n_rows"),
            "n_cols": key_stats_dict.get("n_cols"),
        },
    }
    run_meta_path = bi_root / "run_meta.json"
    run_meta_path.write_text(json.dumps(run_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    copied["run_meta"] = run_meta_path.as_posix()

    stage075_dir = artifacts_root / run_id / "stage_07_5_feature_report"
    layer2_candidate = _build_layer2_candidate(stage075_dir, run_id)
    candidate_path = profile_dir / "layer2_candidate.json"
    if layer2_candidate:
        candidate_payload = layer2_candidate
    else:
        candidate_payload = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": {"variance": None, "comparative": None, "heatmap": None},
            "variance": None,
            "comparative": None,
            "heatmap": None,
            "notes": ["No layer2 data available from stage_07_5_feature_report"],
        }
    candidate_path.write_text(json.dumps(candidate_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    copied["layer2_candidate"] = candidate_path.as_posix()

    analytics_root = artifacts_root / run_id / "phase_07_analytics"
    analytics_profile_src = analytics_root / "profile"
    analytics_outputs_src = analytics_root / "outputs"
    python_analytics_cfg = dict(config.get("python_analytics") or {})
    analytics_enabled = python_analytics_cfg.pop("enabled", True)
    reuse_existing = python_analytics_cfg.pop("reuse_existing", True)
    analytics_force = python_analytics_cfg.pop("force", False) or python_analytics_cfg.pop("force_run", False)
    analytics_result: Optional[Dict[str, Any]] = None
    analytics_error: Optional[str] = None

    use_existing = analytics_outputs_src.exists() and reuse_existing
    should_run = analytics_enabled and (analytics_force or not use_existing)
    analytics_status = "SKIPPED"

    if should_run:
        python_analytics_cfg.setdefault("artifacts_root", artifacts_root.as_posix())
        analytics_result, analytics_error = _run_python_analytics(run_id, inputs, python_analytics_cfg, artifacts_root)
        if analytics_result:
            analytics_status = analytics_result.get("status") or "SUCCESS"
            outputs_info = analytics_result.get("outputs") or {}
            analytics_root = Path(outputs_info.get("analytics_root", analytics_root.as_posix())).expanduser()
            analytics_profile_src = Path(outputs_info.get("profile_dir", (analytics_root / "profile").as_posix()))
            analytics_outputs_src = Path(outputs_info.get("outputs_dir", (analytics_root / "outputs").as_posix()))
        else:
            analytics_status = "ERROR"
    elif analytics_outputs_src.exists():
        analytics_status = "REUSED"
    else:
        analytics_status = "SKIPPED"

    analytics_summary_path = analytics_profile_src / "analytics_summary.json"
    summary_copy = _copy_file(analytics_summary_path, profile_dir / "analytics_summary.json")
    if summary_copy:
        copied["analytics_summary"] = summary_copy

    analytics_copies = _copy_analytics_outputs(analytics_outputs_src, outputs_dir, transforms_dir)

    dq_report_path, dq_coverage_path = _emit_dq_artifacts(analytics_outputs_src / "dq_summary.json", profile_dir)
    if dq_report_path:
        copied["dq_report"] = dq_report_path.as_posix()
    if dq_coverage_path:
        copied["dq_coverage_summary"] = dq_coverage_path.as_posix()

    insights_path = _emit_insights_artifact(
        analytics_outputs_src / "correlation_matrix.json",
        analytics_outputs_src / "cluster_summary.json",
        analytics_outputs_src / "anomalies.json",
        profile_dir,
    )
    copied["insights_fdr"] = insights_path.as_posix()

    notes_path = _write_run_notes(profile_dir, run_id, dataset_path, analytics_status, data_rows)
    copied["run_summary"] = notes_path.as_posix()

    copied_snapshot = {key: value for key, value in copied.items() if value}
    bridge_summary = {
        "run_id": run_id,
        "generated_at": now,
        "mode": mode,
        "git_sha": git_sha,
        "git_branch": git_branch,
        "dataset_source": dataset_path.as_posix(),
        "features_source": features_path.as_posix(),
        "dataset_origin": "layer1_dataset" if layer1_path else "features",
        "layer1_dataset": layer1_path.as_posix() if layer1_path else None,
        "data_rows": data_rows,
        "data_columns": data_cols,
        "copied": copied_snapshot,
        "python_analytics": {
            "status": analytics_status,
            "files_copied": len(analytics_copies),
            "error": analytics_error,
        },
    }
    if analytics_result and isinstance(analytics_result.get("summary"), dict):
        summary = analytics_result["summary"]
        analytics_section = bridge_summary["python_analytics"]
        analytics_section.update(
            {
                "total_rows": summary.get("total_rows"),
                "total_columns": summary.get("total_columns"),
                "completed": summary.get("analyses_completed"),
                "skipped": summary.get("analyses_skipped"),
                "failed": summary.get("analyses_failed"),
            }
        )

    bridge_summary_path = profile_dir / "bridge_summary.json"
    bridge_summary_path.write_text(json.dumps(bridge_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    copied["bridge_summary"] = bridge_summary_path.as_posix()

    for filename in ("bridge_summary.json", "layer2_candidate.json", "feature_report.json"):
        src = profile_dir / filename
        if src.exists():
            dest = stage_bridge_profile_dir / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    outputs = {key: value for key, value in copied.items() if value}

    stage_layer2_path = stage_bridge_profile_dir / "layer2_candidate.json"
    if stage_layer2_path.exists():
        outputs["layer2_candidate"] = stage_layer2_path.as_posix()
    stage_bridge_summary_path = stage_bridge_profile_dir / "bridge_summary.json"
    if stage_bridge_summary_path.exists():
        outputs["bridge_summary"] = stage_bridge_summary_path.as_posix()
    stage_feature_report_path = stage_bridge_profile_dir / "feature_report.json"
    if stage_feature_report_path.exists():
        outputs["feature_report"] = stage_feature_report_path.as_posix()

    required_keys = ("data", "layer2_candidate", "bridge_summary")
    missing_required = [key for key in required_keys if key not in outputs]
    status = "PASS"
    if missing_required or analytics_status == "ERROR":
        status = "WARN"

    metrics: Dict[str, Any] = {
        "mode": mode,
        "dataset_source": dataset_path.as_posix(),
        "dataset_origin": "layer1_dataset" if layer1_path else "features",
        "data_rows": data_rows,
        "data_columns": data_cols,
        "python_analytics": analytics_status,
        "analytics_files_copied": len(analytics_copies),
        "copied_files": len(outputs),
    }
    if analytics_error:
        metrics["python_analytics_error"] = analytics_error
    if analytics_result and isinstance(analytics_result.get("summary"), dict):
        summary_data = analytics_result["summary"]
        metrics["analytics_completed"] = len(summary_data.get("analyses_completed", []))
        metrics["analytics_skipped"] = len(summary_data.get("analyses_skipped", []))
        metrics["analytics_failed"] = len(summary_data.get("analyses_failed", []))

    return {
        "run_id": run_id,
        "status": status,
        "outputs": outputs,
        "metrics": metrics,
    }


__all__ = ["run", "resolve_mode"]
