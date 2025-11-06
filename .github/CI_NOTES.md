# CI/CD Configuration Notes

## Current CI Setup

### ✅ CI Workflow Status

The GitHub Actions CI workflow has been configured to run **only on the `main` branch** to avoid unnecessary workflow runs during development on feature branches.

### 📋 Workflow Configuration

**File**: `.github/workflows/ci.yml`

**Triggers**:
- Push to `main` branch only
- Pull requests to `main` branch only

**Jobs**:
1. **build**: Runs on both Ubuntu and Windows
   - Python 3.11 setup
   - Install dependencies
   - Run ruff (linter)
   - Run mypy (type checker)
   - Run pytest (unit tests)
   - Run smoke tests

2. **smoke-main**: Runs only on `main` branch pushes
   - Strict smoke test validation
   - Upload artifacts

### 🔧 Why CI is Limited to Main Branch

The `port/update-2025-10-11` branch is a development/integration branch with:
- Frequent commits and updates
- Large file additions (frontend)
- Configuration changes for deployment

Running CI on every push to this branch would:
- ❌ Consume unnecessary GitHub Actions minutes
- ❌ Create noise with failing builds during active development
- ❌ Slow down development workflow

### 🚀 When CI Will Run Again

CI will automatically run when:
1. **Pull Request is created** from `port/update-2025-10-11` to `main`
2. **Code is merged** into `main` branch
3. **Direct push** to `main` branch

### 🔄 Re-enabling CI for This Branch

If you need to run CI on this branch, modify `.github/workflows/ci.yml`:

```yaml
on:
  push:
    branches:
      - main
      - port/update-2025-10-11  # Add this line
  pull_request:
    branches:
      - main
```

Or create a separate workflow file for development branches.

### 📊 Current Branch Status

| Branch | CI Enabled | Purpose |
|--------|-----------|---------|
| `main` | ✅ Yes | Production/stable code |
| `port/update-2025-10-11` | ⏸️ Paused | Active development |

### 🛠️ Manual Testing

For this branch, prefer manual testing:

```bash
# Run linter
ruff check .

# Run type checker
mypy --ignore-missing-imports .

# Run tests
pytest -q

# Run smoke test
python -m cli.runner flow --run-id smoke-test
```

---

**Last Updated**: November 4, 2025  
**Reason**: Optimize CI workflow for development branch
