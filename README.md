# Mind-Q Logistics - Data Intelligence Framework (v4)

Mind-Q is a modular data engineering and analytics framework built for logistics, delivery, and fulfillment operators. The twenty-phase program moves from raw ingestion to BI-ready dashboards, with each phase producing versioned, auditable artifacts so teams can trace lineage and decisions end to end.

## Overview
- **Scope:** Data ingestion, quality, standardisation, feature engineering, commercial analytics, financial alignment, BI delivery.
- **Charter:** Aligned with the Mind-Q Engineering Charter v1.2.
- **Roadmap:** 20 phases grouped into Operations (01-09), Commercial (10-13), Financial (14-17), and BI (18-20). See `docs/PHASES_DETAILED_GUIDE.md` for detailed descriptions, dependencies, and status.
- **Artifacts:** Generated per phase under `artifacts/<run-id>/`.

## Technical Stack
- **Language:** Python 3.11
- **Core Libraries:** Polars, PyArrow, DuckDB, FastAPI, structlog
- **Testing & Quality:** pytest, ruff, mypy
- **Observability:** JSON logs, OpenTelemetry (planned)
- **Orchestration:** Prefect (planned), custom CLI runner
- **Frontend / BI:** Next.js, shadcn/ui, Recharts (planned semantic consumers)

## Repository Map
- `phases/` — phase-specific implementation notes and helpers.
- `src/app/services/` — runnable stage services (`stage_02_ingestion`, `stage_02_quality`, `stage_06_standardize`, `stage_06_feature_eng`).
- `contracts/` — schemas, DQ policies, KPI configs, and phase blueprints.
- `shared/` — IO, validation, telemetry, and utility modules.
- `configs/` — environment configuration and defaults.
- `docs/` — runbooks and roadmap documentation (phase catalog, run guides).
- `orchestration/` — entry points for pipeline orchestration.

## Quick Facts
- Language: Python 3.11
- Main runner: `src/runner/main_pipeline.py`
- Artifacts (ignored in Git): `artifacts/{run_id}/{stage_id}/`

## Short Quick Start (Windows PowerShell)
Minimum commands to run a smoke pipeline locally (assumes `.venv` exists):

```powershell
. .\.venv\Scripts\Activate.ps1     # apply venv to session
.\run_pipeline.ps1 -Csv "data\Fastcoo_LM_Data.csv" -RunId "fastcoo-final"
```

If PowerShell execution policy blocks scripts, run once with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_pipeline.ps1 -Csv "data\Fastcoo_LM_Data.csv" -RunId "fastcoo-final"
```

Artifacts to inspect after a successful run (examples):
- `artifacts/fastcoo-final/stage_01_ingestion/raw.parquet`
- `artifacts/fastcoo-final/stage_06_standardize/clean.parquet`
- `artifacts/fastcoo-final/stage_02_quality/quality_report.json`

## For External Reviewers — خطوات للمراجعين الخارجيين
Follow these steps for a quick, safe review.

1. **Branch to review**
   - Source of truth: `main`.
   - Latest runner/docs (if requested): `feature/runner-entrypoint`.

   ```powershell
   git fetch origin
   git checkout feature/runner-entrypoint   # optional latest feature work
   git pull origin feature/runner-entrypoint
   ```

2. **Quick smoke run (local, safe)**
   - Create & activate venv, then run the smoke script above with `data/smoke_fastcoo.csv`.

3. **What to inspect**
   - Contracts and DQ rules: `contracts/` (schemas, `contracts/dq`)
   - Stage implementations: `src/` and `phases/`
   - Documentation and runbooks: `docs/` and `README.md`
   - Artifacts/reports: `stage_02_quality/quality_report.json` is the fast readout

4. **Need results but cannot run locally?**
   - Artifacts stay out of Git. Share requested outputs as ZIP attachments or via a secure file share.

5. **CI artifacts**
   - The `CI — smoke run` workflow uploads `smoke-artifacts` (generated from the `smoke-ci` run id) on pushes to `feature/runner-entrypoint` and `main`.

6. **Security / execution notes**
   - بعض بيئات ويندوز تمنع تشغيل السكربتات. استخدم `-ExecutionPolicy Bypass` كحل سريع لمرة واحدة.

7. **Questions or follow-ups**
   - Happy to open a PR from `feature/runner-entrypoint` → `main` with README updates and sample artifacts if needed.

Quick links: `docs/DEVELOPER_GUIDE.md`, `docs/REPO_STRUCTURE.md`, `docs/phase_status.md`.

## Secrets Setup
1. Copy `.env.example` → `.env` and fill keys locally. **Do not commit `.env`.**
2. Windows PowerShell example:

```powershell
$env:PROVIDER="gpt"
$env:OPENAI_MODEL="gpt-5-thinking"
$env:OPENAI_API_KEY="sk-..."
$env:GEMINI_API_KEY="AIza..."
.\scripts\run_p07.ps1 -RunId "fastcoo-prof-2025-10-10"
```

3. Or create `.env` and let `python-dotenv` load it automatically.

Security note: never expose keys in code, logs, commits, or screenshots; rotate immediately if leaked.

## Header Mapping Registry
- Phase 01 ingestion يعتمد الآن على سجل مركزي لتوحيد أسماء الأعمدة (راجع `contracts/name_maps/`).
- استخدم العلم `--name-map-profile` في `src.runner.main_pipeline` لتحديد ملف التعاريف المناسب لكل مصدر.
- راجع `docs/universal_header_mapping.md` لمعرفة كيفية إضافة aliases جديدة ومراقبة الأعمدة الحرجة.
