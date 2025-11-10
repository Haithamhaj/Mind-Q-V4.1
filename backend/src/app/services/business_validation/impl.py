"""Business validation service facade wrapping legacy phase implementation."""
from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Mapping, Optional

_legacy_impl = import_module("phases.09_business_validation.impl")
_legacy_models = import_module("phases.09_business_validation.models")

ValidationReport = getattr(_legacy_models, "ValidationReport")
OPS_ALIAS_CANDIDATES = getattr(_legacy_impl, "OPS_ALIAS_CANDIDATES")
_prepare_ops = getattr(_legacy_impl, "_prepare_ops")


def run_business_validation(
    run_id: str,
    inputs: Mapping[str, Any],
    config: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute the business validation phase using the legacy implementation."""

    return _legacy_impl.run(run_id, inputs, config)


__all__ = [
    "run_business_validation",
    "ValidationReport",
    "OPS_ALIAS_CANDIDATES",
    "_prepare_ops",
]
