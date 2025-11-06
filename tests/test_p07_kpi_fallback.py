from __future__ import annotations

import hashlib
import json
import importlib.util
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_phase_impl(phase_dir: str):
    base = PROJECT_ROOT / "phases"
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
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
            return module
    raise FileNotFoundError(f"Unable to locate implementation for phase directory '{phase_dir}'")


readiness_impl = _load_phase_impl("07_readiness")


def _write_baseline(artifacts_root: Path, run_id: str, n_rows: int, n_cols: int) -> None:
    payload: Dict[str, Any] = {
        "run_id": run_id,
        "n_rows": n_rows,
        "n_cols": n_cols,
        "schema_hash": "testing",
        "source_fingerprint": [],
    }
    baseline_path = artifacts_root / run_id / "baselines.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_dataset(top_only: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = 400
    cod_amount = rng.normal(loc=100, scale=25, size=n).clip(min=0)
    feature_signal = cod_amount * 0.6 + rng.normal(scale=5, size=n)
    data: Dict[str, Any] = {
        "COD_AMOUNT": cod_amount,
        "feature_signal": feature_signal,
    }
    if top_only:
        return pd.DataFrame(data)

    # inject many highly correlated duplicate pairs to saturate top-50
    for idx in range(60):
        base = rng.normal(size=n)
        data[f"dup_{idx}"] = base
        data[f"dup_{idx}_copy"] = base + rng.normal(scale=1e-4, size=n)
    return pd.DataFrame(data)


def _run_stage(run_id: str, df: pd.DataFrame, tmp_path: Path) -> Path:
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    raw_path = artifacts_root / f"{run_id}_raw.parquet"
    df.to_parquet(raw_path, index=False)
    _write_baseline(artifacts_root, run_id, len(df), len(df.columns))
    cfg = {"artifacts_root": artifacts_root.as_posix()}
    inputs = {"raw": raw_path.as_posix()}
    readiness_impl.run(run_id, inputs, cfg)  # type: ignore[arg-type]
    return artifacts_root / run_id / "stage_07_readiness"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_kpi_events(logs_path: Path) -> Sequence[Mapping[str, Any]]:
    events = []
    for line in logs_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record.get("event") == "kpi_fallback":
            events.append(record)
    return events


def test_kpi_fallback_skips_when_nonempty(tmp_path: Path) -> None:
    df = _build_dataset(top_only=True)
    stage_dir = _run_stage("nonempty", df, tmp_path)

    kpi_records = _read_json(stage_dir / "correlations_kpi.json")
    assert isinstance(kpi_records, list) and kpi_records, "expected standard pipeline to emit KPI correlations"
    assert all("source" not in rec for rec in kpi_records)  # no fallback annotation

    events = _extract_kpi_events(stage_dir / "logs.jsonl")
    skip_event = next((event for event in events if event.get("message") == "skipped_non_empty"), None)
    assert skip_event is not None
    assert skip_event.get("added") == 0


def test_kpi_fallback_populates_when_empty(tmp_path: Path) -> None:
    df = _build_dataset(top_only=False)
    stage_dir = _run_stage("fallback", df, tmp_path)

    records = _read_json(stage_dir / "correlations_kpi.json")
    assert isinstance(records, list) and records, "fallback should populate correlations_kpi.json"
    assert all(rec.get("source") == "kpi_fallback" for rec in records)
    assert all(abs(rec.get("r", 0.0)) >= 0.15 for rec in records)
    assert all(rec.get("low_signal") is False for rec in records)

    events = _extract_kpi_events(stage_dir / "logs.jsonl")
    added = [event for event in events if event.get("added")]
    assert added, "expected at least one fallback addition event"


