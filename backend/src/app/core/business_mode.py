from __future__ import annotations

import os
from enum import Enum


class BusinessMode(str, Enum):
    STRICT_LAB = "strict_lab"
    BUSINESS_FIRST = "business_first"


def get_business_mode() -> BusinessMode:
    """Read the current business mode from the environment."""
    default_mode = BusinessMode.BUSINESS_FIRST
    raw = os.getenv("MINDQ_BUSINESS_MODE")
    if raw is None:
        return default_mode
    normalized = raw.strip().lower()
    try:
        return BusinessMode(normalized)
    except ValueError:
        return default_mode


def is_business_first() -> bool:
    return get_business_mode() == BusinessMode.BUSINESS_FIRST


__all__ = ["BusinessMode", "get_business_mode", "is_business_first"]
