## Mind-Q V4.1 — AI Agent Context
⚠️ CRITICAL RULES — READ FIRST
1. NEVER modify contracts/*.yml without understanding downstream impact
2. NEVER change impl.py files without running tests
3. ALWAYS check gate.json after any pipeline run
4. Mode is business_first: SLA/RTO issues = WARN only, never STOP

### What Is This?
Logistics data pipeline. 12+ stages. Ingests CSV/Excel → processes → outputs BI reports.
Input: Raw delivery/shipment files
Output: BI dashboards, SLA reports, KPI insights

### Pipeline Sequence
01_ingestion → 02_quality → 03_schema → 03.5_textops → 04_profile
     ↓
05_missing → 06_standardize → 06_feature_eng → 07_readiness
     ↓
07.5_feature_report → 07.6_llm_summary → 07.7_correlations
     ↓
08_insights → 09_business_validation → 10_bi
Optional stages: 07_analytics, 07_timeseries, 09.5_causal, 12_routing

### Gating Rules (business_first mode)
- STRUCTURAL → STOP pipeline (e.g., missing file, zero rows, broken schema)
- BUSINESS → WARN only, continues (e.g., low SLA%, high RTO%, PSI drift)

### File Locations
#### Source Code
phases/01_ingestion/impl.py      # Stage 01
phases/02_quality/impl.py        # Stage 02
phases/05_missing/impl.py        # Stage 05
phases/06_standardize/impl.py    # Stage 06
phases/07_readiness/impl.py      # Stage 07
phases/09_business_validation/   # Stage 09
src/app/services/stage_08_*/     # Stage 08
#### Contracts (Business Rules) ⚠️ HIGH IMPACT
contracts/
├── impute/policy_relaxed.yml    # Imputation rules
├── nzv/policy.yml               # Near-zero variance thresholds
├── kpis/critical_columns.yml    # Critical columns for Stage 07
├── analytics/gate.yml           # Stage 08 quality checks
├── sla/sla_defaults.yml         # SLA hour limits
└── payment/payment_rules.yml    # COD/payment rules
#### Outputs
artifacts/{run_id}/stage_XX/
├── gate.json          # PASS/WARN/STOP status + reasons
├── logs.jsonl         # Execution trace
└── [stage outputs]    # Varies by stage

### Before Making Changes
1) Identify Impact Scope
Changing Stage 05? → Affects 06, 07, 08, 09, 10
Changing contracts/? → May affect multiple stages
Changing Stage 08 only? → Affects 09, 10
2) Run Relevant Tests
```zsh
# Specific stage
pytest tests/test_phase05_missing.py -v

# Full suite
make test
```
3) Verify After Changes
```zsh
# Run pipeline
make run

# Check gates
cat artifacts/*/stage_*/gate.json | grep -E '"status"'

# Check for errors
grep -r "STOP\|ERROR" artifacts/*/stage_*/logs.jsonl
```

### Common Tasks
"Change SLA threshold"
File: contracts/sla/sla_defaults.yml
Key: global_hours (default 48)
Impact: Stage 09 SLA calculations
"Add critical column"
File: contracts/kpis/critical_columns.yml
Impact: Stage 07 readiness, Stage 08 preflight
Test: pytest tests/test_phase06_readiness.py
"Change imputation strategy"
File: contracts/impute/policy_relaxed.yml
Impact: Stage 05 → all downstream
Test: pytest tests/test_phase05_missing.py
"Modify Stage 08 insights"
File: src/app/services/stage_08_insights/impl.py
Config: src/app/services/stage_08_insights/settings.py
Gates: contracts/analytics/gate.yml
Test: pytest tests/test_phase08_insights.py

### Debugging
Pipeline stopped?
```zsh
# Find which stage
grep -l '"status": "STOP"' artifacts/*/stage_*/gate.json

# Read reasons
cat artifacts/{run_id}/stage_XX/gate.json | jq '.reasons'
```
Too many warnings?
```zsh
# Count per stage
for f in artifacts/*/stage_*/logs.jsonl; do
     echo "$f: $(grep -c WARN $f 2>/dev/null || echo 0)"
done
```
Understand final state?
```zsh
cat artifacts/*/stage_10*/business_state.json
```

### Stage Dependencies (Change Impact)
If you change...        You affect...
─────────────────────────────────────
Stage 01               → ALL stages
Stage 05               → 06, 07, 07.*, 08, 09, 10
Stage 06               → 07, 07.*, 08, 09, 10
Stage 07               → 07.*, 08, 09, 10
Stage 08               → 09, 10
contracts/impute/      → 05 → downstream
contracts/nzv/         → 05, 06, 07, 08
contracts/kpis/        → 07, 08, 09
contracts/analytics/   → 08, 09
contracts/sla/         → 09, 10

### Quick Commands
```zsh
make run               # Full pipeline
make test              # All tests
make lint              # Code quality
python cli/runner.py --stage 08   # Single stage
```

### Quick Try It — Stage 08 run snapshot
Run one of the prepared Stage 08 scenarios, then summarize gates and business state:
```zsh
# Example: pick a recent run folder and inspect key artifacts
RUN_DIR=$(ls -td artifacts/* | head -n 1)

# If you have scenario folders like stage_08_run_*:
SCENARIO_DIR=$(ls -d stage_08_run-* 2>/dev/null | head -n 1)
echo "Scenario: ${SCENARIO_DIR:-none}"

# Execute pipeline runner if applicable
if [ -f ./run_pipeline.sh ]; then
     ./run_pipeline.sh || true
fi

# Collect gate statuses
grep -E '"status"' ${RUN_DIR}/stage_*/gate.json || true

# Show final business state (Stage 10)
if ls ${RUN_DIR}/stage_10*/business_state.json >/dev/null 2>&1; then
     cat ${RUN_DIR}/stage_10*/business_state.json
fi
```

### Troubleshooting (fast checks)
```zsh
# Path issues (ensure local bin is present for CLI tools)
echo $PATH | grep -q "$HOME/.local/bin" || echo "Add: export PATH=\"$HOME/.local/bin:$PATH\" to ~/.zshrc"

# Missing env keys
env | grep -E 'ANTHROPIC_API_KEY|OPENAI_API_KEY|MINDQ_BUSINESS_MODE' || echo "Set required env vars in ~/.zshrc"

# Find STOP quickly
grep -l '"status": "STOP"' artifacts/*/stage_*/gate.json 2>/dev/null || echo "No STOP found"
```

### Environment Variables
```zsh
export MINDQ_BUSINESS_MODE=business_first  # Default (recommended)
export MINDQ_LLM_PROVIDERS=openai,anthropic
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
```

### For Deep Understanding
docs/PHASES_DETAILED_GUIDE.md    # Full 2000-line documentation
docs/CLAUDE_ARCHITECTURE.md      # Visual maps and relationships
docs/CLAUDE_DECISION_TREE.md     # Troubleshooting flowcharts

### ⚠️ Final Reminder
1. Test before committing
2. Check gate.json after runs
3. Contracts have wide impact - change carefully
4. When in doubt, read PHASES_DETAILED_GUIDE.md