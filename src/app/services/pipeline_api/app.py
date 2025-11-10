"""Compatibility shim for legacy pipeline API import path."""
from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any

_backend_module: ModuleType = import_module("backend.src.app.services.pipeline_api.app")
__all__ = list(getattr(_backend_module, "__all__", []))


def __getattr__(name: str) -> Any:  # pragma: no cover - thin shim
    value = getattr(_backend_module, name)
    globals()[name] = value
    if name not in __all__:
        __all__.append(name)
    return value


def __dir__() -> list[str]:  # pragma: no cover - debug aid
    return sorted(set(__all__) | set(dir(_backend_module)))
