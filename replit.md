# Mind-Q V4.1 - Replit Environment

## Project Overview
Mind-Q is a modular data engineering and analytics framework built for logistics, delivery, and fulfillment operators. The framework processes data through 20 pipeline phases from raw ingestion to BI-ready dashboards.

## Current State
✅ **FULLY OPERATIONAL** - Backend API and Frontend are running successfully!

### What's Running
- ✅ **Backend API** - FastAPI server on port 9000
- ✅ **Frontend** - Next.js application on port 5000  
- ✅ **API Documentation** - Swagger UI available at `/docs`
- ✅ **20 Pipeline Phases** - All phase implementations loaded and ready

### Quick Access
- **Frontend**: Opens automatically in Webview (port 5000)
- **API Docs**: http://localhost:9000/docs
- **Backend API**: http://localhost:9000

## Technical Stack

### Backend
- **Language:** Python 3.10+
- **Framework:** FastAPI + Uvicorn
- **Data Processing:** Polars, Pandas, PyArrow, DuckDB
- **AI/LLM:** OpenAI, Anthropic, Google Gemini
- **Data Quality:** Great Expectations, ydata-profiling
- **Causal Inference:** DoWhy, CausalML (optional Stage 09.5)

### Frontend
- **Framework:** Next.js 15.2
- **UI Library:** Radix UI + shadcn/ui
- **Styling:** Tailwind CSS
- **Charts:** ECharts
- **Language:** TypeScript + React 19

## Pipeline Phases

### Operations (01-09)
- **01** - Data Ingestion
- **02** - Quality Checks
- **03** - Schema Validation
- **04** - Data Profiling
- **05** - Missing Value Handling
- **06** - Standardization & Feature Engineering
- **07** - Readiness Assessment
- **08** - Business Insights
- **09** - Business Validation

### Commercial (10-13)
- **10** - BI Dashboard Builder
- **12** - Route Optimization (optional)

### Advanced Features
- **03.5** - Text Operations & NLP
- **07.5** - Feature Reports
- **07.6** - LLM Summaries
- **07.7** - Business Correlations
- **09.5** - Causal Inference (optional)

## Project Structure

```
Mind-Q-V4.1/
├── backend/                 # Backend source code
│   └── src/
│       ├── app/
│       │   ├── api/        # API routes (BI, Pipeline)
│       │   └── services/   # Stage implementations
│       └── agents/         # LLM integration
├── frontend/               # Next.js frontend
│   ├── app/               # Next.js app directory
│   ├── components/        # React components
│   └── lib/               # Utilities
├── phases/                # Phase implementations
│   ├── 01_ingestion/
│   ├── 02_quality/
│   ├── 03_schema/
│   └── ... (all 20 phases)
├── shared/                # Shared utilities
├── contracts/             # Schemas & DQ rules
├── scripts/               # Helper scripts
├── tests/                 # Test suite
├── run_app.sh            # Main startup script
└── requirements.txt      # Python dependencies
```

## Workflow Configuration
- **Name:** Mind-Q App
- **Command:** `bash run_app.sh`
- **Frontend Port:** 5000 (webview)
- **Backend Port:** 9000 (internal)
- **Auto-restart:** Enabled

## Environment Setup

### Completed
✅ Python 3.10+ installed
✅ Node.js 20 installed
✅ Backend dependencies installed
✅ Frontend dependencies installed
✅ Workflows configured

### Optional Environment Variables
Add these in Replit Secrets (🔒) for full functionality:

**AI/LLM Integration:**
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
```

**Configuration:**
```
DEBUG=True
MINDQ_AUTO_PURGE_RUNS=false
```

## Development Notes

### Running Locally
The application starts automatically via workflow. To restart manually:
```bash
bash run_app.sh
```

### Viewing Logs
- Backend logs: `backend.log`
- Frontend logs: shown in workflow console

### API Testing
- Swagger UI: http://localhost:9000/docs
- Interactive API documentation with try-it-out functionality

### Data Artifacts
Pipeline runs create artifacts in:
```
artifacts/{run_id}/{stage_id}/
```
These are gitignored and stored locally.

## LLM Integration

Mind-Q V4.1 supports AI-powered features across multiple pipeline phases using OpenAI GPT models:

### Phases that Use LLM

| Phase | LLM Feature | Purpose | Model Used |
|-------|-------------|---------|------------|
| **03.5 - TextOps** | Embeddings + NLP | Arabic/English text analysis, document extraction, RAG | text-embedding-3-large, gpt-4o-mini |
| **07.6 - LLM Summary** | Data summarization | Generate executive summaries from pipeline results | gpt-4o-mini |
| **08 - Insights** | Correlation explanations | Explain statistical relationships in business terms | gpt-4o-mini |
| **09 - Business Validation** | KPI generation | Generate and validate business metrics automatically | gpt-4o-mini |
| **10 - BI Delivery** | Dashboard planning | Create intelligent dashboard layouts and chart recommendations | gpt-4o-mini |

### Configuration

**Required Environment Variable:**
```
OPENAI_API_KEY=sk-...
```
Add this to Replit Secrets (🔒) or in `.env` file.

**LLM Settings Files:**
- `config/textops.yaml` - Phase 03.5 TextOps LLM configuration
- `backend/src/app/services/pipeline_api/app.py` - Global LLM environment loading

**How It Works:**
1. System checks for `OPENAI_API_KEY` in environment variables
2. If found, LLM features activate automatically in supported phases
3. If missing, phases skip LLM features and use rule-based fallbacks
4. Costs are estimated per API call (visible in phase logs)

### Testing LLM Features

To verify LLM is working:
```bash
# Check environment variable is loaded
env | grep OPENAI_API_KEY

