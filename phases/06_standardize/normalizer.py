from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd  # type: ignore

from shared.llm_prompts import compose_system_prompt  # type: ignore
from shared.terminology_loader import TerminologyRepository, canonical_key  # type: ignore
from src.agents.llm_adapter import invoke_model

DEFAULT_PROVIDER = os.getenv("STANDARDIZE_LLM_PROVIDER") or os.getenv("RAW_METRICS_LLM_PROVIDER", "openai")
DEFAULT_MODEL = os.getenv("STANDARDIZE_LLM_MODEL") or os.getenv("RAW_METRICS_LLM_MODEL", "gpt-4o-mini")

MAX_UNIQUE_DEFAULT = 200
MAX_SAMPLE_VALUES = 120
CACHE_DEFAULT_SUBDIR = "normalization_cache"
_CACHE_FILENAME_CLEAN = re.compile(r"[^0-9a-zA-Z_\-]+")


def _contains_arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06FF" for ch in text)


def _normalise_str(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


@dataclass
class MappingEntry:
    original: str
    normalized: str
    confidence: float
    source: str


def _preferred_from_entry(entry: Mapping[str, Any]) -> str:
    display = entry.get("display", {}) if isinstance(entry.get("display"), Mapping) else {}
    prefer_en = display.get("en")
    prefer_ar = display.get("ar")
    if prefer_en and not prefer_ar:
        return str(prefer_en)
    if prefer_ar and not prefer_en:
        return str(prefer_ar)
    if prefer_en and prefer_ar:
        # choose based on script
        if _contains_arabic(prefer_ar):
            return str(prefer_ar)
        return str(prefer_en)
    return str(entry.get("column_id") or "")


def _build_synonym_mapping(column_name: str, entry: Mapping[str, Any]) -> Dict[str, MappingEntry]:
    mapping: Dict[str, MappingEntry] = {}
    preferred = _preferred_from_entry(entry) or column_name
    synonyms = entry.get("synonyms", {})
    values: List[str] = []
    if isinstance(synonyms, Mapping):
        values.extend(str(item).strip() for item in synonyms.get("en", []) if isinstance(item, str))
        values.extend(str(item).strip() for item in synonyms.get("ar", []) if isinstance(item, str))
    values.append(column_name)
    values.append(preferred)
    for val in values:
        key = canonical_key(val)
        if key and key not in mapping:
            mapping[key] = MappingEntry(original=val, normalized=preferred, confidence=1.0, source="terminology")
    return mapping


def _cache_file_path(cache_dir: Path, column: str) -> Path:
    safe = _CACHE_FILENAME_CLEAN.sub("_", column.strip() or "column")
    return cache_dir / f"{safe}.json"


def _load_cache_entries(cache_dir: Path, column: str) -> Tuple[Dict[str, MappingEntry], Dict[str, Any], Path]:
    cache_payload: Dict[str, Any] = {"column": column, "mappings": []}
    cache_path = _cache_file_path(cache_dir, column)
    if cache_path.exists():
        try:
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
        if isinstance(loaded, Mapping):
            cache_payload = dict(loaded)
            cache_payload.setdefault("column", column)
            cache_payload.setdefault("mappings", [])
    entries: Dict[str, MappingEntry] = {}
    for item in cache_payload.get("mappings", []):
        if not isinstance(item, Mapping):
            continue
        original = str(item.get("original", "")).strip()
        normalized = str(item.get("normalized", "")).strip()
        if not original or not normalized:
            continue
        confidence = float(item.get("confidence", 1.0))
        source = str(item.get("source", "cache")).strip() or "cache"
        entries[original] = MappingEntry(original=original, normalized=normalized, confidence=confidence, source=source)
    return entries, cache_payload, cache_path


def _write_cache_entries(cache_path: Path, payload: Dict[str, Any], mappings: Iterable[MappingEntry]) -> None:
    merged: Dict[str, Mapping[str, Any]] = {}
    for item in payload.get("mappings", []):
        if isinstance(item, Mapping):
            original = str(item.get("original", "")).strip()
            key = canonical_key(original)
            if not key:
                continue
            merged[key] = {
                "original": original,
                "normalized": str(item.get("normalized", "")).strip(),
                "confidence": float(item.get("confidence", 1.0)),
                "source": str(item.get("source", "cache")).strip() or "cache",
            }
    for entry in mappings:
        key = canonical_key(entry.original)
        if not key:
            continue
        merged[key] = {
            "original": entry.original,
            "normalized": entry.normalized,
            "confidence": entry.confidence,
            "source": entry.source,
        }
    payload["mappings"] = list(merged.values())
    payload["updated_at"] = datetime.utcnow().isoformat()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_system_prompt() -> str:
    return compose_system_prompt(
        [
            "طَبِّق توحيدًا للقيم النصية استنادًا إلى البيانات المرفقة فقط. "
            "أعد JSON بالصيغة:\n"
            "{\n"
            '  \"mappings\": [{\"original\": \"...\", \"normalized\": \"...\", \"confidence\": 0-1}],\n'
            '  \"uncertain\": [\"values\"]\n'
            "}\n"
            "حافظ على المعنى التنفيذي، استخدم العربية مع ذكر المقابل الإنجليزي عند الحاجة.",
        ],
        enforce_data_scope=True,
    )


def _build_user_prompt(column_name: str, entry: Optional[Mapping[str, Any]], samples: Sequence[str]) -> str:
    metadata = {
        "column": column_name,
        "terminology": entry or {},
        "samples": samples[:MAX_SAMPLE_VALUES],
    }
    return (
        "Normalize the following column values. "
        "Preserve meaning, map variants (case differences, misspellings) to a canonical bilingual label.\n"
        f"{json.dumps(metadata, ensure_ascii=False, indent=2)}"
    )


def _request_llm_mapping(
    column_name: str,
    entry: Optional[Mapping[str, Any]],
    samples: Sequence[str],
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[List[MappingEntry], List[str]]:
    response = invoke_model(
        provider=provider,
        model=model,
        system_prompt=_build_system_prompt(),
        user_prompt=_build_user_prompt(column_name, entry, samples),
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=0.9,
        timeout=60,
    )
    try:
        payload = json.loads(response.content)
    except json.JSONDecodeError:
        return [], list(samples)

    results: List[MappingEntry] = []
    mappings = payload.get("mappings")
    if isinstance(mappings, list):
        for item in mappings:
            if not isinstance(item, Mapping):
                continue
            original = _normalise_str(item.get("original"))
            normalized = _normalise_str(item.get("normalized"))
            if not original or not normalized:
                continue
            confidence = float(item.get("confidence", 0.7))
            confidence = max(0.0, min(confidence, 1.0))
            results.append(
                MappingEntry(
                    original=original,
                    normalized=normalized,
                    confidence=confidence,
                    source="llm",
                )
            )
    uncertain_values: List[str] = []
    uncertain = payload.get("uncertain")
    if isinstance(uncertain, list):
        uncertain_values = [str(item).strip() for item in uncertain if isinstance(item, (str, int, float))]
    return results, uncertain_values


def _gather_samples(series: "pd.Series", max_unique: int) -> List[str]:
    values = series.dropna().astype(str).str.strip()
    unique_values = values.unique()
    if len(unique_values) > max_unique:
        return list(values.sample(n=max_unique, random_state=42, replace=False).unique())
    return [str(val) for val in unique_values]


def normalize_values(
    df: "pd.DataFrame",
    run_id: str,
    artifacts_root: Path,
    out_dir: Path,
    config: Mapping[str, Any],
) -> Tuple["pd.DataFrame", Dict[str, Any]]:
    normalization_cfg = config.get("normalization") if isinstance(config, Mapping) else {}
    if normalization_cfg is None:
        normalization_cfg = {}
    if isinstance(normalization_cfg, bool):
        normalization_cfg = {"enabled": normalization_cfg}

    artifacts_root = Path(artifacts_root).expanduser().resolve()

    enabled = bool(normalization_cfg.get("enabled", True))
    base_result = {"logs": [], "mapping_files": [], "pending_path": None}
    if df.empty:
        return df, base_result
    if not enabled:
        return df.copy(), {
            "logs": [{"event": "normalization_disabled"}],
            "mapping_files": [],
            "pending_path": None,
        }

    target_columns = normalization_cfg.get("columns")
    max_unique = int(normalization_cfg.get("max_unique", MAX_UNIQUE_DEFAULT))
    provider = normalization_cfg.get("provider") or DEFAULT_PROVIDER
    model = normalization_cfg.get("model") or DEFAULT_MODEL
    temperature = float(normalization_cfg.get("temperature", 0.1))
    max_tokens = int(normalization_cfg.get("max_tokens", 600))
    confidence_threshold = float(normalization_cfg.get("confidence_threshold", 0.6))
    llm_enabled = bool(normalization_cfg.get("llm_enabled", True))
    llm_unique_cap = int(normalization_cfg.get("llm_max_unique", max_unique * 5))
    cache_dir_raw = normalization_cfg.get("cache_dir")
    if cache_dir_raw is False:
        cache_dir = None
    else:
        if cache_dir_raw:
            cache_dir = Path(str(cache_dir_raw)).expanduser().resolve()
        else:
            cache_dir = artifacts_root.parent / "contracts" / CACHE_DEFAULT_SUBDIR
    cache_enabled = cache_dir is not None

    repo = TerminologyRepository(artifacts_root, run_id)
    normalization_dir = out_dir / "normalization"
    normalization_dir.mkdir(parents=True, exist_ok=True)

    logs: List[Dict[str, Any]] = []
    pending_records: List[Dict[str, Any]] = []
    mapping_files: List[str] = []

    df_out = df.copy()

    candidate_columns: Iterable[str]
    if target_columns:
        candidate_columns = [col for col in target_columns if col in df_out.columns]
    else:
        candidate_columns = [
            col
            for col in df_out.columns
            if pd.api.types.is_object_dtype(df_out[col]) or pd.api.types.is_string_dtype(df_out[col])
        ]

    for column in candidate_columns:
        series = df_out[column]
        if series.dropna().empty:
            continue
        unique_count = int(series.dropna().astype(str).nunique())
        if unique_count <= 1:
            continue
        samples = _gather_samples(series, max_unique=max_unique)
        if len(samples) <= 1:
            continue

        terminology_entry = repo.find_column(column)
        synonym_mapping = _build_synonym_mapping(column, terminology_entry) if terminology_entry else {}

        cache_entries: Dict[str, MappingEntry] = {}
        cache_payload: Optional[Dict[str, Any]] = None
        cache_path: Optional[Path] = None
        existing_cache_normalized: Dict[str, str] = {}
        if cache_enabled and cache_dir is not None:
            cache_entries, cache_payload, cache_path = _load_cache_entries(cache_dir, column)
            if cache_entries:
                logs.append(
                    {
                        "event": "normalization_cache_loaded",
                        "column": column,
                        "entries": len(cache_entries),
                    }
                )
            for cache_entry in cache_entries.values():
                key = canonical_key(cache_entry.original)
                if key and key not in synonym_mapping:
                    synonym_mapping[key] = cache_entry
                if key:
                    existing_cache_normalized[key] = cache_entry.normalized

        remaining_samples = [val for val in samples if canonical_key(val) not in synonym_mapping]

        if unique_count > llm_unique_cap and remaining_samples:
            logs.append(
                {
                    "event": "normalization_llm_skipped_cardinality_cap",
                    "column": column,
                    "unique_count": unique_count,
                    "llm_max_unique": llm_unique_cap,
                }
            )
            llm_required = False
        else:
            llm_required = llm_enabled and bool(remaining_samples)
        llm_mappings: List[MappingEntry] = []
        uncertain_values: List[str] = []
        if llm_required:
            try:
                llm_mappings, uncertain_values = _request_llm_mapping(
                    column,
                    terminology_entry,
                    remaining_samples,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:  # pragma: no cover - credential/network issues
                logs.append({"event": "normalization_llm_skipped", "column": column, "reason": str(exc)})
                llm_mappings = []
                uncertain_values = list(remaining_samples)
        elif remaining_samples and not llm_enabled:
            logs.append(
                {
                    "event": "normalization_llm_disabled",
                    "column": column,
                    "skipped_samples": len(remaining_samples),
                }
            )

        all_mappings = dict(synonym_mapping)
        low_confidence: List[str] = []
        for entry in llm_mappings:
            key = canonical_key(entry.original)
            if not key:
                continue
            if entry.confidence < confidence_threshold:
                low_confidence.append(entry.original)
                continue
            all_mappings[key] = MappingEntry(
                original=entry.original,
                normalized=entry.normalized,
                confidence=entry.confidence,
                source=entry.source,
            )

        if not all_mappings:
            continue

        def _normalize_value(value: Any) -> Any:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return value
            key = canonical_key(str(value))
            match = all_mappings.get(key)
            return match.normalized if match else value

        df_out[column] = series.map(_normalize_value)

        mapping_payload = {
            "column": column,
            "mappings": [
                {
                    "original": entry.original,
                    "normalized": entry.normalized,
                    "confidence": entry.confidence,
                    "source": entry.source,
                }
                for entry in all_mappings.values()
            ],
            "low_confidence": list(set(low_confidence + uncertain_values)),
        }
        mapping_path = normalization_dir / f"{column}.json"
        mapping_path.write_text(json.dumps(mapping_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        mapping_files.append(mapping_path.as_posix())

        if mapping_payload["low_confidence"]:
            for value in mapping_payload["low_confidence"]:
                pending_records.append({"column": column, "value": value})

        logs.append(
            {
                "event": "normalization_applied",
                "column": column,
                "unique_count": unique_count,
                "mappings": len(mapping_payload["mappings"]),
                "low_confidence": len(mapping_payload["low_confidence"]),
            }
        )

        if cache_enabled and cache_dir is not None and cache_payload is not None and cache_path is not None:
            cache_update_entries: List[MappingEntry] = []
            for item in mapping_payload["mappings"]:
                if not isinstance(item, Mapping):
                    continue
                original = str(item.get("original", "")).strip()
                normalized = str(item.get("normalized", "")).strip()
                if not original or not normalized:
                    continue
                cache_update_entries.append(
                    MappingEntry(
                        original=original,
                        normalized=normalized,
                        confidence=float(item.get("confidence", 1.0)),
                        source=str(item.get("source", "cache")).strip() or "cache",
                    )
                )
            if cache_update_entries:
                changed = False
                for entry in cache_update_entries:
                    key = canonical_key(entry.original)
                    if not key:
                        continue
                    prev_norm = existing_cache_normalized.get(key)
                    if prev_norm != entry.normalized:
                        changed = True
                        break
                if changed:
                    _write_cache_entries(cache_path, cache_payload, cache_update_entries)
                    logs.append(
                        {
                            "event": "normalization_cache_updated",
                            "column": column,
                            "entries": len(cache_update_entries),
                            "cache_path": cache_path.as_posix(),
                        }
                    )

    pending_path = None
    if pending_records:
        pending_path = normalization_dir / "pending_review.json"
        pending_path.write_text(json.dumps(pending_records, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {
        "logs": logs,
        "mapping_files": mapping_files,
        "pending_path": pending_path.as_posix() if pending_path else None,
    }
    return df_out, result
