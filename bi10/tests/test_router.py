from __future__ import annotations

from bi10.app.llm_router import plan_chart


def test_keyword_chart_and_dim():
    semantic = {
        "metrics": [
            {
                "id": "sla_pct",
                "name": "SLA%",
                "sql": "SELECT '2025-01-01' AS dt, 95.0 AS val",
                "default_chart": "line",
                "cap": 1000,
            }
        ],
        "dimensions": [
            {"id": "city", "column": "city", "type": "category", "mart": "shipments"},
        ],
    }
    plan = plan_chart("bar sla_pct by city", semantic)
    assert plan["chart_type"] in ("bar", "line")
    assert "LIMIT 1000" in plan["sql"]
