#!/usr/bin/env python3
"""Generate a lightweight size report for Stage 08/09 outputs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

STAGES = ("stage_08_insights", "stage_09_business_validation")


def _collect_sizes(run_dir: Path, stage: str) -> Dict[str, int]:
    stage_dir = run_dir / stage
    sizes: Dict[str, int] = {}
    if not stage_dir.exists():
        return sizes
    for path in stage_dir.rglob("*"):
        if path.is_file():
            try:
                sizes[str(path.relative_to(run_dir))] = path.stat().st_size
            except OSError:
                continue
    return sizes


def main() -> int:
    artifacts_root = Path("artifacts").resolve()
    report: Dict[str, Dict[str, Dict[str, int]]] = {}
    if artifacts_root.exists():
        for run_dir in artifacts_root.iterdir():
            if not run_dir.is_dir():
                continue
            run_entry: Dict[str, Dict[str, int]] = {}
            for stage in STAGES:
                sizes = _collect_sizes(run_dir, stage)
                if sizes:
                    run_entry[stage] = sizes
            if run_entry:
                report[run_dir.name] = run_entry
    output = artifacts_root / "reports" / "stage_size_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "runs": report,
        "notes": "Empty runs indicate that no stage outputs were materialized in this workspace yet.",
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Stage size report written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
