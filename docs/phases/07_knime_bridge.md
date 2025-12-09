# KNIME Bridge (07_knime_bridge)

**Group:** Advanced Analytics  
**Optional:** No

## Goal
Stage 07 evaluates feature readiness by detecting leakage risks, high redundancy, near-zero variance columns, KPI relationships, and semantic coverage to decide which features proceed to analytics and modeling phases.

## Business Impact
Contributes to data quality and pipeline reliability

## Inputs
- Upstream phase outputs

## Outputs
- Phase artifacts

## Main Code Files
- `backend/src/app/services/stage_07_analytics/clustering_engine.py`
- `backend/src/app/services/stage_07_analytics/dq_engine.py`
- `backend/src/app/services/stage_07_analytics/anomaly_engine.py`
- `backend/src/app/services/stage_07_analytics/impl.py`
- `backend/src/app/services/stage_07_analytics/correlation_engine.py`
- `backend/src/app/services/stage_07_analytics/forecast_engine.py`

## KPIs
- Variance

## Pipeline Position
**Upstream:** 07_timeseries
**Downstream:** 08_insights

---
*Generated: 2025-12-09T17:45:01.953508*
