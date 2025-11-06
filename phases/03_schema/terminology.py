from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore

from src.agents.llm_adapter import invoke_model
from shared.llm_prompts import compose_system_prompt

DEFAULT_PROVIDER = os.getenv("SCHEMA_TERMINOLOGY_LLM_PROVIDER") or os.getenv(
    "RAW_METRICS_LLM_PROVIDER",
    "openai",
)
DEFAULT_MODEL = os.getenv("SCHEMA_TERMINOLOGY_LLM_MODEL") or os.getenv("RAW_METRICS_LLM_MODEL", "gpt-4o-mini")

MAX_SAMPLE_VALUES = 40
MAX_UNIQUE_INFERENCE = 120


def canonicalize_column_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value).strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned.lower() or "column"


def _normalise_value(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


@dataclass
class ColumnSummary:
    column_id: str
    original_name: str
    samples: List[str]
    frequent_values: List[Tuple[str, int]]
    dtype: str
    null_fraction: float
    unique_count: int

    def sample_payload(self) -> Mapping[str, Any]:
        return {
            "column_id": self.column_id,
            "original_name": self.original_name,
            "dtype": self.dtype,
            "null_fraction": round(self.null_fraction, 4),
            "unique_count": self.unique_count,
            "frequent_values": [{"value": value, "count": count} for value, count in self.frequent_values],
            "sample_values": self.samples[:MAX_SAMPLE_VALUES],
        }


def _summarise_dataframe(
    df: "pd.DataFrame", 
    max_rows: int = 2000,
    uniqueness_threshold: float = 0.20,
) -> List[ColumnSummary]:
    summaries: List[ColumnSummary] = []
    if df.empty:
        return summaries

    # ✅ فلترة الأعمدة النصية فقط (object, string, category)
    text_types = ['object', 'string', 'category']
    text_df = df.select_dtypes(include=text_types)
    
    # ✅ استخدام كل البيانات لحساب نسبة التكرار بدقة
    total_rows = len(df)
    
    # ✅ فحص كل عمود نصي
    for column in text_df.columns:
        series = df[column]  # ✅ من كل البيانات (لحساب دقيق)
        normalised = series.dropna().astype(str).str.strip()
        non_null_count = len(normalised)
        
        if non_null_count == 0:
            continue  # تخطي الأعمدة الفارغة
        
        # ✅ حساب نسبة التكرار
        unique_count = int(normalised.nunique())
        uniqueness_ratio = unique_count / non_null_count
        
        # ✅ فحص: إذا كانت النسبة أعلى من العتبة → مستبعد (قيم فريدة)
        if uniqueness_ratio >= uniqueness_threshold:
            # نسبة unique عالية = قيم فريدة (أسماء، عناوين) → مستبعد
            continue
        
        # ✅ نسبة unique قليلة = مصطلحات متكررة → معالج
        dtype = str(series.dtype)
        value_counts = normalised.value_counts().head(10)
        frequent_values: List[Tuple[str, int]] = [(str(idx), int(count)) for idx, count in value_counts.items()]
        
        # ✅ استخراج unique values (لأنها مصطلحات محدودة ومتكررة)
        unique_values = normalised.unique()
        # استخدام unique values بدلاً من عينة عشوائية
        samples = unique_values.tolist()[:MAX_SAMPLE_VALUES]
        
        null_fraction = float(series.isna().mean()) if len(series) else 0.0

        summaries.append(
            ColumnSummary(
                column_id=canonicalize_column_id(column),
                original_name=str(column),
                samples=samples,
                frequent_values=frequent_values,
                dtype=dtype,
                null_fraction=null_fraction,
                unique_count=unique_count,
            )
        )
    return summaries


def _build_system_prompt() -> str:
    return compose_system_prompt(
        [
            "أنت تقوم ببناء معجم أعمدة بيانات. أعطِ مخرجات بصيغة JSON وفق المخطط التالي:\n"
            "{\n"
            '  "column_id": "<machine readable identifier>",\n'
            '  "display": {"en": "<english label>", "ar": "<arabic label>"},\n'
            '  "description": {"en": "<english description>", "ar": "<arabic description>"},\n'
            '  "synonyms": {"en": ["..."], "ar": ["..."]},\n'
            '  "units": "<unit if applicable or empty string>",\n'
            '  "is_kpi": true | false,\n'
            '  "kpi_links": ["<related kpi ids>"],\n'
            '  "value_examples": ["value1", "value2"],\n'
            '  "tags": ["dimension" | "metric" | "entity" | "..."]\n'
            "}\n"
            "أعد JSON صالح فقط. في حال عدم وضوح معلومة معينة اتركها فارغة.",
        ],
        enforce_data_scope=True,
    )


def _build_user_prompt(summary: ColumnSummary) -> str:
    payload = summary.sample_payload()
    return (
        "Column metadata:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Provide concise labels and descriptions in both English and Arabic. "
        "If the samples resemble KPI metrics (percentages, amounts), set is_kpi=true and suggest relevant kpi_links (snake_case)."
    )


def _invoke_llm(summary: ColumnSummary, provider: str, model: str, temperature: float, max_tokens: int) -> Mapping[str, Any]:
    response = invoke_model(
        provider=provider,
        model=model,
        system_prompt=_build_system_prompt(),
        user_prompt=_build_user_prompt(summary),
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=0.9,
        timeout=300,  # ✅ زيادة timeout إلى 5 دقائق (كان 60 ثانية)
    )
    try:
        payload = json.loads(response.content)
        if isinstance(payload, Mapping):
            return payload
    except json.JSONDecodeError:
        pass
    return {
        "column_id": summary.column_id,
        "display": {"en": summary.original_name, "ar": summary.original_name},
        "description": {"en": "", "ar": ""},
        "synonyms": {"en": [], "ar": []},
        "units": "",
        "is_kpi": False,
        "kpi_links": [],
        "value_examples": summary.samples[:5],
        "tags": [],
    }


def _normalise_entry(entry: Mapping[str, Any], summary: ColumnSummary) -> Dict[str, Any]:
    display = entry.get("display") if isinstance(entry.get("display"), Mapping) else {}
    description = entry.get("description") if isinstance(entry.get("description"), Mapping) else {}
    synonyms = entry.get("synonyms") if isinstance(entry.get("synonyms"), Mapping) else {}

    def _get(d: Mapping[str, Any], key: str, default: str = "") -> str:
        value = d.get(key)
        return str(value).strip() if isinstance(value, str) else default

    result = {
        "column_id": str(entry.get("column_id") or summary.column_id),
        "original_name": summary.original_name,
        "display": {
            "en": _get(display, "en", summary.original_name),
            "ar": _get(display, "ar", summary.original_name),
        },
        "description": {
            "en": _get(description, "en"),
            "ar": _get(description, "ar"),
        },
        "synonyms": {
            "en": [str(item).strip() for item in synonyms.get("en", []) if isinstance(item, str)],
            "ar": [str(item).strip() for item in synonyms.get("ar", []) if isinstance(item, str)],
        },
        "units": _get(entry, "units", ""),
        "is_kpi": bool(entry.get("is_kpi", False)),
        "kpi_links": [str(item).strip() for item in entry.get("kpi_links", []) if isinstance(item, str)],
        "value_examples": [
            str(item).strip()
            for item in entry.get("value_examples", summary.samples[:5])
            if isinstance(item, (str, int, float))
        ],
        "tags": [str(item).strip() for item in entry.get("tags", []) if isinstance(item, str)],
        "dtype": summary.dtype,
        "null_fraction": summary.null_fraction,
        "unique_count": summary.unique_count,
    }
    return result


def build_terminology(
    df: Optional["pd.DataFrame"],
    run_id: str,
    semantic_dir: Path,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 800,
    max_rows: int = 2000,
    uniqueness_threshold: float = 0.20,
    summaries: Optional[Sequence[ColumnSummary]] = None,
) -> Dict[str, Any]:
    if pd is None:
        raise RuntimeError("pandas is required to build terminology in stage 03")

    if summaries is None:
        if df is None:
            raise RuntimeError("Dataframe is required when summaries are not provided")
        summaries = _summarise_dataframe(df, max_rows=max_rows, uniqueness_threshold=uniqueness_threshold)
    terminology_entries: List[Dict[str, Any]] = []
    alias_map: Dict[str, str] = {}
    logs: List[Dict[str, Any]] = []

    provider = provider or DEFAULT_PROVIDER
    model = model or DEFAULT_MODEL

    for summary in summaries:
        try:
            raw_entry = _invoke_llm(summary, provider, model, temperature, max_tokens)
            entry = _normalise_entry(raw_entry, summary)
        except Exception as exc:  # pragma: no cover - LLM failure handling
            entry = _normalise_entry({}, summary)
            logs.append(
                {
                    "event": "terminology_error",
                    "column": summary.original_name,
                    "error": str(exc),
                }
            )
        else:
            logs.append(
                {
                    "event": "terminology_generated",
                    "column": summary.original_name,
                    "column_id": entry["column_id"],
                    "samples_considered": len(summary.samples),
                }
            )

        terminology_entries.append(entry)
        all_synonyms = set(entry["synonyms"]["en"]) | set(entry["synonyms"]["ar"])
        all_synonyms.add(summary.original_name)
        all_synonyms.add(entry["column_id"])
        for synonym in all_synonyms:
            if synonym:
                alias_map.setdefault(canonicalize_column_id(synonym), entry["column_id"])

    semantic_dir.mkdir(parents=True, exist_ok=True)

    terminology_path = semantic_dir / "terminology.json"
    alias_path = semantic_dir / "aliases.json"
    glossary_path = semantic_dir / "column_glossary.json"
    logs_path = semantic_dir / "terminology_logs.jsonl"

    terminology_path.write_text(json.dumps({"run_id": run_id, "columns": terminology_entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    alias_path.write_text(json.dumps(alias_map, ensure_ascii=False, indent=2), encoding="utf-8")
    glossary_path.write_text(json.dumps(terminology_entries, ensure_ascii=False, indent=2), encoding="utf-8")
    with logs_path.open("w", encoding="utf-8") as handle:
        for record in logs:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "terminology_path": terminology_path.as_posix(),
        "aliases_path": alias_path.as_posix(),
        "glossary_path": glossary_path.as_posix(),
        "logs_path": logs_path.as_posix(),
        "entries": terminology_entries,
    }


__all__ = [
    "LLMResponse",
    "build_terminology",
    "canonicalize_column_id",
    "invoke_model",
    "ColumnSummary",
]
