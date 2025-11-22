PY ?= python
VENV ?= .venv

.PHONY: venv install fmt lint types test smoke run stage01 migrate-smoke

venv:
	python -m venv $(VENV)

install:
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt || true
	$(PY) -m pip install -r requirements-dev.txt || true

fmt:
	$(PY) -m black .
	$(PY) -m ruff format .

lint:
	$(PY) -m ruff check .
	$(PY) -m mypy --ignore-missing-imports .

types:
	$(PY) -m mypy src || true

test:
	$(PY) -m pytest -q

smoke:
	$(PY) -m cli.runner flow --run-id smoke-local

run:
	$(PY) -m cli.runner flow --run-id demo --config configs/default.yml

stage01:
	$(PY) -m cli.runner stage01 --files "data/*.csv"

migrate-smoke:
	$(PY) tools/migrate_artifacts.py --dry-run --run-id fake-run

# Documentation targets
docs:
	@echo "📝 Generating documentation appendix..."
	$(PY) scripts/generate_phase_docs.py --output docs/GENERATED_APPENDIX.md
	@echo "✅ Generated: docs/GENERATED_APPENDIX.md"

validate-docs:
	@echo "🔍 Validating PHASES_DETAILED_GUIDE.md..."
	$(PY) scripts/validate_docs.py

validate-docs-strict:
	@echo "🔍 Validating PHASES_DETAILED_GUIDE.md (strict mode)..."
	$(PY) scripts/validate_docs.py --strict

check-docs: validate-docs docs
	@echo "✅ Documentation check complete"

# Pre-commit setup
pre-commit-install:
	@echo "🔧 Installing pre-commit hooks..."
	pip install pre-commit
	pre-commit install
	@echo "✅ Pre-commit hooks installed"

pre-commit-run:
	@echo "🔍 Running pre-commit checks..."
	pre-commit run --all-files
