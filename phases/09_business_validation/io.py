from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Tuple

import yaml

from . import models

UTF8 = "utf-8"
DEFAULT_TIMEZONE = "Asia/Riyadh"

KPI_CATALOG_SEED = {
    "version": 2,
    "thresholds": {
        "kpi_abs_delta_max": 1e-6,
        "kpi_rel_delta_pct_warn": 2.0,
        "kpi_rel_delta_pct_stop": 5.0,
    },
    "kpis": [
        {
            "name": "orders_cnt",
            "expr": "COUNT(*)",
            "dtype": "integer",
            "description": "Total number of orders captured during the grain window.",
            "owner": "ops_analytics",
            "business_goal": "Measure overall order volume to spot demand spikes.",
            "ml_usage": "demand_forecasting",
            "default_dimensions": ["DESTINATION", "RECEIVER_MODE"],
            "tags": ["core", "volume"],
            "visibility": "public",
            "freshness_sla_hours": 6,
            "quality_notes": "Guard against duplicate AWB rows prior to this stage.",
        },
        {
            "name": "cod_rate",
            "expr": "AVG(CASE WHEN RECEIVER_MODE='COD' THEN 1 ELSE 0 END)",
            "dtype": "percentage",
            "description": "Share of orders using cash on delivery.",
            "owner": "finance",
            "business_goal": "Monitor COD adoption to control cash handling costs.",
            "ml_usage": "payment_preference_classifier",
            "default_dimensions": ["DESTINATION", "forward_company"],
            "tags": ["core", "payment"],
            "visibility": "internal",
            "freshness_sla_hours": 6,
            "quality_notes": "Requires RECEIVER_MODE normalization; exclude nulls.",
            "llm_prompt": "Explain how changes in COD adoption impact cash collection risk.",
        },
        {
            "name": "lead_time_p90",
            "expr": "APPROX_QUANTILE(lead_time_hours, 0.9)",
            "dtype": "hours",
            "description": "90th percentile of door-to-door lead time in hours.",
            "owner": "ops_analytics",
            "business_goal": "Track high-percentile delivery performance.",
            "ml_usage": "sla_breach_model",
            "default_dimensions": ["DESTINATION", "forward_company"],
            "tags": ["sla", "timeliness"],
            "visibility": "restricted",
            "freshness_sla_hours": 3,
            "quality_notes": "Needs at least 200 non-null lead time samples to be reliable.",
        },
    ],
    "columns": [
        {
            "name": "sender_name",
            "classification": "pii",
            "include_in_bi_feed": False,
            "include_in_semantic": False,
            "include_in_exports": False,
            "description": "Customer provided sender name field.",
            "tags": ["customer", "pii"],
        },
        {
            "name": "sender_phone",
            "classification": "pii",
            "include_in_bi_feed": False,
            "include_in_semantic": False,
            "include_in_exports": False,
            "description": "Customer contact phone number for sender.",
            "tags": ["customer", "pii"],
        },
        {
            "name": "receiver_name",
            "classification": "pii",
            "include_in_bi_feed": False,
            "include_in_semantic": False,
            "include_in_exports": False,
            "description": "End customer name.",
            "tags": ["customer", "pii"],
        },
        {
            "name": "receiver_phone",
            "classification": "pii",
            "include_in_bi_feed": False,
            "include_in_semantic": False,
            "include_in_exports": False,
            "description": "End customer phone number.",
            "tags": ["customer", "pii"],
        },
        {
            "name": "forward_company",
            "classification": "internal",
            "include_in_bi_feed": True,
            "include_in_semantic": True,
            "include_in_exports": True,
            "description": "Assigned logistics provider or courier.",
            "tags": ["carrier"],
        },
        {
            "name": "driver_code",
            "classification": "sensitive",
            "include_in_bi_feed": True,
            "include_in_semantic": False,
            "include_in_exports": False,
            "description": "Internal driver identifier; suppress from external exports.",
            "tags": ["carrier"],
        },
    ],
}

BI_CONTRACT_SEED = {
    "version": 1,
    "bi_contract_id": "default",
    "dashboards": [
        {
            "id": "ops_overview",
            "time_grain": "day",
            "kpis": ["orders_cnt", "cod_total", "cod_avg", "cod_rate", "sla_on_time_pct", "rto_pct"],
        }
    ],
    "formatting": {
        "locale": "ar",
        "currency": "SAR",
    },
    "color_rules": {
        "cod_rate": {
            "warn": ">=0.7",
            "stop": ">=0.8",
        }
    },
}

