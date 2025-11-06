from __future__ import annotations

import argparse
import json
import importlib.util
import sys
import hashlib
import shutil
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(f"Unable to locate implementation for phase directory '{phase_dir}'")


readiness = _load_phase_impl("07_readiness")  # type: ignore


def _emit_json(payload: Any) -> None:
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 07 readiness checks")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier")
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Root directory for pipeline artifacts (default: artifacts)",
    )
    parser.add_argument(
        "--features-path",
        help="Override path to features parquet (defaults to stage_06_standardize/features.pre.parquet)",
    )
    return parser.parse_args()


def resolve_features_path(run_id: str, artifacts_root: Path, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return artifacts_root / run_id / "stage_06_feature_eng" / "features.parquet"


def main() -> int:
    args = parse_args()
    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    features_path = resolve_features_path(args.run_id, artifacts_root, args.features_path)
    if not features_path.exists():
        raise FileNotFoundError(f"Features parquet not found: {features_path}")

    cfg: Dict[str, Any] = {"artifacts_root": artifacts_root.as_posix()}
    inputs: Dict[str, Any] = {"raw": features_path.as_posix()}
    result: Dict[str, Any] = readiness.run(args.run_id, inputs, cfg)  # type: ignore[assignment]
    _emit_json(result)

    outputs = result.get("outputs", {}) or {}
    corr_kpi_path = Path(outputs.get("correlations_kpi", ""))
    corr_path = Path(outputs.get("correlations", ""))
    logs_path = Path(result.get("logs_uri", ""))

    preview: Any = "<not_available>"
    if corr_kpi_path.exists():
        try:
            rows = json.loads(corr_kpi_path.read_text(encoding="utf-8"))
            preview = rows[:3] if isinstance(rows, list) else rows
        except Exception as exc:  # pragma: no cover - diagnostic print only
            preview = f"<unable to load correlations_kpi.json: {exc}>"

    corr_hash = None
    if corr_path.exists():
        corr_hash = hashlib.sha256(corr_path.read_bytes()).hexdigest()

    fallback_events: list[Dict[str, Any]] = []
    if logs_path.exists():
        try:
            for line in logs_path.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                record = json.loads(line)
                if record.get("event") == "kpi_fallback":
                    fallback_events.append(record)
        except Exception:
            fallback_events = []

    per_kpi = [
        {
            "kpi": event.get("kpi"),
            "added": event.get("added"),
            "candidates": event.get("candidates"),
            "severity": event.get("severity"),
        }
        for event in fallback_events
        if event.get("kpi") or event.get("severity")
    ]

    _emit_json({
        "correlations_kpi_path": corr_kpi_path.as_posix() if corr_kpi_path.exists() else None,
        "preview": preview,
        "correlations_sha256": corr_hash,
        "kpi_fallback_events": per_kpi,
    })

    # Ensure bridge directory (stage_07_correlations) mirrors latest readiness outputs for downstream phases
    bridge_dir = artifacts_root / args.run_id / "stage_07_correlations"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    readiness_outputs = {
        "correlations.json": outputs.get("correlations"),
        "correlations_kpi.json": outputs.get("correlations_kpi"),
        "redundancy.json": outputs.get("redundancy"),
    }
    readiness_dir = artifacts_root / args.run_id / "stage_07_readiness"
    for name, supplied_path in readiness_outputs.items():
        src = None
        if supplied_path:
            candidate = Path(supplied_path)
            if candidate.exists():
                src = candidate
        if src is None:
            fallback = readiness_dir / name
            if fallback.exists():
                src = fallback
        if src is not None:
            try:
                shutil.copy2(src, bridge_dir / name)
            except Exception:
                continue

    return 0 if result.get("status") != "STOP" else 1


if __name__ == "__main__":
    raise SystemExit(main())
