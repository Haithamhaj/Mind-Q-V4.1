"""Legacy shim exposing pipeline API from the canonical backend package."""

from backend.src.app import pipeline_api as _pipeline_module

app = _pipeline_module.app
fastapi_app = app

__all__ = ["app", "fastapi_app"]