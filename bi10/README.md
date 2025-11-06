# Phase-10 BI MVP v2

Investor-ready BI web app powered by FastAPI, DuckDB, and Apache ECharts. The app reads Phase-10 artifacts (stage_10_bi) and turns natural-language questions into charts via a deterministic, LLM-ready router.

## Quick Start

1. Place artifacts under rtifacts/<RUN_ID>/stage_10_bi/ with:
   - marts/*.parquet
   - semantic/metrics.yaml
2. (Optional) create .env with overrides for ARTIFACTS_ROOT, RUN_ID, TZ, CURRENCY.
3. Validate assets:
   `ash
   make preflight
   `
4. Run the app:
   `ash
   make run
   `
5. Open <http://localhost:8000/> for the executive dashboard or /explorer for picker-driven analysis.

## API Endpoints
- GET /api/meta — returns semantic catalog, timezone, and currency.
- POST /api/query — executes raw SQL against DuckDB views over the marts.
- POST /api/llm/decide_chart — deterministic router returning {plan, data} for chart rendering.

## Tests

`ash
make test
`

## Tech Stack
- FastAPI + FastAPI TestClient
- DuckDB + PyArrow
- Apache ECharts (RTL-first via CDN)
- JSON Schema validation for metrics.yaml

## Deployment Notes
- Default locale/timezone: Asia/Riyadh, currency SAR.
- No PII masking (MVP).
- Per-metric row caps enforced in the router.


## LLM Planning

Set `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`, default `gpt-4o-mini`) to enable real-time planning. Without a key, the router falls back to the deterministic heuristic but keeps sanitisation and LIMIT enforcement.

