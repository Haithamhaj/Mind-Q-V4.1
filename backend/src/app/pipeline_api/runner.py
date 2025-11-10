"""Thin wrappers for invoking pipeline phases outside FastAPI."""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.app.services.pipeline_api import _run_phase10


def run_pipeline(run_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute the BI builder pipeline for the provided run.

    Parameters
    ----------
    run_id:
        Identifier of the pipeline run whose artifacts should be processed.
    config:
        Optional configuration payload (e.g. `{"artifacts_root": "..."}`).
    """

    payload: Dict[str, Any] = dict(config or {})
    return _run_phase10(run_id, payload)


__all__ = ["run_pipeline"]
