# Mind-Q V4.1 - Replit Environment

## Overview
Mind-Q is a modular data engineering and analytics framework designed for logistics, delivery, and fulfillment operators. It processes data through 20 pipeline phases, from raw ingestion to BI-ready dashboards, providing a fully operational backend API (FastAPI) and frontend (Next.js) environment. The project aims to deliver business insights and validation through advanced data processing and AI capabilities.

## User Preferences
- **Expertise Level:** Advanced - deep understanding of system architecture
- **Change Management:** Requires detailed explanations before any code changes
- **Communication:** Prefers approval-based workflow for modifications
- **Language:** Arabic primary, English technical terms acceptable
- **Data Context:** Working with logistics dataset (59 columns, 29 text columns including: STATUS, ORIGIN, DESTINATION, DRIVER_NAME, SENDER_NAME, RECEIVER_NAME, Area Name, etc.)

## System Architecture

### Technical Stack
- **Backend:** Python 3.10+, FastAPI + Uvicorn, Polars, Pandas, PyArrow, DuckDB, OpenAI, Anthropic, Google Gemini, Great Expectations, ydata-profiling, DoWhy, CausalML.
- **Frontend:** Next.js 15.2, Radix UI + shadcn/ui, Tailwind CSS, ECharts, TypeScript + React 19.

### Core Features
- **20 Pipeline Phases:** Comprehensive data processing from ingestion to BI-ready output, including operations (Data Ingestion, Quality Checks, Schema Validation, Data Profiling, Missing Value Handling, Standardization & Feature Engineering, Readiness Assessment, Business Insights, Business Validation) and advanced features (Text Operations & NLP, Feature Reports, LLM Summaries, Business Correlations, Causal Inference, BI Dashboard Builder, Route Optimization).
- **Dynamic BI System:** Phase 09 reads from Phase 06 Standardize (`clean.parquet`) which contains feature-engineered data (59 original columns + 40 engineered features = 99 total). Dynamic column selection automatically includes ALL Phase 06 columns in bi_feed (replacing the previous static ADDITIONAL_BI_COLUMNS list), ensuring complete data flow from Phase 05 → Phase 06 → Phase 09 → Phase 10 without column loss. Phase 10 builds BI dashboards with auto-detecting semantic layer for dataset-agnostic analytics.
- **Asynchronous Phase Execution:** Phase 3.5 (TextOps) runs asynchronously in the background while other phases execute, with later phases waiting for its completion, optimizing pipeline performance.
- **LLM Integration:** AI-powered features are integrated across 5 pipeline phases (TextOps, LLM Summary, Insights, Business Validation, BI Delivery) using OpenAI GPT models (gpt-4o-mini, text-embedding-3-large) for tasks like text analysis, summarization, correlation explanations, KPI generation, and dashboard planning.
- **Robust Data Handling:** Includes helper functions for safe data type conversions and defensive programming to handle missing columns gracefully during feature engineering.

### Project Structure
The project is organized into `backend/`, `frontend/`, `phases/` (containing all 20 phase implementations), `shared/`, `contracts/`, `scripts/`, and `tests/` directories.

## External Dependencies
- **AI/LLM:** OpenAI (GPT models: `gpt-4o-mini`, `text-embedding-3-large`), Anthropic, Google Gemini.
- **Databases/Data Processing:** DuckDB.
- **UI/Charting:** Radix UI, shadcn/ui, ECharts.
- **Other:** npm for frontend package management.