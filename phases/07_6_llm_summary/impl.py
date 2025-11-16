from __future__ import annotations

import json
import math
import os
import re
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yaml  # type: ignore
from pydantic import BaseModel, ValidationError, field_validator

from src.agents import llm_adapter  # type: ignore
from shared.logging import setup_logger  # type: ignore

TOKEN_PATTERN = re.compile(r"(phone|mobile|msisdn|email|name)", re.IGNORECASE)
CARD_MAX_CHARS = 700
DEFAULT_PROVIDER_PLAN: Tuple[str, ...] = ("openai", "anthropic", "gemini")


class RecommendationModel(BaseModel):
    column_name: str
    reason: str
    evidence_key: str

    @field_validator("reason")
    @classmethod
    def _reason_length(cls, value: str) -> str:
        if not (5 <= len(value) <= 400):
            raise ValueError("reason must be between 5 and 400 characters")
        return value


class SummaryPayload(BaseModel):
    executive_summary: str
    recommendations: List[RecommendationModel]
    invalid_references: List[str]

    @field_validator("executive_summary")
    @classmethod
    def _summary_length(cls, value: str) -> str:
        if not (10 <= len(value) <= 600):
            raise ValueError("executive_summary must be between 10 and 600 characters")
        return value


SummaryPayload.model_rebuild()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required input missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def _parse_cols(raw: Optional[Iterable[str]]) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [part.strip() for part in raw.split(",")]
        return [part for part in parts if part]
    return [str(item).strip() for item in raw if str(item).strip()]


