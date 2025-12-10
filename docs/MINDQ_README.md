# Mind-Q Guardian v1.4 - Complete Guide

**The Comprehensive AI Agent Memory & Decision Support System for Complex Data Pipelines**

---

## 📋 Table of Contents

- [Overview](#overview)
- [What Problems Does It Solve?](#what-problems-does-it-solve)
- [Quick Start](#quick-start)
- [Core Features](#core-features)
- [API Reference](#api-reference)
- [CLI Commands](#cli-commands)
- [Usage Examples](#usage-examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

---

## Overview

**Mind-Q Guardian** is a specialized AI agent support system designed for complex, multi-phase data pipeline projects like Mind-Q. It addresses the fundamental challenge that AI coding agents face: **context overload** and **lack of persistent memory**.

### Key Statistics

| Metric | Value |
|--------|-------|
| Documentation Size Reduction | **94%** (150KB+ → <10KB) |
| Pipeline Phases Tracked | **21 phases** |
| Business KPIs Monitored | **8 KPIs** |
| Status Codes | **4 intelligent states** |
| Code Analysis Confidence | **60-90%** |
| Blocking Behavior | **ZERO** (never blocks) |

### What Makes It Special?

1. **Pipeline-Aware**: Understands Mind-Q's 21-phase structure (ingestion → routing)
2. **KPI-Centric**: Maps business metrics (RTO%, SLA, COD, PSI, NZV) to code phases
3. **Context-Optimized**: Generates compact, focused context for LLM agents
4. **Code-Aware**: Deep AST-based analysis finds unused imports, oversized functions, duplicates
5. **Non-Blocking**: Soft guidance layer - helps without hindering

---

## What Problems Does It Solve?

### Problem 1: Documentation Overload
**Before**: AI agents receive 150KB+ of documentation → context window exhausted  
**After**: <10KB focused context based on user request → agent understands exactly what's needed

### Problem 2: Phase Confusion
**Before**: "Fix data quality" → agent doesn't know which of 21 phases to work on  
**After**: Smart detection maps request to `[02_quality, 04_profile]` → agent focuses on right phases

### Problem 3: Memory Loss
**Before**: Agent forgets previous decisions between sessions  
**After**: Persistent change tracking in `.guardian/` → agent sees history and continues coherently

### Problem 4: Unplanned Changes
**Before**: Agent makes structural changes without understanding impact  
**After**: Change planning workflow with KPI impact analysis → agent works with a plan

### Problem 5: Code Quality Drift
**Before**: Unused imports, oversized functions accumulate unnoticed  
**After**: Deep code analysis (Refactor Radar) identifies issues with confidence levels

### Problem 6: KPI Blindness
**Before**: Agent doesn't know which changes affect business metrics  
**After**: Bidirectional KPI-phase mapping → agent understands business impact

---

## Quick Start

### Prerequisites

- Python 3.8+
- Git (for change tracking features)
- Mind-Q project with standard structure:
  ```
  Mind-Q/
  ├── phases/           # Phase implementations
  ├── docs/
  │   └── PHASES_DETAILED_GUIDE.md
  ├── contracts/        # Configuration files
  └── src/              # Source code
  ```

### Installation (3 Steps)

#### Step 1: Get Guardian-H

```bash
git clone https://github.com/Haithamhaj/guardian-h.git
cd guardian-h
```

#### Step 2: Initialize for Your Mind-Q Project

```bash
cd /path/to/your/mind-q-project

# Build pipeline spine
python /path/to/guardian-h/src/guardian_mindq.py . --build-spine

# Generate phase cards
python /path/to/guardian-h/src/guardian_mindq.py . --generate-cards
```

**This creates:**
- `docs/mindq_spine.yaml` - Pipeline structure map
- `docs/phases/*.md` - 21 phase-specific cards
- `.guardian/` directory (auto-created)

#### Step 3: Integrate with Your IDE

```bash
# Generate MDC files for IDE integration
python /path/to/guardian-h/src/guardian_enhanced.py
```

**This creates MDC files for:**
- Cursor (`.cursor/rules/guardian.mdc`)
- Windsurf (`.windsurf/rules/guardian.md`)
- GitHub Copilot (`.github/copilot-instructions.md`)
- Claude (`CLAUDE.md`)

### Verification

```bash
# Check status
python /path/to/guardian-h/src/guardian_mindq.py . --status

# Output should show:
# Status: NO_CHANGES ✅
# Ready for new work
```

---

## Core Features

### 1. Pipeline Spine Generation 🧬

**What**: Creates a compact YAML map of your entire 21-phase pipeline

**Why**: Gives AI agents a mental model of pipeline structure

**File**: `docs/mindq_spine.yaml` (<10KB)

**Contains:**
- 21 phases with dependencies
- 8 KPIs with phase mappings
- Phase-to-phase data flows
- Phase grouping (data foundation, analytics, AI, BI)

**Example**:
```yaml
project: Mind-Q V4.1
phases:
  - id: "01_ingestion"
    name: "Data Ingestion"
    dependencies: []
  - id: "02_quality"
    name: "Quality Checks"
    dependencies: ["01_ingestion"]

kpis:
  - name: "RTO%"
    impacted_by: ["01_ingestion", "07_readiness", "08_insights"]
  - name: "PSI"
    impacted_by: ["04_profile", "05_missing"]
```

**CLI**:
```bash
python -m src.guardian_mindq . --build-spine
```

---

### 2. Phase Cards Generation 📊

**What**: Focused documentation for each phase

**Why**: AI agents get phase-specific context without loading all docs

**Files**: `docs/phases/*.md` (21 files)

**Each card contains:**
- Goal (1-2 sentences)
- Business impact
- Inputs & outputs
- Code files (up to 6)
- KPIs affected
- Upstream/downstream phases

**Example** (`docs/phases/04_profile.md`):
```markdown
# Phase 04: Data Profiling

## Goal
Calculate PSI (Population Stability Index) and detect missing value patterns

## Inputs
- standardized.parquet (from 03_schema)

## Outputs
- profile_report.json
- psi_scores.json

## Code Files
1. phases/04_profile/impl.py
2. phases/04_profile/psi_calculator.py

## KPIs Affected
- PSI (directly calculated)
- Data Quality Score

## Business Impact
Critical for detecting data drift
```

**CLI**:
```bash
# Generate all cards
python -m src.guardian_mindq . --generate-cards
```

---

### 3. Smart Phase Detection 🎯

**What**: Maps natural language to relevant phases

**Why**: AI knows where to focus (out of 21 phases)

**Example**:
```python
from src.guardian_mindq import MindQGuardianAdapter

mindq = MindQGuardianAdapter("/path/to/mindq")

# User says: "Fix PSI calculation issues"
phases = mindq.map_request_to_phases("Fix PSI calculation issues")
# Returns: ['04_profile', '05_missing']

# User says: "Improve SLA tracking"
phases = mindq.map_request_to_phases("Improve SLA tracking")
# Returns: ['01_ingestion', '07_readiness', '08_insights']
```

**How it works:**
1. Detects KPI mentions (PSI, SLA, COD, etc.)
2. Looks up phases that affect those KPIs
3. Detects phase IDs/names in text
4. Returns max 4 most relevant phases

---

### 4. Change Planning Workflow 📝

**What**: 3-step structured workflow for changes

**Why**: Prevents unplanned changes, tracks impact

**Steps:**

#### Step 1: Build Change Request
```python
change_req = mindq.build_change_request("Fix PSI calculation")
# Returns: {id, goal, target_phases, created_at}
```

#### Step 2: Plan Change (Auto-creates Checklist)
```python
plan = mindq.plan_change(change_req)
# Returns: {files_to_edit, affected_kpis, potential_risks}
# Creates: .guardian/mindq_status.md with checklist
```

#### Step 3: Record Change (Auto-completes Checklist)
```python
mindq.record_change(change_req, plan, files_changed=['file1.py'])
# Updates audit trail + marks checklist complete
```

**CLI**:
```bash
python -m src.guardian_mindq . --plan-change "Fix PSI calculation"
```

---

### 5. Status Tracking (4 Codes) 🚦

**What**: Monitors project state with intelligent guidance

**Status Codes:**

| Code | Meaning | Guidance |
|------|---------|----------|
| `NO_CHANGES` ✅ | Clean state | Ready for work |
| `NO_PLAN_FOR_CHANGES` ⚠️ | Files changed, no plan | Avoid large changes without plan |
| `PLAN_VIOLATIONS` 🔔 | Extra files changed | Review before continuing |
| `ON_TRACK` ✅ | Following plan | Continue with plan |

**API**:
```python
from src.guardian_mindq import MindQStatus

status: MindQStatus = mindq.scan_guardian_status()
print(status.status)  # "ON_TRACK"
print(status.extra_files_count)  # 0
```

**CLI**:
```bash
python -m src.guardian_mindq . --status
```

---

### 6. Deep Code Analysis (Refactor Radar) 🔍

**What**: AST-based Python analysis for refactoring opportunities

**Why**: Catches quality issues before they become technical debt

**Detects:**
- Unused imports (85% confidence)
- Oversized functions >100 lines (90% confidence)
- Oversized files >500 lines (80% confidence)
- Duplicate functions (60% confidence)

**Output**: Dual format
- `.guardian/mindq_cleanup.md` (human-readable)
- `.guardian/mindq_cleanup.json` (machine-readable)

**Example Finding**:
```markdown
### CLEANUP-001: Unused Import
- **File**: phases/04_profile/impl.py
- **Symbol**: pandas
- **Confidence**: 85%
- **Action**: Remove unused import
```

**CLI**:
```bash
python -m src.guardian_mindq . --deep-cleanup
```

**Output**:
```
🔍 Running deep code-aware cleanup (Refactor Radar)...
📊 Deep Cleanup Summary:
   Total findings: 47
   High confidence: 23
   
📋 Findings by Category:
   - Unused Import: 18
   - Oversized Function: 5
   
📄 Reports saved:
   Markdown: .guardian/mindq_cleanup.md
   JSON: .guardian/mindq_cleanup.json
```

---

### 7. Documentation Refresh 🔄

**What**: Regenerates spine and phase cards after code changes

**Why**: Keeps documentation in sync with implementation

**Usage**:
```python
# Refresh all
results = mindq.refresh_docs_after_changes()

# Refresh specific phases
results = mindq.refresh_docs_after_changes(['04_profile', '05_missing'])
```

**CLI**:
```bash
python -m src.guardian_mindq . --refresh-docs
```

---

### 8. Context Optimization 📦

**What**: Generates minimal, focused context for AI agents

**Size Reduction**: 94% (150KB+ → <10KB)

**How**:
```python
# Instead of loading ALL docs (150KB+)
context = mindq.get_guardian_context_for_request(
    "Fix data quality issues in profiling stage"
)
# Returns <10KB focused on relevant phases only
```

---

### 9. IDE Integration 🔌

**What**: Auto-detects Mind-Q projects and includes compact status in MDC

**Generated Files** (~250 lines each):
- `guardian_enhanced.mdc`
- `.cursor/rules/guardian.mdc`
- `.windsurf/rules/guardian.md`
- `.github/copilot-instructions.md`
- `CLAUDE.md`

**MDC Includes:**
- Current status (20-30 lines)
- Phase structure summary
- KPI tracking status
- Explicit pointers to detailed files

**Size**: ~250 lines (vs >5000 before)

---

## API Reference

### MindQGuardianAdapter Class

```python
from src.guardian_mindq import MindQGuardianAdapter, MindQStatus, CleanupItem

# Initialize
adapter = MindQGuardianAdapter("/path/to/mindq-project")
```

#### Pipeline Intelligence

```python
# Build pipeline spine
spine_data = adapter.build_spine()
# Returns: Dict with phases, kpis, flows

# Save spine to file
adapter.save_spine()
# Creates: docs/mindq_spine.yaml

# Generate phase cards
adapter.generate_phase_cards()
# Creates: docs/phases/*.md (all phases)

# Generate single phase card
card = adapter.generate_phase_card("04_profile")
# Returns: Dict with goal, inputs, outputs, etc.
```

#### KPI Management

```python
# Get KPI to phase mapping
kpi_map = adapter.get_kpi_phase_mapping()
# Returns: {'RTO%': ['01_ingestion', ...], ...}

# Get KPIs impacted by phase
kpis = adapter.get_phase_kpi_impact('04_profile')
# Returns: ['PSI', 'Data Quality Score']
```

#### Request Mapping

```python
# Map request to relevant phases
phases = adapter.map_request_to_phases("Fix PSI calculation")
# Returns: ['04_profile', '05_missing']
```

#### Change Management

```python
# Step 1: Build change request
change_req = adapter.build_change_request("Improve data quality checks")
# Returns: {id, goal, target_phases, created_at, ...}

# Step 2: Plan change
plan = adapter.plan_change(change_req)
# Returns: {files_to_edit, affected_kpis, potential_risks, ...}
# Creates: .guardian/mindq_status.md

# Step 3: Record change
adapter.record_change(
    change_req,
    plan,
    files_changed=['file1.py', 'file2.py']
)
# Updates: .guardian/mindq_changes.json, .guardian/mindq_status.md
```

#### Status Tracking

```python
# Scan current status
status: MindQStatus = adapter.scan_guardian_status()
# Returns: MindQStatus(status, last_goal, target_phases, planned_files_count, extra_files_count)

# Get status summary
summary = adapter.get_status_summary()
# Returns: str (<500 chars)

# Get changed files
changed = adapter.get_changed_files()
# Returns: List[str] (or [] if git unavailable)

# Load last change
last_change = adapter._load_last_change_record()
# Returns: Dict or None
```

#### Cleanup & Analysis

```python
# Basic cleanup (docs & structure)
report = adapter.run_cleanup()
# Returns: {unused_phases, outdated_cards, missing_cards, stale_contracts, recommendations}
# Creates: .guardian/mindq_cleanup.md

# Deep code analysis (Refactor Radar)
items: List[CleanupItem] = adapter.run_deep_cleanup()
# Returns: List of CleanupItem objects
# Creates: .guardian/mindq_cleanup.md, .guardian/mindq_cleanup.json
```

#### Documentation Management

```python
# Refresh all documentation
results = adapter.refresh_docs_after_changes()
# Returns: {"spine": bool, "phase_cards": int}

# Refresh specific phases
results = adapter.refresh_docs_after_changes(['04_profile', '05_missing'])
# Returns: {"spine": bool, "phase_cards": 2}
```

#### Context Generation

```python
# Get optimized context for LLM
context = adapter.get_guardian_context_for_request(
    "Fix data quality issues"
)
# Returns: str (compact markdown, <10KB)

# Get structured change guidance
guidance = adapter.build_llm_change_context(
    "Fix PSI calculation in missing value imputation"
)
# Returns: str (markdown with phases, files, KPIs, risks, workflow)

# Get MDC-ready context
mdc_context = adapter.get_mindq_context_for_mdc()
# Returns: str (compact status for inclusion in MDC)
```

---

## CLI Commands

### Basic Commands

```bash
# Initialize Mind-Q Guardian
python -m src.guardian_mindq /path/to/mindq --build-spine
python -m src.guardian_mindq /path/to/mindq --generate-cards
```

### Information Commands

```bash
# Show KPI mapping
python -m src.guardian_mindq /path/to/mindq --kpi-mapping

# Show KPIs for specific phase
python -m src.guardian_mindq /path/to/mindq --phase-kpis 04_profile

# Map request to phases
python -m src.guardian_mindq /path/to/mindq --map-request "Fix data quality"

# Check current status
python -m src.guardian_mindq /path/to/mindq --status
```

### Change Management

```bash
# Plan a change
python -m src.guardian_mindq /path/to/mindq --plan-change "Improve PSI calculation"
```

### Cleanup & Analysis

```bash
# Basic cleanup (docs & structure)
python -m src.guardian_mindq /path/to/mindq --cleanup

# Deep code analysis (Refactor Radar)
python -m src.guardian_mindq /path/to/mindq --deep-cleanup
```

### Documentation

```bash
# Refresh all documentation
python -m src.guardian_mindq /path/to/mindq --refresh-docs
```

### Demo

```bash
# Run comprehensive 10-step demo
python -m src.guardian_mindq /path/to/mindq --demo
```

---

## Usage Examples

### Example 1: Starting a New Feature

```python
from src.guardian_mindq import MindQGuardianAdapter

# Initialize
mindq = MindQGuardianAdapter("/path/to/mindq")

# Step 1: Understand which phases are involved
phases = mindq.map_request_to_phases("Add new COD tracking dashboard")
print(phases)  # ['01_ingestion', '08_insights', '10_bi']

# Step 2: Get focused context
context = mindq.get_guardian_context_for_request("Add new COD tracking dashboard")
# Agent receives <10KB focused on these 3 phases only

# Step 3: Create change plan
change_req = mindq.build_change_request("Add new COD tracking dashboard")
plan = mindq.plan_change(change_req)
# Checklist created in .guardian/mindq_status.md

# Step 4: Make changes...
# (agent works on phases/01_ingestion/, phases/08_insights/, phases/10_bi/)

# Step 5: Record completion
mindq.record_change(change_req, plan, files_changed=[
    "phases/01_ingestion/cod_tracker.py",
    "phases/08_insights/dashboard.py",
    "phases/10_bi/reports.py"
])
# Checklist marked complete, audit trail updated
```

### Example 2: Bug Fix Workflow

```python
# Step 1: Check current status
status = mindq.scan_guardian_status()
if status.status != "NO_CHANGES":
    print(f"⚠️ Warning: {status.extra_files_count} files changed without plan")

# Step 2: Plan bug fix
change_req = mindq.build_change_request("Fix PSI calculation bug in profiling")
plan = mindq.plan_change(change_req)

# Step 3: Make changes
# (fix bug in phases/04_profile/psi_calculator.py)

# Step 4: Record fix
mindq.record_change(change_req, plan, files_changed=[
    "phases/04_profile/psi_calculator.py"
])

# Step 5: Verify status
status = mindq.scan_guardian_status()
assert status.status == "ON_TRACK"  # ✅
```

### Example 3: Refactoring with Refactor Radar

```python
# Step 1: Run deep analysis
items = mindq.run_deep_cleanup()

# Step 2: Filter high-confidence findings
high_conf = [item for item in items if item.confidence >= 0.8]
print(f"Found {len(high_conf)} high-confidence issues")

# Step 3: Group by kind
from collections import defaultdict
by_kind = defaultdict(list)
for item in high_conf:
    by_kind[item.kind].append(item)

# Step 4: Address unused imports first (easiest wins)
for item in by_kind['unused_import']:
    print(f"TODO: Remove {item.symbol} from {item.file}")
    
# Step 5: Plan larger refactorings
oversized = by_kind['oversized_function']
if oversized:
    change_req = mindq.build_change_request(
        f"Refactor {len(oversized)} oversized functions"
    )
    plan = mindq.plan_change(change_req)
```

### Example 4: Documentation Sync

```python
# After adding new phase "13_export"
mindq.refresh_docs_after_changes(['13_export'])

# After modifying multiple phases
mindq.refresh_docs_after_changes([
    '04_profile',
    '05_missing',
    '06_standardize'
])

# After major restructuring
mindq.refresh_docs_after_changes()  # Refresh all
```

---

## Best Practices

### 1. Always Plan Changes
✅ **DO**:
```python
change_req = mindq.build_change_request("Your change description")
plan = mindq.plan_change(change_req)
# Work on planned files...
mindq.record_change(change_req, plan, files_changed=[...])
```

❌ **DON'T**:
```python
# Just start changing files without a plan
# Status will show "NO_PLAN_FOR_CHANGES"
```

### 2. Check Status Regularly
```python
status = mindq.scan_guardian_status()
if status.status == "PLAN_VIOLATIONS":
    print(f"⚠️ {status.extra_files_count} extra files changed - review needed")
```

### 3. Use Focused Context
✅ **DO**:
```python
# Get context for specific request
context = mindq.get_guardian_context_for_request(
    "Fix PSI calculation"
)
# Returns <10KB focused on relevant phases
```

❌ **DON'T**:
```python
# Load all documentation
docs = load_all_markdown_files()  # 150KB+
```

### 4. Run Deep Cleanup Periodically
```bash
# Weekly or after major changes
python -m src.guardian_mindq . --deep-cleanup

# Review high-confidence findings
# Address unused imports first (quick wins)
# Plan larger refactorings
```

### 5. Refresh Docs After Changes
```python
# After modifying phases
mindq.refresh_docs_after_changes(['04_profile', '05_missing'])

# After adding/removing phases
mindq.refresh_docs_after_changes()  # Full refresh
```

### 6. Review Generated Checklists
- Open `.guardian/mindq_status.md` in your IDE
- Review tasks before starting work
- Check off items as you complete them
- Use as reference during code review

### 7. Use KPI Awareness
```python
# Before making changes
phases = mindq.map_request_to_phases("Improve SLA tracking")
kpis = mindq.get_phase_kpi_impact(phases[0])
print(f"This change will affect: {kpis}")
# Agent understands business impact
```

---

## Troubleshooting

### Issue: "Mind-Q project not detected"

**Symptoms**: Guardian Enhanced doesn't show Mind-Q status section

**Cause**: Project doesn't have enough markers (needs 2+)

**Solution**:
```bash
# Check for required markers
ls -la phases/                          # Should exist
ls -la docs/PHASES_DETAILED_GUIDE.md   # Should exist
ls -la contracts/                       # Should exist

# If missing, create required structure
mkdir -p phases docs contracts
```

---

### Issue: "No phase cards generated"

**Symptoms**: `docs/phases/` is empty

**Cause**: PHASES_DETAILED_GUIDE.md not found or malformed

**Solution**:
```bash
# Verify guide exists
cat docs/PHASES_DETAILED_GUIDE.md

# Regenerate cards
python -m src.guardian_mindq . --generate-cards

# Check for errors in output
```

---

### Issue: "Status shows NO_PLAN_FOR_CHANGES"

**Symptoms**: Warning in MDC about unplanned changes

**Cause**: Files were changed without creating a change plan

**Solution**:
```python
# Create retroactive plan
change_req = mindq.build_change_request("Describe what you changed")
plan = mindq.plan_change(change_req)
mindq.record_change(change_req, plan, files_changed=[...])
```

---

### Issue: "Deep cleanup finds too many false positives"

**Symptoms**: Duplicate function findings are incorrect

**Cause**: Confidence threshold too low (60%)

**Solution**:
```python
# Filter by higher confidence
items = mindq.run_deep_cleanup()
high_conf = [item for item in items if item.confidence >= 0.8]
# Focus on high-confidence findings only
```

---

### Issue: "Context still too large for LLM"

**Symptoms**: Agent says context is too big

**Cause**: Request mapped to too many phases

**Solution**:
```python
# Be more specific in request
context = mindq.get_guardian_context_for_request(
    "Fix PSI calculation in profile phase"  # More specific
)
# vs
context = mindq.get_guardian_context_for_request(
    "Fix data issues"  # Too broad
)
```

---

### Issue: "Git operations fail"

**Symptoms**: get_changed_files() returns []

**Cause**: Not a git repository or git not available

**Solution**:
```bash
# Initialize git if needed
git init

# Or ignore git features (all operations soft-fail gracefully)
# Agent can still use all other features
```

---

### Issue: "MDC files not auto-updated"

**Symptoms**: Changes not reflected in .cursor/rules/guardian.mdc

**Cause**: Guardian Enhanced not re-run

**Solution**:
```bash
# Re-run Guardian Enhanced to regenerate MDC
cd /path/to/mindq
python /path/to/guardian-h/src/guardian_enhanced.py

# Or use auto-refresh if available
```

---

## FAQ

**Q: Does Mind-Q Guardian modify code automatically?**  
A: No. It only analyzes and reports. All code changes are manual.

**Q: Does it work offline?**  
A: Yes. All features work offline except git-related operations.

**Q: Can I use it with other data pipeline projects?**  
A: Yes, but it's optimized for Mind-Q structure. You may need to customize phase detection.

**Q: Does it block commits or deployments?**  
A: No. It's purely informational. No git hooks, no blocking behavior.

**Q: How much disk space does it use?**  
A: Minimal. `.guardian/` typically <1MB. Generated docs ~500KB.

**Q: Can multiple agents use it simultaneously?**  
A: Yes. All operations are file-based and atomic.

**Q: Does it support languages other than Python?**  
A: Deep cleanup only supports Python (AST-based). Other features are language-agnostic.

**Q: How often should I run deep cleanup?**  
A: Weekly or after major changes. It's fast (~5 seconds for 800 files).

---

## Generated Files

### In Project Root

```
Mind-Q/
├── guardian_enhanced.mdc              # Compact MDC (~250 lines)
├── .cursor/
│   └── rules/
│       └── guardian.mdc               # Cursor IDE rules
├── .windsurf/
│   └── rules/
│       └── guardian.md                # Windsurf IDE rules
├── .github/
│   └── copilot-instructions.md        # GitHub Copilot instructions
├── CLAUDE.md                          # Claude instructions
```

### In .guardian/ Directory

```
.guardian/
├── mindq_changes.json                 # Change audit trail
├── mindq_status.md                    # Current status & checklist
├── mindq_cleanup.md                   # Cleanup report (markdown)
├── mindq_cleanup.json                 # Cleanup report (JSON)
├── file_index.md                      # Full file listing (not for LLM)
├── decisions.json                     # Locked decisions
├── changes.json                       # General change history
├── sessions.json                      # Agent session tracking
└── snapshots/                         # Project snapshots
```

### In docs/ Directory

```
docs/
├── mindq_spine.yaml                   # Pipeline structure map
└── phases/
    ├── 01_ingestion.md                # Phase 1 card
    ├── 02_quality.md                  # Phase 2 card
    ├── 03_schema.md                   # Phase 3 card
    ├── ...                            # (21 phase cards total)
    └── 12_routing.md                  # Phase 12 card
```

---

## Version History

### v1.4 (Current)
- Added deep code-aware cleanup (Refactor Radar)
- AST-based Python analysis
- Unused import detection (85% confidence)
- Oversized code detection (80-90% confidence)
- Duplicate function detection (60% confidence)
- Dual report format (Markdown + JSON)

### v1.3
- Added basic cleanup mode
- Added documentation refresh capability
- Added structured status API (MindQStatus)
- Enhanced MDC integration

### v1.2
- Added compact MDC integration
- Added status-aware guidance
- 67% reduction in MDC section size

### v1.1
- Added soft guidance layer
- Added status tracking
- Added checklist management

### v1.0
- Initial release
- Pipeline spine generation
- Phase cards
- KPI mapping
- Change planning workflow
- Context optimization

---

## Support & Contributing

**Issues**: https://github.com/Haithamhaj/guardian-h/issues  
**Discussions**: https://github.com/Haithamhaj/guardian-h/discussions  
**Documentation**: https://github.com/Haithamhaj/guardian-h/tree/main/docs

**Contributing**: PRs welcome! Please:
1. Maintain non-blocking behavior
2. Add tests for new features
3. Update documentation
4. Keep MDC compact

---

## License

See main Guardian-H repository for license information.

---

## Credits

Developed as part of Guardian-H v7.0 to solve the AI agent memory and context overload problems in complex data pipeline projects.

**Part of**: Guardian-H v7.0  
**Optimized for**: Mind-Q V4.1 logistics data pipeline
