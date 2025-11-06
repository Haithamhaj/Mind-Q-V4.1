from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence

from .terminology_loader import TerminologyRepository  # type: ignore


def _normalize_token(value: str) -> str:
    cleaned = re.sub(r"[\s_\-]+", " ", str(value or "")).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


def _default_label(column: str) -> str:
    token = str(column or "").strip()
    if not token:
        return "Unknown"
    parts = re.split(r"[_\-\s]+", token)
    formatted = " ".join(part.capitalize() for part in parts if part)
    return formatted or token


KPI_META: Dict[str, Dict[str, str]] = {
    "sla_achieved": {
        "label": "On-time delivery rate",
        "direction": "higher_is_better",
        "unit": "percentage",
    },
    "rto_rate": {
        "label": "Return-to-origin rate",
        "direction": "lower_is_better",
        "unit": "percentage",
    },
    "rto_flag": {
        "label": "Return shipment flag rate",
        "direction": "lower_is_better",
        "unit": "ratio",
    },
    "cod_amount": {
        "label": "Cash collected (COD)",
        "direction": "higher_is_better",
        "unit": "currency",
    },
}


DOMAIN_KEYWORDS: Dict[str, Sequence[str]] = {
    "Linehaul": ("linehaul", "line_haul", "hub_transit", "transit_delay", "transit"),
    "First Mile": ("pickup", "first_mile", "wh_pickup", "fm_"),
    "Last Mile": ("last_mile", "courier", "delivery", "attempt", "otp", "pod"),
    "Fulfillment": ("warehouse", "fulfillment", "inventory", "processing", "sorting", "sorter", "hub"),
    "Finance": ("cod", "amount", "value", "payment", "fee", "charge", "invoice", "cash"),
    "Risk": ("rto", "return", "cancel", "fraud", "dispute", "chargeback", "lost"),
    "Customer": ("nps", "csat", "complaint", "support", "feedback", "survey"),
    "Product": ("sku", "product", "category", "item"),
}

SENSITIVITY_KEYWORDS: Dict[str, str] = {
    "cod": "high",
    "rto": "high",
    "sla": "high",
    "delay": "high",
    "lead_time": "high",
    "return": "high",
    "cancel": "high",
    "complaint": "medium",
    "support": "medium",
}


@dataclass
class FeatureDescriptor:
    name: str
    label: str
    domain: str
    sensitivity: str
    description: Optional[str] = None


