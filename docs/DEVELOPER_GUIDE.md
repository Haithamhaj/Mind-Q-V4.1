# Developer Guide# Developer Quick Start



- Smoke run:This guide helps a developer or reviewer get started quickly on Windows (PowerShell) and on Linux/macOS (bash). It focuses on reproducible steps for smoke runs, tests, and opening PRs.



```powershellPrerequisites

python -m cli.runner flow --run-id smoke-local- Python 3.11

```- Git

- PowerShell (Windows) or bash (Linux/macOS)

- Artifacts appear under `artifacts/<run-id>/`.

Create & activate a virtualenv (Windows PowerShell)

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Create & activate a virtualenv (bash)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run a smoke pipeline locally (PowerShell)

```powershell
. .\.venv\Scripts\Activate.ps1
.\run_pipeline.ps1 -Csv "data\Fastcoo_LM_Data.csv" -RunId "local-smoke"
```

Run only a single phase using the CLI

```powershell
poetry run python -m cli.runner phase --phase 01 --run-id local-smoke --csv data\Fastcoo_LM_Data.csv
```

Run tests (fast subset)

```bash
pytest -k smoke -q
```

How to open a reviewer-friendly PR
- Rebase or create a branch from `feature/runner-entrypoint` when making runner changes.
-- Keep artifacts out of Git. If you need to attach sample outputs, upload them to the PR as GitHub Action artifacts or as a ZIP attached to the PR description.

Include a short PR checklist:

- What changed and why (2–3 lines)
- Which phases or files are touched
- How to run the change locally (commands)
- Which tests were added/updated

Useful files:

- `docs/REPO_STRUCTURE.md` — map of where things live
- `README.md` — quick-start and reviewer tips

If you'd like, I can open a PR with these changes and the README updates to the `main` branch.
