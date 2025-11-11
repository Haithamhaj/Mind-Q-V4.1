# one-way shim to backend; avoid circular imports
from importlib import import_module as _im
from typing import Any

_b = _im("backend.src.app.pipeline_api")
app = _b.app
PipelineRequest = _b.PipelineRequest
PipelineResponse = _b.PipelineResponse
run_pipeline = _b.run_pipeline

__all__ = ["app", "PipelineRequest", "PipelineResponse", "run_pipeline"]


def __getattr__(name: str) -> Any:
    return getattr(_b, name)