class ShippingCorrelationEnricher:
    """Attach shipping-aware semantics and impact metadata to correlation records."""

    def __init__(
        self,
        artifacts_root: Path | str,
        run_id: str,
        *,
        repo: Optional[TerminologyRepository] = None,
        numeric_stats: Optional[Mapping[str, Mapping[str, float]]] = None,
        kpi_synonyms: Optional[Mapping[str, Sequence[str]]] = None,
    ) -> None:
        self._artifacts_root = Path(artifacts_root)
        self._run_id = run_id
        self._repo = repo or TerminologyRepository(self._artifacts_root, run_id)
        self._numeric_stats: Dict[str, Mapping[str, float]] = dict(numeric_stats or {})
        self._kpi_lookup = self._build_kpi_lookup(kpi_synonyms or {})
        self._descriptor_cache: Dict[str, FeatureDescriptor] = {}

    def set_numeric_stats(self, stats: Mapping[str, Mapping[str, float]]) -> None:
        self._numeric_stats = dict(stats)

    def _build_kpi_lookup(self, synonyms: Mapping[str, Sequence[str]]) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for canonical, values in synonyms.items():
            canon_norm = _normalize_token(canonical)
            if canon_norm:
                lookup[canon_norm] = str(canonical)
            for alias in values:
                norm = _normalize_token(alias)
                if norm:
                    lookup[norm] = str(canonical)
        return lookup

    def _describe_from_repo(self, column: str) -> Optional[FeatureDescriptor]:
        try:
            entry = self._repo.find_column(column)
        except Exception:  # pragma: no cover - defensive
            entry = None
        if not entry:
            return None
        label = str(entry.get("display") or entry.get("title") or _default_label(column))
        description = entry.get("description")
        domain = str(entry.get("domain") or entry.get("business_domain") or "").strip()
        sensitivity = str(entry.get("criticality") or entry.get("sensitivity") or "").strip().lower()
        if not domain:
            domain = self._guess_domain(column)
        if sensitivity not in {"low", "medium", "high"}:
            sensitivity = self._guess_sensitivity(column, default="medium")
        return FeatureDescriptor(
            name=column,
            label=label,
            description=str(description) if isinstance(description, str) else None,
            domain=domain,
            sensitivity=sensitivity,
        )

    def describe_feature(self, column: str) -> FeatureDescriptor:
        if column in self._descriptor_cache:
            return self._descriptor_cache[column]
        descriptor = self._describe_from_repo(column)
        if descriptor is None:
            label = _default_label(column)
            domain = self._guess_domain(column)
            sensitivity = self._guess_sensitivity(column, default="medium")
            descriptor = FeatureDescriptor(name=column, label=label, domain=domain, sensitivity=sensitivity)
        self._descriptor_cache[column] = descriptor
        return descriptor

    def identify_kpi(self, feature_a: str, feature_b: str) -> Optional[Dict[str, str]]:
        for feature in (feature_a, feature_b):
            norm = _normalize_token(feature)
            canonical = self._kpi_lookup.get(norm)
            if canonical:
                meta = KPI_META.get(canonical, {})
                return {
                    "id": canonical,
                    "feature": feature,
                    "label": meta.get("label") or _default_label(canonical),
                    "direction": meta.get("direction", "higher_is_better"),
                    "unit": meta.get("unit", ""),
                }
        return None

    def _guess_domain(self, column: str) -> str:
        token = _normalize_token(column)
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(keyword in token for keyword in keywords):
                return domain
        if "time" in token or "sla" in token or "delivery" in token:
            return "Operations"
        if "cod" in token or "amount" in token or "revenue" in token:
            return "Finance"
        if "return" in token or "rto" in token or "cancel" in token:
            return "Risk"
        return "Operations"

    def _guess_sensitivity(self, column: str, *, default: str = "medium") -> str:
        token = _normalize_token(column)
        for keyword, level in SENSITIVITY_KEYWORDS.items():
            if keyword in token:
                return level
        if "rto" in token or "sla" in token:
            return "high"
        return default

    def _numeric_stat(self, column: str, key: str) -> Optional[float]:
        stats = self._numeric_stats.get(column)
        if not stats:
            return None
        value = stats.get(key)
        if value is None:
            return None
        try:
            numeric = float(value)
            if math.isfinite(numeric):
                return numeric
        except (TypeError, ValueError):
            return None
        return None

    def enrich_pair(
        self,
        feature_a: str,
        feature_b: str,
        correlation: float,
        sample_size: int,
        *,
        method: str,
        notes: Optional[Mapping[str, object]] = None,
    ) -> Dict[str, object]:
        descriptor_a = self.describe_feature(feature_a)
        descriptor_b = self.describe_feature(feature_b)
        enrichment: Dict[str, object] = {
            "feature_a_label": descriptor_a.label,
            "feature_b_label": descriptor_b.label,
            "feature_a_domain": descriptor_a.domain,
            "feature_b_domain": descriptor_b.domain,
            "feature_a_sensitivity": descriptor_a.sensitivity,
            "feature_b_sensitivity": descriptor_b.sensitivity,
        }

        if descriptor_a.description:
            enrichment["feature_a_description"] = descriptor_a.description
        if descriptor_b.description:
            enrichment["feature_b_description"] = descriptor_b.description

        kpi_info = self.identify_kpi(feature_a, feature_b)
        if kpi_info:
            enrichment.update(
                {
                    "kpi_tag": kpi_info["id"],
                    "kpi_label": kpi_info["label"],
                    "kpi_direction": kpi_info["direction"],
                    "kpi_unit": kpi_info["unit"],
                    "kpi_feature": kpi_info["feature"],
                }
            )
            effect = self._compute_effect(kpi_info, feature_a, feature_b, correlation)
        else:
            effect = None

        if effect:
            enrichment.update(effect)

        enrichment["business_label"] = f"{descriptor_a.label} ↔ {descriptor_b.label}"
        enrichment["sensitivity"] = self._resolve_sensitivity(correlation, descriptor_a, descriptor_b, effect)
        enrichment["impact_summary"] = self._build_summary(
            descriptor_a,
            descriptor_b,
            correlation,
            effect,
            kpi_info,
            sample_size,
            method,
            notes,
        )
        return enrichment

    def _compute_effect(
        self,
        kpi_info: Mapping[str, str],
        feature_a: str,
        feature_b: str,
        correlation: float,
    ) -> Optional[Dict[str, object]]:
        kpi_feature = str(kpi_info["feature"])
        driver_feature = feature_b if kpi_feature == feature_a else feature_a
        std_kpi = self._numeric_stat(kpi_feature, "std")
        mean_kpi = self._numeric_stat(kpi_feature, "mean")
        if std_kpi is None or std_kpi <= 0:
            return None

        delta = correlation * std_kpi
        delta_pct: Optional[float] = None
        if mean_kpi and not math.isclose(mean_kpi, 0.0, abs_tol=1e-9):
            delta_pct = (delta / abs(mean_kpi)) * 100.0

        direction_meta = kpi_info.get("direction", "higher_is_better")
        if direction_meta == "higher_is_better":
            positive = correlation >= 0
        else:
            positive = correlation <= 0
        effect_direction = "improves" if positive else "worsens"

        driver_descriptor = self.describe_feature(driver_feature)

        payload: Dict[str, object] = {
            "impact_driver_feature": driver_feature,
            "impact_driver_label": driver_descriptor.label,
            "effect_direction": effect_direction,
            "expected_kpi_delta": delta,
        }
        if delta_pct is not None and math.isfinite(delta_pct):
            payload["expected_kpi_delta_pct"] = delta_pct
        payload["effect_is_positive"] = positive
        payload["driver_domain"] = driver_descriptor.domain
        return payload

    def _resolve_sensitivity(
        self,
        correlation: float,
        descriptor_a: FeatureDescriptor,
        descriptor_b: FeatureDescriptor,
        effect: Optional[Mapping[str, object]],
    ) -> str:
        magnitude = abs(correlation)
        delta_pct = None
        if effect:
            delta_pct = effect.get("expected_kpi_delta_pct")
            if isinstance(delta_pct, (int, float)) and not math.isfinite(float(delta_pct)):
                delta_pct = None

        if descriptor_a.sensitivity == "high" or descriptor_b.sensitivity == "high":
            return "high"
        if magnitude >= 0.55:
            return "high"
        if delta_pct is not None and abs(float(delta_pct)) >= 5:
            return "high"
        if magnitude >= 0.35:
            return "medium"
        return "low"

    def _build_summary(
        self,
        descriptor_a: FeatureDescriptor,
        descriptor_b: FeatureDescriptor,
        correlation: float,
        effect: Optional[Mapping[str, object]],
        kpi_info: Optional[Mapping[str, str]],
        sample_size: int,
        method: str,
        notes: Optional[Mapping[str, object]],
    ) -> str:
        corr_fmt = f"{correlation:+.2f}"
        if effect and kpi_info:
            driver_label = effect.get("impact_driver_label") or descriptor_a.label
            kpi_label = kpi_info.get("label") or _default_label(kpi_info.get("id", "KPI"))
            direction = str(effect.get("effect_direction") or "shifts")
            delta_pct = effect.get("expected_kpi_delta_pct")
            if isinstance(delta_pct, (int, float)):
                delta_text = f"{float(delta_pct):+.1f}%"
            else:
                delta = effect.get("expected_kpi_delta")
                if isinstance(delta, (int, float)):
                    delta_text = f"{float(delta):+.2f}"
                else:
                    delta_text = corr_fmt
            return (
                f"{driver_label} {direction} {kpi_label} by {delta_text} (r={corr_fmt}, n={sample_size}, {method})."
            )

        note_hint = ""
        if notes and isinstance(notes, Mapping):
            top = notes.get("top_category") or notes.get("top_pair")
            if isinstance(top, Mapping):
                values = [str(v) for v in top.values() if isinstance(v, (str, int, float))]
                if values:
                    note_hint = f" Top signal: {' / '.join(values[:3])}."

        return (
            f"{descriptor_a.label} moves with {descriptor_b.label} (r={corr_fmt}, n={sample_size}, {method}).{note_hint}"
        )