def _schema_hash(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _rough_token_estimate(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _llm_provider_plan(config: Mapping[str, Any]) -> List[Tuple[str, Optional[str]]]:
    plan: List[Tuple[str, Optional[str]]] = []
    raw_plan = config.get("providers") if isinstance(config, Mapping) else None
    if isinstance(raw_plan, str):
        entries = [entry.strip() for entry in raw_plan.split(",") if entry.strip()]
        plan.extend((entry, None) for entry in entries)
    elif isinstance(raw_plan, Sequence):
        for entry in raw_plan:
            if isinstance(entry, str):
                plan.append((entry.strip(), None))
            elif isinstance(entry, Mapping):
                provider_name = str(entry.get("provider") or entry.get("name") or "").strip()
                if provider_name:
                    model_name = entry.get("model")
                    plan.append((provider_name, str(model_name)) if model_name else (provider_name, None))
    if not plan:
        env_plan = os.getenv("MINDQ_LLM_PROVIDERS")
        if env_plan:
            entries = [entry.strip() for entry in env_plan.split(",") if entry.strip()]
            plan.extend((entry, None) for entry in entries)
    if not plan:
        plan.extend((provider, None) for provider in DEFAULT_PROVIDER_PLAN)
    # Preserve order while removing duplicates
    ordered: List[Tuple[str, Optional[str]]] = []
    seen: set[str] = set()
    for provider, model in plan:
        key = provider.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append((provider, model))
    return ordered


def _llm_cache_key(provider: str, model: str, prompt_hash: str) -> str:
    return hashlib.sha256(f"{provider}|{model}|{prompt_hash}".encode("utf-8")).hexdigest()


def _read_cache(cache_dir: Path, cache_key: str) -> Optional[Dict[str, Any]]:
    cache_file = cache_dir / f"{cache_key}.json"
    if not cache_file.exists():
        return None
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(cache_dir: Path, cache_key: str, payload: Mapping[str, Any]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{cache_key}.json"
    cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


MODEL_RATES = {
    "openai": {
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    },
    "anthropic": {
        "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    },
    "gemini": {
        "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    },
}


def _estimate_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    provider_rates = MODEL_RATES.get(provider, {})
    model_rates = provider_rates.get(model)
    if not model_rates:
        return 0.0
    input_cost = model_rates["input"] * (prompt_tokens / 1000.0)
    output_cost = model_rates["output"] * (completion_tokens / 1000.0)
    return input_cost + output_cost


def _mask_prompt_text(text: str) -> str:
    return TOKEN_PATTERN.sub("<محجوب>", text)


def _build_column_card(name: str, profile: Mapping[str, Any]) -> str:
    dtype = profile.get("dtype", "غير محدد")
    missing_pct = profile.get("missing_pct", 0.0)
    unique = profile.get("unique", 0)
    lines = [
        f"{name}: نوع {dtype}",
        f"نسبة الفراغ {missing_pct:.1%}",
        f"عدد القيم المميزة {unique}",
    ]
    stats = profile.get("stats_numeric") or {}
    if stats:
        std = stats.get("std")
        p75 = stats.get("p75")
        p25 = stats.get("p25")
        lines.append(f"تباين عددي (انحراف معياري {std:.3f})" if std is not None else "")
        if p75 is not None and p25 is not None:
            spread = p75 - p25
            lines.append(f"مجال ربع سنوي {spread:.3f}")
        outliers = stats.get("outliers") or []
        if outliers:
            lines.append(f"مؤشرات خارجية عددها {len(outliers)}")
    topk = profile.get("top_categories") or []
    if topk:
        sample = ", ".join(f"{item['value']} ({item['pct']:.1%})" for item in topk[:5])
        lines.append(f"أكثر الفئات تكراراً {sample}")
    time_profile = profile.get("time_profile") or {}
    if time_profile.get("min_ts") and time_profile.get("max_ts"):
        lines.append(f"نطاق زمني من {time_profile['min_ts']} إلى {time_profile['max_ts']}")
    joined = "؛ ".join(filter(None, lines))
    truncated = joined[:CARD_MAX_CHARS]
    return _mask_prompt_text(truncated)


def _build_prompt(
    allowed_columns: Sequence[str],
    report: Mapping[str, Any],
    focus_cols: Sequence[str],
) -> Tuple[str, str, str, str]:
    cards: List[str] = []
    for col in allowed_columns:
        profile = report.get("columns", {}).get(col)
        if not isinstance(profile, Mapping):
            continue
        cards.append(_build_column_card(col, profile))
    per_column_cards = "\n---\n".join(cards)
    allowed_csv = ", ".join(allowed_columns)
    focus_note = ", ".join(focus_cols) if focus_cols else ""
    system_prompt = (
        "أنت مساعد تحليلي ملتزم بإرجاع JSON صالح فقط وفقاً للمخطط المعروف. "
        "لا تضف أي شروح خارج حقل JSON."
    )
    user_prompt = (
        "أنت كبير محللي البيانات في شركة لوجستيات. حوّل التقرير الإحصائي التالي إلى خلاصة تنفيذية وتوصيات عملية **باللغة العربية**.\n"
        "قيود صارمة:\n"
        "- أعد **JSON فقط** وفق المخطط المحدد.\n"
        "- لا تذكر أعمدة غير موجودة في قائمة الأعمدة المسموح بها.\n"
        "- لكل توصية **evidence_key** يشير لمسار داخل report.json.\n\n"
        "مثال على بنية report.json لاستخدام المسارات:\n"
        "```\n"
        "{\n"
        "  \"summary\": {\"n_rows\": 19998},\n"
        "  \"columns\": {\n"
        "    \"COD_AMOUNT\": {\n"
        "      \"stats_numeric\": {\n"
        "        \"std\": 37.18,\n"
        "        \"mean\": 120.0\n"
        "      }\n"
        "    },\n"
        "    \"DESTINATION\": {\n"
        "      \"top_categories\": [\n"
        "        {\"value\": \"Jeddah\", \"n\": 3780, \"pct\": 0.19}\n"
        "      ]\n"
        "    }\n"
        "  }\n"
        "}\n"
        "```\n"
        f"قائمة الأعمدة المسموح بها:\n{allowed_csv}\n"
    )
    if focus_note:
        user_prompt += f"(الأولوية للأعمدة: {focus_note})\n"
    user_prompt += "\nملخص موجز لكل عمود:\n---\n"
    user_prompt += per_column_cards
    user_prompt += "\n---\n\nناتجك (JSON فقط):\n{\n  \"executive_summary\": \"...\",\n  \"recommendations\": [\n    {\"column_name\":\"...\", \"reason\":\"...\", \"evidence_key\":\"columns.<col>....\"}\n  ],\n  \"invalid_references\": []\n}"
    combined = system_prompt + "\n" + user_prompt
    prompt_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    return system_prompt, user_prompt, per_column_cards, prompt_hash


def _resolve_path(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not part:
            raise KeyError("empty path segment")
        match = re.match(r"^(?P<key>[^\[]+)(\[(?P<index>\d+)\])?$", part)
        if not match:
            raise KeyError(f"invalid path segment: {part}")
        key = match.group("key")
        index = match.group("index")
        if not isinstance(current, Mapping):
            raise KeyError(f"cannot access key '{key}' on non-mapping")
        current = current[key]
        if index is not None:
            idx = int(index)
            if not isinstance(current, Sequence):
                raise KeyError(f"segment '{part}' does not refer to a sequence")
            current = current[idx]
    return current


def _first_resolvable_path(report: Mapping[str, Any], candidates: Sequence[str]) -> Optional[str]:
    for candidate in candidates:
        try:
            _resolve_path(report, candidate)
            return candidate
        except (KeyError, IndexError, TypeError):
            continue
    return None


def _valid_recommendations(report: Mapping[str, Any], recs: List[Mapping[str, Any]]) -> List[str]:
    invalid: List[str] = []
    for rec in recs:
        evidence = rec.get("evidence_key")
        if not isinstance(evidence, str):
            invalid.append("")
            continue
        try:
            _resolve_path(report, evidence)
        except (KeyError, IndexError, TypeError):
            invalid.append(evidence)
    return invalid


def _collect_kpi_targets(kpi_payload: Mapping[str, Any]) -> List[str]:
    targets: List[str] = []
    for value in kpi_payload.values():
        if isinstance(value, Mapping):
            name = value.get("column")
            if isinstance(name, str):
                targets.append(name)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, Mapping) and isinstance(item.get("column"), str):
                    targets.append(item["column"])
    return targets


def _generate_fallback_summary(
    run_id: str,
    report: Mapping[str, Any],
    allowed_columns: Sequence[str],
    kpi_targets: Sequence[str],
) -> Tuple[str, List[Dict[str, Any]]]:
    columns = report.get("columns", {})
    summary_info = report.get("summary", {})
    drivers = summary_info.get("drivers_preview") or []
    driver_map = {item["column"]: (idx, item) for idx, item in enumerate(drivers) if isinstance(item, Mapping) and "column" in item}

    numeric_std_values: List[float] = []
    candidates: List[Dict[str, Any]] = []
    column_scope = list(dict.fromkeys(allowed_columns or list(columns.keys())))
    for col in column_scope:
        profile = columns.get(col)
        if not isinstance(profile, Mapping):
            continue
        stats = profile.get("stats_numeric") or {}
        std = float(stats.get("std", 0.0) or 0.0)
        if std > 0:
            numeric_std_values.append(std)
        missing_pct = float(profile.get("missing_pct", 0.0) or 0.0)
        corr_entry = driver_map.get(col)
        corr_abs = float(corr_entry[1].get("abs_r", 0.0)) if corr_entry else 0.0
        candidates.append(
            {
                "column": col,
                "missing_pct": missing_pct,
                "std": std,
                "corr_abs": corr_abs,
                "driver_index": corr_entry[0] if corr_entry else None,
                "stats": stats,
                "profile": profile,
            }
        )

    max_std = max(numeric_std_values) if numeric_std_values else 0.0

    kpi_focus = {target.upper() for target in kpi_targets}

    def _score(item: Mapping[str, Any]) -> float:
        missing = item["missing_pct"]
        std_norm = (item["std"] / max_std) if max_std else 0.0
        corr = item["corr_abs"]
        bonus = 0.0
        if kpi_focus and ("COD_AMOUNT" in kpi_focus or "COD" in "".join(kpi_focus)) and corr > 0:
            bonus = 0.1
        return missing * 0.5 + std_norm * 0.2 + corr * 0.3 + bonus

    ranked = sorted(candidates, key=_score, reverse=True)[:3]

    recommendations: List[Dict[str, Any]] = []
    for item in ranked:
        column = item["column"]
        entry_profile = item["profile"]
        missing_pct = item["missing_pct"]
        std = item["std"]
        corr_abs = item["corr_abs"]
        driver_index = item["driver_index"]
        reason_parts: List[str] = []
        if missing_pct >= 0.05:
            reason_parts.append(f"نسبة الفراغ في `{column}` تبلغ {missing_pct:.1%}")
        if std > 0:
            reason_parts.append(f"تشتت عددي واضح (انحراف {std:.2f})")
        if corr_abs > 0:
            reason_parts.append(f"ترابط قوي مع مؤشر التدفق (|r|={corr_abs:.2f})")
        if not reason_parts:
            reason_parts.append(f"سلوك `{column}` يتطلب متابعة لضمان جودة النمذجة")
        evidence_candidates = [
            f"columns.{column}.missing_pct",
            f"columns.{column}.stats_numeric.std",
        ]
        if driver_index is not None:
            evidence_candidates.insert(0, f"summary.drivers_preview[{driver_index}].abs_r")
        evidence_key = _first_resolvable_path(report, evidence_candidates)
        if not evidence_key:
            continue
        recommendations.append(
            {
                "column_name": column,
                "reason": "؛ ".join(reason_parts),
                "evidence_key": evidence_key,
            }
        )

    if not recommendations and column_scope:
        column = column_scope[0]
        fallback_evidence = _first_resolvable_path(
            report,
            [f"columns.{column}.missing_pct", f"columns.{column}.unique"],
        )
        if fallback_evidence:
            recommendations.append(
                {
                    "column_name": column,
                    "reason": f"الحقل `{column}` هو الوحيد المتاح للمراجعة حالياً.",
                    "evidence_key": fallback_evidence,
                }
            )

    bullets: List[str] = [
        "- تنفيذ حملات تنظيف للحقول ذات الفراغ المرتفع بالتنسيق مع فرق العمليات.",
        "- تثبيت الحقول العددية الحرجة عبر إعداد حدود إنذار للانحرافات اليومية.",
        "- إنشاء مراجعة شهرية مشتركة مع فريق التحصيل لضبط المؤشرات المرتبطة بالإيراد.",
    ]

    headline = f"تم تحليل {summary_info.get('n_cols_reported', 0)} عموداً مع الحفاظ على جميع الصفوف المتاحة."
    executive_summary = "\n".join(
        [
            "## ملخص تنفيذي",
            "",
            headline,
            "",
            *bullets,
            "",
        ]
    ).strip()

    return executive_summary, recommendations


def run(run_id: str, inputs: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    start = time.perf_counter()
    logs: List[Dict[str, Any]] = [{"event": "start", "run_id": run_id, "timestamp": datetime.now(timezone.utc).isoformat()}]

    artifacts_root = Path(cfg.get("artifacts_root", "artifacts")).expanduser().resolve()
    report_path = Path(inputs.get("report", ""))
    kpis_path = Path(inputs.get("kpis", "")) if inputs.get("kpis") else None

    report = _read_json(report_path)
    logs.append({"event": "load_report", "path": report_path.as_posix(), "n_columns": len(report.get("columns", {}))})

    kpis_payload = _load_yaml(kpis_path) if kpis_path else {}
    kpi_targets = _collect_kpi_targets(kpis_payload) if kpis_payload else []
    if kpis_payload:
        logs.append({"event": "load_kpis", "path": kpis_path.as_posix(), "targets": kpi_targets})

    focus_cols = _parse_cols(cfg.get("focus_cols"))
    exclude_cols = set(_parse_cols(cfg.get("exclude_cols")))

    columns_available = list(report.get("columns", {}).keys())
    allowed_columns = [col for col in columns_available if col not in exclude_cols]
    if focus_cols:
        focus_set = set(focus_cols)
        allowed_columns = [col for col in allowed_columns if col in focus_set]
    logs.append({"event": "column_scope", "allowed": allowed_columns, "excluded": list(exclude_cols), "focus": focus_cols})

    llm_cfg = cfg.get("llm") if isinstance(cfg.get("llm"), Mapping) else {}
    budget_usd = float(llm_cfg.get("budget_usd", cfg.get("budget_usd", 0.5)))
    provider_plan = _llm_provider_plan(llm_cfg)
    max_tokens = int(llm_cfg.get("max_tokens", cfg.get("max_tokens", 1200)))
    temperature = float(llm_cfg.get("temperature", cfg.get("temperature", 0.1)))
    top_p = float(llm_cfg.get("top_p", cfg.get("top_p", 0.0)))
    timeout = int(llm_cfg.get("timeout", cfg.get("timeout", 60)))
    cache_enabled = bool(llm_cfg.get("cache_enabled", True))

    system_prompt, user_prompt, per_column_cards, prompt_hash = _build_prompt(allowed_columns, report, focus_cols)
    estimated_prompt_tokens = _rough_token_estimate(system_prompt) + _rough_token_estimate(user_prompt)
    estimated_completion_tokens = max_tokens

    logs.append(
        {
            "event": "llm_plan",
            "budget": budget_usd,
            "estimated_prompt_tokens": estimated_prompt_tokens,
            "max_tokens": max_tokens,
            "providers": [{"provider": prov, "model": mdl or _default_model(prov)} for prov, mdl in provider_plan],
        }
    )

    output_dir = artifacts_root / run_id / "stage_07_6_llm_summary"
    _ensure_dir(output_dir)
    cache_dir = output_dir / "_cache"

    llm_payload: Optional[SummaryPayload] = None
    metrics_payload: Dict[str, Any] = {}
    fallback_chain: List[Dict[str, Any]] = []
    cache_hit = False
    provider_used: Optional[str] = None
    model_used: Optional[str] = None

    llm_allowed = bool(allowed_columns and provider_plan)
    if llm_allowed:
        for provider_name, model_hint in provider_plan:
            candidate_model = str(model_hint or _default_model(provider_name))
            estimated_cost = _estimate_cost(
                provider_name,
                candidate_model,
                estimated_prompt_tokens,
                estimated_completion_tokens,
            )
            if math.isfinite(estimated_cost) and estimated_cost > budget_usd:
                fallback_chain.append(
                    {
                        "provider": provider_name,
                        "model": candidate_model,
                        "status": "skipped_budget",
                        "estimated_cost": round(estimated_cost, 4),
                        "budget": budget_usd,
                    }
                )
                continue

            cache_key = _llm_cache_key(provider_name, candidate_model, prompt_hash)
            cached_payload = _read_cache(cache_dir, cache_key) if cache_enabled else None
            if cached_payload:
                try:
                    cached_summary = SummaryPayload.model_validate(cached_payload.get("summary", {}))
                except Exception:
                    cached_payload = None
                else:
                    llm_payload = cached_summary
                    metrics_payload = cached_payload.get("metrics", {})
                    metrics_payload.setdefault("provider", provider_name)
                    metrics_payload.setdefault("model", candidate_model)
                    metrics_payload["cache_hit"] = True
                    cache_hit = True
                    provider_used = provider_name
                    model_used = candidate_model
                    fallback_chain.append({"provider": provider_name, "model": candidate_model, "status": "cache_hit"})
                    break

            attempt_logs: List[Dict[str, Any]] = []
            for attempt in range(3):
                try:
                    response = llm_adapter.invoke_model(
                        provider=provider_name,
                        model=candidate_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        timeout=timeout,
                    )
                    parsed = json.loads(response.content)
                    payload = SummaryPayload.model_validate(parsed)
                    invalid_refs = _valid_recommendations(
                        report, [rec.model_dump() for rec in payload.recommendations]
                    )
                    payload.invalid_references = invalid_refs
                    if invalid_refs:
                        attempt_logs.append(
                            {
                                "event": "llm_attempt",
                                "attempt": attempt + 1,
                                "provider": provider_name,
                                "model": response.model,
                                "status": "invalid_references",
                                "invalid": invalid_refs,
                            }
                        )
                        fallback_chain.append(
                            {
                                "provider": provider_name,
                                "model": response.model,
                                "status": "invalid_references",
                                "attempt": attempt + 1,
                            }
                        )
                        continue
                    llm_payload = payload
                    provider_used = provider_name
                    model_used = response.model
                    metrics_payload = {
                        "provider": provider_name,
                        "model": response.model,
                        "tokens_in": response.tokens_in,
                        "tokens_out": response.tokens_out,
                        "cost_estimate": response.cost_estimate,
                        "duration_s": response.duration_s,
                        "prompt_hash": prompt_hash,
                        "response_hash": hashlib.sha256(response.content.encode("utf-8")).hexdigest(),
                        "cache_hit": False,
                    }
                    fallback_chain.append(
                        {
                            "provider": provider_name,
                            "model": response.model,
                            "status": "success",
                            "attempt": attempt + 1,
                        }
                    )
                    if cache_enabled:
                        _write_cache(
                            cache_dir,
                            cache_key,
                            {
                                "summary": payload.model_dump(mode="json"),
                                "metrics": {k: v for k, v in metrics_payload.items() if k not in {"fallback_chain", "cache_hit"}},
                            },
                        )
                    break
                except (ValidationError, json.JSONDecodeError) as exc:
                    attempt_logs.append(
                        {
                            "event": "llm_attempt",
                            "attempt": attempt + 1,
                            "provider": provider_name,
                            "model": candidate_model,
                            "status": "invalid_json",
                            "error": str(exc),
                        }
                    )
                    fallback_chain.append(
                        {
                            "provider": provider_name,
                            "model": candidate_model,
                            "status": "invalid_json",
                            "attempt": attempt + 1,
                        }
                    )
                except Exception as exc:  # pragma: no cover
                    attempt_logs.append(
                        {
                            "event": "llm_attempt",
                            "attempt": attempt + 1,
                            "provider": provider_name,
                            "model": candidate_model,
                            "status": "error",
                            "error": str(exc),
                        }
                    )
                    fallback_chain.append(
                        {
                            "provider": provider_name,
                            "model": candidate_model,
                            "status": "error",
                            "attempt": attempt + 1,
                        }
                    )
            logs.extend(attempt_logs)
            if llm_payload:
                break

    if llm_payload and not llm_payload.invalid_references:
        summary_output = llm_payload
        if not metrics_payload:
            metrics_payload = {
                "provider": provider_used or (provider_plan[0][0] if provider_plan else "unknown"),
                "model": model_used or (provider_plan[0][1] or _default_model(provider_plan[0][0])) if provider_plan else "unknown",
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_estimate": 0.0,
                "duration_s": time.perf_counter() - start,
                "prompt_hash": prompt_hash,
                "response_hash": "",
                "cache_hit": cache_hit,
            }
    else:
        executive_summary, recommendations = _generate_fallback_summary(run_id, report, allowed_columns, kpi_targets)
        summary_output = SummaryPayload(
            executive_summary=executive_summary,
            recommendations=[RecommendationModel(**item) for item in recommendations] or [RecommendationModel(column_name="????", reason="?? ???? ?????? ?????.", evidence_key="summary.n_rows")],
            invalid_references=[],
        )
        metrics_payload = {
            "provider": "heuristic",
            "model": "heuristic",
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_estimate": 0.0,
            "duration_s": time.perf_counter() - start,
            "prompt_hash": prompt_hash,
            "response_hash": "",
            "cache_hit": False,
        }
        fallback_chain.append({"provider": "heuristic", "status": "used"})
        logs.append({"event": "fallback", "reason": "heuristic"})

    metrics_payload["fallback_chain"] = fallback_chain

    exec_path = output_dir / "executive_summary.md"
    exec_path.write_text(summary_output.executive_summary + "\n", encoding="utf-8")

    recommendations_payload = summary_output.model_dump(mode="json")
    rec_path = output_dir / "recommendations.json"
    rec_path.write_text(json.dumps(recommendations_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    provenance = {
        "run_id": run_id,
        "tool_version": "stage_07_6_summary_v1",
        "schema_hash": _schema_hash(report),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    prov_path = output_dir / "provenance.json"
    prov_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

    log_path = output_dir / "logs.jsonl"
    logger = setup_logger(log_path.as_posix())
    for record in logs:
        logger.info(json.dumps(record, ensure_ascii=False))

    # Generate summary.json - combines executive summary and recommendations
    summary_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executive_summary": summary_output.executive_summary,
        "recommendations": [item.model_dump(mode="json") for item in summary_output.recommendations],
        "provider": metrics_payload.get("provider"),
        "model": metrics_payload.get("model"),
        "language": "ar",
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Generate prompts.json - contains the prompts used
    prompts_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "prompt_hash": prompt_hash,
        "provider": metrics_payload.get("provider"),
        "model": metrics_payload.get("model"),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }
    prompts_path = output_dir / "prompts.json"
    prompts_path.write_text(json.dumps(prompts_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    duration = time.perf_counter() - start

    # Determine status based on provider
    if metrics_payload.get("provider") == "heuristic":
        status = "WARN"  # Fallback used
    else:
        status = "PASS"

    return {
        "run_id": run_id,
        "status": status,
        "outputs": {
            "executive_summary": exec_path.as_posix(),
            "recommendations": rec_path.as_posix(),
            "metrics": metrics_path.as_posix(),
            "provenance": prov_path.as_posix(),
            "logs": log_path.as_posix(),
            "summary": summary_path.as_posix(),
            "prompts": prompts_path.as_posix(),
        },
        "metrics": {
            "provider": metrics_payload.get("provider"),
            "model": metrics_payload.get("model"),
            "duration_s": duration,
        },
    }


def _default_model(provider: str) -> str:
    if provider == "openai":
        return "gpt-4-turbo"
    if provider == "gemini":
        return "gemini-2.0-flash"
    if provider == "anthropic":
        return "claude-3-5-sonnet"
    return "gpt-4-turbo"


__all__ = ["run"]