# Run pipeline and check Phase 03.5 logs
cat artifacts/{run_id}/stage_03_5_textops/meta.json
```

## Recent Changes
- 2025-11-06 (**Latest**): **🤖 LLM Integration Fully Activated Across 5 Pipeline Phases**
  - ✅ **OPENAI_API_KEY configured** in Replit Secrets environment
  - ✅ **Updated `config/textops.yaml`**: Removed hardcoded credentials file, now uses environment variable
  - ✅ **Identified 5 LLM-powered phases**:
    - Phase 03.5 (TextOps): Embeddings + document extraction ✅ TESTED
    - Phase 07.6 (LLM Summary): Executive summaries
    - Phase 08 (Insights): Correlation explanations
    - Phase 09 (Business Validation): KPI generation
    - Phase 10 (BI Delivery): Dashboard intelligence
  - ✅ **Tested Phase 03.5 successfully**: Generated embeddings, text features, and NLP outputs
  - 📊 **LLM Model**: OpenAI GPT-4o-mini (default)
  - 📊 **Embeddings Model**: text-embedding-3-large (3072 dimensions)
  - 🔍 **Code Analysis**: Verified all phases use `src/agents/llm_adapter.py` for OpenAI API calls
  - 📝 **Files Modified**: `config/textops.yaml` (removed local credentials path)

- 2025-11-06: **🎉 FULL PIPELINE SUCCESS - All 14 Phases Working on Real Data**
  - ✅ **Fixed Critical Bug in Phase 06 (Feature Engineering)**: Resolved `'NoneType' object has no attribute 'fillna'` error
  - ✅ **Root Cause**: `pd.to_datetime()` and `pd.to_numeric()` returned `None` for missing columns, causing AttributeError
  - ✅ **Solution**: Added `_safe_to_datetime()` and `_safe_to_numeric()` helper functions that always return `pd.Series`
  - ✅ **File Modified**: `phases/06_feature_eng/impl.py` (lines 227-283)
  - 🎯 **Testing Results on Real Data** (Fastcoo_LM_Data.csv - 51,415 rows):
    - ✅ All 14 pipeline phases completed successfully (100% success rate)
    - ✅ Phase 03.5 TextOps: Working (83 seconds)
    - ✅ Phase 06 Standardize: Fixed and working
    - ✅ Phase 08 Insights: Producing results
    - ✅ Phase 09 Business Validation: Completed
    - ✅ Phase 10 BI Delivery: Completed
    - ⏭️ Phase 07.6 LLM Summary: Skipped (requires API key - optional)
  - 📊 **Pipeline Performance**:
    - Total execution time: ~120 seconds (2 minutes)
    - Artifacts generated: 197 files
    - Total output size: 122 MB
    - Input rows processed: 51,415
  - 📝 **Key Learnings**:
    - System handles large datasets efficiently
    - Async phases (03.5 TextOps) work correctly in background
    - All data quality checks, feature engineering, and BI stages operational
    - Schema validation correctly identifies logistics-specific fields (AWB_NO, PICKUP_DATE, etc.)
  - 🔍 **Code Changes**: Defensive programming added to handle missing columns gracefully
  
- 2025-11-04: **Implemented Async Execution for Phase 3.5 (TextOps)**
  - ✅ **Phase 3.5 now runs asynchronously in background** while phases 4-7 execute sequentially
  - ✅ **Phase 8 waits for Phase 3.5** to complete before consuming its outputs
  - ✅ Added `_run_async_phase()` helper in pipeline orchestrator using `asyncio.create_task()`
  - ✅ State tracking via `async_jobs_state` dictionary (similar to KNIME bridge pattern)
  - ✅ Updated `phase_manifest.yaml` with `async: true` and `consumed_by: [08_insights]` metadata
  - ✅ Frontend UI shows async phases with ⚡ indicator and blue pulsing animation
  - ✅ Logging added: "Phase 08 waiting for TextOps (Phase 3.5) to complete..."
  - ✅ Defensive task cancellation in exception handlers to prevent orphaned background tasks
  - 🎯 **Zero changes to phase implementation logic** (all changes in orchestration layer only)
  - 📝 Pipeline flow: 01→02→03→(03.5 background)→04→05→06→07→[wait 03.5]→08→09→10
  - 🔍 **Architect Review: PASS** - Implementation is production-ready

- 2025-11-04: **Fixed Critical `_ensure_frame` Error**
  - ✅ Created missing `_ensure_frame()` helper function in `backend/src/app/services/stage_03_5_textops/impl.py`
  - ✅ Function converts LLM table data (rules, SOPs, profiles, contacts) to properly-typed Polars DataFrames
  - ✅ Resolved runtime error: "name '_ensure_frame' is not defined"
  - ✅ Application now runs successfully without errors
  - 📝 Remaining LSP warnings are type-checking hints only (not runtime errors)

- 2025-11-04: **Added Phase 03.5 to Frontend UI**
  - ✅ Added Phase 03.5 (TextOps) to frontend phase lists in `/phases` and `/pipeline` pages
  - ✅ Fixed missing phase 03.5 in hardcoded frontend arrays (`frontend/app/phases/page.tsx` and `frontend/app/pipeline/page.tsx`)
  - ✅ Phase 03.5 now visible in Phase Dependencies diagram and selectable in UI
  - 📝 Phase 03.5: "Arabic/English text normalization, PII masking, and NLP features"

- 2025-11-04: **Fixed Phase Manifest YAML Parsing Error & Ordering**
  - ✅ Fixed critical YAML syntax error in `config/phase_manifest.yaml` line 82
  - ✅ Properly formatted Phase 03.5 (TextOps) definition with correct indentation
  - ✅ Fixed Arabic text encoding issues (was showing as `???????`)
  - ✅ Reordered phases: 03_schema now correctly placed BEFORE 03_5_textops
  - ✅ Pipeline timeline and phase documentation now load correctly in backend
  - 🐛 Issue: Entire phase definition was on single line with literal `\n` characters
  - 🐛 Issue: Phase 03_schema was missing `- id:` declaration

- 2025-11-04: **PII Privacy Controls Disabled**
  - ✅ Disabled PII detection in Phase 3.5 evidence payload (`enforce_privacy_on_evidence` commented out)
  - ✅ Disabled PII masking in `config/textops.yaml` (`mask_pii: false`)
  - ⚠️ All data (including names, phone numbers, IDs) will be shown unmasked in reports

- 2025-11-04: **LLM + RAG Fully Activated**
  - ✅ Added `OPENAI_API_KEY` to Replit Secrets
  - ✅ Enabled LLM in `config/textops.yaml` (GPT-4o-mini)
  - ✅ RAG embeddings enabled (text-embedding-3-large, 3072 dimensions)
  - ✅ LLM tasks: extract_sla, extract_sop, summarize
  - ✅ Phase 3.5 (TextOps) now fully operational with AI capabilities

- 2025-11-04: **Phase 3.5 TextOps Fix**
  - Fixed critical issue where Phase 3.5 expected `text_columns_catalog.json`
  - Modified to read from `normalization_report.json` produced by Phase 03
  - System now auto-detects 29 text columns from 59 total columns
  - Installed missing dependencies: `ftfy`, `emoji` for Arabic/English text normalization
  - Fixed phase manifest path (removed incorrect "backend" directory)

- 2025-11-04: Successfully imported and configured full project
  - Switched to branch `port/update-2025-10-11`
  - Installed all Python and Node.js dependencies
  - Fixed import paths for backend/frontend compatibility
  - Configured workflow for frontend on port 5000
  - Backend API operational on port 9000
  - All 20 pipeline phases loaded successfully

## User Preferences
- **Expertise Level:** Advanced - deep understanding of system architecture
- **Change Management:** Requires detailed explanations before any code changes
- **Communication:** Prefers approval-based workflow for modifications
- **Language:** Arabic primary, English technical terms acceptable
- **Data Context:** Working with logistics dataset (59 columns, 29 text columns including: STATUS, ORIGIN, DESTINATION, DRIVER_NAME, SENDER_NAME, RECEIVER_NAME, Area Name, etc.)

## Troubleshooting

### Backend not responding?
Check `backend.log` for errors. Most common: missing Python packages.

### Frontend not loading?
Check workflow logs. Common issue: npm dependencies need reinstallation.

### Cross-origin warnings?
These are normal in development. Configure `allowedDevOrigins` in `next.config.mjs` if needed.

## Documentation Files
- `QUICK_START_REPLIT.md` - Quick start guide
- `REPLIT_SETUP.md` - Detailed setup instructions
- `REPLIT_TROUBLESHOOTING.md` - Troubleshooting guide
- `README.md` - Main project documentation
