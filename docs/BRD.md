# Business Requirements Document (BRD) – Mind-Q V4 Logistics Intelligence Platform

## 1. Introduction
- **Project Name:** Mind-Q V4 Logistics Intelligence Platform  
- **Purpose:** End-to-end logistics data platform covering ingestion, data quality, business validation, SLA tracking, and BI delivery, with APIs for integration and LLM-powered narratives.  
- **Current Scope:** Supports Phases 01 → 09 plus supporting services (LLM chat, RAG context builder, FastAPI orchestration). The BRD covers features that exist today.

## 2. Stakeholders
- **Internal Data Team:** Operates phases, reviews artifacts, and performs internal audits.  
- **External Clients (Logistics Operators):** Consume BI feeds, SLA results, and operational stories.  
- **Integration Partners:** Invoke FastAPI endpoints to automate phase execution or embed results.  
- **Product Management:** Monitors compliance, reliability, and reporting outputs.

## 3. Functional Scope (Current)
### 3.1 Data Lifecycle Management
- **Stage 01 – Ingestion:** Multi-file CSV/Parquet ingestion, metadata capture, schema baseline, and SLA document ingestion (PDF, DOCX, HTML, CSV, multi-sheet Excel).  
- **Stage 02 – Quality:** Row guards, missingness statistics, schema hash comparison, non-ASCII detection, future timestamp detection, issue cataloging.  
- **Stage 03 – Schema:** Schema extraction, baseline row verification, `schema_v1.json` output.  
- **Stage 04 – Profile:** Lightweight profiling, `row_meta.json`, row-count consistency guard.  
- **Stage 05 – Missing:** Hybrid/groupwise imputation based on `contracts/impute/policy.yml`, PSI monitoring, missing-value indicator generation.  
- **Stage 06 – Standardize & Feature Engineering:** Protected-column enforcement, exclusion application, creation of `features.curated.parquet`, `features.parquet`, and differential reports.  
- **Stage 07 – Readiness:** Leakage detection, high-correlation analysis, near-zero variance scan, PSI analysis, readiness gate reports, stability metrics.  
- **Stage 07.5 – Feature Report:** Column profiling with PII masking, Markdown/JSON outputs summarizing key metrics and outliers.  
- **Stage 07.6 – LLM Summary:** Executive narrative using configured LLM provider (OpenAI/Gemini/Anthropic) with cost guardrails and usage logging.  
- **Stage 08 – Insights:** Associative insights, operational stories, diagnostics, coverage stats, and gate control (PASS/WARN/STOP).  
- **Stage 09 – Business Validation:** DuckDB-based KPI recompute, rule evaluation, SLA assessment, BI feed generation (`bi_feed.parquet`, whitelist/blacklist), SLA summary emission.

### 3.2 SLA Management
- SLA documents normalized in Stage 01 into structured JSON under `contracts/sla_processed/<run_id>/`.  
- Stage 09 evaluates each SLA term against actual KPIs/effect metrics, records statuses and reasons in `validation_report.json` and `sla_summary.json`.  
- Supports multiple SLA files per run with hash-based naming and manifest logging.

### 3.3 Interfaces & Integration
- **FastAPI (`pipeline_api`):**  
  - Endpoints for each phase (`/v1/runs/{run_id}/phases/...`).  
  - Full pipeline endpoint (`/v1/runs/{run_id}/pipeline/full`).  
  - Generated OpenAPI definition stored at `docs/pipeline_api_openapi.yaml`.  
- **LLM Chat Service (`sla_chat`):** Context-driven responses based on Stage 09 outputs using OpenAI-compatible APIs.  
- **CLI Scripts:** `scripts/run_phaseXX.py` mirror the same implementations for command-line usage.

### 3.4 RAG Context Pipeline
- `scripts/build_sla_context.py` compiles Stage 09 outputs (validation report, SLA summary, stories) into JSONL files under `artifacts/context/<run_id>/`.  
- LLM chat and external consumers leverage these context bundles for answers about KPIs and SLA compliance.

