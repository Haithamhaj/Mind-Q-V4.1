from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import importlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple, cast

try:
    import pyarrow.parquet as pq  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pq = None  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = PROJECT_ROOT / "backend"
ANALYTICS_MODULE = "src.app.services.stage_07_analytics.impl"
DEFAULT_WORKFLOW_NAME = "phase07_feature_app.knwf"


def _normalize_mode(value: Optional[Any]) -> str:
    if value is None:
        return "prompt"
    text = str(value).strip().lower()
    if text in {"auto", "yes", "y", "1", "true", "enable", "enabled"}:
        return "auto"
    if text in {"skip", "no", "n", "0", "false", "disable", "disabled"}:
        return "skip"
    if text in {"prompt", "ask", "askme"}:
        return "prompt"
    return "prompt"


def _resolve_mode(config: Dict[str, Any]) -> str:
    for key in ("mode", "knime_mode"):
        if key in config:
            return _normalize_mode(config[key])

    for env_key in ("MINDQ_KNIME_MODE", "KNIME_PIPELINE_MODE"):
        env_value = os.getenv(env_key)
        if env_value:
            return _normalize_mode(env_value)

    if config.get("auto_approve") is True:
        return "auto"
    if config.get("auto_skip") is True:
        return "skip"
    return "prompt"


def resolve_mode(config: Dict[str, Any]) -> str:
    """Public helper so pipeline controller can detect KNIME execution mode."""
    return _resolve_mode(config)


def _prompt_user(run_id: str) -> bool:
    message = (
        f"\n[Stage 07 :: KNIME Bridge] Run '{run_id}' is ready for KNIME preparation.\n"
        "Do you want to prepare artifacts for KNIME now?\n"
        "  [Y]es  -> generate phase_07_knime inputs\n"
        "  [N]o   -> skip for this run\n"
        "Hint: set MINDQ_KNIME_MODE=auto to auto-approve or =skip to suppress this prompt.\n"
    )
    if not sys.stdin or not sys.stdin.isatty():
        print(f"{message}No interactive TTY detected. Defaulting to 'No'.")
        return False

    try:
        resp = input(message + "Your choice [y/N]: ").strip().lower()
    except EOFError:
        return False

    if not resp:
        return False
    return resp in {"y", "yes", "1", "true"}


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