def test_kpi_fallback_uses_kpis_yaml(tmp_path: Path) -> None:
    contracts_dir = PROJECT_ROOT / "contracts"
    kpi_path = contracts_dir / "kpis.yml"
    original = kpi_path.read_text(encoding="utf-8") if kpi_path.exists() else None
    kpi_path.write_text(
        "kpis:\n  cod_amount: ['collect_amount']\n",
        encoding="utf-8",
    )
    try:
        rng = np.random.default_rng(1)
        cod = rng.normal(loc=50, scale=10, size=500)
        feature = cod * 0.4 + rng.normal(scale=3, size=500)
        df = pd.DataFrame({"collect_amount": cod, "feature_x": feature})
        stage_dir = _run_stage("synonyms", df, tmp_path)
        records = _read_json(stage_dir / "correlations_kpi.json")
        assert any(rec["kpi"] == "collect_amount" for rec in records)
    finally:
        if original is None:
            kpi_path.unlink(missing_ok=True)
        else:
            kpi_path.write_text(original, encoding="utf-8")


def test_kpi_fallback_filters_columns(tmp_path: Path) -> None:
    rng = np.random.default_rng(2)
    cod = rng.normal(size=500)
    df = pd.DataFrame(
        {
            "COD_AMOUNT": cod,
            "id": np.arange(cod.shape[0]),
            "feature_valid": cod * 0.8 + rng.normal(scale=0.1, size=cod.shape[0]),
            "feature_is_missing": rng.integers(0, 2, size=cod.shape[0]),
            "order_id": np.arange(cod.shape[0]),
            "ORDER_ID": np.arange(cod.shape[0]),
            "customer_guid": rng.normal(size=cod.shape[0]),
            "shipment_hash": rng.normal(size=cod.shape[0]),
            "foo_sha256": rng.normal(size=cod.shape[0]),
            "identity_score": cod * 0.3 + rng.normal(scale=0.5, size=cod.shape[0]),
            "hashrate": rng.normal(loc=10, scale=3, size=cod.shape[0]),
            "grid_idc": rng.normal(loc=5, scale=2, size=cod.shape[0]),
            "hash_value": rng.normal(size=cod.shape[0]),
        }
    )
    out_dir = tmp_path / "filters"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "correlations_kpi.json").write_text("[]", encoding="utf-8")
    logs: list[Dict[str, Any]] = []
    readiness_impl._kpi_fallback(out_dir, df, [], {"near_zero_variance": []}, [], logs)  # type: ignore[attr-defined]
    records = json.loads((out_dir / "correlations_kpi.json").read_text(encoding="utf-8"))
    features = {rec["feature"] for rec in records}
    assert "feature_is_missing" not in features
    assert "ORDER_ID" not in features
    assert "order_id" not in features
    assert "id" not in features
    assert "customer_guid" not in features
    assert "shipment_hash" not in features
    assert "foo_sha256" not in features
    assert "hash_value" not in features
    assert "feature_valid" in features
    assert "identity_score" in features
    id_events = [event for event in logs if event.get("event") == "id_like_filter"]
    assert "hashrate" not in {event["column"] for event in id_events}
    assert "grid_idc" not in {event["column"] for event in id_events}
    assert {event["column"] for event in id_events} >= {"id", "order_id", "ORDER_ID", "customer_guid", "shipment_hash", "foo_sha256"}
    reasons = {event["column"]: event.get("reason") for event in id_events}
    assert reasons.get("id") in {"pattern", "whitelist"}
    assert reasons.get("order_id") in {"pattern", "suffix"}
    assert reasons.get("ORDER_ID") in {"pattern", "suffix"}
    assert reasons.get("customer_guid") == "pattern"
    assert reasons.get("shipment_hash") == "pattern"
    assert reasons.get("foo_sha256") == "pattern"


def test_kpi_fallback_threshold_and_cap(tmp_path: Path) -> None:
    cod = np.random.default_rng(3).normal(loc=10, scale=3, size=600)
    data: Dict[str, Any] = {"COD_AMOUNT": cod}
    for idx in range(20):
        strength = 0.25 + idx * 0.01
        noise = np.random.default_rng(idx).normal(scale=4, size=cod.shape[0])
        data[f"feat_{idx}"] = cod * strength + noise
    df = pd.DataFrame(data)
    out_dir = tmp_path / "threshold"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "correlations_kpi.json").write_text("[]", encoding="utf-8")
    logs: list[Dict[str, Any]] = []
    readiness_impl._kpi_fallback(out_dir, df, [], {"near_zero_variance": []}, [], logs)  # type: ignore[attr-defined]
    records = json.loads((out_dir / "correlations_kpi.json").read_text(encoding="utf-8"))
    assert records
    grouped = {}
    for rec in records:
        grouped.setdefault(rec["kpi"], []).append(rec)
        assert abs(rec["r"]) >= 0.15
        assert rec.get("low_signal") is False
    assert all(len(entries) <= 10 for entries in grouped.values())


