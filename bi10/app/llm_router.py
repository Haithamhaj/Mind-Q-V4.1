from __future__ import annotations

import re
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx  # type: ignore

from .config import settings

CHART_KEYWORDS = {"bar", "line", "area", "pie", "table", "pareto", "heatmap"}

PRESETS: Dict[str, Dict[str, Any]] = {
    "line": {
        "grid": {"left": 24, "right": 16, "top": 24, "bottom": 36},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category"},
        "yAxis": {"type": "value"},
        "series": [{"type": "line", "smooth": True, "areaStyle": {"opacity": 0.08}}],
    },
    "bar": {
        "grid": {"left": 24, "right": 16, "top": 24, "bottom": 36},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category"},
        "yAxis": {"type": "value"},
        "series": [{"type": "bar"}],
    },
    "area": {
        "grid": {"left": 24, "right": 16, "top": 24, "bottom": 36},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category"},
        "yAxis": {"type": "value"},
        "series": [{"type": "line", "smooth": True, "areaStyle": {"opacity": 0.2}}],
    },
    "pie": {
        "tooltip": {"trigger": "item"},
        "series": [{"type": "pie", "radius": ["35%", "70%"]}],
    },
    "pareto": {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 24, "right": 16, "top": 24, "bottom": 36},
        "xAxis": {"type": "category"},
        "yAxis": [{"type": "value"}, {"type": "value"}],
        "series": [
            {"type": "bar", "name": "Value"},
            {"type": "line", "name": "Cumulative", "yAxisIndex": 1, "smooth": True},
        ],
    },
    "heatmap": {
        "tooltip": {"trigger": "item"},
        "grid": {"left": 60, "right": 20, "top": 40, "bottom": 50},
        "xAxis": {"type": "category"},
        "yAxis": {"type": "category"},
        "visualMap": {"min": 0, "max": 100, "calculable": True, "orient": "horizontal", "left": "center"},
        "series": [{"type": "heatmap"}],
    },
}

LOGGER = logging.getLogger("bi10.router")


def _sanitize_prompt(question: str) -> str:
    sanitized = re.sub(r"`[^`]*`", " ", question)
    sanitized = re.sub(r"(select|update|delete|insert|drop|;)", " ", sanitized, flags=re.IGNORECASE)
    return " ".join(sanitized.split())


def _chart_hint(question: str) -> Optional[str]:
    lowered = question.lower()
    for keyword in CHART_KEYWORDS:
        if keyword in lowered:
            return keyword
    return None


def _guess_dimension(question: str, dimensions: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    lowered = question.lower()
    for dimension in dimensions:
        if dimension["id"].lower() in lowered:
            return dimension
        if dimension.get("name", "").lower() in lowered:
            return dimension
    return None


def plan_chart(user_question: str, semantic: Dict[str, Any]) -> Dict[str, Any]:
    if not semantic.get("metrics"):
        raise ValueError("No metrics defined in semantic layer")
    sanitized = _sanitize_prompt(user_question)
    fallback_plan = _deterministic_plan(sanitized, semantic)
    if not settings.llm_enabled:
        return fallback_plan

    try:
        candidate = _llm_plan(sanitized, semantic)
        return _merge_plan(candidate, fallback_plan, semantic, sanitized)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.debug("LLM plan failed: %s", exc)
        return fallback_plan


def _deterministic_plan(sanitized: str, semantic: Dict[str, Any]) -> Dict[str, Any]:
    metrics = semantic["metrics"]
    dimensions = semantic.get("dimensions", [])
    chosen = next(
        (
            metric
            for metric in metrics
            if metric["id"] in sanitized or metric["name"].lower() in sanitized.lower()
        ),
        metrics[0],
    )
    base_sql = chosen["sql"].strip()
    cap = int(chosen.get("cap", 10000))

    dimension = _guess_dimension(sanitized, dimensions)
    chart_hint = _chart_hint(sanitized)
    chart_type = chart_hint if chart_hint in PRESETS else chosen.get("default_chart", "line")

    if dimension:
        dimension_column = dimension["column"]
        sql = (
            "SELECT {col} AS dim, AVG(val) AS val "
            "FROM ({inner}) t LEFT JOIN fact_shipments USING (dt) "
            "GROUP BY 1 ORDER BY 1"
        ).format(col=dimension_column, inner=base_sql)
        xkey = "dim"
    else:
        sql = base_sql
        xkey = "dt"

    limited_sql = f"SELECT * FROM ({sql}) LIMIT {cap}"
    option = PRESETS.get(chart_type, PRESETS["line"])
    explain = (
        f"Metric: {chosen['name']}. Chart: {chart_type}. "
        f"Plan derived from your prompt with legal dimensions only. Cap={cap}."
    )
    return {
        "metric": chosen["id"],
        "sql": limited_sql,
        "chart_type": chart_type,
        "xkey": xkey,
        "option": option,
        "explain_ar": explain,
    }


def _llm_plan(sanitized: str, semantic: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    instructions = (
        "You are a BI planning agent. Given a user question and semantic catalog, "
        "return JSON with keys metric, sql, chart_type, option (ECharts option JSON object), explain_ar. "
        "Metrics must use ids from the catalog. Include SQL that produces columns 'dt' and 'val' "
        "or 'dim' and 'val'. Do not include LIMIT clauses."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": instructions},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": sanitized,
                        "semantic": semantic,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=15) as client:
        response = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def _merge_plan(
    candidate: Dict[str, Any],
    fallback: Dict[str, Any],
    semantic: Dict[str, Any],
    sanitized: str,
) -> Dict[str, Any]:
    metrics = {metric["id"]: metric for metric in semantic["metrics"]}
    metric_id = candidate.get("metric", fallback["metric"])
    if metric_id not in metrics:
        return fallback
    metric = metrics[metric_id]
    base_sql = candidate.get("sql", metric.get("sql", fallback["sql"]))
    cap = int(metric.get("cap", 10000))

    dimension = _guess_dimension(sanitized, semantic.get("dimensions", []))
    chart_type = candidate.get("chart_type") or metric.get("default_chart", "line")
    if chart_type not in PRESETS:
        chart_type = fallback["chart_type"]

    if dimension:
        dimension_column = dimension["column"]
        sql = (
            "SELECT {col} AS dim, AVG(val) AS val "
            "FROM ({inner}) t LEFT JOIN fact_shipments USING (dt) "
            "GROUP BY 1 ORDER BY 1"
        ).format(col=dimension_column, inner=base_sql.strip())
        xkey = "dim"
    else:
        sql = base_sql.strip()
        xkey = "dt"

    limited_sql = f"SELECT * FROM ({sql}) LIMIT {cap}"
    option = candidate.get("option") or PRESETS.get(chart_type, PRESETS["line"])
    explain = candidate.get("explain_ar") or fallback["explain_ar"]

    return {
        "metric": metric_id,
        "sql": limited_sql,
        "chart_type": chart_type,
        "xkey": xkey,
        "option": option,
        "explain_ar": explain,
    }


__all__ = ["plan_chart", "PRESETS", "CHART_KEYWORDS"]
