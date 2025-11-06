from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_POLICY_PATH = PROJECT_ROOT / "contracts" / "impute" / "policy.yml"


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


missing = _load_phase_impl("05_missing")  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 05 missing-data imputation")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier")
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Root directory for pipeline artifacts (default: artifacts)",
    )
    parser.add_argument(
        "--raw-path",
        help="Override path to raw parquet (defaults to stage_01_ingestion/raw.parquet)",
    )
    parser.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY_PATH),
        help="Path to default imputation policy YAML (default: contracts/impute/policy.yml)",
    )
    parser.add_argument(
        "--strategy",
        choices=["baseline", "groupwise", "hybrid"],
        help="Override strategy selection for auto-plan builder",
    )
    return parser.parse_args()


def resolve_raw_path(run_id: str, artifacts_root: Path, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return artifacts_root / run_id / "stage_01_ingestion" / "raw.parquet"


def _missing_cfg(policy_path: Path, strategy: str | None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"policy_path": policy_path.as_posix()}
    if strategy:
        payload["strategy_override"] = strategy.lower()
    return payload


def _format_summary(metrics: Dict[str, Any]) -> str:
    psi = metrics.get("psi") or {}
    summary_bits = [
        f"cols_changed={metrics.get('cols_changed_count', 0)}",
        f"rows_imputed={metrics.get('rows_imputed_total', 0)}",
        f"psi_warn={len(psi.get('warn', []))}",
        f"psi_stop={len(psi.get('stop', []))}",
    ]
    return ", ".join(summary_bits)


def main() -> int:
    args = parse_args()
    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    raw_path = resolve_raw_path(args.run_id, artifacts_root, args.raw_path)
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw parquet not found: {raw_path}")

    policy_path = Path(args.policy).expanduser()
    cfg: Dict[str, Any] = {
        "artifacts_root": artifacts_root.as_posix(),
        "missing": _missing_cfg(policy_path, args.strategy),
    }
    inputs: Dict[str, Any] = {"raw": raw_path.as_posix()}
    result: Dict[str, Any] = missing.run(args.run_id, inputs, cfg)  # type: ignore[assignment]

    status = str(result.get("status", "PASS")).upper()
    metrics = result.get("metrics") or {}
    summary = _format_summary(metrics)
    print(f"[MISSING] {status}: {summary}")

    exit_map = {"PASS": 0, "WARN": 1, "STOP": 2}
    return exit_map.get(status, 1)


if __name__ == "__main__":
    raise SystemExit(main())
