from __future__ import annotations

import pathlib
from typing import List, Tuple

from .config import settings
from .semantic import load_semantic


def preflight(run_id: str = settings.default_run_id) -> None:
    semantic = load_semantic(run_id, settings.artifacts_root)
    mart_dir = pathlib.Path(settings.artifacts_root) / run_id / "stage_10_bi" / "marts"
    missing: List[Tuple[str, str]] = []
    for mart in semantic.get("marts", []):
        mart_id = mart.get("id")
        for file_name in mart.get("files", []):
            path = mart_dir / file_name
            if not path.exists():
                missing.append((mart_id, file_name))
    if missing:
        raise SystemExit(f"Missing mart files: {missing}")
    print("Preflight OK.")


if __name__ == "__main__":
    preflight()
