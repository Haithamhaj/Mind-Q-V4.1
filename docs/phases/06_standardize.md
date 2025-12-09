# Standardization (06_standardize)

**Group:** Advanced Analytics  
**Optional:** No

## Goal
Stage 06 Standardization ingests the authoritative Stage 05 dataset and standardizes column names, value formats, and numeric types while honoring protected logistics fields and preserving curated outputs for subsequent phases.

## Business Impact
Contributes to data quality and pipeline reliability

## Inputs
- Upstream phase outputs

## Outputs
- Phase artifacts

## Main Code Files
- `phases/06_standardize/impl.py`
- `phases/06_standardize/normalizer.py`

## Pipeline Position
**Upstream:** 05_missing
**Downstream:** 06_feature_eng

---
*Generated: 2025-12-09T17:45:01.936040*
