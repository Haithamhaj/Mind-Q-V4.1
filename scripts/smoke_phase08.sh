#!/usr/bin/env bash
set -euo pipefail

RUN_ID=${1:-sample_run}
ARTIFACTS_ROOT=${ARTIFACTS_ROOT:-artifacts}

python scripts/run_phase08_insights.py --run-id "${RUN_ID}" --artifacts-root "${ARTIFACTS_ROOT}"
