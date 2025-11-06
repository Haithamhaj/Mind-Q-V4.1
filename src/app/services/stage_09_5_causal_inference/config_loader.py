from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional

import yaml  # type: ignore


class InvalidConfigError(ValueError):
    """Raised when the causal problem YAML is invalid or missing required keys."""


@dataclass(frozen=True)
class CausalConfig:
    problem_name: str
    description: str
    treatment: str
    outcome: str
    common_causes: List[str] = field(default_factory=list)
    effect_modifiers: List[str] = field(default_factory=list)
    instrumental_variables: List[str] = field(default_factory=list)
    frontdoor_variables: List[str] = field(default_factory=list)
    min_sample_size: int = 0
    confidence_level: float = 0.95
    test_size: float = 0.3
    estimation_methods: List[str] = field(default_factory=list)
    refutation_tests: List[str] = field(default_factory=list)
    bi_publish_rule: str = "SUPPORTED_ONLY"

    def as_dict(self) -> Mapping[str, Any]:
        return asdict(self)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = unicodedata.normalize("NFC", value)
    return value.strip()


def _ensure_list(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        return [_normalize_text(values)]
    if isinstance(values, Iterable):
        normalized: List[str] = []
        for item in values:
            text = _normalize_text(item)
            if text:
                normalized.append(text)
        return normalized
    return []


def _validate_required(payload: Mapping[str, Any], key: str) -> str:
    value = _normalize_text(payload.get(key))
    if not value:
        raise InvalidConfigError(f"Missing required key '{key}' in causal problem config")
    return value


def _validate_numeric(payload: Mapping[str, Any], key: str, expected_type: type) -> Any:
    value = payload.get(key)
    if value is None:
        raise InvalidConfigError(f"Missing required numeric key '{key}' in causal problem config")
    try:
        return expected_type(value)
    except (TypeError, ValueError) as exc:
        raise InvalidConfigError(f"Invalid value for '{key}': {value!r}") from exc


MODULE_PATH = Path(__file__).resolve()
BACKEND_ROOT = MODULE_PATH.parents[4]


def load_config(problem_name: str, root: Optional[Path] = None) -> CausalConfig:
    """Load and validate a causal problem configuration from YAML."""
    normalized_name = _normalize_text(problem_name)
    if not normalized_name:
        raise InvalidConfigError("problem_name must be a non-empty string")

    base = root or BACKEND_ROOT / "contracts" / "causal_problems"
    if not base.exists():
        raise FileNotFoundError(f"Causal problems directory not found at {base.as_posix()}")

    candidates = [
        base / f"{normalized_name}.yml",
        base / f"{normalized_name}.yaml",
    ]
    config_path: Optional[Path] = None
    for candidate in candidates:
        if candidate.exists():
            config_path = candidate
            break

    if config_path is None:
        raise FileNotFoundError(f"Causal problem config '{normalized_name}' not found under {base.as_posix()}")

    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise InvalidConfigError(f"Unable to read YAML config: {exc}") from exc

    if not isinstance(payload, Mapping):
        raise InvalidConfigError("Causal problem YAML must define a mapping at the top level")

    estimation_methods = _ensure_list(payload.get("estimation_methods"))
    if not estimation_methods:
        raise InvalidConfigError("At least one estimation method is required")

    refutations = _ensure_list(payload.get("refutation_tests"))
    if len(refutations) < 1:
        raise InvalidConfigError("At least one refutation test must be configured")

    min_sample_size = _validate_numeric(payload, "min_sample_size", int)
    if min_sample_size <= 0:
        raise InvalidConfigError("min_sample_size must be positive")

    confidence_level = float(payload.get("confidence_level", 0.95))
    if not 0 < confidence_level < 1:
        raise InvalidConfigError("confidence_level must be between 0 and 1")

    test_size = float(payload.get("test_size", 0.3))
    if not 0 < test_size < 1:
        raise InvalidConfigError("test_size must be between 0 and 1")

    bi_publish_rule = _normalize_text(payload.get("bi_publish_rule") or "SUPPORTED_ONLY")
    if not bi_publish_rule:
        bi_publish_rule = "SUPPORTED_ONLY"

    return CausalConfig(
        problem_name=_validate_required(payload, "problem_name"),
        description=_validate_required(payload, "description"),
        treatment=_validate_required(payload, "treatment"),
        outcome=_validate_required(payload, "outcome"),
        common_causes=_ensure_list(payload.get("common_causes")),
        effect_modifiers=_ensure_list(payload.get("effect_modifiers")),
        instrumental_variables=_ensure_list(payload.get("instrumental_variables")),
        frontdoor_variables=_ensure_list(payload.get("frontdoor_variables")),
        min_sample_size=min_sample_size,
        confidence_level=confidence_level,
        test_size=test_size,
        estimation_methods=estimation_methods,
        refutation_tests=refutations,
        bi_publish_rule=bi_publish_rule,
    )
