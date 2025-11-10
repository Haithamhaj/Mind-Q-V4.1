from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import threading

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PARAMS_PATH = _PROJECT_ROOT / "config" / "params.yml"
_CACHE_LOCK = threading.Lock()


def _coerce_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        if "value" in value:
            return value["value"]
    return value


@lru_cache(maxsize=1)
def _raw_params() -> Dict[str, Any]:
    if not _PARAMS_PATH.exists():
        return {}
    try:
        payload = yaml.safe_load(_PARAMS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def reload() -> None:
    with _CACHE_LOCK:
        _raw_params.cache_clear()


def load_params() -> Dict[str, Any]:
    data = _raw_params()
    return {key: _coerce_value(value) for key, value in data.items()}


def get_param(key: str, default: Any = None, *, coerce: Optional[type] = None) -> Any:
    curr: Any = load_params()
    for part in key.split('.'):
        if isinstance(curr, Mapping) and part in curr:
            curr = curr[part]
        else:
            return default
    curr = _coerce_value(curr)
    if curr is None:
        return default
    if coerce is not None:
        try:
            return coerce(curr)
        except (TypeError, ValueError):
            return default
    return curr


__all__ = ["get_param", "load_params", "reload"]
