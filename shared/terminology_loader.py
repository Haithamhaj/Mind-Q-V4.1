from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


class TerminologyRepository:
    """Utility to load terminology resources generated in stage 03."""

    def __init__(self, artifacts_root: Path | str, run_id: str):
        self._artifacts_root = Path(artifacts_root)
        self._run_id = run_id
        self._stage_dir = self._artifacts_root / run_id / "stage_03_schema" / "semantic"
        self._profile_dir = self._artifacts_root / run_id / "stage_04_profile" / "semantic"
        self._fallback_dir = Path(__file__).resolve().parents[2] / "bi" / "semantic"

    @lru_cache(maxsize=1)
    def _load_terminology(self) -> Dict[str, Any]:
        paths = [
            self._profile_dir / "terminology_enriched.json",
            self._stage_dir / "terminology.json",
            self._fallback_dir / "terminology.json",
        ]
        for path in paths:
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    return payload
        return {"columns": []}

    @lru_cache(maxsize=1)
    def _load_aliases(self) -> Dict[str, str]:
        paths = [
            self._stage_dir / "aliases.json",
            self._fallback_dir / "aliases.json",
        ]
        for path in paths:
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    return {str(key): str(value) for key, value in payload.items()}
        return {}

    def get_columns(self) -> Iterable[Dict[str, Any]]:
        payload = self._load_terminology()
        columns = payload.get("columns")
        if isinstance(columns, list):
            return columns
        if isinstance(payload, list):  # fallback legacy structure
            return payload
        return []

    def find_column(self, column_id: str) -> Optional[Dict[str, Any]]:
        canonical = canonical_key(column_id)
        for entry in self.get_columns():
            entry_id = entry.get("column_id")
            if entry_id and canonical_key(entry_id) == canonical:
                return entry
        return None

    def resolve_alias(self, name: str) -> Optional[str]:
        aliases = self._load_aliases()
        return aliases.get(canonical_key(name))

    @lru_cache(maxsize=1)
    def _load_profiles(self) -> Dict[str, Any]:
        path = self._profile_dir / "column_profile.json"
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
            if isinstance(payload, Mapping):
                profiles = payload.get("profiles")
                if isinstance(profiles, Mapping):
                    return profiles  # type: ignore[return-value]
        return {}

    def get_profile(self, column_id: str) -> Optional[Dict[str, Any]]:
        profiles = self._load_profiles()
        profile = profiles.get(column_id)
        if isinstance(profile, Mapping):
            return profile  # type: ignore[return-value]
        return None


def canonical_key(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value).strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned.lower()
