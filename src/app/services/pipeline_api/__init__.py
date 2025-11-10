"""Public surface for pipeline APIs without tying consumers to FastAPI internals."""
from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any

from . import app as _shim  # noqa: F401  # re-exported for backwards compatibility

_PIPELINE_MODULE: ModuleType = import_module("src.app.services.pipeline_api.app")
app = getattr(_PIPELINE_MODULE, "app")  # FastAPI app exposed for server entrypoints

__all__ = list(getattr(_PIPELINE_MODULE, "__all__", []))
if "app" not in __all__:
    __all__.append("app")


def __getattr__(name: str) -> Any:  # pragma: no cover - passthrough
    return getattr(_PIPELINE_MODULE, name)


def __dir__() -> list[str]:  # pragma: no cover - debug aid
    return sorted(set(__all__) | set(dir(_PIPELINE_MODULE)))
