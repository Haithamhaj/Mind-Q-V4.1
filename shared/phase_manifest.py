from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "config" / "phase_manifest.yaml"


@dataclass(frozen=True)
class LocalisedText:
    en: str
    ar: str

    @classmethod
    def from_mapping(cls, payload: Dict[str, Any], *, default_en: str = "", default_ar: str = "") -> "LocalisedText":
        en = str(payload.get("en", default_en) or default_en).strip()
        ar = str(payload.get("ar", default_ar) or default_ar).strip()
        return cls(en=en, ar=ar)


@dataclass(frozen=True)
class PhaseResource:
    id: str
    name: LocalisedText
    description: LocalisedText

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "PhaseResource":
        resource_id = str(payload.get("id", "")).strip()
        name = LocalisedText.from_mapping(payload.get("name") or {}, default_en=resource_id, default_ar=resource_id)
        description = LocalisedText.from_mapping(payload.get("description") or {})
        return cls(id=resource_id, name=name, description=description)


@dataclass(frozen=True)
class LearningResource:
    title: str
    url: Optional[str] = None


@dataclass(frozen=True)
class PhaseDefinition:
    id: str
    name: LocalisedText
    description: LocalisedText
    expected_inputs: List[PhaseResource] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)
    key_checks: List[str] = field(default_factory=list)
    common_failures: List[str] = field(default_factory=list)
    learning_resources: List[LearningResource] = field(default_factory=list)


def _ensure_manifest_path(path: Optional[Path] = None) -> Path:
    candidate = path or MANIFEST_PATH
    if not candidate.exists():
        raise FileNotFoundError(f"Phase manifest not found at {candidate}")
    return candidate


def _normalise_outputs(raw_outputs: Iterable[Any]) -> List[str]:
    outputs: List[str] = []
    for entry in raw_outputs:
        if isinstance(entry, str):
            outputs.append(entry.strip())
        elif isinstance(entry, dict):
            schema = entry.get("schema")
            if isinstance(schema, str) and schema.strip():
                outputs.append(schema.strip())
    return outputs


def _normalise_learning_resources(raw_resources: Iterable[Any]) -> List[LearningResource]:
    items: List[LearningResource] = []
    for entry in raw_resources:
        if isinstance(entry, dict):
            title = str(entry.get("title", "")).strip()
            url = entry.get("url")
            url_value = str(url).strip() if isinstance(url, str) else None
            if title:
                items.append(LearningResource(title=title, url=url_value or None))
        elif isinstance(entry, str) and entry.strip():
            items.append(LearningResource(title=entry.strip()))
    return items


def _coerce_phase_definition(payload: Dict[str, Any]) -> PhaseDefinition:
    phase_id = str(payload.get("id", "")).strip()
    if not phase_id:
        raise ValueError("Phase manifest entry missing 'id'")

    name = LocalisedText.from_mapping(payload.get("name") or {}, default_en=phase_id, default_ar=phase_id)
    description = LocalisedText.from_mapping(payload.get("description") or {})

    expected_inputs = [
        PhaseResource.from_payload(item) for item in payload.get("expected_inputs") or [] if isinstance(item, dict)
    ]

    expected_outputs = _normalise_outputs(payload.get("expected_outputs") or [])
    key_checks = [str(item).strip() for item in payload.get("key_checks") or [] if str(item).strip()]
    common_failures = [str(item).strip() for item in payload.get("common_failures") or [] if str(item).strip()]
    learning_resources = _normalise_learning_resources(payload.get("learning_resources") or [])

    return PhaseDefinition(
        id=phase_id,
        name=name,
        description=description,
        expected_inputs=expected_inputs,
        expected_outputs=expected_outputs,
        key_checks=key_checks,
        common_failures=common_failures,
        learning_resources=learning_resources,
    )


@lru_cache()
def load_phase_manifest(path: Optional[Path] = None) -> Dict[str, PhaseDefinition]:
    manifest_path = _ensure_manifest_path(path)
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or []
    definitions: Dict[str, PhaseDefinition] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        definition = _coerce_phase_definition(entry)
        definitions[definition.id] = definition
    return definitions


def get_phase_definition(phase_id: str) -> Optional[PhaseDefinition]:
    phase_id_normalised = str(phase_id or "").strip()
    if not phase_id_normalised:
        return None
    return load_phase_manifest().get(phase_id_normalised)


def iter_phase_definitions() -> Iterable[PhaseDefinition]:
    return load_phase_manifest().values()


__all__ = [
    "LocalisedText",
    "PhaseDefinition",
    "PhaseResource",
    "LearningResource",
    "load_phase_manifest",
    "get_phase_definition",
    "iter_phase_definitions",
]
