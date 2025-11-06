from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional


def _normalise_metric_id(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _normalise_target(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def build_gap_analysis(
    expectations: Iterable[Mapping[str, Any]],
    sla_payload: Mapping[str, Any],
    metric_catalog: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    kpis = sla_payload.get("kpis") or []
    legacy_metrics = sla_payload.get("metrics") or []
    overall = sla_payload.get("summary") or sla_payload.get("overall") or {}

    metrics_by_id: Dict[str, Mapping[str, Any]] = {}
    for entry in kpis:
        metric_id = _normalise_metric_id(str(entry.get("id") or ""))
        if metric_id:
            metrics_by_id[metric_id] = entry

    if not metrics_by_id:
        for metric in legacy_metrics:
            metric_id = _normalise_metric_id(str(metric.get("id") or ""))
            if metric_id:
                metrics_by_id[metric_id] = metric

    analysis: List[Dict[str, Any]] = []
    for expectation in expectations:
        metric_id = _normalise_metric_id(str(expectation.get("metric_id") or expectation.get("id") or ""))
        if not metric_id:
            continue

        actual_metric = metrics_by_id.get(metric_id)
        actual_value = None
        if actual_metric:
            if "raw_value" in actual_metric and actual_metric.get("raw_value") is not None:
                actual_value = float(actual_metric.get("raw_value"))
            elif "value" in actual_metric and actual_metric.get("value") is not None:
                actual_value = float(actual_metric.get("value"))
            elif "value_pct" in actual_metric and actual_metric.get("value_pct") is not None:
                actual_value = float(actual_metric.get("value_pct")) / 100.0
        target_value = _normalise_target(expectation.get("target_value"))

        delta = None
        if actual_value is not None and target_value is not None:
            delta = float(actual_value) - target_value

        metric_meta = (metric_catalog or {}).get(metric_id, {})
        label = expectation.get("metric_name")
        if not label and actual_metric:
            label = actual_metric.get("label")
        if not label:
            label = metric_meta.get("label")

        analysis.append(
            {
                "metric_id": metric_id,
                "metric_label": label,
                "target_value": target_value,
                "target_unit": expectation.get("target_unit"),
                "actual_value": actual_value,
                "delta": delta,
                "timeframe": expectation.get("timeframe"),
                "condition": expectation.get("condition"),
                "responsible_team": expectation.get("responsible_team"),
                "source_document": expectation.get("source_document"),
                "citation": expectation.get("citation"),
                "rationale": expectation.get("rationale"),
                "status": _infer_status(delta, expectation),
            }
        )

    return {
        "overall": overall,
        "analysis": analysis,
    }


def _infer_status(delta: Optional[float], expectation: Mapping[str, Any]) -> str:
    if delta is None:
        return "unknown"
    tolerance = expectation.get("tolerance")
    if tolerance is not None:
        try:
            tolerance_value = float(tolerance)
            if abs(delta) <= tolerance_value:
                return "within_tolerance"
        except (TypeError, ValueError):
            pass
    if delta >= 0:
        return "on_track"
    return "behind"
