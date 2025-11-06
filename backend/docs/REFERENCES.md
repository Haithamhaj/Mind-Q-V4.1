# Backend References

## Document Field Extraction
- TextOps exports `document_field_predictions.json` only when `USE_EXT_DOCUMENT_FIELD_EXTRACTION=1`.
- `backend.adapters.docs_textqa_baseline` keeps a pure regex baseline; optional PDF parsing uses `pdfminer.six` when available.
- Regex patterns are customisable via the adapter APIs; failures emit warnings instead of stopping the run.

## KPI Anomaly Scoring
- Stage 08 defaults to z-score heuristics and switches to the PyOD IsolationForest adapter when `USE_EXT_KPI_ANOMALY_SCORING=1`.
- Adapter execution records `anomalies.method` = `adapter` and logs model metadata; baseline remains unchanged when the flag is off or dependencies are missing.

## Causal Root Cause Hints
- Stage 09.5 writes `root_cause_hints.json` when `USE_EXT_ROOT_CAUSE_HINTS=1` and backdoor columns are available.
- The payload and logs expose `method=adapter`; otherwise the baseline summaries remain and no additional artefact is emitted.

## VRPTW Routing
- Stage 12 runs a deterministic greedy fallback by default and upgrades to OR-Tools when `USE_EXT_VRPTW_SOLVER=1`.
- Route plans surface `method` in both the JSON artefact and logs so BI consumers can differentiate between baseline and adapter runs.

## Adapter Feature Flags

- `USE_EXT_DOCUMENT_FIELD_EXTRACTION`
- `USE_EXT_KPI_ANOMALY_SCORING`
- `USE_EXT_FORECAST_TEMPLATES`
- `USE_EXT_ROOT_CAUSE_HINTS`
- `USE_EXT_VRPTW_SOLVER`

## Local Run (Adapters)

```bash
pip install -r requirements-adapters.txt
export USE_EXT_KPI_ANOMALY_SCORING=1
export USE_EXT_FORECAST_TEMPLATES=1
export USE_EXT_VRPTW_SOLVER=1
export USE_EXT_ROOT_CAUSE_HINTS=1
pytest -q tests/adapters/test_anomaly_pyod.py \
        tests/adapters/test_timeseries_statsforecast.py \
        tests/adapters/test_routing_ortools.py \
        tests/adapters/test_causal_dowhy.py
```

Tests skip only when the corresponding optional dependency cannot be imported.

لمزيد من التفاصيل راجع `backend/docs/ADAPTERS.md`.