class CorrelationHistoryTracker:
    """Maintain rolling history of correlation pairs across runs to flag persistent patterns."""

    def __init__(self, artifacts_root: Path | str, *, window: int = 6, persistence_threshold: int = 3) -> None:
        self._root = Path(artifacts_root)
        self._window = max(1, int(window))
        self._threshold = max(1, int(persistence_threshold))
        self._store_path = self._root / "_global" / "correlation_history.json"
        self._store_path.parent.mkdir(parents=True, exist_ok=True)

    def _pair_key(self, feature_a: str, feature_b: str) -> str:
        ordered = sorted([str(feature_a), str(feature_b)])
        return "::".join(ordered)

    def _load(self) -> Dict[str, Dict[str, object]]:
        if not self._store_path.exists():
            return {}
        try:
            payload = json.loads(self._store_path.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover - defensive
            return {}
        if isinstance(payload, dict):
            return payload
        return {}

    def _save(self, payload: Mapping[str, object]) -> None:
        self._store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def mark_and_update(self, run_id: str, records: Iterable[Mapping[str, object]]) -> None:
        history = self._load()
        changed = False
        for record in records:
            feature_a = record.get("feature_a")
            feature_b = record.get("feature_b")
            if not feature_a or not feature_b:
                continue
            key = self._pair_key(str(feature_a), str(feature_b))
            details = history.get(key) or {"seen_runs": []}
            seen_runs = list(details.get("seen_runs") or [])
            if run_id not in seen_runs:
                seen_runs.append(run_id)
                changed = True
            seen_runs = seen_runs[-self._window :]
            details["seen_runs"] = seen_runs
            details["last_seen"] = run_id
            details["seen_count"] = len(seen_runs)
            history[key] = details
            is_persistent = len(seen_runs) >= self._threshold
            record["is_persistent"] = is_persistent
            record["history_runs"] = seen_runs
        if changed:
            self._save(history)

