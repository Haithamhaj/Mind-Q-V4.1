# AUTO-GENERATED DOCUMENTATION APPENDIX

**Generated:** 2025-11-22 19:59:43
**Source:** `scripts/generate_phase_docs.py`

> ⚠️ This appendix is auto-generated. Do not edit manually.
> Run `make docs` or `python scripts/generate_phase_docs.py` to regenerate.

---

## 1. Pipeline Phase Sequence

**Source:** `backend/src/app/services/pipeline_api/app.py` (Line 174)

```python
PIPELINE_PHASE_SEQUENCE = (
    "01_ingestion",
    "02_quality",
    "03_schema",
    "03_5_textops",
    "04_profile",
    "05_missing",
    "06_standardize",
    "07_readiness",
    "07_5_feature_report",
    "07_6_llm_summary",
    "07_7_business_correlations",
    "07_analytics",
    "07_timeseries",
    "07_knime_bridge",
    "08_insights",
    "09_business_validation",
    "09_5_causal",
    "10_bi",
    "12_routing",
)
```

**Total Phases:** 19


## 2. Phase Module Mapping

❌ Could not extract PHASE_MODULES


## 3. Stage Implementation Details


### Stage: `01_ingestion`

**Implementation:** `phases/01_ingestion/impl.py`

**Run Function:** Line 560
```python
def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> StageOutputs:  # type: ignore[override]
```

**Detected Outputs:** baselines.json, contracts.json, ingestion_report.json, logs.jsonl, meta_ingestion.json, missing_summary.json, raw.parquet, raw_streaming.parquet, row_meta.json, shape_mismatch.json, sla_manifest.json, sla_raw, source_meta.json

**STOP Conditions Found:**
- `"status": "STOP",`
- `health.emit_report(extra={"stage": stage_id, "status": "STOP"})`
- `"status": "STOP",`

**WARN Conditions Found:**
- `"WARN",`


### Stage: `02_quality`

**Implementation:** `phases/02_quality/impl.py`

**Run Function:** Line 75
```python
def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> StageOutputs:  # type: ignore[override]
```

**Detected Outputs:** issues.parquet, logs.jsonl, quality_overview.json, quality_report.json, row_meta.json, shape_guard.json

**STOP Conditions Found:**
- `"status": "STOP",`
- `_write_logs(out_dir, [{"rule": "read_raw", "severity": "STOP", "message": str(exc)}])`
- `"status": "STOP",`
- `_write_logs(out_dir, [{"rule": "row_guard", "severity": "STOP", "message": "input resulted in zero r`
- `"status": "STOP",`

**WARN Conditions Found:**
- `issues.append({"col": col, "issue": "phone_column_not_string", "severity": "WARN", "sample_value": s`
- `logs.append({"rule": "dtype_guard", "column": col, "severity": "WARN", "dtype": str(dtype)})`
- `severity = "WARN" if pct >= 0.2 else "NOTE"`
- `issues.append({"col": col, "issue": "invalid_datetime", "severity": "WARN", "sample_value": series[i`
- `logs.append({"rule": "invalid_datetimes", "column": col, "severity": "WARN", "count": invalid_count}`


### Stage: `03_schema`

**Implementation:** `phases/03_schema/impl.py`

**Run Function:** Line 170
```python
def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
```

**Detected Outputs:** aliases.json, column_glossary.json, logs.jsonl, normalization_report.json, normalized_sample.parquet, row_meta.json, schema_v1.json, semantic, terminology.json, terminology_filter_report.json, terminology_logs.jsonl, terminology_value_counts.json


### Stage: `03_5_textops`

**Implementation:** `backend/src/app/services/stage_03_5_textops/impl.py`

**Run Function:** Line 1095
```python
def run(run_id: str, inputs: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
```

**Detected Outputs:** _READY.OK, company_profile_llm.parquet, config/textops.yaml, contacts_llm.parquet, doc_segments.parquet, document_field_predictions.json, embeddings.faiss, embeddings.map.parquet, kpi_links.parquet, llm_trace.jsonl, logs, manifest.json, normalization_report.json, profile_entities.json, quality_findings.json, rules_sla_llm.parquet, sentiment_features.parquet, sla_policies.json, sop_rules.json, sop_steps_llm.parquet, structured_fields.parquet, svd_components.parquet, text_profile.json, textops_report.json, tfidf_info.json

