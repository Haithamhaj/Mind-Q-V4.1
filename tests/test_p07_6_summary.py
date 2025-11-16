from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

import importlib.util
import numpy as np
import pandas as pd


def _load_phase_impl(phase_dir: str):
    base = Path(__file__).resolve().parents[1] / "phases"
    candidates = [
        base / phase_dir / "impl.py",
        base / f"_{phase_dir}" / "impl.py",
    ]
    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location(f"phase_{phase_dir.replace('/', '_')}", path.as_posix())
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(f"Unable to locate implementation for phase directory '{phase_dir}'")


feature_report = _load_phase_impl("07_5_feature_report")
llm_summary = _load_phase_impl("07_6_llm_summary")


def _build_dataset() -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=60, freq="D")
    amount = np.linspace(10, 110, num=60)
    cod_amount = amount * 1.1
    emails = [f"user{i}@example.com" for i in range(60)]
    emails[10] = None
    rng = np.random.default_rng(456)
    return pd.DataFrame(
        {
            "amount": amount,
            "COD_AMOUNT": cod_amount,
            "created_at": dates,
            "customer_email": emails,
            "carrier": rng.choice(["A", "B"], size=60),
        }
    )


def _write_manifest(path: Path, keep: list[str]) -> None:
    payload: Dict[str, Any] = {"keep": keep, "drop": [], "review": []}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_path(payload: Dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if "[" in part:
            key, index = part.rstrip("]").split("[")
            current = current[key][int(index)]
        else:
            current = current[part]
    return current


def _seed_nzv_artifacts(
    artifacts_root: Path,
    run_id: str,
    *,
    column_name: str,
    n_rows: int,
    dominant_value: Any,
    dominant_pct: float,
) -> None:
    stage05_dir = artifacts_root / run_id / "stage_05_missing"
    stage05_dir.mkdir(parents=True, exist_ok=True)
    nzv_entry = {
        "name": column_name,
        "n_valid": n_rows,
        "missing_pct": 0.0,
        "unique_count": 1,
        "dominant_value": dominant_value,
        "dominant_pct": dominant_pct,
        "top_values": [{"value": dominant_value, "pct": dominant_pct}],
        "nzv_category": "near_zero_variance",
        "is_nzv": True,
        "nzv_reason": "dominant_pct>=0.95,max_unique<=5",
    }
    summary_payload = {
        "imputed_columns": [],
        "indicator_columns": [],
        "model_exclusions": [],
        "nzv_summary": {
            "n_nzv_columns": 1,
            "n_constant_like": 1,
            "n_high_imbalance": 0,
            "n_total_columns": 1,
            "nzv_ratio": 1.0,
        },
    }
    (stage05_dir / "summary.json").write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    nzv_payload = {"run_id": run_id, "n_rows": n_rows, "columns": [nzv_entry], "nzv_summary": summary_payload["nzv_summary"]}
    (stage05_dir / "nzv_summaries.json").write_text(json.dumps(nzv_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    stage06_dir = artifacts_root / run_id / "stage_06_standardize"
    stage06_dir.mkdir(parents=True, exist_ok=True)
    standardize_payload = {
        "columns": {
            column_name: {
                "original_name": column_name,
                "standardized_name": column_name,
                "dtype_before": "string",
                "dtype_after": "string",
                "is_nzv": True,
                "nzv_category": "near_zero_variance",
                "nzv_reason": "dominant_pct>=0.95,max_unique<=5",
                "nzv_dominant_value": dominant_value,
                "nzv_dominant_pct": dominant_pct,
            }
        },
        "nzv_summary": summary_payload["nzv_summary"],
    }
    (stage06_dir / "standardize_report.json").write_text(json.dumps(standardize_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_stage_07_6_fallback_outputs(tmp_path: Path) -> None:
    run_id = "summaryrun"
    artifacts_root = tmp_path / "artifacts"
    features_dir = artifacts_root / run_id / "stage_06_feature_eng"
    readiness_dir = artifacts_root / run_id / "stage_07_readiness"
    features_dir.mkdir(parents=True, exist_ok=True)
    readiness_dir.mkdir(parents=True, exist_ok=True)

    df = _build_dataset()
    features_path = features_dir / "features.parquet"
    df.to_parquet(features_path, index=False)

    _seed_nzv_artifacts(
        artifacts_root,
        run_id,
        column_name="customer_email",
        n_rows=len(df),
        dominant_value="user0@example.com",
        dominant_pct=0.98,
    )

    manifest_path = readiness_dir / "decision_manifest.json"
    keep_cols = ["amount", "COD_AMOUNT", "created_at", "customer_email"]
    _write_manifest(manifest_path, keep_cols)
    feature_spec = {"main_ts": "created_at"}
    (features_dir / "feature_spec.json").write_text(json.dumps(feature_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg_report = {
        "artifacts_root": artifacts_root.as_posix(),
        "focus_cols": keep_cols,
        "exclude_cols": ["carrier"],
        "top_k": 5,
        "tz": "Asia/Riyadh",
    }
    inputs_report = {
        "features": features_path.as_posix(),
        "decision_manifest": manifest_path.as_posix(),
        "feature_spec": (features_dir / "feature_spec.json").as_posix(),
    }
    feature_report.run(run_id, inputs_report, cfg_report)  # type: ignore[arg-type]

    report_path = artifacts_root / run_id / "stage_07_5_feature_report" / "report.json"
    assert report_path.exists()

    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload.get("low_variance_fields")

    kpis_path = tmp_path / "kpis.yml"
    kpis_payload = {"primary": {"column": "COD_AMOUNT"}}
    kpis_path.write_text(json.dumps(kpis_payload), encoding="utf-8")

    cfg_summary = {
        "artifacts_root": artifacts_root.as_posix(),
        "llm_provider": "gemini",
        "llm_model": "gemini-1.5-pro",
        "max_tokens": 1200,
        "temperature": 0.1,
        "top_p": 0.0,
        "focus_cols": ["amount"],
        "exclude_cols": [],
        "budget_usd": 0.0,
    }
    inputs_summary = {
        "report": report_path.as_posix(),
        "kpis": kpis_path.as_posix(),
    }
    llm_summary.run(run_id, inputs_summary, cfg_summary)  # type: ignore[arg-type]

    output_dir = artifacts_root / run_id / "stage_07_6_llm_summary"
    exec_path = output_dir / "executive_summary.md"
    rec_path = output_dir / "recommendations.json"
    metrics_path = output_dir / "metrics.json"
    logs_path = output_dir / "logs.jsonl"

    assert exec_path.exists()
    assert rec_path.exists()
    assert metrics_path.exists()
    assert logs_path.exists()
    assert (output_dir / "provenance.json").exists()

    summary_text = exec_path.read_text(encoding="utf-8")
    assert summary_text.count("-") >= 3
    assert re.search(r"[A-Za-z]", summary_text) is None
    assert "?" not in summary_text

    recommendations = json.loads(rec_path.read_text(encoding="utf-8"))
    assert recommendations["invalid_references"] == []
    assert 1 <= len(recommendations["recommendations"]) <= 6
    assert any(any("\u0600" <= ch <= "\u06FF" for ch in rec["reason"]) for rec in recommendations["recommendations"])
    assert all("?" not in rec["reason"] for rec in recommendations["recommendations"])
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    for rec in recommendations["recommendations"]:
        assert rec["column_name"] != "customer_email"
        assert rec["column_name"] in {"amount", "COD_AMOUNT", "created_at"}
        _resolve_path(report_payload, rec["evidence_key"])

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["provider"] == "heuristic"
    assert metrics["model"] == "heuristic"
    assert metrics["tokens_in"] == 0
    assert metrics["tokens_out"] == 0
    assert metrics.get("cache_hit") is False
    assert metrics.get("fallback_chain")

    with logs_path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
    assert any("llm_plan" in line for line in lines)
    assert any("nzv_prompt_instruction_loaded" in line for line in lines)


def test_stage_07_6_handles_empty_focus_scope(tmp_path: Path) -> None:
    run_id = "focusfallback"
    artifacts_root = tmp_path / "artifacts"
    features_dir = artifacts_root / run_id / "stage_06_feature_eng"
    readiness_dir = artifacts_root / run_id / "stage_07_readiness"
    features_dir.mkdir(parents=True, exist_ok=True)
    readiness_dir.mkdir(parents=True, exist_ok=True)

    df = _build_dataset()
    features_path = features_dir / "features.parquet"
    df.to_parquet(features_path, index=False)

    manifest_path = readiness_dir / "decision_manifest.json"
    keep_cols = ["amount", "COD_AMOUNT", "created_at", "customer_email", "carrier"]
    _write_manifest(manifest_path, keep_cols)

    cfg_report = {
        "artifacts_root": artifacts_root.as_posix(),
        "focus_cols": keep_cols,
        "top_k": 3,
    }
    inputs_report = {
        "features": features_path.as_posix(),
        "decision_manifest": manifest_path.as_posix(),
    }
    feature_report.run(run_id, inputs_report, cfg_report)  # type: ignore[arg-type]

    report_path = artifacts_root / run_id / "stage_07_5_feature_report" / "report.json"
    assert report_path.exists()

    cfg_summary = {
        "artifacts_root": artifacts_root.as_posix(),
        "focus_cols": ["nonexistent_field"],
        "budget_usd": 0.0,
    }
    inputs_summary = {"report": report_path.as_posix()}
    llm_summary.run(run_id, inputs_summary, cfg_summary)  # type: ignore[arg-type]

    recommendations_path = artifacts_root / run_id / "stage_07_6_llm_summary" / "recommendations.json"
    assert recommendations_path.exists()
    recommendations = json.loads(recommendations_path.read_text(encoding="utf-8"))
    assert recommendations["recommendations"]
    assert recommendations["recommendations"][0]["column_name"] in keep_cols
    assert "?" not in recommendations["recommendations"][0]["reason"]


def test_llm_provider_plan_respects_env_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.1")
    plan = llm_summary._llm_provider_plan({})  # type: ignore[attr-defined]
    assert plan[0] == ("openai", "gpt-5.1")
