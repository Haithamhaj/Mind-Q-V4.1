# Pipeline Logic Audit Report

This document summarizes how each Mind-Q stage operates, what it consumes and produces, and which conditions can halt or warn the pipeline. Stage names follow the CLI order in `cli/runner.py`.

## Stage 01 – Ingestion
1. **Objective:** Consolidate raw shipment/SLA files, persist them into the artifact tree, and capture provenance for downstream baselines.
2. **Dependencies:** none; pipeline entry point.
3. **Input/Output:** Reads raw CSV/Parquet from CLI `data_files` plus optional SLA PDFs; emits `stage_01_ingestion/raw.parquet`, `source_meta.json`, `sla_manifest.json`, `row_meta.json`, and logs.
4. **Gating Logic:**
   - **STOP Conditions:** (a) file missing or below the configured `min_file_size_bytes`; (b) combined row count below `min_rows_required`; (c) unreadable raw table. Defined in `phases/01_ingestion/impl.py`.
   - **WARN Conditions:** Streaming ingestion failures or SLA parsing errors fall back with WARN entries in `logs.jsonl` (same file).
5. **Behavior on Failure:** Stage returns `status: STOP` and no later stages run.

## Stage 02 – Quality
1. **Objective:** Run basic structural checks on the raw parquet and enforce early row guards.
2. **Dependencies:** Stage 01 must finish and create `raw.parquet`.
3. **Input/Output:** Reads `stage_01_ingestion/raw.parquet`; writes `stage_02_quality/quality_report.json`, `row_meta.json`, `issues.json` (embedded in report), and logs.
4. **Gating Logic:**
   - **STOP:** zero rows, row-count mismatch vs `baselines.json`, or raw file read failure. Source: `phases/02_quality/impl.py`.
   - **WARN:** dtype mismatches (phones not strings), columns with ≥20% missing, non-ASCII, or timestamp anomalies; logged as WARN within the same file but pipeline continues.
5. **Behavior:** STOP triggers hard exit; WARN entries are recorded for later diagnostics.

## Stage 03 – Schema & Terminology
1. **Objective:** Capture schema metadata, seed bilingual terminology, and keep row baselines.
2. **Dependencies:** Stages 01–02; uses `raw.parquet` and baseline metadata.
3. **Input/Output:** Reads `stage_01_ingestion/raw.parquet`; writes `stage_03_schema/schema_v1.json`, `semantic/terminology.json`, `row_meta.json`, and logs.
4. **Gating Logic:**
   - **STOP:** Enforced row guard via `baseline_utils.enforce_row_guard`; schema extraction itself does not STOP otherwise (`phases/03_schema/impl.py`).
   - **WARN:** None (terminology skips simply log reasons).
5. **Behavior:** If row guard trips, pipeline stops; otherwise stage always passes.

## Stage 03.5 – TextOps
1. **Objective:** Clean free-text fields, extract SOP/SLA intelligence, structured phones/addresses, and run lightweight sentiment.
2. **Dependencies:** Requires Stage 03 schema plus artifacts such as baselines and client documents.
3. **Input/Output:** Reads curated text columns and uploaded PDFs; outputs `stage_03_5_textops/structured_fields.parquet`, `sentiment.parquet`, `quality_findings.json`, SOP/SLA JSON payloads, and logs (`backend/src/app/services/stage_03_5_textops/impl.py`).
4. **Gating Logic:**
   - **STOP:** Missing text inputs or join-key mismatches that prevent creating `structured_fields.parquet` raise STOP (inside the same impl file).
   - **WARN:** LLM document parsing issues, OCR fallbacks, or RAG misses are logged as WARN and surfaced in `quality_findings.json`.
5. **Behavior:** On fatal errors the stage sets `status: STOP`; otherwise it degrades to heuristics and marks WARN.

## Stage 04 – Profile
1. **Objective:** Generate descriptive statistics, PSI seeds, and KPI-ready profiles over the standardized raw set.
2. **Dependencies:** Needs Stage 03 schema artifacts and Stage 01 raw data.
3. **Input/Output:** Consumes the cleaned dataset, writes `stage_04_profile/profile.json`, `psi_summary.json`, histograms, and logs (`phases/04_profile/impl.py`).
4. **Gating Logic:**
   - **STOP:** Only row-guard failures via `baseline_utils` when counts drift.
   - **WARN:** High PSI or coverage issues recorded as WARN in the profile report (same file).
