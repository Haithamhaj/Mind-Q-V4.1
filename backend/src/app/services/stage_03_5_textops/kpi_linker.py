from __future__ import annotations

import json
from typing import Any, Mapping

import polars as pl  # type: ignore


def _normalise(text: Any) -> str:
    return str(text).lower().strip() if text is not None else ""


def build_kpi_links(rules_df: pl.DataFrame, kpi_map: Mapping[str, Any]) -> pl.DataFrame:
    if rules_df.height == 0:
        return pl.DataFrame(
            schema={
                "entity_type": pl.Utf8,
                "entity_id": pl.Utf8,
                "kpi_id": pl.Utf8,
                "dim_keys": pl.Utf8,
                "link_confidence": pl.Float64,
            }
        )

    catalogue = kpi_map.get("kpis", {}) if isinstance(kpi_map, Mapping) else {}
    rows = []
    for row in rules_df.iter_rows(named=True):
        metric = _normalise(row.get("metric"))
        if not metric:
            continue
        for name, meta in catalogue.items():
            if not isinstance(meta, Mapping):
                continue
            kpi_id = meta.get("id") or name
            aliases = [name, kpi_id, meta.get("description", "")]
            aliases.extend(meta.get("aliases", []))
            matches = [alias for alias in aliases if metric in _normalise(alias)]
            if not matches:
                continue
            dim_payload = {
                "scope": row.get("scope"),
                "partner_id": row.get("partner_id"),
            }
            rows.append(
                {
                    "entity_type": "SLA",
                    "entity_id": row.get("rule_id"),
                    "kpi_id": kpi_id,
                    "dim_keys": json.dumps({k: v for k, v in dim_payload.items() if v}, ensure_ascii=False),
                    "link_confidence": 0.9 if metric == _normalise(kpi_id) else 0.7,
                }
            )
    if not rows:
        return pl.DataFrame(
            schema={
                "entity_type": pl.Utf8,
                "entity_id": pl.Utf8,
                "kpi_id": pl.Utf8,
                "dim_keys": pl.Utf8,
                "link_confidence": pl.Float64,
            }
        )
    return pl.DataFrame(rows)


__all__ = ["build_kpi_links"]
