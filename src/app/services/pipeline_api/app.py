"""Compatibility shim that re-exports the backend pipeline API surface."""

from backend.src.app.services.pipeline_api.app import *  # noqa: F401, F403
from backend.src.app.services.pipeline_api.app import app  # noqa: F401