5. **Behavior:** WARN-only stage; STOP only when row guard fails.

## Stage 05 – Missing Value Repair
1. **Objective:** Apply imputation policies (numeric, categorical, geo) and produce `clean_imputed.parquet` plus PSI diagnostics.
2. **Dependencies:** Stage 04 profile output and Stage 01 raw data.
3. **Input/Output:** Reads Stage 04/Stage 01 parquet; writes `stage_05_missing/clean_imputed.parquet`, `imputation_plan.json`, `imputation_report.json`, `psi_summary.json`, logs.
4. **Gating Logic:**
   - **STOP:** Triggered when row counts shift, PSI exceeds `gates.psi_stop` (default 0.3), or critical imputation rules fail. Controlled by `phases/05_missing/impl.py` and policies in `contracts/impute/policy.yml` (or `policy_relaxed.yml`).
   - **WARN:** PSI between warn/stop thresholds (default 0.2–0.3), high missingness beyond `indicator_if_missing_pct_gt`, or geo columns exceeding warn threshold per the same policy file.
5. **Behavior:** STOP stops pipeline; WARN writes to reports but continues. Stage can switch to “relaxed” policy configs if provided.

## Stage 06A – Standardize
1. **Objective:** Normalize column names/values, enforce sector-protected fields, and mirror curated datasets for feature engineering.
2. **Dependencies:** Stage 05 outputs plus optional Stage 03.5 structured fields.
3. **Input/Output:** Reads `stage_05_missing/clean_imputed.parquet`; emits `stage_06_standardize/clean.parquet`, `features.pre.parquet`, `standardize_report.json`, `exclusions_applied.json`, `row_meta.json` (`phases/06_standardize/impl.py`).
4. **Gating Logic:**
   - **STOP:** Row-count mismatches, every column excluded (all-columns drop), failure to enforce exclusion policy. Controlled directly in the impl.
   - **WARN:** None; ignored exclusions are just logged.
5. **Behavior:** Hard-stop on guard failures; otherwise deterministic pass-through.

## Stage 06B – Feature Engineering
1. **Objective:** Preserve curated columns, derive Layer 1 dataset, and (new) compute client-driven `PAYMENT_TYPE`.
2. **Dependencies:** Requires Stage 06A curated data and standardize metadata.
3. **Input/Output:** Reads `stage_06_standardize/clean.parquet`; writes `stage_06_feature_eng/features.parquet`, `layer1_dataset.parquet`, `layer1_schema.json`, `feature_manifest.json`, `diff_report.json`, logs with payment distribution (`phases/06_feature_eng/impl.py`).
4. **Gating Logic:**
   - **STOP:** Row guard (inherited from baseline utils) or empty column set. Same file.
   - **WARN:** Logged events when payment-rule file missing or COD parsing fails (degrades to 0). Rules defined in `phases/06_feature_eng/payment.py` with config `contracts/payment/payment_rules.yml`.
5. **Behavior:** On payment-rule issues, stage falls back to defaults and emits WARN; STOP only for structural issues.

## Stage 07 – Readiness
1. **Objective:** Validate feature readiness (leakage, NZV, PSI, KPI coverage) and determine which columns proceed.
2. **Dependencies:** Stage 06B outputs, Stage 05 NZV summary, KPI contracts.
3. **Input/Output:** Reads `stage_06_feature_eng/features.parquet` and related metadata; outputs `stage_07_readiness/readiness_report.json`, `diagnostics.json`, `decision_manifest.json`, `correlations*.json`, `redundancy.json` (`phases/07_readiness/impl.py`).
4. **Gating Logic:**
   - **STOP:** PSI ≥ `PSI_STOP_THRESHOLD` (0.3), leakage detections (ID-like predictors of outcomes), zero surviving features, row guard failure, or critical NZV hits listed in `contracts/kpis/critical_columns.yml`. Additional tolerances are read from `contracts/nzv/policy.yml`.
   - **WARN:** PSI between 0.2–0.3, NZV ratio above `max_nzv_ratio_for_pass`, geo coverage issues, or KPI coverage shortfalls. Documented with `gate_status: WARN` in readiness report.
5. **Behavior:** STOP halts pipeline; WARN downgrades readiness but still emits keep lists and diagnostics.

