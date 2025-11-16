from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional, Set

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACTS_ROOT = PROJECT_ROOT / "contracts"
DEFAULT_POLICY_PATH = CONTRACTS_ROOT / "nzv" / "policy.yml"


@dataclass(frozen=True)
class NZVPolicy:
    dominant_constant_like: float = 0.98
    dominant_nzv: float = 0.95
    dominant_high_imbalance: float = 0.90
    max_unique_for_nzv: int = 5
    min_rows_required: int = 50
    enable_readiness_adjustment: bool = True
    max_nzv_ratio_for_pass: float = 0.35
    force_nzv: Set[str] = field(default_factory=frozenset)
    force_not_nzv: Set[str] = field(default_factory=frozenset)
    special_columns: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


class PolicyLoadError(RuntimeError):
    """Raised when an NZV policy file cannot be parsed."""


def load_policy(path: Optional[Path] = None) -> NZVPolicy:
    """Return the NZV policy, reading and caching it from disk."""
    policy_path = Path(path) if path else DEFAULT_POLICY_PATH
    resolved = policy_path.expanduser().resolve()
    return _load_policy_from_disk(resolved)


def clear_policy_cache() -> None:
    """Clear the cached policy (useful for tests)."""
    _load_policy_from_disk.cache_clear()


@lru_cache(maxsize=4)
def _load_policy_from_disk(resolved_path: Path) -> NZVPolicy:
    if not resolved_path.exists():
        raise FileNotFoundError(f"NZV policy file not found: {resolved_path}")

    raw_data = resolved_path.read_text(encoding="utf-8")
    try:
        payload: MutableMapping[str, Any] = yaml.safe_load(raw_data) or {}
    except yaml.YAMLError as exc:  # pragma: no cover
        raise PolicyLoadError(f"Unable to parse NZV policy at {resolved_path}") from exc

    defaults = payload.get("defaults") or {}
    overrides = payload.get("overrides") or {}
    special_columns = payload.get("special_columns") or {}

    return NZVPolicy(
        dominant_constant_like=_coerce_float(defaults.get("dominant_constant_like"), 0.98),
        dominant_nzv=_coerce_float(defaults.get("dominant_nzv"), 0.95),
        dominant_high_imbalance=_coerce_float(defaults.get("dominant_high_imbalance"), 0.90),
        max_unique_for_nzv=_coerce_int(defaults.get("max_unique_for_nzv"), 5),
        min_rows_required=_coerce_int(defaults.get("min_rows_required"), 50),
        enable_readiness_adjustment=_coerce_bool(defaults.get("enable_readiness_adjustment"), True),
        max_nzv_ratio_for_pass=_coerce_float(defaults.get("max_nzv_ratio_for_pass"), 0.35),
        force_nzv=frozenset(_as_name_list(overrides.get("force_nzv"))),
        force_not_nzv=frozenset(_as_name_list(overrides.get("force_not_nzv"))),
        special_columns=_normalize_special_columns(special_columns),
    )


def classify_column(
    stats: Mapping[str, Any],
    *,
    policy: Optional[NZVPolicy] = None,
) -> Dict[str, Any]:
    """Classify a column based on summary stats."""
    active_policy = policy or load_policy()
    column_name = _extract_column_name(stats)

    if _coerce_bool(stats.get("force_not_nzv")) or (column_name and column_name in active_policy.force_not_nzv):
        return _classification("normal", False, "force_not_nzv")

    if _coerce_bool(stats.get("force_nzv")) or (column_name and column_name in active_policy.force_nzv):
        return _classification("near_zero_variance", True, "force_nzv")

    n_rows = _coerce_int(stats.get("n_rows"))
    if n_rows is not None and n_rows < active_policy.min_rows_required:
        return _classification(
            "normal",
            False,
            f"insufficient_rows<{active_policy.min_rows_required}",
        )

    dominant_pct = _coerce_float(stats.get("dominant_pct") or stats.get("dominant_ratio") or 0.0, 0.0)
    unique_count = _coerce_int(stats.get("unique_count"))

    if dominant_pct >= active_policy.dominant_constant_like:
        return _classification(
            "constant_like",
            True,
            f"dominant_pct>={_format_float(active_policy.dominant_constant_like)}",
        )

    meets_unique_guard = unique_count is None or unique_count <= active_policy.max_unique_for_nzv
    if dominant_pct >= active_policy.dominant_nzv and meets_unique_guard:
        reason = f"dominant_pct>={_format_float(active_policy.dominant_nzv)}"
        if unique_count is not None:
            reason = f"{reason},unique_count<={active_policy.max_unique_for_nzv}"
        return _classification("near_zero_variance", True, reason)

    if dominant_pct >= active_policy.dominant_high_imbalance:
        return _classification(
            "high_imbalance",
            False,
            f"dominant_pct>={_format_float(active_policy.dominant_high_imbalance)}",
        )

    return _classification("normal", False, "no_threshold_matched")


def _classification(nzv_category: str, is_nzv: bool, reason: str) -> Dict[str, Any]:
    return {"nzv_category": nzv_category, "is_nzv": is_nzv, "reason": reason}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
        return default
    return bool(value)


def _as_name_list(value: Any) -> Set[str]:
    if not value:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, Mapping):
        return {str(item) for item in value.values()}
    try:
        return {str(item) for item in value}
    except TypeError:
        return {str(value)}


def _normalize_special_columns(payload: Any) -> Mapping[str, tuple[str, ...]]:
    if not isinstance(payload, Mapping):
        if not payload:
            return {}
        return {"default": tuple(sorted(_as_name_list(payload)))}

    normalized: Dict[str, tuple[str, ...]] = {}
    for key, items in payload.items():
        normalized[str(key)] = tuple(sorted(_as_name_list(items)))
    return normalized


def _extract_column_name(stats: Mapping[str, Any]) -> Optional[str]:
    for key in ("name", "column", "column_name", "feature"):
        value = stats.get(key)
        if value:
            return str(value)
    return None


def _format_float(value: float) -> str:
    formatted = f"{value:.3f}"
    return formatted.rstrip("0").rstrip(".") if "." in formatted else formatted
