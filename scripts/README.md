# Documentation Automation Scripts

This directory contains scripts for automated documentation maintenance and validation.

## Scripts

### 1. `generate_phase_docs.py` - Documentation Generator

**Purpose:** Automatically extracts information from the codebase and generates a documentation appendix.

**What it extracts:**
- `PIPELINE_PHASE_SEQUENCE` from `pipeline_api/app.py`
- `PHASE_MODULES` mapping
- `run()` function signatures from all stage implementations
- Output artifacts (JSON, parquet, etc.)
- STOP/WARN conditions from each stage
- Contract file existence checks

**Usage:**
```bash
# Generate appendix (default location)
python3 scripts/generate_phase_docs.py

# Specify custom output
python3 scripts/generate_phase_docs.py --output docs/MY_APPENDIX.md

# Using Make
make docs
```

**Output:** `docs/GENERATED_APPENDIX.md` (295+ lines)

---

### 2. `validate_docs.py` - Documentation Validator

**Purpose:** Validates `PHASES_DETAILED_GUIDE.md` against the actual codebase.

**Validation Checks:**
1. ✅ **Placeholders** - Finds `{{TO_FILL_DATE}}` that need updating
2. ✅ **Line References** - Checks `filepath#L123` references are valid
3. ✅ **File References** - Verifies referenced files exist
4. ✅ **Pipeline Sequence** - Compares documented vs actual `PIPELINE_PHASE_SEQUENCE`
5. ✅ **STOP/WARN Keywords** - Validates gate logic matches implementation
6. ✅ **RAG Integration** - Checks RAG features are documented

**Usage:**
```bash
# Run validation (shows warnings)
python3 scripts/validate_docs.py

# Strict mode (exits with error on warnings)
python3 scripts/validate_docs.py --strict

# Using Make
make validate-docs          # Normal mode
make validate-docs-strict   # Strict mode
make check-docs            # Validate + generate
```

**Exit Codes:**
- `0` - All checks passed
- `1` - Errors found (or warnings in strict mode)

---

## Integration with Development Workflow

### Pre-commit Hooks

The validation scripts run automatically before each commit via `.pre-commit-config.yaml`:

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Or use Make
make pre-commit-install
```

**What runs on commit:**
1. `validate-docs` - Checks documentation accuracy
2. `generate-docs-appendix` - Updates appendix if impl files changed
3. `check-placeholder-dates` - Blocks commit if `{{TO_FILL_DATE}}` found

**To bypass hooks (not recommended):**
```bash
git commit --no-verify -m "message"
```

---

### GitHub Actions CI

The `.github/workflows/docs-validation.yml` workflow runs on:
- Every PR that touches documentation or implementation files
- Every push to `main` or `port/update-*` branches

**What it does:**
1. ✅ Runs `validate_docs.py --strict`
2. ✅ Checks for `{{TO_FILL_DATE}}` placeholders
3. ✅ Generates `GENERATED_APPENDIX.md`
4. ⚠️ Comments on PR if validation fails
5. 🚫 Blocks merge if errors found

**How to fix CI failures:**
```bash
# 1. Run validation locally
make validate-docs

# 2. Fix reported issues in PHASES_DETAILED_GUIDE.md

# 3. Regenerate appendix
make docs

# 4. Commit and push
git add docs/
git commit -m "docs: fix validation errors"
git push
```

---

## Common Issues and Fixes

### ⚠️ "Found placeholder {{TO_FILL_DATE}}"
**Fix:** Replace with actual date (e.g., `2025-11-22`)

```bash
# Find all occurrences
grep -n "{{TO_FILL_DATE}}" docs/PHASES_DETAILED_GUIDE.md

# Replace all with current date
sed -i '' 's/{{TO_FILL_DATE}}/2025-11-22/g' docs/PHASES_DETAILED_GUIDE.md
```

### ❌ "Line reference exceeds file length"
**Fix:** Update line number references

```bash
# Find actual line number
grep -n "PIPELINE_PHASE_SEQUENCE" backend/src/app/services/pipeline_api/app.py
```

### ⚠️ "Referenced file does not exist"
**Fix:** Either create the file or remove the reference from docs

### ❌ "PIPELINE_PHASE_SEQUENCE mismatch"
**Fix:** Sync documented sequence with actual code

```bash
# Check actual sequence
python3 scripts/generate_phase_docs.py
# Review docs/GENERATED_APPENDIX.md section 1
```

---

## Makefile Commands

Quick reference for all documentation commands:

```makefile
make docs                  # Generate GENERATED_APPENDIX.md
make validate-docs         # Validate documentation (warnings OK)
make validate-docs-strict  # Validate documentation (fail on warnings)
make check-docs           # Validate + generate in one command
make pre-commit-install   # Install pre-commit hooks
make pre-commit-run       # Run all pre-commit checks manually
```

---

## Development Tips

### When to run these scripts:

1. **After modifying impl.py files** → Run `make docs`
2. **Before committing doc changes** → Run `make validate-docs`
3. **After changing PIPELINE_PHASE_SEQUENCE** → Run `make check-docs`
4. **Before creating PR** → Run `make validate-docs-strict`

### How to keep docs always synchronized:

1. **Use pre-commit hooks** (automatic)
2. **Review CI failures immediately**
3. **Update appendix regularly**: `make docs`
4. **Never commit with `{{TO_FILL_DATE}}`**

---

## Script Architecture

### `generate_phase_docs.py` Functions:

```python
extract_pipeline_sequence()      # From app.py
extract_phase_modules()          # Module mapping
extract_run_signature(path)      # Function signatures
extract_stage_outputs(path)      # Artifact files
extract_stop_warn_conditions(path)  # Gate logic
generate_appendix()              # Main generator
```

### `validate_docs.py` Validators:

```python
validate_placeholders()          # {{TO_FILL_DATE}}
validate_line_references()       # #L123 checks
validate_file_references()       # Path existence
validate_pipeline_sequence()     # Sequence sync
validate_stop_warn_keywords()    # Gate logic
validate_rag_integration()       # RAG features
```

---

## Troubleshooting

### Script fails with import errors
```bash
# Ensure project root is accessible
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python3 scripts/validate_docs.py
```

### Pre-commit hooks not running
```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install
pre-commit run --all-files
```

### CI workflow not triggering
Check that your PR touches these paths:
- `docs/PHASES_DETAILED_GUIDE.md`
- `phases/**/impl.py`
- `src/app/services/**/impl.py`
- `backend/src/app/services/pipeline_api/app.py`

---

## Future Enhancements

Potential improvements for these scripts:

1. **Auto-fix mode** - Automatically update line numbers
2. **Diff reporting** - Show before/after changes
3. **Coverage metrics** - Track documentation completeness
4. **LLM integration** - Generate stage descriptions
5. **Snapshot testing** - Compare against baseline docs
6. **Interactive mode** - Walk through fixes step-by-step

---

## Support

For questions or issues:
1. Check this README
2. Review workflow logs in GitHub Actions
3. Run scripts locally with verbose output
4. Examine `docs/GENERATED_APPENDIX.md` for reference

**Remember:** These scripts are your friends! They catch issues before reviewers do. 🎯
