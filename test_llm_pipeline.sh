#!/usr/bin/env bash
set -e

RUN_ID="llm-complete-test"
BACKEND_URL="http://localhost:9000"
DATA_FILE="data/Fastcoo_LM_Data.csv"

echo "🧪 Testing Mind-Q Pipeline with LLM Enabled"
echo "=========================================="
echo "Run ID: $RUN_ID"
echo "Dataset: $DATA_FILE (50,000 rows)"
echo ""

# Function to call phase endpoint
call_phase() {
    local phase_path=$1
    local phase_name=$2
    local payload=${3:-'{}'}
    
    echo "▶ Running $phase_name..."
    response=$(curl -s -X POST "$BACKEND_URL/v1/runs/$RUN_ID/phases/$phase_path" \
        -H "Content-Type: application/json" \
        -d "$payload")
    
    status=$(echo "$response" | python -c "import json,sys; print(json.load(sys.stdin).get('status', 'UNKNOWN'))" 2>/dev/null || echo "ERROR")
    echo "  Status: $status"
    
    if [ "$status" = "ERROR" ]; then
        echo "  Response: $response"
    fi
}

# Phase 01: Ingestion
call_phase "01/ingestion" "Phase 01 - Ingestion" '{"data_files": ["'"$DATA_FILE"'"]}'

# Phases 02-07
call_phase "02/quality" "Phase 02 - Quality"
call_phase "03/schema" "Phase 03 - Schema"
call_phase "03/textops" "Phase 03.5 - TextOps (with LLM)"
call_phase "04/profile" "Phase 04 - Profiling"
call_phase "05/missing" "Phase 05 - Missing Values"
call_phase "06/standardize" "Phase 06 - Standardization"
call_phase "07/readiness" "Phase 07 - Readiness"

# LLM-specific phases
call_phase "07/llm-summary" "Phase 07.6 - LLM Summary (OpenAI)"
call_phase "07/business-correlations" "Phase 07.7 - Business Correlations"

# Phase 08-10
call_phase "08/insights" "Phase 08 - Insights (with LLM)"
call_phase "09/business-validation" "Phase 09 - Business Validation (with LLM)"
call_phase "10/bi" "Phase 10 - BI Delivery (with LLM)"

echo ""
echo "✅ Pipeline test completed!"
echo "Checking artifacts..."
ls -lh artifacts/$RUN_ID/ | head -20
