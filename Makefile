.PHONY: lint test smoke formatVENV=.venv

lint: ; ruff check . && mypy --ignore-missing-imports .PY=poetry run

test: ; pytest -q

smoke: ; python -m cli.runner flow --run-id smoke-local.PHONY: venv install fmt lint types test run

format: ; ruff format . && isort .

venv:
	python -m venv $(VENV)

install:
	$(PY) pip install --upgrade pip
	$(PY) pip install -r requirements.txt || true

fmt:
	$(PY) black .

lint:
	$(PY) ruff check .

types:
	$(PY) mypy src || true

test:
	$(PY) pytest -q

run:
	$(PY) python -m cli.runner flow --run-id demo --config configs/default.yml
PY?=python

.PHONY: test stage01 migrate-smoke

test:
	$(PY) -m pytest backend/tests/stage_02_ingestion -q
	$(PY) -m pytest backend/tests/stage_02_quality -q
	$(PY) -m pytest backend/tests/stage_06_standardize -q
	$(PY) -m pytest backend/tests/stage_06_feature_eng -q
	$(PY) -m pytest backend/tests/api_kpi -q

stage01:
	$(PY) -m cli.runner stage01 --files "data/*.csv"

migrate-smoke:
	$(PY) tools/migrate_artifacts.py --dry-run --run-id fake-run