SAMPLE_RULES_SEED = [
    {
        "rule_id": "kpi_cod_amount_non_negative",
        "level": "STOP",
        "type": "range",
        "column": "COD_AMOUNT",
        "min": 0.0,
        "message": "COD amount must be non-negative",
        "suggested_fix": "Investigate COD capture source and correct negatives.",
        "severity": "high",
    },
    {
        "rule_id": "status_known",
        "level": "WARN",
        "type": "enum",
        "column": "STATUS",
        "allowed": ["DELIVERED", "IN_TRANSIT", "CANCELLED", "RETURNED"],
        "message": "Unknown status detected",
        "suggested_fix": "Align status codes with canonical list.",
        "severity": "medium",
    },
]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json_sorted(payload: Any, path: Path) -> None:
    _ensure_parent(path)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(serialized, encoding=UTF8)


def write_jsonl(records: Iterable[Mapping[str, Any]], path: Path) -> None:
    _ensure_parent(path)
    with path.open("w", encoding=UTF8) as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def ensure_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    _ensure_parent(path)
    if not path.exists():
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding=UTF8)


def ensure_sample_rules(path: Path) -> None:
    _ensure_parent(path)
    if not path.exists():
        path.write_text(yaml.safe_dump(SAMPLE_RULES_SEED, sort_keys=False, allow_unicode=True), encoding=UTF8)


def load_kpi_catalog(path: Path) -> models.KPICatalog:
    ensure_yaml(path, KPI_CATALOG_SEED)
    payload = yaml.safe_load(path.read_text(encoding=UTF8)) or {}
    return models.KPICatalog.model_validate(payload)


def load_rules(rules_dir: Path) -> models.RuleSet:
    rules: List[models.RuleSpec] = []
    if not rules_dir.exists():
        ensure_sample_rules(rules_dir / "sample_rules.yaml")
    for yaml_path in sorted(rules_dir.glob("*.yaml")):
        payload = yaml.safe_load(yaml_path.read_text(encoding=UTF8))
        if not payload:
            continue
        if isinstance(payload, dict):
            payload = [payload]
        for item in payload:
            try:
                rules.append(models.RuleSpec.model_validate(item))
            except Exception as exc:  # pragma: no cover - defensive
                raise ValueError(f"Invalid rule definition in {yaml_path}: {exc}") from exc
    return models.RuleSet.model_validate(rules)


def load_bi_contract(path: Path) -> models.BIContract:
    ensure_yaml(path, BI_CONTRACT_SEED)
    payload = yaml.safe_load(path.read_text(encoding=UTF8)) or {}
    return models.BIContract.model_validate(payload)


def load_what_if(path: Optional[Path]) -> Optional[models.WhatIfConfig]:
    if path is None or not path.exists():
        return None
    payload = yaml.safe_load(path.read_text(encoding=UTF8))
    if not payload:
        return None
    return models.WhatIfConfig.model_validate(payload)


def copy_configs_snapshot(dest_dir: Path, kpi_path: Path, rules_dir: Path, bi_contract_path: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    # copy KPI catalog
    (dest_dir / "kpi_catalog.yaml").write_text(kpi_path.read_text(encoding=UTF8), encoding=UTF8)
    # copy BI contract
    (dest_dir / "bi_contract.yaml").write_text(bi_contract_path.read_text(encoding=UTF8), encoding=UTF8)
    # copy rules
    rules_snapshot_dir = dest_dir / "rules"
    rules_snapshot_dir.mkdir(parents=True, exist_ok=True)
    for rule_path in sorted(rules_dir.glob("*.yaml")):
        target = rules_snapshot_dir / rule_path.name
        target.write_text(rule_path.read_text(encoding=UTF8), encoding=UTF8)


def ensure_contract(schema: Mapping[str, Any], path: Path) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True), encoding=UTF8)


def write_parquet(df: "pl.DataFrame", path: Path) -> None:  # type: ignore[name-defined]
    import polars as pl

    _ensure_parent(path)
    if not isinstance(df, pl.DataFrame):
        df = pl.DataFrame(df)
    df.write_parquet(path.as_posix())


def ensure_configs_structure(project_root: Path) -> Tuple[Path, Path, Path]:
    kpi_path = project_root / "configs" / "kpi" / "kpi_catalog.yaml"
    rules_dir = project_root / "configs" / "rules"
    bi_contract_path = project_root / "configs" / "bi" / "bi_contract.yaml"

    ensure_yaml(kpi_path, KPI_CATALOG_SEED)
    ensure_sample_rules(rules_dir / "sample_rules.yaml")
    ensure_yaml(bi_contract_path, BI_CONTRACT_SEED)
    return kpi_path, rules_dir, bi_contract_path


__all__ = [
    "DEFAULT_TIMEZONE",
    "write_json_sorted",
    "write_jsonl",
    "write_parquet",
    "load_kpi_catalog",
    "load_rules",
    "load_bi_contract",
    "load_what_if",
    "ensure_configs_structure",
    "copy_configs_snapshot",
    "ensure_contract",
]
