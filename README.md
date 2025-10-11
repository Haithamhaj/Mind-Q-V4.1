# Mind-Q V4.1# Mind-Q Logistics - Data Intelligence Framework (v4)



One-minute run:Mind-Q is a modular data engineering and analytics framework built for logistics, delivery, and fulfillment operators. The program spans twenty phases that move from raw ingestion to BI-ready dashboards. Every phase produces versioned, auditable artifacts so teams can trace lineage and decisions end to end.



```powershell## Overview

python -m cli.runner flow --run-id demo- **Scope:** Data ingestion, quality, standardisation, feature engineering, commercial analytics, financial alignment, BI delivery.

```- **Charter:** Aligned with the Mind-Q Engineering Charter v1.2.

- **Roadmap:** 20 phases grouped into Operations (01-09), Commercial (10-13), Financial (14-17), and BI (18-20). See `docs/pipeline-phases.md` for detailed descriptions, dependencies, and current status.

Artifacts appear under `artifacts/<run-id>/` per phase.

## Technical Stack
- **Language:** Python 3.11
- **Core Libraries:** Polars, PyArrow, DuckDB, FastAPI, structlog
- **Testing & Quality:** pytest, ruff, mypy
- **Observability:** JSON logs, OpenTelemetry (planned)
- **Orchestration:** Prefect (planned), custom CLI runner
- **Frontend / BI:** Next.js, shadcn/ui, Recharts (planned semantic consumers)

## R- `phases/` - phase-specific implementation notes and helpers.
- `src/app/services/` - runnable stage services (`stage_02_ingestion`, `stage_02_quality`, `stage_06_standardize`, `stage_06_feature_eng`).
- `contracts/` - schemas, DQ policies, KPI configs, and phase blueprints.
- `shared/` - IO, validation, telemetry, and utility modules.
- `configs/` - environment configuration and defaults.
- `docs/` - runbooks and roadmap documentation (Phase catalog, run guides).
- `orchestration/` - entry points for pipeline orchestration.
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

Security note: Keys must NOT appear in code, logs, commits, or screenshots. If leaked, rotate keys and purge history.

## Header Mapping Registry
- Phase 01 ingestion يعتمد الآن على سجل مركزي لتوحيد أسماء الأعمدة (راجع `contracts/name_maps/`).
- استخدم العلم `--name-map-profile` في `src.runner.main_pipeline` لتحديد ملف التعاريف المناسب لكل مصدر.
- راجع ملف التوثيق `docs/universal_header_mapping.md` لمعرفة كيفية إضافة aliases جديدة ومراقبة الأعمدة الحرجة.
