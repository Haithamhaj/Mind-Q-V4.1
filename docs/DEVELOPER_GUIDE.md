# Developer Quick Start

This guide helps developers and reviewers ramp up quickly on Windows (PowerShell) and Linux/macOS (bash). It focuses on reproducible steps for smoke runs, tests, and preparing PRs.

## Prerequisites
- Python 3.11
- Git
- PowerShell (Windows) or bash (Linux/macOS)
- Artifacts live under `artifacts/<run-id>/`

## Create & Activate a Virtual Environment

### Windows PowerShell
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

### bash (Linux/macOS)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Run a Smoke Pipeline (PowerShell)
```powershell
. .\.venv\Scripts\Activate.ps1
.\run_pipeline.ps1 -Csv "data\Fastcoo_LM_Data.csv" -RunId "local-smoke"
```

## Run a Single Phase via CLI
```powershell
poetry run python -m cli.runner phase --phase 01 --run-id local-smoke --csv data\Fastcoo_LM_Data.csv
```

## Run Tests (fast subset)
```bash
pytest -k smoke -q
```

## Reviewer-Friendly PR Checklist
- Branch from or rebase onto `feature/runner-entrypoint` for runner work.
- Keep artifacts out of Git; share outputs as Action artifacts or ZIP attachments on the PR.
- Include in the PR description:
  - What changed and why (2–3 lines)
  - Which phases/files are touched
  - How to run the change locally (commands)
  - Which tests were added or updated

Useful references: `docs/REPO_STRUCTURE.md`, `README.md`.

If you prefer, I can open a PR with these changes plus the README updates targeting `main`.