## Stage 07.5 – Feature Report
1. **Objective:** Produce human-readable feature summaries (distributions, NZV notes, cards) for ops teams.
2. **Dependencies:** Consumes Stage 07 outputs, Stage 05 NZV metadata.
3. **Input/Output:** Writes `stage_07_5_feature_report/report.json`, `cards.json`, `feature_flags.json`, `profile/*` (`phases/07_5_feature_report/impl.py`).
4. **Gating Logic:** Informational only; no STOP/WARN aside from missing inputs which raise errors.
5. **Behavior:** If inputs missing, raises exception; otherwise always PASS.

## Stage 07.6 – LLM Summary
1. **Objective:** Generate bilingual executive summary and remediation suggestions via LLM providers.
2. **Dependencies:** Requires readiness outputs plus LLM credentials (`backend/llm.env`).
3. **Input/Output:** Writes `stage_07_6_llm_summary/summary.json`, `metrics.json`, cache entries (`phases/07_6_llm_summary/impl.py`).
4. **Gating Logic:**
   - **STOP:** Only if all providers fail and heuristics cannot run (rare). Controlled by the impl and environment variables (`MINDQ_LLM_PROVIDERS`, `<PROVIDER>_MODEL`).
   - **WARN:** Provider outages fall back to heuristics and log WARN flags.
5. **Behavior:** Falls back to heuristic narrations and records `provider: heuristic` when models unavailable.

## Stage 07.7 – Business Correlations
1. **Objective:** Build correlation stories and variance analyses for business review.
2. **Dependencies:** Stage 07 readiness plus Stage 06 features.
3. **Input/Output:** Outputs `stage_07_7_business_correlations/report.json`, `corr_matrix.json`, `logs.jsonl` (`phases/07_7_business_correlations/impl.py`).
4. **Gating Logic:** Analytical only; STOP occurs if correlation inputs missing or row guard fails; no WARN thresholds beyond logged notes.
5. **Behavior:** Halts when prerequisites missing; otherwise PASS.

## Stage 07 Analytics (optional)
1. **Objective:** Python alternative to KNIME analytics—DQ rules, clustering, anomaly detection.
2. **Dependencies:** Requires Stage 06 features and Stage 07 readiness.
3. **Input/Output:** Writes to `phase_07_analytics/outputs/*` such as `dq_summary.json`, `cluster_summary.json` (`backend/src/app/services/stage_07_analytics/impl.py`).
4. **Gating Logic:**
   - **STOP:** Fatal DQ failures (schema mismatch, missing timestamp) result in STOP with reasons recorded in `dq_summary.json`.
   - **WARN:** High NZV ratios, imbalance warnings, or sampling fallbacks annotated in the same outputs. Config comes from `contracts/analytics/*.yml` referenced by the engine.
5. **Behavior:** When STOP occurs Stage 08 still sees recorded diagnostics but pipeline halts; WARN allows continuation.

## Stage 07 Timeseries (optional)
1. **Objective:** Build dedicated time-series metrics when explicitly enabled.
2. **Dependencies:** Stage 06 features, CLI-provided config.
3. **Input/Output:** Emits `stage_07_timeseries/forecast.json` and supporting plots (`backend/src/app/services/stage_07_timeseries/*.py`).
4. **Gating Logic:** STOP when config missing or time index absent; WARN when coverage insufficient (logged only).
5. **Behavior:** Optional; CLI forces STOP if inputs missing.

## Stage 07 KNIME Bridge
1. **Objective:** Package features, schema, KPIs, and readiness report into `phase_07_knime/` for downstream KNIME or BI tooling.
2. **Dependencies:** Needs Stage 06 features, Stage 07 readiness, Stage 07.5 report.
3. **Input/Output:** Writes `phase_07_knime/data.parquet`, `schema.json`, `run_meta.json`, `profile/*` (`src/app/services/stage_07_bi_prep_python/impl.py`).
4. **Gating Logic:** Fails only when required files absent; no WARN tier.
5. **Behavior:** On failure the stage raises STOP to avoid distributing incomplete packages.