def _build_layer2_candidate(stage075_dir: Path, run_id: str) -> Optional[Dict[str, Any]]:
    variance_path = stage075_dir / "variance_analysis.json"
    comparative_path = stage075_dir / "comparative_summary.json"
    heatmap_path = stage075_dir / "heatmap_matrix.json"

    variance_payload = _load_json_any(variance_path) if variance_path.exists() else None
    comparative_payload = _load_json_any(comparative_path) if comparative_path.exists() else None
    heatmap_payload = _load_json_any(heatmap_path) if heatmap_path.exists() else None

    if not any([variance_payload, comparative_payload, heatmap_payload]):
        return None

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


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    artifacts_root = Path(config.get("artifacts_root", "artifacts")).expanduser().resolve()
    mode = _resolve_mode(config)
    enable_knime_stub = bool(
        config.get("enable_knime_stub")
        or os.getenv("MINDQ_ENABLE_KNIME_STUB", "").strip().lower() in {"1", "true", "yes", "y"}
    )

    if mode == "skip":
        return {
            "run_id": run_id,
            "status": "SKIP",
            "reason": "knime_bridge_disabled",
            "meta": {"mode": mode},
        }

    approve = mode == "auto" or _prompt_user(run_id)
    if not approve:
        return {
            "run_id": run_id,
            "status": "SKIP",
            "reason": "knime_bridge_declined",
            "meta": {"mode": mode},
        }

    features_path = Path(inputs["features"]).expanduser().resolve()
    if not features_path.exists():
        raise FileNotFoundError(f"Stage 06 features not found: {features_path}")

    layer1_path: Optional[Path] = None
    layer1_input = inputs.get("layer1_dataset")
    if layer1_input:
        try:
            candidate = Path(str(layer1_input)).expanduser().resolve()
        except FileNotFoundError:
            candidate = None
        else:
            if candidate.exists():
                layer1_path = candidate

    dataset_path = layer1_path or features_path

    schema_path = Path(inputs["schema"]).expanduser().resolve() if inputs.get("schema") else None
    kpis_path = Path(inputs["kpis"]).expanduser().resolve() if inputs.get("kpis") else None
    readiness_path = Path(inputs["readiness_report"]).expanduser().resolve() if inputs.get("readiness_report") else None
    decisions_path = Path(inputs["decision_manifest"]).expanduser().resolve() if inputs.get("decision_manifest") else None
    feature_report_path = Path(inputs["feature_report"]).expanduser().resolve() if inputs.get("feature_report") else None

    knime_root = artifacts_root / run_id / "phase_07_knime"
    profile_dir = knime_root / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    copied: Dict[str, Optional[str]] = {}
    copied["data"] = _copy_file(dataset_path, knime_root / "data.parquet")
    if layer1_path and layer1_path.exists() and layer1_path != features_path:
        copied["features_original"] = _copy_file(features_path, knime_root / "features_original.parquet")

    data_rows, data_cols = _parquet_overview(dataset_path)


    # Schema preferred from stage 03; fallback to global schema.
    if not schema_path or not schema_path.exists():
        schema_fallback = (artifacts_root / run_id / "stage_03_schema" / "schema_v1.json").expanduser()
        if schema_fallback.exists():
            schema_path = schema_fallback
        else:
            default_schema = PROJECT_ROOT / "contracts" / "schema.json"
            if default_schema.exists():
                schema_path = default_schema

    if schema_path and schema_path.exists():
        copied["schema"] = _copy_file(schema_path, knime_root / "schema.json")

    if not kpis_path or not kpis_path.exists():
        fallback_kpis = BACKEND_ROOT / "contracts" / "kpis.yml"
        if fallback_kpis.exists():
            kpis_path = fallback_kpis
    if kpis_path and kpis_path.exists():
        copied["kpi_map"] = _copy_file(kpis_path, knime_root / "kpi_map.yml")

    copied["readiness_report"] = _copy_file(readiness_path, profile_dir / "readiness_report.json")
    copied["decision_manifest"] = _copy_file(decisions_path, profile_dir / "decision_manifest.json")
    copied["feature_report"] = _copy_file(feature_report_path, profile_dir / "feature_report.json")

    readiness_payload = _load_json(readiness_path)
    gate_info = (readiness_payload or {}).get("gate") if isinstance(readiness_payload, dict) else None
    key_stats = (readiness_payload or {}).get("key_stats") if isinstance(readiness_payload, dict) else None
    if isinstance(gate_info, dict):
        gate_dict = cast(Dict[str, Any], gate_info)
    else:
        gate_dict = {}
    if isinstance(key_stats, dict):
        key_stats_dict = cast(Dict[str, Any], key_stats)
    else:
        key_stats_dict = {}

    now = datetime.now(timezone.utc).isoformat()
    git_sha, git_branch = _safe_git_info()

    run_meta: Dict[str, Any] = {
        "run_id": run_id,
        "created_at": now,
        "workflow": DEFAULT_WORKFLOW_NAME,
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
            "input_dir": knime_root.as_posix() + "/",
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


    run_meta_path = knime_root / "run_meta.json"
    run_meta_path.write_text(json.dumps(run_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    copied["run_meta"] = run_meta_path.as_posix()

    bridge_summary_path = profile_dir / "bridge_summary.json"
    bridge_summary: Dict[str, Any] = {
        "run_id": run_id,
        "generated_at": now,
        "mode": mode,
        "git_sha": git_sha,
        "git_branch": git_branch,
        "dataset_source": dataset_path.as_posix(),
        "features_source": features_path.as_posix(),
        "dataset_origin": "layer1_dataset" if layer1_path and layer1_path.exists() else "features",
        "data_rows": data_rows,
        "data_columns": data_cols,
        "copied": copied,
    }

    bridge_summary_path.write_text(json.dumps(bridge_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    copied["bridge_summary"] = bridge_summary_path.as_posix()

    stage075_dir = artifacts_root / run_id / "stage_07_5_feature_report"
    layer2_candidate = _build_layer2_candidate(stage075_dir, run_id)
    candidate_path = profile_dir / "layer2_candidate.json"
    
    # Always create layer2_candidate.json, even if empty
    if layer2_candidate:
        candidate_path.write_text(json.dumps(layer2_candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        # Create empty layer2_candidate.json if no data available
        empty_candidate = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": {
                "variance": None,
                "comparative": None,
                "heatmap": None,
            },
            "variance": None,
            "comparative": None,
            "heatmap": None,
            "notes": ["No layer2 data available from stage_07_5_feature_report"],
        }
        candidate_path.write_text(json.dumps(empty_candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    
    copied["layer2_candidate"] = candidate_path.as_posix()

    # Also create stage_07_knime_bridge directory and copy files there for expected output location
    stage_bridge_dir = artifacts_root / run_id / "stage_07_knime_bridge"
    stage_bridge_profile_dir = stage_bridge_dir / "profile"
    stage_bridge_profile_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy/link files to stage_07_knime_bridge/profile for expected outputs
    if bridge_summary_path.exists():
        shutil.copy2(bridge_summary_path, stage_bridge_profile_dir / "bridge_summary.json")
    if candidate_path.exists():
        shutil.copy2(candidate_path, stage_bridge_profile_dir / "layer2_candidate.json")
    profile_feature_report = profile_dir / "feature_report.json"
    if profile_feature_report.exists():
        shutil.copy2(profile_feature_report, stage_bridge_profile_dir / "feature_report.json")

    # Ensure all expected outputs are included
    outputs = {key: value for key, value in copied.items() if value}

    knime_outputs_dir = knime_root / "outputs"
    knime_outputs_dir.mkdir(parents=True, exist_ok=True)

    analytics_root = artifacts_root / run_id / "phase_07_analytics"
    analytics_profile_dir = analytics_root / "profile"
    analytics_profile_dir.mkdir(parents=True, exist_ok=True)
    analytics_summary_path = analytics_profile_dir / "analytics_summary.json"
    if enable_knime_stub:
        if not analytics_summary_path.exists():
            analytics_summary_payload = {
                "run_id": run_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "SKIP",
                "notes": ["Python analytics stub generated by KNIME bridge"],
            }
            analytics_summary_path.write_text(
                json.dumps(analytics_summary_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        outputs.setdefault("analytics_summary", analytics_summary_path.as_posix())
    elif analytics_summary_path.exists():
        # Preserve real analytics outputs when they already exist (e.g. re-run)
        outputs.setdefault("analytics_summary", analytics_summary_path.as_posix())

    
    # Ensure layer2_candidate is in outputs (from stage_07_knime_bridge/profile)
    stage_layer2_path = stage_bridge_profile_dir / "layer2_candidate.json"
    if stage_layer2_path.exists():
        outputs["layer2_candidate"] = stage_layer2_path.as_posix()
    elif candidate_path.exists():
        outputs["layer2_candidate"] = candidate_path.as_posix()
    
    # Ensure bridge_summary is in outputs (from stage_07_knime_bridge/profile)
    stage_bridge_summary_path = stage_bridge_profile_dir / "bridge_summary.json"
    if stage_bridge_summary_path.exists():
        outputs["bridge_summary"] = stage_bridge_summary_path.as_posix()
    elif bridge_summary_path.exists():
        outputs["bridge_summary"] = bridge_summary_path.as_posix()
    
    # Ensure feature_report is in outputs (from stage_07_knime_bridge/profile)
    stage_feature_report_path = stage_bridge_profile_dir / "feature_report.json"
    if stage_feature_report_path.exists():
        outputs["feature_report"] = stage_feature_report_path.as_posix()
    elif profile_feature_report.exists():
        outputs["feature_report"] = profile_feature_report.as_posix()
    
    status = "PASS" if len([k for k in ["layer2_candidate", "bridge_summary", "feature_report"] if k in outputs]) >= 3 else "WARN"
    metrics: Dict[str, Any] = {
        "prepared_files": len(outputs),
        "mode": mode,
        "dataset_source": dataset_path.as_posix(),
        "dataset_origin": "layer1_dataset" if layer1_path and layer1_path.exists() else "features",
    }
    metrics.setdefault("python_analytics", "skipped" if enable_knime_stub else "disabled")
    if data_rows is not None:
        metrics["data_rows"] = data_rows
    if data_cols is not None:
        metrics["data_columns"] = data_cols


    # Optional: execute KNIME batch after preparation (useful during testing)
    def _run_knime_batch(run_id_local: str, knime_root_local: Path) -> Tuple[int, Optional[str]]:
        script = PROJECT_ROOT / "knime" / "run_knime_workflow.ps1"
        logs_dir = knime_root_local / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"knime_batch_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.log"
        if not script.exists():
            msg = f"KNIME script not found: {script.as_posix()}"
            try:
                stdout_path.write_text(msg, encoding="utf-8")
            except Exception:
                pass
            return 127, stdout_path.as_posix()
        cmd = [
            "pwsh",
            "-NoLogo",
            "-NonInteractive",
            "-File",
            script.as_posix(),
            "-RunId",
            run_id_local,
            "-AutoApprove",
        ]
        try:
            with stdout_path.open("w", encoding="utf-8") as out:
                proc = subprocess.run(cmd, cwd=PROJECT_ROOT, stdout=out, stderr=subprocess.STDOUT)
            return proc.returncode, stdout_path.as_posix()
        except Exception as e:  # best-effort, do not fail the bridge
            try:
                stdout_path.write_text(f"Failed to start KNIME batch: {e}", encoding="utf-8")
            except Exception:
                pass
            return 126, stdout_path.as_posix()

    # Decide whether to execute batch now
    run_batch = bool(config.get("run_batch")) or (mode == "auto" and bool(config.get("auto_execute", True)))
    only_execute = bool(config.get("only_execute"))

    knime_exit_code: Optional[int] = None
    knime_stdout: Optional[str] = None

    if only_execute or run_batch:
        # If only_execute, assume preparation already done; otherwise we just prepared above
        knime_exit_code, knime_stdout = _run_knime_batch(run_id, knime_root)
        # Append batch info into bridge_summary.json
        try:
            summary_path = profile_dir / "bridge_summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
            summary.setdefault("batch", {})
            summary["batch"].update({
                "exit_code": knime_exit_code,
                "stdout_path": knime_stdout,
            })
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        # Reflect batch result in overall status/metrics
        if knime_exit_code is not None and knime_exit_code != 0:
            status = "WARN"
        metrics["knime_exit_code"] = knime_exit_code

    result: Dict[str, Any] = {
        "run_id": run_id,
        "status": status,
        "outputs": outputs,
        "metrics": metrics,
    }
    if knime_stdout:
        result["logs"] = {"knime_stdout": knime_stdout}
    return result


__all__ = ["run", "resolve_mode"]