**STOP Conditions Found:**
- `STOP = "STOP"`

**WARN Conditions Found:**
- `WARN = "WARN"`


### Stage: `04_profile`

**Implementation:** `phases/04_profile/impl.py`

**Run Function:** Line 103
```python
def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
```

**Detected Outputs:** column_profile.json, distribution.xlsx, logs.jsonl, profile.json, row_meta.json, semantic, summary.parquet, terminology_enriched.json


### Stage: `05_missing`

**Implementation:** `phases/05_missing/impl.py`

**Run Function:** Line 1038
```python
def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
```

**Detected Outputs:** changelog.jsonl, clean_imputed.parquet, cleaning_summary.json, imputation_plan.json, imputation_report.json, imputed.parquet, logs.jsonl, metrics.json, missing_summary.json, nzv_summaries.json, policy_relaxed.yml, psi_summary.json, row_meta.json, summary.json

**STOP Conditions Found:**
- `status = "STOP"`
- `if stops_entries and status == "STOP":`

**WARN Conditions Found:**
- `logs.append({"event": "skip_missing_feature", "feature": feature, "severity": "WARN"})`
- `"severity": "WARN",`
- `"severity": "WARN",`
- `logs.append({"event": "psi_key_missing", "feature": key, "severity": "WARN"})`
- `status = "WARN"`


### Stage: `06_standardize`

**Implementation:** `phases/06_standardize/impl.py`

**Run Function:** Line 391
```python
def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
```

**Detected Outputs:** clean.parquet, exclusions.json, exclusions_applied.json, logs.jsonl, nzv_summaries.json, row_meta.json, shape_mismatch.json, standardize_report.json, structured_fields.parquet


### Stage: `06_feature_eng`

**Implementation:** `phases/06_feature_eng/impl.py`

**Run Function:** Line 425
```python
def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[override]
```

**Detected Outputs:** diff_report.json, exclusions_applied.json, feature_manifest.json, feature_spec.json, features.curated.parquet, features.parquet, features.pre.parquet, layer1_dataset.parquet, layer1_sample.json, layer1_schema.json, logs.jsonl, payment_rules.yml, profile_entities.json, row_meta.json, run_meta.json, shape_mismatch.json, sla_policies.json, sop_rules.json


### Stage: `07_readiness`

**Implementation:** `phases/07_readiness/impl.py`

**Run Function:** Line 1228
```python
def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[override]
```

**Detected Outputs:** correlations.json, correlations_datetime.json, correlations_kpi.json, critical_columns.yml, decision_manifest.json, diagnostics.json, feature_flags.json, feature_spec.json, kpi_candidates.json, kpis.yml, layer1_catalog.json, layer1_preview.json, leakage_scan.json, logs.jsonl, network.json, nzv_summaries.json, readiness_report.json, redundancy.json, row_meta.json, semantic, stability.json, standardize_report.json, summary.json

**STOP Conditions Found:**
- `flags.append({"feature": feature, "flag": "unstable_feature", "severity": "STOP", "source": "psi"})`
- `status = "STOP"`
- `status = "STOP"`
- `"gate": {"status": "STOP", "reasons": ["no_features"]},`
- `gate_status = "STOP"`

**WARN Conditions Found:**
- `flags.append({"feature": feature, "flag": "unstable_feature", "severity": "WARN", "source": "psi"})`
- `logs.append({"event": "kpi_fallback", "severity": "WARN", "message": "no_kpi_columns_found"})`
- `logs.append({"event": "kpi_fallback", "severity": "WARN", "message": "no_kpi_correlations_added"})`
- `logs.append({"rule": "correlations_kpi", "severity": "WARN", "error": str(exc)})`
- `status = "WARN"`


### Stage: `08_insights`

**Implementation:** `src/app/services/stage_08_insights/impl.py`

**Run Function:** Line 2592
```python
def run(run_id: str, context: Mapping[str, Any], config: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
```

