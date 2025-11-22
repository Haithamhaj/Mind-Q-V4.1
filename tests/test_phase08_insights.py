from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from typing import Any, Callable, Dict, Optional, Sequence, TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    import polars as pl
else:
    pl = pytest.importorskip("polars")  # type: ignore[assignment]

jsonschema = pytest.importorskip("jsonschema")

from backend.src.app.services.stage_08_insights import impl

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = BACKEND_ROOT / "src/app/services/stage_08_insights/schema_insights.json"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_phase_impl(phase_dir: str) -> Any:
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


feature_report_impl = _load_phase_impl("07_5_feature_report")


def _seed_nzv_artifacts(
    artifacts_root: Path,
    run_id: str,
    *,
    low_variance: Optional[Sequence[str]] = None,
    high_imbalance: Optional[Sequence[str]] = None,
) -> None:
    stage05_dir = artifacts_root / run_id / "stage_05_missing"
    stage05_dir.mkdir(parents=True, exist_ok=True)
    columns: List[Dict[str, Any]] = []
    low_variance = list(low_variance or [])
    high_imbalance = list(high_imbalance or [])
    for name in low_variance:
        columns.append(
            {
                "name": name,
                "n_valid": 100,
                "missing_pct": 0.0,
                "unique_count": 1,
                "dominant_value": "A",
                "dominant_pct": 0.98,
                "top_values": [{"value": "A", "pct": 0.98}],
                "nzv_category": "near_zero_variance",
                "is_nzv": True,
                "nzv_reason": "dominant_pct>=0.95,max_unique<=5",
            }
        )
    for name in high_imbalance:
        columns.append(
            {
                "name": name,
                "n_valid": 100,
                "missing_pct": 0.0,
                "unique_count": 3,
                "dominant_value": "X",
                "dominant_pct": 0.92,
                "top_values": [{"value": "X", "pct": 0.92}],
                "nzv_category": "high_imbalance",
                "is_nzv": False,
                "nzv_reason": "dominant_pct>=0.90",
            }
        )
    summary_payload = {
        "imputed_columns": [],
        "indicator_columns": [],
        "model_exclusions": [],
        "nzv_summary": {
            "n_nzv_columns": len(low_variance),
            "n_constant_like": len(low_variance),
            "n_high_imbalance": len(high_imbalance),
            "n_total_columns": len(low_variance) + len(high_imbalance),
            "nzv_ratio": float(len(low_variance)) / float(max(1, len(low_variance) + len(high_imbalance))),
        },
    }
    (stage05_dir / "summary.json").write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    nzv_payload = {
        "run_id": run_id,
        "n_rows": 100,
        "columns": columns,
        "nzv_summary": summary_payload["nzv_summary"],
    }
    (stage05_dir / "nzv_summaries.json").write_text(json.dumps(nzv_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    stage06_dir = artifacts_root / run_id / "stage_06_standardize"
    stage06_dir.mkdir(parents=True, exist_ok=True)
    stage06_columns: Dict[str, Dict[str, Any]] = {}
    for name in low_variance:
        stage06_columns[name] = {
            "original_name": name,
            "standardized_name": name,
            "dtype_before": "string",
            "dtype_after": "string",
            "is_nzv": True,
            "nzv_category": "near_zero_variance",
            "nzv_reason": "dominant_pct>=0.95,max_unique<=5",
            "nzv_dominant_value": "A",
            "nzv_dominant_pct": 0.98,
            "usage_hint": "context_only",
        }
    for name in high_imbalance:
        stage06_columns.setdefault(
            name,
            {
                "original_name": name,
                "standardized_name": name,
                "dtype_before": "string",
                "dtype_after": "string",
            },
        )
    stage06_payload = {
        "columns": stage06_columns,
        "nzv_summary": summary_payload["nzv_summary"],
    }
    (stage06_dir / "standardize_report.json").write_text(json.dumps(stage06_payload, ensure_ascii=False, indent=2), encoding="utf-8")



def _build_features() -> pl.DataFrame:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    base_ts = datetime(2024, 1, 1, 8, 0, tzinfo=ZoneInfo("Asia/Riyadh"))
    rows: list[tuple[Any, ...]] = []
    for idx in range(8):
        rows.append(
            (
                idx + 1,
                1 if idx % 2 == 0 else 0,
                80 + idx * 5,
                1 if idx < 4 else 0,
                150.0 + idx * 10,
                "ALPHA" if idx < 4 else "BETA",
                "EAST" if idx < 4 else "WEST",
                base_ts + timedelta(days=idx),
            )
        )
    return pl.DataFrame(
        rows,
        schema={
            "row_id": pl.Int64,
            "IS_COD": pl.Int64,
            "WEIGHT": pl.Float64,
            "DELIVERED": pl.Int64,
            "COD_AMOUNT": pl.Float64,
            "CARRIER": pl.Utf8,
            "REGION": pl.Utf8,
            "created_at": pl.Datetime(time_zone="Asia/Riyadh"),
        },
        orient="row",
    )


def _build_low_signal_features() -> pl.DataFrame:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    rng: Any = np.random.default_rng(99)
    base_ts = datetime(2024, 1, 1, 8, 0, tzinfo=ZoneInfo("Asia/Riyadh"))
    size = 120
    carriers = ["ALPHA", "BETA", "GAMMA"]
    regions = ["EAST", "WEST", "NORTH"]
    rows: list[tuple[Any, ...]] = []
    for idx in range(size):
        rows.append(
            (
                idx + 1,
                int(rng.integers(0, 2)),
                float(rng.normal(50, 6)),
                int(rng.integers(0, 2)),
                float(rng.normal(75, 12)),
                carriers[idx % len(carriers)],
                regions[idx % len(regions)],
                base_ts + timedelta(hours=idx),
            )
        )
    return pl.DataFrame(
        rows,
        schema={
            "row_id": pl.Int64,
            "IS_COD": pl.Int64,
            "WEIGHT": pl.Float64,
            "DELIVERED": pl.Int64,
            "COD_AMOUNT": pl.Float64,
            "CARRIER": pl.Utf8,
            "REGION": pl.Utf8,
            "created_at": pl.Datetime(time_zone="Asia/Riyadh"),
        },
        orient="row",
    )



def _build_anomaly_features() -> pl.DataFrame:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    base_ts = datetime(2024, 1, 1, 8, 0, tzinfo=ZoneInfo("Asia/Riyadh"))
    rows: list[tuple[Any, ...]] = []
    idx = 0
    for group in range(10):
        carrier = f"ALPHA_{group}"
        region = f"REGION_{group}"
        cod_amount = 60.0 + (group % 3)
        for _ in range(320):
            rows.append(
                (
                    idx + 1,
                    1 if group % 2 == 0 else 0,
                    55.0 + (idx % 30),
                    1,
                    cod_amount,
                    carrier,
                    region,
                    base_ts + timedelta(hours=idx),
                )
            )
            idx += 1
    carrier = "OUTLIER"
    region = "ALERT"
    for _ in range(320):
        rows.append(
            (
                idx + 1,
                1,
                75.0 + (idx % 20),
                1,
                350.0,
                carrier,
                region,
                base_ts + timedelta(hours=idx),
            )
        )
        idx += 1
    return pl.DataFrame(
        rows,
        schema={
            "row_id": pl.Int64,
            "IS_COD": pl.Int64,
            "WEIGHT": pl.Float64,
            "DELIVERED": pl.Int64,
            "COD_AMOUNT": pl.Float64,
            "CARRIER": pl.Utf8,
            "REGION": pl.Utf8,
            "created_at": pl.Datetime(time_zone="Asia/Riyadh"),
        },
        orient="row",
    )


def _build_correlations() -> list[Dict[str, Any]]:
    return [
        {"kpi": "DELIVERED", "feature": "IS_COD", "rel_key": "DELIVERED|IS_COD"},
        {"kpi": "DELIVERED", "feature": "WEIGHT", "rel_key": "DELIVERED|WEIGHT"},
    ]


def _build_redundancy() -> Dict[str, Any]:
    return {
        "DELIVERED|IS_COD": {"redundancy_score": 0.05},
        "DELIVERED|WEIGHT": {"redundancy_score": 0.10},
    }


def _build_sla_features() -> pl.DataFrame:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    base_ts = datetime(2024, 1, 1, 9, 0, tzinfo=ZoneInfo("Asia/Riyadh"))
    rows: list[tuple[Any, ...]] = []
    for idx in range(24):
        rows.append(
            (
                idx + 1,
                idx % 2,
                1 if idx % 3 == 0 else 0,
                "ACME_DELTA",
                base_ts + timedelta(hours=idx),
            )
        )
    return pl.DataFrame(
        rows,
        schema={
            "row_id": pl.Int64,
            "IS_COD": pl.Int64,
            "SLA_ACHIEVED": pl.Int64,
            "CLIENT_ID": pl.Utf8,
            "created_at": pl.Datetime(time_zone="Asia/Riyadh"),
        },
        orient="row",
    )


def _seed_rag_bundle(artifacts_root: Path, run_id: str, *, client_id: str = "ACME_DELTA", kpi_id: str = "SLA_ACHIEVED") -> None:
    text_dir = artifacts_root / run_id / "stage_03_5_textops"
    text_dir.mkdir(parents=True, exist_ok=True)
    segments = pl.DataFrame(
        {
            "segment_id": [0],
            "vector_id": [0],
            "source": ["doc"],
            "source_key": ["acme_sla.pdf"],
            "text": ["Deliver within 24 hours for premium service lanes."],
        }
    )
    segments.write_parquet((text_dir / "doc_segments.parquet").as_posix())
    rules = pl.DataFrame(
        {
            "rule_id": ["sla_clause_1"],
            "partner_id": [client_id],
            "metric": [kpi_id],
            "operator": [">="],
            "value": ["0.95"],
            "unit": ["ratio"],
            "scope": ["premium"],
            "valid_from": ["2024-01-01"],
            "valid_to": ["2024-12-31"],
            "source_doc_id": ["acme_sla.pdf"],
            "citation_segment_ids": [[0]],
        }
    )
    rules.write_parquet((text_dir / "rules_sla_llm.parquet").as_posix())
    links = pl.DataFrame(
        {
            "entity_type": ["SLA"],
            "entity_id": ["sla_clause_1"],
            "kpi_id": [kpi_id],
            "dim_keys": [json.dumps({"partner_id": client_id})],
            "link_confidence": [0.9],
        }
    )
    links.write_parquet((text_dir / "kpi_links.parquet").as_posix())


def _build_text_profile() -> Dict[str, Any]:
    return {
        "global": {"total_docs": 8},
        "columns": {
            "NOTES": {
                "counts": {"n": 8, "missing_pct": 0.0},
                "top_tokens": [
                    {"t": "fast delivery", "c": 4},
                    {"t": "support@company.com", "c": 2},
                    {"t": "966500000000", "c": 1},
                ],
            }
        },
    }


def _build_sentiment() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "row_id": list(range(1, 9)),
            "sentiment_score": [0.7, 0.6, 0.55, 0.5, -0.4, -0.5, -0.45, -0.3],
            "subjectivity": [0.5] * 8,
            "tox_prob": [0.1] * 8,
        }
    )


