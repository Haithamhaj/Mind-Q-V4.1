"""Compatibility layer for importing the pipeline FastAPI app."""

from __future__ import annotations

from typing import Any

__all__ = ["app"]


def __getattr__(name: str) -> Any:
    if name == "app":
        from .app import app as _app  # Local import to avoid circular dependency

        return _app
    raise AttributeError(name)