**Detected Outputs:** advanced, anomalies.json, basic_stats.json, cards.json, cluster_summary.json, column_coverage.json, column_roles.json, comparative_summary.json, correlation_matrix.json, correlations.json, correlations_kpi.json, dashboard_data.parquet, decision_manifest.json, diagnostics.json, dq_summary.json, features.parquet, forecast.parquet, forecast_summary.json, gate.json, gate.yml, heatmap_matrix.json, input.json, insights_candidates.json, insights_report.json, keyphrases_topk.json, kpis.yml, logs.jsonl, metrics.json, narratives.json, nzv_summaries.json, orders_forecast.parquet, quality_findings.json, quality_report.json, redundancy.json, segment_stats.parquet, sentiment_features.parquet, standardize_report.json, story_ops.json, summary.json, text_profile.json, text_stats.json, time_stats.parquet, variance_analysis.json

**STOP Conditions Found:**
- `if enforce_readiness and readiness_gate in {"WARN", "STOP"}:`
- `if readiness_gate == "STOP" and status == "PASS":`
- `if severity == "STOP":`
- `status = "STOP"`
- `status = "STOP"`

**WARN Conditions Found:**
- `if enforce_readiness and readiness_gate in {"WARN", "STOP"}:`
- `status = "WARN"`
- `status = "WARN"`
- `severity = str(rule.get("severity", "WARN")).upper()`
- `return "WARN", ["Only low-signal fallback candidates were available; treat insights as exploratory."`


### Stage: `09_business_validation`

**Implementation:** `phases/09_business_validation/impl.py`

**Run Function:** Line 1826
```python
def run(run_id: str, inputs: Mapping[str, Any], config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
```

**Detected Outputs:** benchmarks.parquet, bi_blacklist.json, bi_feed.parquet, bi_tiles, bi_whitelist.jsonl, changelog.json, clean.parquet, configs_snapshot, contracts, data_health.json, diagnostics.json, gate.json, insights_report.json, kpi_catalog.json, logs.jsonl, metrics.json, models_catalog.yml, nzv_summaries.json, ops_actions.json, quality_findings.json, raw.parquet, row_decisions.parquet, segment_insights.parquet, sentiment_features.parquet, sla_defaults.yml, sla_manifest.json, sla_policies.json, sla_summary.json, sop_rules.json, standardize_report.json, targets.json, text_profile.json, validation_report.json, what_if_report.json

**STOP Conditions Found:**
- `if result.status == "STOP":`
- `stop_failure = any(result.rule.level == "STOP" and result.count > 0 for result in failures)`
- `return "STOP", reasons`
- `stop_hit = any(rule.level == "STOP" for rule, _ in entity_hits)`
- `top_rule = next(rule for rule, _ in entity_hits if rule.level == "STOP")`

**WARN Conditions Found:**
- `elif result.status == "WARN":`
- `warn_failure = any(result.rule.level == "WARN" and result.count > 0 for result in failures)`
- `return "WARN", reasons`
- `"level": "WARN",`
- `"level": "WARN",`


### Stage: `10_bi`

**Implementation:** `phases/phase10_bi/impl.py`

**Run Function:** Line 1067
```python
def run(run_id: str, inputs: Optional[Mapping[str, Any]], config: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
```

**Detected Outputs:** benchmarks.parquet, bi_feed.parquet, business_correlations.parquet, causal_insights.json, causal_recommendations.json, correlations_datetime.json, data_health.json, datetime_correlations.parquet, dimensions.json, fact_benchmarks.parquet, fact_business.parquet, fact_causal_effects.parquet, fact_decisions.parquet, insights.json, insights_candidates.json, insights_candidates.parquet, insights_official.parquet, insights_report.json, kpi_catalog.yaml, metrics.json, metrics.yaml, ops_actions.json, orders.parquet, raw.parquet, row_decisions.parquet, segment_insights.parquet, summary_metrics.parquet, validation_report.json


## 4. Referenced Contract Files

| Contract File | Exists |
|--------------|--------|
| `contracts/nzv/policy.yml` | ✅ |
| `contracts/kpis/critical_columns.yml` | ❌ |
| `contracts/analytics/gate.yml` | ✅ |
| `contracts/payment/payment_rules.yml` | ✅ |
| `contracts/impute/policy_relaxed.yml` | ✅ |
| `contracts/models/models_catalog.yml` | ✅ |


## 5. Validation Metadata

- **Generation Date:** 2025-11-22 19:59:43
- **Project Root:** `/Users/haitham/development/Mind-Q-V4.1-port`
- **Script Version:** 1.0.0

---

**End of Auto-Generated Appendix**