#!/bin/bash
# Pipeline Runner Script for Mind-Q V4.1
# Usage: ./run_pipeline.sh [run-id] [dataset-path]

# Navigate to project root
cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

# Set PYTHONPATH to include project root
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# Default values
RUN_ID="${1:-test-run}"
DATASET="${2:-data/sample.csv}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Running Mind-Q Pipeline..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 Project Root: ${PROJECT_ROOT}"
echo "🆔 Run ID: ${RUN_ID}"
echo "📊 Dataset: ${DATASET}"
echo "🐍 PYTHONPATH: ${PYTHONPATH}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run the pipeline
python3 cli/runner.py flow --run-id "${RUN_ID}" --dataset "${DATASET}"