## 4. Non-Functional Requirements
- **Auditability:** UTF-8 encoded artifacts with timestamps, SHA-256 hashes, and manifest references.  
- **Re-run Capability:** Each phase is restartable via CLI or API without running the entire pipeline.  
- **Security:** API keys for LLM providers are environment-based; repository contains no secrets. Pipeline API is authentication-agnostic by default—deployment owners add auth as needed.  
- **Reliability:** Every stage returns structured status (PASS/WARN/STOP) and metrics suitable for monitoring.  
- **Documentation:** README, `docs/SLA_PIPELINE.md`, `docs/LLM_SLA_GUIDE.md`, `docs/PIPELINE_API.md`, and generated OpenAPI spec.

## 5. Data Flow Summary
1. Stage 01 generates `raw.parquet`, `meta_ingestion.json`, `sla_manifest.json`, and baseline metadata.  
2. Stages 02–07 progressively produce quality checks, schema outputs, imputed datasets, feature sets, readiness diagnostics.  
3. Stage 07 outputs feed Stage 08 (correlations, redundancy). Stage 08 produces insight artifacts.  
4. Stage 09 consumes feature datasets, insights report, SLA data, and configuration contracts to generate validation and BI artifacts.  
5. RAG builder aggregates Stage 09 outputs into context files for LLM chat and external queries.

## 6. Services & Interfaces
- **FastAPI `pipeline_api`:** REST endpoints for individual phases and pipeline orchestration.  
- **FastAPI `sla_chat`:** LLM-powered chat over SLA/BI context.  
- **OpenAPI YAML (`docs/pipeline_api_openapi.yaml`):** Comprehensive machine-readable API documentation.  
- **CLI Tools:** PowerShell/Bash friendly scripts for manual or automated runs.

## 7. Analytics & Reporting Outputs
- Stage 08: `insights_report.json`, `story_ops.json`, `diagnostics.json`, `basic_stats.json`, `segment_stats.parquet`, `time_stats.parquet`, `keyphrases_topk.json`, `column_coverage.json`.  
- Stage 09: `validation_report.json`, `bi_whitelist.jsonl`, `bi_blacklist.json`, `bi_feed.parquet`, `segment_insights.parquet`, `benchmarks.parquet`, `targets.json`, `sla_summary.json`, `ops_actions.json`, `data_health.json`, `changelog.json`.  
- Stage 07.5: Markdown/JSON column reports with outlier highlights.

## 8. Dependencies & Configuration Sources
- **Runtime:** Python 3.11, Polars, PyArrow, DuckDB, Pydantic, FastAPI, Uvicorn, OpenAI SDK, httpx, PyYAML, etc.  
- **Contracts & Config:**  
  - `configs/kpi/kpi_catalog.yaml`  
  - `configs/rules/*.yaml`  
  - `configs/bi/bi_contract.yaml`  
  - `contracts/impute/policy.yml`  
- **SLA Artifacts:** `contracts/sla_processed/<run_id>/` with stage-level manifest `artifacts/<run_id>/stage_01_ingestion/sla_manifest.json`.

## 9. Risks & Constraints
- **LLM Dependency:** Stage 07.6 and `sla_chat` depend on external LLM services and cost controls.  
- **Unauthenticated API:** External deployment should wrap `pipeline_api` with auth/Gateway for production use.  
- **Library Compatibility:** Compatibility shim added for Polars `Series.apply`; future updates may require further adjustments.  
- **Missing KPI Data:** SLA terms with unavailable metrics default to WARN status; accuracy depends on upstream data quality.

## 10. Glossary
- **SLA/SAL:** Service Level Agreement / Acceptance Letter.  
- **RAG:** Retrieval-Augmented Generation using context from `artifacts/context/`.  
- **BI Feed:** Structured outputs supporting dashboards (`bi_feed.parquet`, `bi_whitelist`, `bi_blacklist`).  
- **Gate Status:** PASS/WARN/STOP classification emitted by stages.  
- **Artifacts Root:** Top-level folder for pipeline outputs (`artifacts/`).  
- **Run ID:** Unique identifier for a pipeline execution.  

---
This BRD reflects the current functionality and artifacts available in Mind-Q V4. Update the document as capabilities evolve.