def _make_artifacts(
    tmp_path: Path,
    run_id: str,
    *,
    features: Optional[pl.DataFrame] = None,
    correlations: Optional[list[Dict[str, Any]]] = None,
    redundancy: Optional[Dict[str, Any]] = None,
) -> Path:
    artifacts_root = tmp_path / "artifacts"
    base = artifacts_root / run_id

    features_dir = base / "stage_06_feature_eng"
    correlations_dir = base / "stage_07_correlations"
    text_dir = base / "stage_03_5_textops"

    features_dir.mkdir(parents=True, exist_ok=True)
    correlations_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    features_df = features if features is not None else _build_features()
    features_df.write_parquet((features_dir / "features.parquet").as_posix())

    corr_payload = correlations if correlations is not None else _build_correlations()
    redundancy_payload = redundancy if redundancy is not None else _build_redundancy()

    _write_json(correlations_dir / "correlations.json", corr_payload)
    _write_json(correlations_dir / "redundancy.json", redundancy_payload)

    _write_json(text_dir / "text_profile.json", _build_text_profile())
    _build_sentiment().write_parquet((text_dir / "sentiment_features.parquet").as_posix())

    readiness_dir = base / "stage_07_readiness"
    readiness_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = readiness_dir / "decision_manifest.json"
    keep_cols = list(features_df.columns)
    _write_json(manifest_path, {"keep": keep_cols, "drop": [], "review": []})

    feature_spec_path = features_dir / "feature_spec.json"
    main_ts = next((col for col in keep_cols if "created" in col.lower() or col.lower().endswith("_at")), None)
    _write_json(feature_spec_path, {"main_ts": main_ts})

    layer2_metric = "COD_AMOUNT" if "COD_AMOUNT" in keep_cols else (keep_cols[0] if keep_cols else None)
    stage07_cfg: Dict[str, Any] = {
        "artifacts_root": artifacts_root.as_posix(),
        "focus_cols": keep_cols,
        "tz": "Asia/Riyadh",
        "layer2_metric": layer2_metric,
        "comparative_dimensions": ["REGION", "CARRIER"],
        "layer2_min_group": 1,
        "layer2_top_n": 5,
        "layer2_heatmap": {
            "metric": layer2_metric,
            "x": "REGION",
            "y": "CARRIER",
            "agg": "mean",
            "max_x": 6,
            "max_y": 6,
        },
    }
    stage07_cfg = {key: value for key, value in stage07_cfg.items() if value is not None}
    stage07_inputs = {
        "features": (features_dir / "features.parquet").as_posix(),
        "decision_manifest": manifest_path.as_posix(),
        "feature_spec": feature_spec_path.as_posix(),
    }
    feature_report_impl.run(run_id, stage07_inputs, stage07_cfg)

    return artifacts_root


