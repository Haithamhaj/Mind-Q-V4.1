"""Expose pipeline API application under the backend namespace."""

from .app import app as fastapi_app  # noqa: F401

app = fastapi_app

__all__ = ["fastapi_app", "app"]
