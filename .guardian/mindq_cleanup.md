# 🔍 Mind-Q Deep Cleanup Report (Refactor Radar)

**Generated**: 2025-12-09T17:36:33.908385  
**Scan Type**: Deep Code-Aware Analysis

## 📊 Executive Summary

- **Total Findings**: 69
- **High Confidence**: 69
- **Medium Confidence**: 0
- **Low Confidence**: 0

### Findings by Category

- 📦 **Unused Import**: 30
- 🔧 **Oversized Function**: 23
- 📄 **Oversized File**: 10
- ❌ **Missing Phase Doc**: 6

## 🔴 High Confidence Findings

### CLEANUP-001: Unused Import

- **File**: `phases/06_standardize/impl.py`
- **Symbol**: `importlib.util`
- **Why**: Import 'importlib.util' is not used in the file
- **Confidence**: 85%
- **Phase**: 06_standardize
- **Action**: remove unused import

### CLEANUP-002: Unused Import

- **File**: `phases/06_standardize/impl.py`
- **Symbol**: `annotations`
- **Why**: Import 'annotations' is not used in the file
- **Confidence**: 85%
- **Phase**: 06_standardize
- **Action**: remove unused import

### CLEANUP-003: Oversized Function

- **File**: `phases/06_standardize/impl.py`
- **Symbol**: `run`
- **Line**: 391
- **Why**: Function has 253 lines (threshold: 100)
- **Confidence**: 90%
- **Phase**: 06_standardize
- **Action**: consider splitting function
- **Details**: Large function may be hard to maintain and test

### CLEANUP-004: Oversized File

- **File**: `phases/06_standardize/impl.py`
- **Why**: File has 645 lines (threshold: 500)
- **Confidence**: 80%
- **Phase**: 06_standardize
- **Action**: consider splitting module
- **Details**: Large file may benefit from being split into smaller modules

### CLEANUP-005: Unused Import

- **File**: `phases/06_standardize/normalizer.py`
- **Symbol**: `annotations`
- **Why**: Import 'annotations' is not used in the file
- **Confidence**: 85%
- **Phase**: 06_standardize
- **Action**: remove unused import

### CLEANUP-006: Oversized Function

- **File**: `phases/06_standardize/normalizer.py`
- **Symbol**: `normalize_values`
- **Line**: 227
- **Why**: Function has 247 lines (threshold: 100)
- **Confidence**: 90%
- **Phase**: 06_standardize
- **Action**: consider splitting function
- **Details**: Large function may be hard to maintain and test

### CLEANUP-007: Unused Import

- **File**: `phases/09_business_validation/models.py`
- **Symbol**: `ValidationError`
- **Why**: Import 'ValidationError' is not used in the file
- **Confidence**: 85%
- **Phase**: 09_business_validation
- **Action**: remove unused import

### CLEANUP-008: Unused Import

- **File**: `phases/09_business_validation/models.py`
- **Symbol**: `Tuple`
- **Why**: Import 'Tuple' is not used in the file
- **Confidence**: 85%
- **Phase**: 09_business_validation
- **Action**: remove unused import

### CLEANUP-009: Unused Import

- **File**: `phases/09_business_validation/models.py`
- **Symbol**: `Iterable`
- **Why**: Import 'Iterable' is not used in the file
- **Confidence**: 85%
- **Phase**: 09_business_validation
- **Action**: remove unused import

### CLEANUP-010: Unused Import

- **File**: `phases/09_business_validation/models.py`
- **Symbol**: `Sequence`
- **Why**: Import 'Sequence' is not used in the file
- **Confidence**: 85%
- **Phase**: 09_business_validation
- **Action**: remove unused import

### CLEANUP-011: Unused Import

- **File**: `phases/09_business_validation/models.py`
- **Symbol**: `annotations`
- **Why**: Import 'annotations' is not used in the file
- **Confidence**: 85%
- **Phase**: 09_business_validation
- **Action**: remove unused import

### CLEANUP-012: Unused Import

- **File**: `phases/09_business_validation/io.py`
- **Symbol**: `Dict`
- **Why**: Import 'Dict' is not used in the file
- **Confidence**: 85%
- **Phase**: 09_business_validation
- **Action**: remove unused import

### CLEANUP-013: Unused Import

- **File**: `phases/09_business_validation/io.py`
- **Symbol**: `annotations`
- **Why**: Import 'annotations' is not used in the file
- **Confidence**: 85%
- **Phase**: 09_business_validation
- **Action**: remove unused import

### CLEANUP-014: Unused Import

- **File**: `phases/09_business_validation/impl.py`
- **Symbol**: `annotations`
- **Why**: Import 'annotations' is not used in the file
- **Confidence**: 85%
- **Phase**: 09_business_validation
- **Action**: remove unused import

### CLEANUP-015: Unused Import

- **File**: `phases/09_business_validation/impl.py`
- **Symbol**: `pd`
- **Why**: Import 'pd' is not used in the file
- **Confidence**: 85%
- **Phase**: 09_business_validation
- **Action**: remove unused import

### CLEANUP-016: Oversized Function

- **File**: `phases/09_business_validation/impl.py`
- **Symbol**: `run`
- **Line**: 1905
- **Why**: Function has 520 lines (threshold: 100)
- **Confidence**: 90%
- **Phase**: 09_business_validation
- **Action**: consider splitting function
- **Details**: Large function may be hard to maintain and test

### CLEANUP-017: Oversized File

- **File**: `phases/09_business_validation/impl.py`
- **Why**: File has 2429 lines (threshold: 500)
- **Confidence**: 80%
- **Phase**: 09_business_validation
- **Action**: consider splitting module
- **Details**: Large file may benefit from being split into smaller modules

### CLEANUP-018: Unused Import

- **File**: `phases/07_5_feature_report/impl.py`
- **Symbol**: `annotations`
- **Why**: Import 'annotations' is not used in the file
- **Confidence**: 85%
- **Phase**: 07_5_feature_report
- **Action**: remove unused import

### CLEANUP-019: Oversized Function

- **File**: `phases/07_5_feature_report/impl.py`
- **Symbol**: `run`
- **Line**: 655
- **Why**: Function has 324 lines (threshold: 100)
- **Confidence**: 90%
- **Phase**: 07_5_feature_report
- **Action**: consider splitting function
- **Details**: Large function may be hard to maintain and test

### CLEANUP-020: Oversized File

- **File**: `phases/07_5_feature_report/impl.py`
- **Why**: File has 983 lines (threshold: 500)
- **Confidence**: 80%
- **Phase**: 07_5_feature_report
- **Action**: consider splitting module
- **Details**: Large file may benefit from being split into smaller modules

_...and 49 more high-confidence findings. See JSON report for full list._

## 💡 Recommendations

1. Consider removing 30 unused imports
2. Review 23 oversized functions for potential splitting
3. Consider refactoring 10 large files

---

## 📝 Notes

- This is an **informational report only** - no automatic changes are made
- Review each finding and take appropriate action based on your project needs
- Confidence levels indicate likelihood of the finding being actionable
- Low confidence findings may be false positives and require manual review

## 🔧 Available Actions

- **Refresh docs**: `python -m src.guardian_mindq . --refresh-docs`
- **Review JSON**: `.guardian/mindq_cleanup.json` for structured data
- **Create refactor plan**: Use findings to create a structured refactor plan

---

Generated by Mind-Q Guardian v1.4 - Refactor Radar
