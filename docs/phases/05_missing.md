# Missing Value Repair (05_missing)

**Group:** Advanced Analytics  
**Optional:** No

## Goal
Stage 05 orchestrates hybrid imputation for logistics features, generating curated `clean_imputed.parquet`, indicator columns, PSI drift diagnostics, and a transparent imputation plan that downstream models can trust.

## Business Impact
Contributes to data quality and pipeline reliability

## Inputs
- Upstream phase outputs

## Outputs
- Phase artifacts

## Main Code Files
- `phases/05_missing/impl.py`

## KPIs
- Drift
- PSI

## Pipeline Position
**Upstream:** 04_profile
**Downstream:** 06_standardize

---
*Generated: 2025-12-09T17:29:57.830319*
