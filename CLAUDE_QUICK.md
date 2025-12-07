## Mind-Q V4.1 — Claude Quick Context (≤1–2 pages)

Use this file as the primary context for AI agents to avoid truncation. It summarizes only essential signals and commands.

### 🔐 Rules
- Do not change `contracts/*.yml` without tests.
- Check `gate.json` after runs.
- Default mode: `business_first` (business alerts = WARN).

### 🧭 Pipeline (short)
01 Ingestion → 02 Quality → 03 Schema → 03.5 TextOps → 04 Profile → 05 Missing → 06 Standardize → 07 Readiness → 07.5/07.6/07.7 → 08 Insights → 09 Business Validation → 10 BI

Optional: 07 Analytics, 07 Timeseries, 09.5 Causal, 12 Routing

### 🚦 Gates (short)
- STRUCTURAL → STOP (missing file, zero rows, broken schema)
- BUSINESS → WARN (low SLA%, high RTO%, PSI drift)

### 📂 Key Paths
- Stages: `phases/*/impl.py`
- Contracts: `contracts/*.yml`
- Artifacts: `artifacts/{run_id}/stage_*/{gate.json,logs.jsonl}`
- Docs: `docs/PHASES_DETAILED_GUIDE.md`

### ⚙️ Env (zsh)
```zsh
export MINDQ_BUSINESS_MODE=business_first
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
```

### ▶️ Run & Inspect (zsh)
```zsh
make run                          # Full pipeline
cat artifacts/*/stage_*/gate.json | grep -E '"status"'
```

### 🧪 Tests (zsh)
```zsh
make test                         # Full suite
pytest tests/test_phase05_missing.py -v
```

### 🧰 Quick Debug (zsh)
```zsh
grep -l '"status": "STOP"' artifacts/*/stage_*/gate.json || echo "No STOP"
for f in artifacts/*/stage_*/logs.jsonl; do echo "$f: $(grep -c WARN $f 2>/dev/null || echo 0)"; done
```

### 📌 Common Edits
- SLA hours: `contracts/sla/sla_defaults.yml`
- Critical columns: `contracts/kpis/critical_columns.yml`
- Imputation policy: `contracts/impute/policy_relaxed.yml`

### 📄 Use Claude Code
- Ask/Refine selection in VS Code, review diffs, apply.
- CLI one‑liner:
```zsh
claude -p "اقترح تحسينات قصيرة لهذا المشروع" --output-format text
```

### 🔚 Final Reminder
Test → Run → Check gates. Keep secrets in env. Use `CLAUDE_QUICK.md` as the primary context.
