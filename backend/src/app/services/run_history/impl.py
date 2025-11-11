"""Run history helpers exposed for tests and tooling."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union

from backend.src.app.pipeline_api.app import _purge_run_history as _legacy_purge
from backend.src.app.pipeline_api.timeline import build_run_timeline

PathLike = Union[str, Path]


def _normalize_root(root: Optional[PathLike]) -> Path:
    if root is None:
        return Path("artifacts").resolve()
    return Path(root).expanduser().resolve()


def purge_run_history(current_run_id: str, artifacts_root: PathLike, *, force: bool = False) -> None:
    """Remove historical runs from the provided artifacts root."""

    root = _normalize_root(artifacts_root)
    _legacy_purge(current_run_id, root, force=force)


def get_run_timeline(run_id: str, artifacts_root: Optional[PathLike] = None) -> Dict[str, Any]:
    """Return the run timeline JSON payload."""

    root = _normalize_root(artifacts_root)
    return build_run_timeline(run_id, root)


__all__ = ["purge_run_history", "get_run_timeline"]