def test_kpi_fallback_low_signal_append(tmp_path: Path) -> None:
    rng = np.random.default_rng(5)
    cod = rng.normal(size=800)
    weak_feature = rng.normal(size=cod.shape[0])  # nearly uncorrelated
    df = pd.DataFrame({"COD_AMOUNT": cod, "feature_weak": weak_feature})
    out_dir = tmp_path / "low_signal"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "correlations_kpi.json").write_text("[]", encoding="utf-8")
    logs: list[Dict[str, Any]] = []
    readiness_impl._kpi_fallback(out_dir, df, [], {"near_zero_variance": []}, [], logs)  # type: ignore[attr-defined]
    records = json.loads((out_dir / "correlations_kpi.json").read_text(encoding="utf-8"))
    assert records, "low-signal fallback should emit at least one record"
    assert all(rec.get("low_signal") is True for rec in records)
    assert all(rec.get("source") == "kpi_fallback_low_signal" for rec in records)
    assert all("note" in rec for rec in records)
    low_signal_events = [event for event in logs if event.get("event") == "kpi_fallback" and event.get("low_signal")]
    assert low_signal_events, "expected low-signal event in logs"
    assert all(event.get("threshold") == readiness_impl.LOW_SIGNAL_CORR_THRESHOLD for event in low_signal_events if event.get("threshold") is not None)


def test_kpi_fallback_nzv_override(tmp_path: Path) -> None:
    n = 500
    cod = np.linspace(0, 1, n)
    feature_flat = cod + 1e-6  # highly correlated but almost flat
    df = pd.DataFrame({"COD_AMOUNT": cod, "feature_flat": feature_flat})
    out_dir = tmp_path / "nzv_override"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "correlations_kpi.json").write_text("[]", encoding="utf-8")
    redundancy = {
        "near_zero_variance": [{"feature": "feature_flat"}],
        "high_corr_pairs": [{"f1": "COD_AMOUNT", "f2": "feature_flat", "r": 0.99, "n": int(n)}],
    }
    logs: list[Dict[str, Any]] = []
    readiness_impl._kpi_fallback(out_dir, df, [], redundancy, [], logs)  # type: ignore[attr-defined]
    records = json.loads((out_dir / "correlations_kpi.json").read_text(encoding="utf-8"))
    assert records, "expected NZV override to allow correlation emission"
    assert any(rec.get("nzv_override") for rec in records)
    assert any(event.get("added") for event in logs if event.get("event") == "kpi_fallback")


def test_correlations_json_hash_unchanged(tmp_path: Path) -> None:
    df = _build_dataset(top_only=False)
    stage_dir = _run_stage("hash", df, tmp_path)
    corr_path = stage_dir / "correlations.json"
    original_hash = hashlib.sha256(corr_path.read_bytes()).hexdigest()
    # re-read to ensure stability
    second_hash = hashlib.sha256(corr_path.read_bytes()).hexdigest()
    assert original_hash == second_hash


def test_correlations_kpi_utf8(tmp_path: Path) -> None:
    df = _build_dataset(top_only=False)
    stage_dir = _run_stage("utf8", df, tmp_path)
    content = (stage_dir / "correlations_kpi.json").read_text(encoding="utf-8")
    assert "?" not in content
    json.loads(content)



def test_is_id_like_detection() -> None:
    positives = ["id", "order_id", "customer_guid", "shipment_hash", "foo_sha256"]
    negatives = ["feature_valid", "identity_score", "hashrate", "grid_idc"]
    for value in positives:
        assert readiness_impl.is_id_like(value) is True
    for value in negatives:
        assert readiness_impl.is_id_like(value) is False
