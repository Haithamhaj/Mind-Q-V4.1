from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

HASH_TOKEN_RE = re.compile(r"^[a-f0-9]{6,}$", re.IGNORECASE)
NUMERIC_TOKEN_RE = re.compile(r"^\d{4,}$")

STATUS_PRIORITY = {
    "stop": 3,
    "warn": 2,
    "pass": 1,
    "unknown": 0,
}


def _filter_mapping_list(value: Any) -> List[Mapping[str, Any]]:
    if not isinstance(value, Iterable):
        return []
    result: List[Mapping[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            result.append(item)
    return result


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _normalize_percentage(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if -1.0 <= value <= 1.0:
        value *= 100.0
    value = max(min(value, 100.0), 0.0)
    return round(value, 2)


def _normalize_metric_value(value: Optional[float], metric_format: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    if metric_format == "percentage":
        return _normalize_percentage(value)
    return round(value, 2)


def _clean_document_label(raw: Optional[str]) -> str:
    if not raw:
        return ""
    value = str(raw).strip()
    value = value.replace("\\", "/")
    value = value.split("/")[-1]
    value = re.sub(r"\.[A-Za-z0-9]{1,4}$", "", value)
    tokens = [token.strip() for token in re.split(r"[\s_\-]+", value) if token.strip()]
    filtered = [
        token
        for token in tokens
        if not HASH_TOKEN_RE.match(token)
        and not NUMERIC_TOKEN_RE.match(token)
    ]
    if not filtered:
        filtered = tokens
    label = " ".join(filtered)
    label = re.sub(r"\s+", " ", label).strip()
    return label or value or raw


DOCUMENT_TYPE_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("supplier_contract", ("contract", "supplier", "vendor", "اتفاق", "مورد")),
    ("delivery_agreement", ("delivery", "logistics", "ship", "توصيل", "خدمة")),
    ("operations_policy", ("policy", "operations", "تشغيل", "سياسة")),
    ("operations_procedure", ("sop", "procedure", "process", "إجراء")),
    ("service_level", ("sla", "service level", "service-level")),
]


def _infer_document_type(title: str, media_type: Optional[str], fallback: Optional[str] = None) -> str:
    label = title.lower()
    for doc_type, keywords in DOCUMENT_TYPE_RULES:
        if any(keyword in label for keyword in keywords):
            return doc_type
    if fallback:
        fallback_label = fallback.lower()
        for doc_type, keywords in DOCUMENT_TYPE_RULES:
            if any(keyword in fallback_label for keyword in keywords):
                return doc_type
    if media_type:
        if "spreadsheet" in media_type or media_type.endswith(("excel", "sheet")):
            return "operations_policy"
    return "other"


def _dedupe_list(values: Iterable[Any]) -> List[Any]:
    seen: Dict[Any, bool] = {}
    result: List[Any] = []
    for item in values:
        if item in seen:
            continue
        seen[item] = True
        result.append(item)
    return result


def _status_from_counts(pass_count: int, warn_count: int, stop_count: int, total_terms: int) -> str:
    if stop_count > 0:
        return "stop"
    if warn_count > 0:
        return "warn"
    if total_terms > 0 and pass_count == total_terms:
        return "pass"
    if total_terms == 0:
        return "unknown"
    return "pass"


def _build_catalog_lookup(metric_catalog: Mapping[str, Mapping[str, Any]]) -> Dict[str, Tuple[str, Mapping[str, Any]]]:
    lookup: Dict[str, Tuple[str, Mapping[str, Any]]] = {}
    for key, info in metric_catalog.items():
        candidates = {key, key.replace("_", " "), key.replace("-", " ")}
        for candidate in candidates:
            lookup[candidate.lower()] = (key, info)
    return lookup


def _resolve_kpi_id(raw_id: Any, catalog_lookup: Mapping[str, Tuple[str, Mapping[str, Any]]]) -> Tuple[str, Mapping[str, Any]]:
    key = str(raw_id or "").strip()
    lowered = key.lower()
    if lowered in catalog_lookup:
        return catalog_lookup[lowered]
    normalized = lowered.replace("-", " ").replace("_", " ")
    if normalized in catalog_lookup:
        return catalog_lookup[normalized]
    return key, {}


def _merge_manifest_contract_entry(
    document_id: str,
    entry: Mapping[str, Any],
    manifest_index: Mapping[str, Mapping[str, Any]],
    contracts_index: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    if document_id in manifest_index:
        return manifest_index[document_id]
    normalized = entry.get("normalized_path")
    if normalized and normalized in manifest_index:
        return manifest_index[normalized]
    sha = entry.get("sha256")
    if sha and sha in manifest_index:
        return manifest_index[sha]
    if document_id in contracts_index:
        return contracts_index[document_id]
    if normalized and normalized in contracts_index:
        return contracts_index[normalized]
    if sha and sha in contracts_index:
        return contracts_index[sha]
    return {}


def _collect_document_cards(
    run_id: str,
    summary_entries: Sequence[Mapping[str, Any]],
    results_by_document: Mapping[str, List[Mapping[str, Any]]],
    manifest_index: Mapping[str, Mapping[str, Any]],
    contracts_index: Mapping[str, Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, int], Dict[str, Dict[str, Any]]]:
    documents: List[Dict[str, Any]] = []
    lookup: Dict[str, Dict[str, Any]] = {}
    stats: Dict[str, int] = {
        "documents_total": 0,
        "terms_extracted": 0,
        "terms_evaluated": 0,
        "warn_terms": 0,
        "stop_terms": 0,
        "documents_with_warnings": 0,
        "documents_without_terms": 0,
    }

    for entry in summary_entries:
        raw_id = (
            entry.get("document_id")
            or entry.get("normalized_path")
            or entry.get("sha256")
            or entry.get("source_path")
        )
        document_id = str(raw_id or f"{run_id}-document-{len(documents) + 1}")
        manifest_entry = _merge_manifest_contract_entry(document_id, entry, manifest_index, contracts_index)
        display_name = _clean_document_label(entry.get("title") or manifest_entry.get("original_name") or document_id)
        doc_results = results_by_document.get(document_id, [])

        extracted_terms = len(entry.get("terms") or [])
        evaluated_terms = len(doc_results)
        pass_count = sum(1 for result in doc_results if str(result.get("status", "")).upper() == "PASS")
        warn_count = sum(1 for result in doc_results if str(result.get("status", "")).upper() == "WARN")
        stop_count = sum(1 for result in doc_results if str(result.get("status", "")).upper() == "STOP")
        status = _status_from_counts(pass_count, warn_count, stop_count, evaluated_terms)

        compliance_pct = None
        if evaluated_terms:
            compliance_pct = round((pass_count / evaluated_terms) * 100.0, 2)

        document_type = entry.get("detected_type") or manifest_entry.get("detected_type")
        document_type = document_type or _infer_document_type(
            display_name,
            manifest_entry.get("media_type"),
            entry.get("media_type"),
        )

        notes = _dedupe_list(
            list(entry.get("notes") or []) + list(manifest_entry.get("notes") or []),
        )

        card: Dict[str, Any] = {
            "id": document_id,
            "title": entry.get("title") or manifest_entry.get("title") or display_name,
            "display_name": display_name,
            "type": document_type,
            "status": status,
            "compliance_pct": compliance_pct,
            "term_counts": {
                "extracted": extracted_terms,
                "evaluated": evaluated_terms,
                "passed": pass_count,
                "warn": warn_count,
                "stop": stop_count,
            },
            "kpi_refs": [],
            "notes": notes,
            "sources": {
                "document_id": document_id,
                "normalized_path": entry.get("normalized_path") or manifest_entry.get("normalized_path"),
                "stored_path": manifest_entry.get("stored_path"),
                "sha256": entry.get("sha256") or manifest_entry.get("sha256"),
                "media_type": manifest_entry.get("media_type") or entry.get("media_type"),
                "size_bytes": manifest_entry.get("size_bytes") or entry.get("size_bytes"),
            },
        }
        documents.append(card)
        lookup[document_id] = card

        stats["documents_total"] += 1
        stats["terms_extracted"] += extracted_terms
        stats["terms_evaluated"] += evaluated_terms
        stats["warn_terms"] += warn_count
        stats["stop_terms"] += stop_count
        if evaluated_terms == 0:
            stats["documents_without_terms"] += 1
        if stop_count or warn_count:
            stats["documents_with_warnings"] += 1

    for document_id, doc_results in results_by_document.items():
        if document_id in lookup:
            continue
        manifest_entry = manifest_index.get(document_id) or contracts_index.get(document_id) or {}
        display_name = _clean_document_label(manifest_entry.get("original_name") or document_id)
        pass_count = sum(1 for result in doc_results if str(result.get("status", "")).upper() == "PASS")
        warn_count = sum(1 for result in doc_results if str(result.get("status", "")).upper() == "WARN")
        stop_count = sum(1 for result in doc_results if str(result.get("status", "")).upper() == "STOP")
        evaluated_terms = len(doc_results)
        compliance_pct = round((pass_count / evaluated_terms) * 100.0, 2) if evaluated_terms else None
        status = _status_from_counts(pass_count, warn_count, stop_count, evaluated_terms)

        card = {
            "id": document_id,
            "title": manifest_entry.get("title") or display_name,
            "display_name": display_name,
            "type": _infer_document_type(display_name, manifest_entry.get("media_type")),
            "status": status,
            "compliance_pct": compliance_pct,
            "term_counts": {
                "extracted": len(manifest_entry.get("terms") or []),
                "evaluated": evaluated_terms,
                "passed": pass_count,
                "warn": warn_count,
                "stop": stop_count,
            },
            "kpi_refs": [],
            "notes": list(manifest_entry.get("notes") or []),
            "sources": {
                "document_id": document_id,
                "normalized_path": manifest_entry.get("normalized_path"),
                "stored_path": manifest_entry.get("stored_path"),
                "sha256": manifest_entry.get("sha256"),
                "media_type": manifest_entry.get("media_type"),
                "size_bytes": manifest_entry.get("size_bytes"),
            },
        }
        documents.append(card)
        lookup[document_id] = card

    return documents, stats, lookup


def _collect_kpi_cards(
    kpi_values: Mapping[str, Optional[float]],
    kpi_original_values: Mapping[str, Optional[float]],
    kpi_deltas: Mapping[str, Mapping[str, Any]],
    targets: Mapping[str, Mapping[str, Any]],
    sla_results: Sequence[Mapping[str, Any]],
    metric_catalog: Mapping[str, Mapping[str, Any]],
    documents_lookup: Mapping[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    catalog_lookup = _build_catalog_lookup(metric_catalog)
    cards: List[Dict[str, Any]] = []
    kpi_lookup: Dict[str, Dict[str, Any]] = {}

    results_by_kpi: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for result in sla_results:
        raw_kpi = result.get("kpi")
        canonical_id, _ = _resolve_kpi_id(raw_kpi, catalog_lookup)
        if not canonical_id:
            continue
        results_by_kpi[canonical_id].append(result)

    candidate_ids = set(kpi_values.keys()) | set(results_by_kpi.keys()) | set(targets.keys())

    for raw_id in sorted(candidate_ids):
        canonical_id, info = _resolve_kpi_id(raw_id, catalog_lookup)
        if not canonical_id:
            continue

        metric_format = info.get("format") if info else None
        unit = info.get("unit") if info else None
        label = info.get("label") if info else _clean_document_label(canonical_id).title()

        raw_value = _safe_float(kpi_values.get(raw_id) if raw_id in kpi_values else kpi_values.get(canonical_id))
        if raw_value is None:
            raw_value = _safe_float(kpi_values.get(canonical_id))
        normalized_value = _normalize_metric_value(raw_value, metric_format)

        delta_payload = kpi_deltas.get(raw_id) or kpi_deltas.get(canonical_id) or {}

        target_payload = targets.get(raw_id) or targets.get(canonical_id) or {}
        warn_raw = _safe_float(
            target_payload.get("warn")
            or target_payload.get("warn_threshold")
            or target_payload.get("warning")
        )
        stop_raw = _safe_float(
            target_payload.get("stop")
            or target_payload.get("stop_threshold")
            or target_payload.get("critical")
        )
        warn_pct = _normalize_metric_value(warn_raw, metric_format)
        stop_pct = _normalize_metric_value(stop_raw, metric_format)
        direction = target_payload.get("direction") or target_payload.get("comparison")

        result_records = results_by_kpi.get(canonical_id, [])
        best_status = "unknown"
        best_document_id = None
        best_reason = None
        best_result: Optional[Mapping[str, Any]] = None
        for result in result_records:
            status = str(result.get("status", "")).lower()
            if status not in STATUS_PRIORITY:
                continue
            if STATUS_PRIORITY[status] > STATUS_PRIORITY[best_status]:
                best_status = status
                best_document_id = result.get("source", {}).get("document_id") or result.get("raw", {}).get("document_id")
                best_reason = result.get("reason")
                best_result = result

        card: Dict[str, Any] = {
            "id": canonical_id,
            "label": label,
            "value_pct": normalized_value,
            "raw_value": raw_value,
            "unit": unit,
            "status": best_status,
            "direction": direction,
            "warn_threshold_pct": warn_pct,
            "stop_threshold_pct": stop_pct,
            "warn_threshold_raw": warn_raw,
            "stop_threshold_raw": stop_raw,
            "document_id": best_document_id,
            "term_reference": best_result.get("raw", {}).get("id") if best_result else None,
            "reason": best_reason,
            "source": {
                "document_id": best_document_id,
                "window": best_result.get("window") if best_result else None,
                "unit": best_result.get("unit") if best_result else info.get("unit") if info else None,
                "actual_raw": best_result.get("actual") if best_result else raw_value,
                "target_raw": best_result.get("target") if best_result else target_payload.get("target"),
                "warn_raw": best_result.get("warn") if best_result else warn_raw,
                "stop_raw": best_result.get("stop") if best_result else stop_raw,
            },
            "trend": {
                "original": _safe_float(delta_payload.get("original")),
                "recomputed": _safe_float(delta_payload.get("recomputed")),
                "abs_delta": _safe_float(delta_payload.get("abs_delta")),
                "rel_delta_pct": _normalize_percentage(_safe_float(delta_payload.get("rel_delta_pct")) or None)
                if _safe_float(delta_payload.get("rel_delta_pct")) is not None
                else None,
            },
        }

        cards.append(card)
        kpi_lookup[canonical_id] = card

        if best_document_id and best_document_id in documents_lookup:
            doc_card = documents_lookup[best_document_id]
            doc_card.setdefault("kpi_refs", [])
            doc_card["kpi_refs"].append(
                {
                    "kpi_id": canonical_id,
                    "label": label,
                    "status": best_status,
                    "value_pct": normalized_value,
                    "warn_threshold_pct": warn_pct,
                    "stop_threshold_pct": stop_pct,
                }
            )

    for doc_card in documents_lookup.values():
        doc_card["kpi_refs"] = _dedupe_list(doc_card.get("kpi_refs", []))

    return cards, kpi_lookup


def _collect_alerts(
    *,
    gate: Mapping[str, Any],
    rule_failures: Sequence[Mapping[str, Any]],
    documents: Sequence[Mapping[str, Any]],
    kpis: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []

    gate_status_raw = str(gate.get("status", "")).lower()
    gate_status = "stop" if gate_status_raw == "stop" else "warn" if gate_status_raw == "warn" else "pass"
    for reason in gate.get("reasons") or []:
        canonical_reason = str(reason)
        category = "contract" if canonical_reason.startswith("sla::") else "data"
        severity = "critical" if category == "contract" and gate_status == "stop" else "warning"
        alerts.append(
            {
                "id": f"gate::{canonical_reason}",
                "category": category,
                "severity": severity,
                "message": canonical_reason.replace("::", " - "),
                "recommendation": None,
                "related": {},
            }
        )

    for failure in rule_failures:
        level = str(failure.get("level", "")).upper()
        severity = "critical" if level == "STOP" else "warning"
        message = failure.get("message") or failure.get("rule_id") or "Rule failure"
        clause_payload = failure.get("sla_clause")
        alerts.append(
            {
                "id": f"rule::{failure.get('rule_id') or message}",
                "category": "contract",
                "severity": severity,
                "message": message,
                "recommendation": None,
                "related": {
                    "rule_id": failure.get("rule_id"),
                    "sla_clause": clause_payload,
                },
            }
        )

    for document in documents:
        status = document.get("status")
        if status in {"warn", "stop"}:
            severity = "critical" if status == "stop" else "warning"
            alerts.append(
                {
                    "id": f"document::{document.get('id')}::{status}",
                    "category": "contract",
                    "severity": severity,
                    "message": f"Document {document.get('display_name')} status is {status.upper()}",
                    "recommendation": None,
                    "related": {
                        "document_id": document.get("id"),
                    },
                }
            )
        for note in document.get("notes", []):
            alerts.append(
                {
                    "id": f"document-note::{document.get('id')}::{note}",
                    "category": "data",
                    "severity": "warning",
                    "message": f"{document.get('display_name')}: {note}",
                    "recommendation": None,
                    "related": {
                        "document_id": document.get("id"),
                    },
                }
            )

    for kpi in kpis:
        status = kpi.get("status")
        if status in {"warn", "stop"}:
            severity = "critical" if status == "stop" else "warning"
            message = f"KPI {kpi.get('label')} flagged as {status.upper()}"
            recommendation = None
            if status == "stop":
                recommendation = f"راجع KPI {kpi.get('label')} واضبط خطة تصحيح الامتثال فوراً."
            elif status == "warn":
                recommendation = f"راقب KPI {kpi.get('label')} وقارن بالقيم التحذيرية."
            alerts.append(
                {
                    "id": f"kpi::{kpi.get('id')}::{status}",
                    "category": "contract",
                    "severity": severity,
                    "message": message,
                    "recommendation": recommendation,
                    "related": {
                        "kpi_id": kpi.get("id"),
                        "document_id": kpi.get("document_id"),
                    },
                }
            )

    return _dedupe_list(alerts)


def _compose_summary(
    *,
    run_id: str,
    stats: Mapping[str, int],
    summary_payload: Mapping[str, Any],
    kpis: Sequence[Mapping[str, Any]],
    alerts: Sequence[Mapping[str, Any]],
    gate: Mapping[str, Any],
    performance: Mapping[str, Any],
) -> Dict[str, Any]:
    overall_compliance = None
    if summary_payload.get("overall_score_pct") is not None:
        overall_compliance = summary_payload["overall_score_pct"]
    elif kpis:
        overall_metric = next((kpi for kpi in kpis if kpi.get("id") == "sla_pct"), None)
        if overall_metric:
            overall_compliance = overall_metric.get("value_pct")

    gate_status = str(gate.get("status", "")).lower()
    if gate_status not in {"pass", "warn", "stop"}:
        gate_status = "pass"

    critical_kpis = [kpi for kpi in kpis if kpi.get("status") == "stop"]
    warning_kpis = [kpi for kpi in kpis if kpi.get("status") == "warn"]
    total_docs = stats.get("documents_total", 0)
    total_terms = stats.get("terms_evaluated", 0)

    summary_text_parts: List[str] = []
    summary_text_parts.append(f"تمت مراجعة {total_docs} وثيقة تغطي {total_terms} بنداً.")
    if overall_compliance is not None:
        summary_text_parts.append(f"درجة الامتثال العامة {overall_compliance:.2f}%.")
    summary_text_parts.append(f"حالة البوابة: {gate_status.upper()}.")
    if critical_kpis:
        summary_text_parts.append(f"{len(critical_kpis)} KPI في حالة إيقاف.")
    if warning_kpis and not critical_kpis:
        summary_text_parts.append(f"{len(warning_kpis)} KPI تحت المراقبة.")

    recommendations: List[str] = []
    for kpi in critical_kpis:
        label = kpi.get("label")
        doc_name = kpi.get("document_id")
        recommendations.append(f"راجع KPI {label} وتواصل مع مالك العقد {doc_name or ''} لتصعيد خطة التحسين.")
    if not recommendations and warning_kpis:
        for kpi in warning_kpis[:2]:
            label = kpi.get("label")
            recommendations.append(f"تابع KPI {label} لضمان عدم تجاوز حدود الإيقاف.")
    for alert in alerts:
        if alert.get("category") == "data":
            recommendations.append(alert.get("message"))

    return {
        "label": "SLA Snapshot",
        "run_id": run_id,
        "compliance_pct": overall_compliance,
        "status": gate_status,
        "documents_total": total_docs,
        "terms_total": total_terms,
        "warn_terms": stats.get("warn_terms", 0),
        "stop_terms": stats.get("stop_terms", 0),
        "documents_with_warnings": stats.get("documents_with_warnings", 0),
        "documents_without_terms": stats.get("documents_without_terms", 0),
        "last_execution": summary_payload.get("generated_at"),
        "execution_seconds": performance.get("exec_seconds"),
        "narrative": " ".join(summary_text_parts),
        "recommendations": _dedupe_list(recommendations)[:6],
    }


def _collect_attachments(
    entries: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    attachments: List[Dict[str, Any]] = []
    for entry in entries:
        display_name = _clean_document_label(entry.get("original_name") or entry.get("title") or entry.get("source_path"))
        attachments.append(
            {
                "name": display_name,
                "document_id": entry.get("document_id"),
                "media_type": entry.get("media_type"),
                "size_bytes": entry.get("size_bytes"),
                "sha256": entry.get("sha256"),
                "normalized_path": entry.get("normalized_path"),
                "stored_path": entry.get("stored_path"),
            }
        )
    return attachments


def _compose_metadata(
    *,
    run_id: str,
    summary_payload: Mapping[str, Any],
    validation: Mapping[str, Any],
    targets: Mapping[str, Any],
    stage_sources: Mapping[str, str],
    kpis: Sequence[Mapping[str, Any]],
    alerts: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    generated_at = summary_payload.get("generated_at")
    if not generated_at:
        generated_at = validation.get("generated_at")
    if not generated_at:
        generated_at = datetime.utcnow().isoformat()

    kpi_thresholds = {
        kpi.get("id"): {
            "warn_pct": kpi.get("warn_threshold_pct"),
            "stop_pct": kpi.get("stop_threshold_pct"),
            "direction": kpi.get("direction"),
        }
        for kpi in kpis
    }

    next_actions: List[Dict[str, Any]] = []
    for alert in alerts:
        recommendation = alert.get("recommendation")
        if recommendation:
            next_actions.append(
                {
                    "message": recommendation,
                    "category": alert.get("category"),
                    "severity": alert.get("severity"),
                }
            )
    next_actions = next_actions[:8]

    return {
        "run_id": run_id,
        "generated_at": generated_at,
        "sources": stage_sources,
        "provenance": validation.get("provenance"),
        "gate": validation.get("gate"),
        "performance": validation.get("perf"),
        "notes": summary_payload.get("notes") or [],
        "targets": targets,
        "kpi_thresholds": kpi_thresholds,
        "next_actions": next_actions,
    }


def build_dashboard_payload(
    *,
    run_id: str,
    validation: Mapping[str, Any],
    sla_summary: Mapping[str, Any],
    targets: Mapping[str, Any],
    manifest: Optional[Mapping[str, Any]],
    contracts_index: Optional[Mapping[str, Any]],
    stage_sources: Mapping[str, str],
    metric_catalog: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    manifest_entries = _filter_mapping_list((manifest or {}).get("entries"))
    manifest_index: Dict[str, Mapping[str, Any]] = {}
    for entry in manifest_entries:
        if entry.get("document_id"):
            manifest_index[str(entry["document_id"])] = entry
        if entry.get("normalized_path"):
            manifest_index[str(entry["normalized_path"])] = entry
        if entry.get("sha256"):
            manifest_index[str(entry["sha256"])] = entry

    contract_entries = _filter_mapping_list((contracts_index or {}).get("entries"))
    contract_index: Dict[str, Mapping[str, Any]] = {}
    for entry in contract_entries:
        if entry.get("document_id"):
            contract_index[str(entry["document_id"])] = entry
        if entry.get("normalized_path"):
            contract_index[str(entry["normalized_path"])] = entry
        if entry.get("sha256"):
            contract_index[str(entry["sha256"])] = entry

    summary_entries = _filter_mapping_list(sla_summary.get("entries"))
    sla_results = _filter_mapping_list(sla_summary.get("results"))

    results_by_document: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for result in sla_results:
        source = result.get("source") or {}
        document_id = (
            source.get("document_id")
            or source.get("document_path")
            or source.get("document_sha")
            or source.get("document")
        )
        if document_id:
            results_by_document[str(document_id)].append(result)

    documents, stats, documents_lookup = _collect_document_cards(
        run_id,
        summary_entries,
        results_by_document,
        manifest_index,
        contract_index,
    )

    kpi_recalc = _filter_mapping_list(validation.get("kpi_recalc"))
    kpi_values: Dict[str, Optional[float]] = {}
    kpi_original_values: Dict[str, Optional[float]] = {}
    kpi_deltas: Dict[str, Mapping[str, Any]] = {}
    for record in kpi_recalc:
        name = str(record.get("name", "")).strip()
        if not name:
            continue
        kpi_values[name] = _safe_float(record.get("recomputed"))
        kpi_original_values[name] = _safe_float(record.get("original"))
        kpi_deltas[name] = record

    kpi_cards, kpi_lookup = _collect_kpi_cards(
        kpi_values,
        kpi_original_values,
        kpi_deltas,
        targets or {},
        sla_results,
        metric_catalog,
        documents_lookup,
    )

    alerts = _collect_alerts(
        gate=validation.get("gate") or {},
        rule_failures=_filter_mapping_list(validation.get("rule_failures")),
        documents=documents,
        kpis=kpi_cards,
    )

    summary_block = _compose_summary(
        run_id=run_id,
        stats=stats,
        summary_payload={
            "generated_at": sla_summary.get("generated_at"),
            "overall_score_pct": kpi_lookup.get("sla_pct", {}).get("value_pct"),
        },
        kpis=kpi_cards,
        alerts=alerts,
        gate=validation.get("gate") or {},
        performance=validation.get("perf") or {},
    )

    attachments = _collect_attachments(manifest_entries)

    metadata = _compose_metadata(
        run_id=run_id,
        summary_payload={"generated_at": summary_block.get("last_execution"), "notes": sla_summary.get("notes")},
        validation=validation,
        targets=targets or {},
        stage_sources=stage_sources,
        kpis=kpi_cards,
        alerts=alerts,
    )

    legacy_metrics: List[Dict[str, Any]] = []
    for kpi in kpi_cards:
        info = metric_catalog.get(kpi.get("id"), {})
        legacy_metrics.append(
            {
                "id": kpi.get("id"),
                "label": kpi.get("label"),
                "value": kpi.get("raw_value"),
                "format": info.get("format", "number"),
                "unit": info.get("unit"),
                "status": kpi.get("status", "unknown"),
                "thresholds": {
                    "warn": kpi.get("warn_threshold_raw"),
                    "stop": kpi.get("stop_threshold_raw"),
                },
            }
        )

    overall_metric = next((metric for metric in legacy_metrics if metric.get("id") == "sla_pct"), None)
    overall_payload = {
        "label": metric_catalog.get("sla_pct", {}).get("label", "Overall SLA"),
        "score": overall_metric.get("value") if overall_metric else None,
        "score_pct": summary_block.get("compliance_pct"),
        "status": summary_block.get("status", "unknown"),
    }

    return {
        "run": run_id,
        "summary": summary_block,
        "documents": documents,
        "kpis": kpi_cards,
        "alerts": alerts,
        "attachments": attachments,
        "metadata": metadata,
        "metrics": legacy_metrics,
        "overall": overall_payload,
        "gate": validation.get("gate") or {},
        "rule_failures": _filter_mapping_list(validation.get("rule_failures")),
        "performance": validation.get("perf") or {},
        "notes": sla_summary.get("notes") or [],
        "generated_at": summary_block.get("last_execution"),
        "targets": targets or {},
        "sla_results": sla_results,
        "kpi_values": {card.get("id"): card.get("raw_value") for card in kpi_cards},
    }


__all__ = ["build_dashboard_payload"]
