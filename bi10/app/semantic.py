from __future__ import annotations

import pathlib
import yaml
from typing import Any, Dict, Tuple
from jsonschema import validate

from .schema_metrics import METRICS_SCHEMA

_cache: Dict[str, Any] = {"key": None, "data": None}


def _cache_key(path: pathlib.Path) -> Tuple[str, float]:
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        mtime = 0.0
    return (str(path), mtime)


def load_semantic(run_id: str, root: str) -> Dict[str, Any]:
    path = pathlib.Path(root) / run_id / "stage_10_bi" / "semantic" / "metrics.yaml"
    key = _cache_key(path)
    if _cache.get("key") == key and _cache.get("data") is not None:
        return _cache["data"]
    if not path.exists():
        raise FileNotFoundError(f"semantic metrics.yaml missing at {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    validate(instance=payload, schema=METRICS_SCHEMA)
    _cache["key"] = key
    _cache["data"] = payload
    return payload


__all__ = ["load_semantic"]
