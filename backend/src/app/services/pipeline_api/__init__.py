"""Expose pipeline API application under the backend namespace."""

import sys
from importlib import import_module

_pipeline_module = import_module("src.app.services.pipeline_api.app")
sys.modules[__name__ + ".app"] = _pipeline_module
fastapi_app = _pipeline_module.app  # type: ignore[attr-defined]
app = fastapi_app

__all__ = ["fastapi_app", "app"]
