"""Compatibility shim that re-exports the backend pipeline API surface."""

from importlib import import_module

_backend_app = import_module("backend.src.app.services.pipeline_api.app")

for _name in dir(_backend_app):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_backend_app, _name)

del import_module, _backend_app, _name

__all__ = [name for name in globals() if not name.startswith("_")]
