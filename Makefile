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
