from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

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


llm_summary = _load_phase_impl("07_6_llm_summary")  # type: ignore


def _emit_json(payload: Any) -> None:
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _configure_io() -> None:
    if not os.environ.get("PYTHONUTF8"):
        os.environ["PYTHONUTF8"] = "1"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        if platform.system() == "Windows":
            subprocess.run(["chcp", "65001"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _load_dotenv() -> None:
    candidates = [PROJECT_ROOT / ".env", PROJECT_ROOT / ".env.txt"]
    env_path = next((path for path in candidates if path.exists()), None)
    if env_path is None:
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Stage 07.6 LLM executive summary")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier")
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Root directory for pipeline artifacts (default: artifacts)",
    )
    parser.add_argument(
        "--report-path",
        help="Override path to Stage 07.5 report.json (default resolves from artifacts)",
    )
    parser.add_argument(
        "--kpis-path",
        help="Optional override for contracts/kpis.yml",
    )
    parser.add_argument("--llm-provider", default="openai", help="LLM provider (openai|gemini|anthropic)")
    parser.add_argument("--llm-model", help="Provider model identifier")
    parser.add_argument("--max-tokens", type=int, default=1200, help="Maximum output tokens (default: 1200)")
    parser.add_argument("--temperature", type=float, default=0.1, help="Sampling temperature (default: 0.1)")
    parser.add_argument("--top-p", type=float, default=0.0, help="Top-p nucleus sampling (default: 0.0)")
    parser.add_argument("--focus-cols", help="Optional comma separated columns to prioritize")
    parser.add_argument("--exclude-cols", help="Optional comma separated columns to forbid")
    parser.add_argument("--budget-usd", type=float, default=0.50, help="Maximum spend for the call (default: 0.50)")
    return parser.parse_args()


def resolve_paths(run_id: str, artifacts_root: Path, args: argparse.Namespace) -> tuple[Path, Optional[Path]]:
    report = (
        Path(args.report_path).expanduser().resolve()
        if args.report_path
        else artifacts_root / run_id / "stage_07_5_feature_report" / "report.json"
    )
    kpis = (
        Path(args.kpis_path).expanduser().resolve()
        if args.kpis_path
        else PROJECT_ROOT / "contracts" / "kpis.yml"
    )
    if not kpis.exists():
        kpis = None
    return report, kpis


def main() -> int:
    _configure_io()
    _load_dotenv()
    args = parse_args()
    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    report_path, kpis_path = resolve_paths(args.run_id, artifacts_root, args)

    inputs = {
        "report": report_path.as_posix(),
    }
    if kpis_path:
        inputs["kpis"] = kpis_path.as_posix()

    cfg = {
        "artifacts_root": artifacts_root.as_posix(),
        "llm_provider": args.llm_provider,
        "llm_model": args.llm_model,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "focus_cols": args.focus_cols,
        "exclude_cols": args.exclude_cols,
        "budget_usd": args.budget_usd,
    }
    result = llm_summary.run(args.run_id, inputs, cfg)  # type: ignore[arg-type]
    _emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
