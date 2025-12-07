I've generated a comprehensive CLAUDE.md file for the Mind-Q V4.1 repository. The document includes:

## What's Included

**1. Quick Start** - 3-command setup for macOS zsh

**2. Build & Run**
- Makefile targets (venv, install, fmt, lint, test, smoke, docs)
- Shell scripts (run_pipeline.sh, run_app.sh, start_*.sh)
- CLI runner commands
- Port information for backend (9000) and frontend (3000/5000)

**3. Python Environment**
- pyproject.toml overview (Python 3.11+)
- Requirements breakdown (requirements.txt, requirements-dev.txt, requirements-adapters.txt)
- Virtual environment setup and management

**4. Testing & Validation**
- pytest commands (unit, integration, smoke tests)
- Code quality tools (black, ruff, mypy, bandit, safety)
- Pre-commit hooks setup
- Documentation validation

**5. Documentation Map**
- Getting started docs (00_START_HERE.md, README.md, QUICK_START.md)
- Core docs hierarchy under docs/
- PHASES_DETAILED_GUIDE.md as the master blueprint
- Stage-specific, advanced features, frontend/BI, and technical docs

**6. Stage 08 Context Files**
- Explanation of stage_08_* files and their purpose
- Categories: run modes, RAG/context, advanced analytics, correlation, debug
- Usage examples and best practices

**7. Best Practices**
- Diff management with conventional commits
- Structured logging with structlog
- Code organization and import order
- **Documentation sync (CRITICAL: AI_RULES.md compliance)**
- Testing pyramid strategy
- Performance tips (Polars vs Pandas)

**8. Credentials & Security**
- .env setup and environment variables
- LLM API keys (OpenAI, Anthropic, Google)
- Pipeline configuration (business_first vs strict_lab modes)
- Security best practices (never commit secrets, PII masking)
- macOS zsh persistent environment setup

**9. Quick Reference Card** - Essential commands, key directories, help resources

The document is formatted in clear Markdown with short, executable commands optimized for macOS zsh as requested. It emphasizes the AI_RULES.md requirement to keep PHASES_DETAILED_GUIDE.md synced with code changes.