## Stage 08 – Insights
1. **Objective:** Generate governed KPI insights, candidates, and diagnostics using Stage 07 artifacts.
2. **Dependencies:** Requires Stage 06 features, Stage 07 readiness/correlations, analytics overlays, and optional TextOps/LLM context.
3. **Input/Output:** Writes `stage_08_insights/insights_report.json`, `insights_candidates.json`, `gate.json`, `diagnostics.json`, `advanced/*`, `layer2_*` (`src/app/services/stage_08_insights/impl.py`).
4. **Gating Logic:**
   - **STOP:** Critical missing columns exceeding `critical_missing_stop`, future-dated timestamps, numeric rule violations with `severity: STOP`, readiness STOP propagation, or failure to load policy files. Thresholds configured in `contracts/analytics/gate.yml` (quality_checks, numeric_rules) and supplemented by `contracts/impute/policy.yml` for geo tolerances.
   - **WARN:** Missing ratios between warn/stop, warn-only columns (e.g., `COD_AMOUNT`) exceeding coverage, numeric rule WARN hits, readiness WARN, analytics DQ alerts, or heuristics fallback; recorded in diagnostics.
5. **Behavior:** STOP produces empty insights and writes gate diagnostics; WARN still emits insights but attaches cautionary notes.

## Stage 09 – Business Validation
1. **Objective:** Apply client-specific validation rules, SLA checks, and escalation logic before BI delivery.
2. **Dependencies:** Stage 08 outputs plus SLA contracts under `contracts/sla_processed/*`.
3. **Input/Output:** Produces `stage_09_business_validation/gate.json`, `diagnostics.json`, `violations.json` (`phases/09_business_validation/impl.py`).
4. **Gating Logic:**
   - **STOP:** Any rule with `level: STOP` producing counts >0 (e.g., KPI breaches, policy conflicts) or stage 08 STOP propagation. Rules defined in the same impl and contract payloads.
   - **WARN:** WARN-level rules triggered, runbook warnings, or missing SLA context; logged in diagnostics.
5. **Behavior:** STOP prevents BI delivery; WARN documents advisory actions.

## Stage 09.5 – Causal Insights (optional)
1. **Objective:** Run causal inference experiments for a selected problem definition.
2. **Dependencies:** Stage 08 insights and stage-specific problem configs under `contracts/causal_problems/*.yml`.
3. **Input/Output:** Writes `stage_09_5_causal/results.json`, `diagnostics.json` (`src/app/services/stage_09_5_causal_inference/impl.py`).
4. **Gating Logic:** STOP if required problem name missing or if uplift model fails; WARN when sample size insufficient.
5. **Behavior:** Optional; pipeline skips unless CLI flag set.

## Stage 10 – BI Delivery
1. **Objective:** Assemble BI-ready datasets, copy them into the BI workspace, and trigger downstream dashboards.
2. **Dependencies:** Needs completed Stage 07 Knime Bridge bundle and Stage 08 outputs.
3. **Input/Output:** Writes to `phase_07_knime/` mirrors, BI profile exports, and updates `phase_07_knime/run_meta.json` for BI connectors (`phases/phase10_bi/impl.py`).
4. **Gating Logic:** STOP when mandatory inputs missing or when file copy fails; WARN when some optional exports (e.g., advanced clusters) unavailable.
5. **Behavior:** On STOP the pipeline halts before BI exposure; WARN simply notes missing extras.

## Stage 12 – Routing (optional)
1. **Objective:** Run routing heuristics/optimizations when explicitly enabled.
2. **Dependencies:** Requires Stage 08/09 artifacts and CLI-provided routing config.
3. **Input/Output:** Writes routing recommendations and logs under `stage_12_routing/` (`backend/src/app/services/stage_12_routing/impl.py`).
4. **Gating Logic:** STOP if config missing/invalid or solver fails; WARN on partial coverage or heuristic fallbacks.
5. **Behavior:** Optional; skipped unless `--run-routing` flag used.

---

## Configuration Cheat Sheet
- **NZV threshold:** `contracts/nzv/policy.yml` (`max_nzv_ratio_for_pass`, per-stage toggles). Stage 05/07/08 consume this contract.
- **Critical column lists:**
  - Readiness gate: `contracts/kpis/critical_columns.yml`.
  - Stage 08 preflight (critical vs warn-only): `contracts/analytics/gate.yml` (`quality_checks`).
- **LLM model selection:** `phases/07_6_llm_summary/impl.py` reads `MINDQ_LLM_PROVIDERS`, `<PROVIDER>_MODEL`, and the optional plan in `contracts/llm` (if provided). Default env overrides live in `backend/llm.env` or project-level `.env`.
- **API keys:** Provide or edit values in `backend/llm.env`, `backend/.env`, or repo-level `llm.env`; `cli/runner.py` loads them through `dotenv`.
