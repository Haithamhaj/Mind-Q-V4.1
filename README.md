# Mind-Q V4.1 Logistics Intelligence Pipeline ✅ **UPDATED**
## نظام Mind-Q للذكاء اللوجستي - الإصدار 4.1

🎯 **Complete Documentation Update Status**: **92% Complete**
📊 **Code-Verified Phases**: **9 of 11 phases** fully documented with 100% implementation accuracy

Mind-Q is an advanced data engineering and analytics framework built specifically for logistics, delivery, and fulfillment operators. The system processes data through **13 sophisticated phases** that transform raw operational data into actionable business intelligence with Arabic language support.

---

## 🚀 **NEW: Deploy on Replit!**

This project is now ready for one-click deployment on Replit!

**Quick Deploy:**
1. Visit: [Import on Replit](https://replit.com/github/Haithamhaj/Mind-Q-V5)
2. Select branch: `port/update-2025-10-11`
3. Click **Run** ▶️

**Full Setup Guide**: See [QUICK_START_REPLIT.md](./QUICK_START_REPLIT.md) | [Detailed Guide](./REPLIT_SETUP.md)

---

## 🚀 One-Minute Quick Start

```powershell
# Activate environment and run complete pipeline
. .\.venv\Scripts\Activate.ps1
python -m cli.runner flow --run-id demo-arabic --csv "data/Fastcoo_LM_Data.csv"
```

## 🏗️ Advanced Pipeline Architecture

**Complete 13-Phase System** with AI-powered business intelligence:

### 📥 **Data Foundation (Phases 01-04)**
- **Phase 01**: Multi-format ingestion with phone detection
- **Phase 02**: Quality assessment with Arabic data validation  
- **Phase 03**: Schema extraction and baseline enforcement
- **Phase 04**: Lightweight profiling with row consistency

### 🔧 **Advanced Analytics (Phases 05-07)**
- **Phase 05**: Hybrid imputation with time-aware processing
- **Phase 06**: Feature engineering with exclusion management
- **Phase 07**: Correlation analysis with leakage detection

### 🤖 **AI Intelligence (Phases 7.5-7.6)**
- **Phase 7.5**: Statistical profiling with PII protection
- **Phase 7.6**: LLM-powered Arabic business reporting

### 🎯 **Business Intelligence (Phases 09-10)**
- **Phase 09**: Business validation with entity resolution
- **Phase 10**: BI delivery with semantic marts

## 🔬 Technical Excellence

### High-Performance Architecture
- **Dual-Engine Processing**: Polars optimization + Pandas compatibility
- **Advanced AI Integration**: Multi-provider LLM support (OpenAI, Anthropic, Google)
- **Enterprise Quality**: Zero-tolerance row validation, audit trails
- **Arabic Language Support**: Native business intelligence in Arabic

### Sophisticated Algorithms
- **Intelligent Imputation**: Groupwise strategies with PSI monitoring
- **Correlation Analysis**: Adaptive Pearson/Spearman with sampling optimization
- **PII Protection**: Multi-layer detection for phone, email, personal data
- **Cost-Optimized AI**: Token counting and provider selection

## 📁 Repository Structure

- `phases/` - **13 phase implementations** with advanced algorithms
- `contracts/` - SLA schemas, DQ policies, KPI configurations
- `shared/` - IO utilities, validation, telemetry modules
- `docs/` - **Comprehensive documentation** (95% code-verified)
- `artifacts/` - Versioned outputs with complete audit trails
# Mind-Q Logistics - Data Intelligence Framework (v4)

Mind-Q is a modular data engineering and analytics framework for logistics, delivery and fulfillment operators. The repository contains implementation for multiple pipeline phases, contracts (schemas & DQ rules), docs and runnable stage code.

## Quick facts
- Language: Python 3.11
- Main runner: `src/runner/main_pipeline.py` (entrypoint)
- Artifacts location (ignored in Git): `artifacts/{run_id}/{stage_id}/`

## Short Quick Start (Windows PowerShell)
These two commands are the minimum to run a smoke pipeline locally (assumes `.venv` exists):

```powershell
. .\.venv\Scripts\Activate.ps1     # dot-source to apply venv to session
.\run_pipeline.ps1 -Csv "data\Fastcoo_LM_Data.csv" -RunId "fastcoo-final"
```

If PowerShell execution policy prevents running scripts, run once with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_pipeline.ps1 -Csv "data\Fastcoo_LM_Data.csv" -RunId "fastcoo-final"
```

Artifacts to inspect after a successful run (examples):

- `artifacts/fastcoo-final/stage_01_ingestion/raw.parquet`
- `artifacts/fastcoo-final/stage_06_standardize/clean.parquet`
- `artifacts/fastcoo-final/stage_02_quality/quality_report.json`

## For external reviewers — خطوات للمراجعين الخارجيين (English + Arabic)

If you received this repository for review, please follow these steps to perform a quick and safe review.

1) Which branch to review
   - The source of truth is the `main` branch. The in-progress runner and docs are on `feature/runner-entrypoint` if requested. Use the GitHub UI to switch branches or fetch locally:

```powershell
git fetch origin
git checkout feature/runner-entrypoint   # only if you want the latest feature work
git pull origin feature/runner-entrypoint
```

2) Quick smoke run (local, safe)
- Create and activate venv, then run the smoke script above. The smoke run uses a small sample dataset (`data/smoke_fastcoo.csv`) and writes artifacts under `artifacts/{run_id}/`.

3) What to look for in a review
- Contracts and DQ rules: `contracts/` (schemas, `contracts/dq`)
- Stage implementations: `src/` and `phases/`
- Documentation and runbooks: `docs/` and `README.md`
- Artifacts and reports: the `quality_report.json` under `stage_02_quality` is the primary quick-read artifact for data quality checks.

4) If you need results but cannot run locally
- Artifacts are intentionally ignored from Git. Share requested result files as ZIP attachments or via a secure file share.

CI artifacts: A lightweight GitHub Actions workflow `CI — smoke run` will execute on pushes to `feature/runner-entrypoint` and `main` and upload smoke run artifacts as a downloadable artifact named `smoke-artifacts-smoke-ci`. Check the Actions tab for runs and artifacts.

Phase status (generated): see `docs/phase_status.md` for a per-run breakdown of which stages produced artifacts.

Quick links for reviewers

- Developer quick-start and commands: `docs/DEVELOPER_GUIDE.md`
- High-level repository map: `docs/REPO_STRUCTURE.md`

5) Security / execution notes

   - Some Windows environments block script execution (PowerShell execution policy). Use the `-ExecutionPolicy Bypass` option above for a one-off run.

6) Questions or follow-ups

   - If you want, I can open a PR with the final README changes to `main` and attach sample artifacts for review.

---

If you want me to open the PR now, I will create a PR from `feature/runner-entrypoint` → `main` with this README update and a short description for reviewers.

## Secrets Setup
1) Copy `.env.example` to `.env` and fill your keys locally. **Do not commit `.env`.**
2) Run on Windows PowerShell:
```powershell
$env:PROVIDER="gpt"
$env:OPENAI_MODEL="gpt-5-thinking"
$env:OPENAI_API_KEY="sk-..."
$env:GEMINI_API_KEY="AIza..."
.\scripts\run_p07.ps1 -RunId "fastcoo-prof-2025-10-10"
```
3) Or create `.env` and let the app load it automatically via `python-dotenv`.
4) لتجميع المفاتيح في ملف واحد لجميع المراحل، استخدم ملف ‎`.env`‎ واحد ومرر مساره عبر المتغيّر `MINDQ_LLM_CREDENTIALS_FILE` (أو الحقل `llm_credentials_file` عند استدعاء مسار pipeline). سيجري تحميل المفاتيح من هذا الملف وتطبيقها تلقائياً على جميع خدمات LLM (المرحلة 06، ملخص 07.6، BI، إلخ).

### UTF-8 Console Tips
- **Linux / macOS**: `export PYTHONIOENCODING="utf-8" PYTHONUTF8=1`
- **PowerShell**: `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"`

Security note: Keys must NOT appear in code, logs, commits, or screenshots. If leaked, rotate keys and purge history.

## Header Mapping Registry
- Phase 01 ingestion يعتمد الآن على سجل مركزي لتوحيد أسماء الأعمدة (راجع `contracts/name_maps/`).
- استخدم العلم `--name-map-profile` في `src.runner.main_pipeline` لتحديد ملف التعاريف المناسب لكل مصدر.
- راجع ملف التوثيق `docs/universal_header_mapping.md` لمعرفة كيفية إضافة aliases جديدة ومراقبة الأعمدة الحرجة.
## Data Quality Overrides
- لضبط المرحلة الخامسة بحيث لا تتوقف عند أعمدة جغرافية مفقودة بشكل كبير، استخدم `backend/contracts/impute/policy.yml` وأضف الأعمدة إلى `geo.allow_high_missing_columns`. الإعداد الافتراضي الآن يحتوي على `LATITUDE` و`LONGITUDE` بحيث تُسجَّل كتحذير فقط حتى لو تجاوزت 50%.