def test_stage08_supplemental_context(tmp_path: Path) -> None:
    run_id = "ctx"
    artifacts_root = _make_artifacts(tmp_path, run_id)
    base = artifacts_root / run_id

    readiness_dir = base / "stage_07_readiness"
    readiness_dir.mkdir(parents=True, exist_ok=True)
    (readiness_dir / "diagnostics.json").write_text(
        json.dumps({"gate_status": "WARN", "gate_reasons": ["missing_layer1"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest_payload = {
        "reasons": ["layer1 incomplete"],
        "entries": [
            {"action": "collect_addresses", "reason": "missing geo", "features": ["address", "city"]},
        ],
    }
    (readiness_dir / "decision_manifest.json").write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (readiness_dir / "layer1_catalog.json").write_text(
        json.dumps({"field_count": 12, "row_count": 1000}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (readiness_dir / "layer1_preview.json").write_text(json.dumps([{"AWB": "1"}], ensure_ascii=False, indent=2), encoding="utf-8")
    layer1_df = pl.DataFrame({"AWB": ["1"], "CITY": ["RUH"]})
    layer1_df.write_parquet((readiness_dir / "layer1_dataset.parquet").as_posix())

    analytics_dir = base / "phase_07_analytics" / "outputs"
    analytics_dir.mkdir(parents=True, exist_ok=True)
    (analytics_dir / "dq_summary.json").write_text(
        json.dumps({"critical_failures": 2, "failed": 3}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    textops_dir = base / "stage_03_5_textops"
    textops_dir.mkdir(parents=True, exist_ok=True)
    (textops_dir / "quality_findings.json").write_text(
        json.dumps({"warnings": ["Customers mention delays"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    llm_dir = base / "stage_07_6_llm_summary"
    llm_dir.mkdir(parents=True, exist_ok=True)
    (llm_dir / "metrics.json").write_text(
        json.dumps({"provider": "heuristic", "fallback_chain": [{"provider": "openai", "status": "error"}]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})

    insights_dir = base / "stage_08_insights"
    diagnostics = json.loads((insights_dir / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics.get("readiness", {}).get("actions")
    assert diagnostics.get("analytics", {}).get("dq", {}).get("critical_failures") == 2
    assert diagnostics.get("textops", {}).get("warnings")

    story_payload = json.loads((insights_dir / "story_ops.json").read_text(encoding="utf-8"))
    assert story_payload.get("context", {}).get("text_ops")

    cards_payload = json.loads((insights_dir / "cards.json").read_text(encoding="utf-8"))
    assert cards_payload["count"] == len(story_payload.get("items", []))

    insights_report = json.loads((insights_dir / "insights_report.json").read_text(encoding="utf-8"))
    assert insights_report.get("context", {}).get("llm_summary", {}).get("provider") == "heuristic"

def _run_stage(
    tmp_path: Path,
    run_id: str,
    config: Optional[Dict[str, Any]] = None,
    *,
    features: Optional[pl.DataFrame] = None,
    correlations: Optional[list[Dict[str, Any]]] = None,
    redundancy: Optional[Dict[str, Any]] = None,
    setup_hook: Optional[Callable[[Path], None]] = None,
) -> tuple[Dict[str, Any], Path]:
    artifacts_root = _make_artifacts(tmp_path, run_id, features=features, correlations=correlations, redundancy=redundancy)
    if setup_hook:
        setup_hook(artifacts_root)
    base_config: Dict[str, Any] = {
        "artifacts_root": artifacts_root.as_posix(),
        "n_min_per_segment": 4,
        "sampling_threshold_rows": 10000,
        "sample_fraction": 1.0,
        "emit_threshold": 0.2,
        "high_bucket": 0.4,
    }
    if config:
        base_config.update(config)
    result: Dict[str, Any] = impl.run(run_id, {}, base_config)
    output_dir = artifacts_root / run_id / "stage_08_insights"
    return result, output_dir


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_schema(payload: Dict[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)


def test_happy_path_emits_official_and_candidates(tmp_path: Path) -> None:
    run_id = "run_happy"
    result, out_dir = _run_stage(tmp_path, run_id)
    assert result["status"] in {"PASS", "WARN"}

    insights_path = out_dir / "insights_report.json"
    assert insights_path.exists()
    insights = _load_json(insights_path)
    _validate_schema(insights)
    assert insights["summary"]["official_count"] > 0
    assert all("cause" not in entry["relation"].lower() for entry in insights["insights"])
    assert all("<->" in entry["relation"] for entry in insights["insights"])

    outputs = result["outputs"]
    assert "layer2_snapshot" in outputs
    advanced_dir = out_dir / "advanced"
    legacy_layer2_dir = out_dir / "layer2"
    layer2_dir = advanced_dir if advanced_dir.exists() else legacy_layer2_dir
    assert layer2_dir.exists()
    snapshot = _load_json(layer2_dir / "layer2_snapshot.json")
    assert snapshot["sources"]
    assert "variance" in snapshot and snapshot["variance"]["columns"]
    assert "heatmap" in snapshot and snapshot["heatmap"]["matrix"]
    assert "layer2_variance" in outputs
    assert (layer2_dir / "variance_analysis.json").exists()



def test_rag_context_unavailable_when_missing_artifacts(tmp_path: Path) -> None:
    run_id = "run_no_rag"
    result, out_dir = _run_stage(tmp_path, run_id)
    assert result["status"] in {"PASS", "WARN"}
    insights = _load_json(out_dir / "insights_report.json")
    rag_context = insights.get("context", {}).get("rag")
    assert rag_context
    assert rag_context.get("status") == "UNAVAILABLE"
    assert all("business_context" not in entry for entry in insights.get("insights", []))


def test_business_context_attaches_when_rag_available(tmp_path: Path) -> None:
    run_id = "run_rag_context"
    features = _build_sla_features()
    correlations = [{"kpi": "SLA_ACHIEVED", "feature": "IS_COD", "rel_key": "SLA_ACHIEVED|IS_COD"}]

    def _hook(root: Path) -> None:
        _seed_rag_bundle(root, run_id)

    result, out_dir = _run_stage(
        tmp_path,
        run_id,
        config={"segments": ["CLIENT_ID"], "emit_threshold": 0.15},
        features=features,
        correlations=correlations,
        setup_hook=_hook,
    )
    assert result["status"] in {"PASS", "WARN"}
    insights = _load_json(out_dir / "insights_report.json")
    rag_context = insights.get("context", {}).get("rag")
    assert rag_context and rag_context.get("status") in {"OK", "PARTIAL"}
    sla_insights = [entry for entry in insights.get("insights", []) if entry.get("kpi") == "SLA_ACHIEVED"]
    assert sla_insights, "Expected SLA insights to be emitted"
    payload = sla_insights[0].get("business_context")
    assert payload and payload.get("docs")
    assert payload["retrieval_meta"]["rag_status"] == "OK"
    assert payload["docs"][0]["raw_text"]


def test_advanced_outputs_fallback_created(tmp_path: Path) -> None:
    run_id = "run_adv_fallback"
    result, out_dir = _run_stage(tmp_path, run_id)

    advanced_dir = out_dir / "advanced"
    assert advanced_dir.exists()

    cluster_payload = _load_json(advanced_dir / "cluster_summary.json")
    assert cluster_payload.get("source") == "fallback"
    assert "clusters" in cluster_payload

    anomalies_payload = _load_json(advanced_dir / "anomalies.json")
    assert anomalies_payload.get("source") == "fallback"

    summary_payload = _load_json(advanced_dir / "summary.json")
    assert summary_payload["sources"]["cluster_summary"]["source"] in {"fallback", "knime"}
    assert summary_payload["sources"]["orders_forecast"]["source"] in {"fallback", "knime"}

    forecast_path = advanced_dir / "orders_forecast.parquet"
    assert forecast_path.exists()
    forecast_df = pl.read_parquet(forecast_path.as_posix())
    assert {"forecast_date", "forecast", "step", "metric", "method"}.issubset(set(forecast_df.columns))

    outputs = result["outputs"]
    assert "cluster_summary" in outputs
    assert "orders_forecast" in outputs


def test_advanced_outputs_use_knime_when_available(tmp_path: Path) -> None:
    run_id = "run_adv_knime"
    artifacts_root = _make_artifacts(tmp_path, run_id)
    knime_outputs = artifacts_root / run_id / "phase_07_knime" / "outputs"
    knime_outputs.mkdir(parents=True, exist_ok=True)

    _write_json(
        knime_outputs / "cluster_summary.json",
        {"run_id": run_id, "source": "knime", "clusters": [{"id": "Cluster A", "count": 5}]},
    )
    _write_json(
        knime_outputs / "anomalies.json",
        {"run_id": run_id, "source": "knime", "records": [{"cluster": "Cluster A", "score": 2.4}]},
    )
    _write_json(
        knime_outputs / "correlation_matrix.json",
        {"run_id": run_id, "source": "knime", "matrix": {"DELIVERED": {"IS_COD": 0.82}}},
    )

    from datetime import datetime
    from zoneinfo import ZoneInfo

    forecast_df = pl.DataFrame(
        {
            "forecast_date": [datetime(2025, 1, 1, tzinfo=ZoneInfo("Asia/Riyadh"))],
            "forecast": [180.0],
            "step": [1],
            "metric": ["COD_AMOUNT"],
            "method": ["knime"],
        }
    )
    forecast_df.write_parquet((knime_outputs / "orders_forecast.parquet").as_posix())

    base_config = {
        "artifacts_root": artifacts_root.as_posix(),
        "n_min_per_segment": 4,
        "sampling_threshold_rows": 10000,
        "sample_fraction": 1.0,
        "emit_threshold": 0.2,
        "high_bucket": 0.4,
    }
    result = impl.run(run_id, {}, base_config)
    out_dir = artifacts_root / run_id / "stage_08_insights"
    advanced_dir = out_dir / "advanced"

    summary_payload = _load_json(advanced_dir / "summary.json")
    assert summary_payload["sources"]["cluster_summary"]["source"] == "knime"
    assert summary_payload["sources"]["anomalies"]["source"] == "knime"
    assert summary_payload["sources"]["orders_forecast"]["source"] == "knime"

    cluster_payload = _load_json(advanced_dir / "cluster_summary.json")
    assert cluster_payload.get("source") == "knime"
    anomalies_payload = _load_json(advanced_dir / "anomalies.json")
    assert anomalies_payload.get("source") == "knime"

    forecast_path = advanced_dir / "orders_forecast.parquet"
    assert forecast_path.exists()
    copied_forecast = pl.read_parquet(forecast_path.as_posix())
    assert copied_forecast["method"][0] == "knime"

    outputs = result["outputs"]
    assert outputs["cluster_summary"].endswith("cluster_summary.json")
    assert outputs["orders_forecast"].endswith("orders_forecast.parquet")


def test_stage08_ignores_low_variance_fields(tmp_path: Path) -> None:
    run_id = "nzv_skip"
    artifacts_root = _make_artifacts(tmp_path, run_id)
    _seed_nzv_artifacts(artifacts_root, run_id, low_variance=["CARRIER"])
    result, out_dir = _run_stage(tmp_path, run_id)
    assert result["status"] in {"PASS", "WARN"}
    diagnostics = _load_json(out_dir / "diagnostics.json")
    impact = diagnostics.get("nzv_impact", {})
    ignored = impact.get("low_variance_ignored_columns", [])
    assert all(isinstance(entry, dict) for entry in ignored)
    assert any(entry.get("name") == "CARRIER" for entry in ignored)
    assert any(entry.get("usage_hint") == "context_only" for entry in ignored)
    column_roles = diagnostics.get("column_roles", {})
    assert "context_columns" in column_roles
    assert "CARRIER" in column_roles.get("context_columns", [])
    insights = _load_json(out_dir / "insights_report.json")
    impact_report = insights.get("nzv_impact", {})
    assert any(entry.get("name") == "CARRIER" for entry in impact_report.get("low_variance_ignored_columns", []))
    llm_input = _load_json(out_dir / "input.json")
    assert "context_columns" in llm_input
    assert "analysis_columns" in llm_input
    assert "CARRIER" in llm_input["context_columns"]
    assert "instructions" in llm_input and "NEVER" in llm_input["instructions"].upper()
    story = _load_json(out_dir / "story_ops.json")
    assert story.get("context", {}).get("column_roles", {}).get("context_columns")


def test_high_nzv_ratio_falls_back_to_warn(tmp_path: Path) -> None:
    run_id = "nzv_warn"
    artifacts_root = _make_artifacts(tmp_path, run_id)
    _seed_nzv_artifacts(artifacts_root, run_id, low_variance=["CARRIER", "REGION", "STATUS"])
    config = {"emit_threshold": 0.95}
    result, out_dir = _run_stage(tmp_path, run_id, config=config)
    assert result["status"] == "WARN"
    gate = _load_json(out_dir / "gate.json")
    assert gate["status"] == "WARN"
    assert any("High NZV ratio" in reason for reason in gate.get("reasons", []))
    diagnostics = _load_json(out_dir / "diagnostics.json")
    assert "demotion_note" in diagnostics.get("column_roles", {})


def test_stage08_tags_high_imbalance_columns(tmp_path: Path) -> None:
    run_id = "nzv_high_imbalance"
    artifacts_root = _make_artifacts(tmp_path, run_id)
    _seed_nzv_artifacts(artifacts_root, run_id, high_imbalance=["REGION"])
    result, out_dir = _run_stage(tmp_path, run_id)
    assert result["status"] in {"PASS", "WARN"}
    diagnostics = _load_json(out_dir / "diagnostics.json")
    impact = diagnostics.get("nzv_impact", {})
    high_imbalance = impact.get("high_imbalance_included_columns", [])
    assert any(entry.get("name") == "REGION" for entry in high_imbalance)


def test_anomalies_absent_when_sample_small(tmp_path: Path) -> None:
    run_id = "small_sample"
    _, out_dir = _run_stage(tmp_path, run_id, features=_build_features())
    diagnostics = _load_json(out_dir / "diagnostics.json")
    anomalies = diagnostics.get("anomalies", {})
    assert anomalies.get("records") == []


def test_anomalies_detected_for_large_shift(tmp_path: Path) -> None:
    run_id = "large_sample"
    features = _build_anomaly_features()
    result, out_dir = _run_stage(tmp_path, run_id, features=features)
    diagnostics = _load_json(out_dir / "diagnostics.json")
    anomalies = diagnostics.get("anomalies", {})
    records = cast(list[Dict[str, Any]], anomalies.get("records") or [])
    assert records, "expected anomaly records for significant COD shift"
    assert any(abs(record.get("z_score", 0)) > 3 for record in records)

    candidates_path = out_dir / "insights_candidates.json"
    assert candidates_path.exists()
    candidates = _load_json(candidates_path)["candidates"]
    assert result["status"] in {"WARN", "PASS"}
    assert candidates
    first_candidate = candidates[0]
    required_candidate_fields = {
        "kpi",
        "feature",
        "metric",
        "effect",
        "strength",
        "direction",
        "n",
        "coverage",
        "confidence",
        "bucket",
        "stability_score",
        "stability",
        "redundancy",
        "signal_score",
        "segment",
        "window",
        "source",
        "notes",
        "flags",
        "evidence",
        "diagnostics",
        "low_signal",
        "nzv_override",
    }
    assert required_candidate_fields.issubset(first_candidate.keys())

    story_path = out_dir / "story_ops.json"
    story = _load_json(story_path)
    insights = _load_json(out_dir / "insights_report.json")
    story_items = story["items"]
    assert len(story_items) >= insights["summary"]["official_count"]
    official_kpis = {entry["kpi"] for entry in insights["insights"]}
    story_kpis = {item.get("kpi") for item in story_items if item.get("kpi")}
    assert official_kpis.issubset(story_kpis)
    assert story["confidence_note"].endswith("Non-causal.")

    segment_stats_path = out_dir / "segment_stats.parquet"
    assert segment_stats_path.exists()
    segment_df = pl.read_parquet(segment_stats_path.as_posix())
    assert "segment" in segment_df.columns

    time_stats_path = out_dir / "time_stats.parquet"
    assert time_stats_path.exists()
    time_df = pl.read_parquet(time_stats_path.as_posix())
    assert "time_bucket" in time_df.columns

    keyphrases = _load_json(out_dir / "keyphrases_topk.json")
    assert "keyphrases" in keyphrases
    assert keyphrases["keyphrases"]

    diagnostics = _load_json(out_dir / "diagnostics.json")
    for field in ("warnings", "notes", "sampling"):
        assert field in diagnostics
    assert isinstance(diagnostics["warnings"], list)
    assert isinstance(diagnostics["notes"], list)
    assert diagnostics["counts"].get("low_signal") == 0
    assert diagnostics["counts"].get("nzv_override") == 0
    assert "disabled_features" in diagnostics
    assert "coverage_report" in diagnostics
    coverage_report = cast(Dict[str, Any], diagnostics["coverage_report"])
    assert coverage_report["rows"] == features.height
    assert math.isclose(float(coverage_report["threshold"]), 0.9, rel_tol=1e-6)
    coverage_path = out_dir / "column_coverage.json"
    assert coverage_path.exists()
    coverage_payload = _load_json(coverage_path)
    assert len(coverage_payload["kept"]) + len(coverage_payload["dropped"]) == coverage_payload["total_columns"]
    quality_report = _load_json(out_dir / "quality_report.json")
    assert "excluded_columns" in quality_report
    gate_payload = _load_json(out_dir / "gate.json")
    assert gate_payload["low_signal_candidates"] == 0


def test_preflight_stop_on_missing(tmp_path: Path) -> None:
    features = _build_features().with_columns(pl.lit(None).alias("DELIVERED"))
    result, out_dir = _run_stage(tmp_path, "run_preflight", features=features)
    assert result["status"] == "STOP"
    gate = _load_json(out_dir / "gate.json")
    assert gate["status"] == "STOP"
    assert any("missing ratio" in reason for reason in gate["reasons"])
    coverage_path = out_dir / "column_coverage.json"
    assert coverage_path.exists()
    diagnostics = _load_json(out_dir / "diagnostics.json")
    assert "coverage_report" in diagnostics


def test_geo_columns_relaxed_threshold(tmp_path: Path) -> None:
    base_features = _build_features()
    latitude_series = pl.Series("LATITUDE", [None, None, None, 24.5, None, None, 24.2, None])
    longitude_series = pl.Series("LONGITUDE", [None, None, None, 46.7, None, None, 46.5, None])
    features = base_features.with_columns(latitude_series, longitude_series)
    correlations = _build_correlations() + [
        {"kpi": "DELIVERED", "feature": "LATITUDE", "rel_key": "DELIVERED|LATITUDE"},
        {"kpi": "DELIVERED", "feature": "LONGITUDE", "rel_key": "DELIVERED|LONGITUDE"},
    ]
    result, out_dir = _run_stage(tmp_path, "run_geo_relaxed", features=features, correlations=correlations)
    assert result["status"] != "STOP"
    gate = _load_json(out_dir / "gate.json")
    assert gate["status"] != "STOP"
    diagnostics = _load_json(out_dir / "diagnostics.json")
    assert math.isclose(float(diagnostics["coverage_report"]["threshold"]), 0.9, rel_tol=1e-6)


def test_small_n_blocks_official(tmp_path: Path) -> None:
    run_id = "run_smalln"
    config: Dict[str, Any] = {"n_min_per_segment": 500}  # force small_n flag
    result, out_dir = _run_stage(tmp_path, run_id, config=config)
    assert result["status"] == "STOP"
    gate = _load_json(out_dir / "gate.json")
    assert gate["counts"]["emitted"] == 0


def test_low_signal_candidates_trigger_warn(tmp_path: Path) -> None:
    correlations: list[Dict[str, Any]] = [
        {
            "kpi": "DELIVERED",
            "feature": "IS_COD",
            "rel_key": "DELIVERED|IS_COD",
            "r": 0.05,
            "n": 120,
            "source": "kpi_fallback_low_signal",
            "low_signal": True,
            "note": "abs(r)=0.050 below threshold",
        }
    ]
    result, out_dir = _run_stage(
        tmp_path,
        "run_low_signal",
        correlations=correlations,
        redundancy={},
        features=_build_low_signal_features(),
    )
    assert result["status"] == "WARN"
    gate = _load_json(out_dir / "gate.json")
    assert gate["status"] == "WARN"
    assert gate["low_signal_candidates"] >= 1
    diagnostics = _load_json(out_dir / "diagnostics.json")
    assert diagnostics["counts"]["low_signal"] >= 1
    candidates = _load_json(out_dir / "insights_candidates.json")["candidates"]
    assert candidates
    logs_content = (out_dir / "logs.jsonl").read_text(encoding="utf-8")
    assert '"low_signal_fallback"' in logs_content


def test_no_correlations_emits_warn(tmp_path: Path) -> None:
    result, out_dir = _run_stage(
        tmp_path,
        "run_no_corr",
        correlations=[],
        redundancy={},
    )
    assert result["status"] == "WARN"
    gate = _load_json(out_dir / "gate.json")
    assert gate["status"] == "WARN"
    assert gate["counts"]["all"] == 0
    assert any("No correlation signals" in reason for reason in gate["reasons"])
    insights_payload = _load_json(out_dir / "insights_report.json")
    assert insights_payload["summary"]["official_count"] == 0

def test_text_stats_mask_pii(tmp_path: Path) -> None:
    _, out_dir = _run_stage(tmp_path, "run_text")
    text_stats = _load_json(out_dir / "text_stats.json")
    notes = text_stats["columns"]["NOTES"]["top_tokens"]
    tokens = {entry["token"] for entry in notes}
    assert "[PII]" in tokens


def test_sampling_info_present_when_threshold_lowered(tmp_path: Path) -> None:
    config: Dict[str, Any] = {"sampling_threshold_rows": 4, "sample_fraction": 0.5}
    _, out_dir = _run_stage(tmp_path, "run_sampling", config=config)
    diagnostics = _load_json(out_dir / "diagnostics.json")
    sampling = diagnostics["sampling"]
    assert sampling["enabled"] is True
    assert sampling["population_rows"] > sampling["sampled_rows"]
    logs = (out_dir / "logs.jsonl").read_text(encoding="utf-8")
    assert '"event": "env_info"' in logs
    assert '"event": "column_screen"' in logs
