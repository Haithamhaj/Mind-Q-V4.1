from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, Field, RootModel, ValidationError, model_validator

GateStatus = Literal["PASS", "WARN", "STOP"]
Decision = Literal["APPROVE", "REJECT"]
Severity = Literal["low", "medium", "high", "critical"]
RuleLevel = Literal["WARN", "STOP"]


class DataGateStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    STOP = "STOP"


class BusinessGateStatus(str, Enum):
    OK = "OK"
    ALERT = "ALERT"
    CRITICAL_ALERT = "CRITICAL_ALERT"


class KPIDelta(BaseModel):
    name: str
    original: Optional[float] = None
    recomputed: float
    abs_delta: Optional[float] = None
    rel_delta_pct: Optional[float] = None


class RuleFailure(BaseModel):
    rule_id: str
    level: RuleLevel
    count: int
    sample_ids: List[str] = Field(default_factory=list)
    message: str
    sla_clause: Optional[Dict[str, Any]] = None


class RowDecision(BaseModel):
    entity_id: str
    decision: Decision
    reasons: List[str] = Field(default_factory=list)
    rules_hits: List[str] = Field(default_factory=list)
    suggested_fix: Optional[str] = None
    severity: Optional[Severity] = None


class OpsAction(BaseModel):
    action_type: Literal["FIX_DATA", "REQUEST_UPDATE", "REPRICE", "HOLD_SHIPMENT"]
    entity_id: str
    severity: Severity
    reason: str
    suggested_fix: str


class ValidationReport(BaseModel):
    gate: Dict[str, Any]
    kpi_recalc: List[KPIDelta]
    rule_failures: List[RuleFailure]
    provenance: Dict[str, Any]
    unit_currency_meta: Dict[str, Any]
    perf: Dict[str, Any]
    bi_hints: Dict[str, Any]
    sla: List[Dict[str, Any]] = Field(default_factory=list)
    nzv_impact: Optional[Dict[str, Any]] = None
    business_alerts: Optional[Dict[str, Any]] = None


class KPIThresholds(BaseModel):
    kpi_abs_delta_max: float = 1e-6
    kpi_rel_delta_pct_warn: float = 2.0
    kpi_rel_delta_pct_stop: float = 5.0


KPIVisibility = Literal["public", "internal", "restricted"]
ColumnClassification = Literal["public", "internal", "sensitive", "pii"]


class KPIEntry(BaseModel):
    name: str
    expr: str
    dtype: Optional[str] = None
    unit: Optional[str] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    business_goal: Optional[str] = None
    ml_usage: Optional[str] = None
    default_dimensions: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    visibility: KPIVisibility = "internal"
    freshness_sla_hours: Optional[int] = Field(default=None, ge=1)
    llm_prompt: Optional[str] = None
    quality_notes: Optional[str] = None


class ColumnPolicy(BaseModel):
    name: str
    classification: ColumnClassification = "internal"
    include_in_bi_feed: bool = True
    include_in_semantic: bool = True
    include_in_exports: bool = True
    description: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class KPICatalog(BaseModel):
    version: int = 2
    thresholds: KPIThresholds = Field(default_factory=KPIThresholds)
    kpis: List[KPIEntry]
    columns: List[ColumnPolicy] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ensure_unique_names(self) -> "KPICatalog":
        names = [entry.name for entry in self.kpis]
        if len(names) != len(set(names)):
            raise ValueError("duplicate KPI names detected")
        column_names = [entry.name for entry in self.columns]
        if len(column_names) != len(set(column_names)):
            raise ValueError("duplicate column policy names detected")
        return self


class RuleType(str, Enum):
    RANGE = "range"
    ENUM = "enum"
    IMPLICATION = "implication"
    TIME_WINDOW = "time_window"
    CURRENCY = "currency"
    UNIT = "unit"


class RuleSpec(BaseModel):
    rule_id: str
    level: RuleLevel = "WARN"
    type: RuleType
    column: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    allowed: Optional[List[Any]] = None
    if_expr: Optional[str] = Field(default=None, description="Left expression for implication")
    then_expr: Optional[str] = Field(default=None, description="Right expression for implication")
    window_days: Optional[int] = None
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    message: Optional[str] = None
    suggested_fix: Optional[str] = None
    severity: Optional[Severity] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RuleSet(RootModel[List[RuleSpec]]):
    pass


class BIContractDashboard(BaseModel):
    id: str
    time_grain: Literal["day", "week", "month"]
    kpis: List[str]


class BIContract(BaseModel):
    version: int = 1
    bi_contract_id: str = "default"
    dashboards: List[BIContractDashboard]
    formatting: Dict[str, Any] = Field(default_factory=dict)
    color_rules: Dict[str, Dict[str, str]] = Field(default_factory=dict)

    @property
    def default_time_grain(self) -> str:
        if not self.dashboards:
            return "day"
        return self.dashboards[0].time_grain

    @property
    def kpis(self) -> List[str]:
        if not self.dashboards:
            return []
        all_kpis: List[str] = []
        for dashboard in self.dashboards:
            all_kpis.extend(dashboard.kpis)
        seen: set[str] = set()
        ordered: List[str] = []
        for item in all_kpis:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered


class WhatIfScenario(BaseModel):
    scenario_id: str
    description: Optional[str] = None
    adjustments: Dict[str, Any] = Field(default_factory=dict)


class WhatIfConfig(BaseModel):
    scenarios: List[WhatIfScenario]


@dataclass(slots=True)
class KPIComputationResult:
    name: str
    recomputed: float
    original: Optional[float]
    thresholds: KPIThresholds

    def to_delta(self) -> KPIDelta:
        if self.original is None:
            return KPIDelta(
                name=self.name,
                original=None,
                recomputed=self.recomputed,
                abs_delta=None,
                rel_delta_pct=None,
            )
        abs_delta = abs(self.recomputed - self.original)
        rel_delta_pct: Optional[float]
        if self.original == 0:
            rel_delta_pct = None
        else:
            rel_delta_pct = (abs_delta / abs(self.original)) * 100.0
        return KPIDelta(
            name=self.name,
            original=self.original,
            recomputed=self.recomputed,
            abs_delta=abs_delta,
            rel_delta_pct=rel_delta_pct,
        )


@dataclass(slots=True)
class RuleEvaluationResult:
    rule: RuleSpec
    failing_ids: List[str] = field(default_factory=list)
    message: Optional[str] = None
    sla_clause: Optional[Dict[str, Any]] = None

    @property
    def count(self) -> int:
        return len(self.failing_ids)

    def to_failure(self, sample_limit: int = 20) -> RuleFailure:
        return RuleFailure(
            rule_id=self.rule.rule_id,
            level=self.rule.level,
            count=self.count,
            sample_ids=self.failing_ids[:sample_limit],
            message=self.message or self.rule.message or "",
            sla_clause=self.sla_clause,
        )


def stable_hash(*parts: str, length: int = 12) -> str:
    digest = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
    return digest[:length]


def safe_model_dump(model: BaseModel) -> Dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True)


__all__ = [
    "GateStatus",
    "Decision",
    "Severity",
    "RuleLevel",
    "KPIDelta",
    "RuleFailure",
    "RowDecision",
    "OpsAction",
    "ValidationReport",
    "ColumnPolicy",
    "ColumnClassification",
    "KPIVisibility",
    "KPIThresholds",
    "KPIEntry",
    "KPICatalog",
    "RuleSpec",
    "RuleSet",
    "BIContract",
    "WhatIfConfig",
    "KPIComputationResult",
    "RuleEvaluationResult",
    "stable_hash",
    "safe_model_dump",
]
