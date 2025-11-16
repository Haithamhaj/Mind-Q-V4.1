#!/bin/bash
# Backend Startup Script for Mind-Q V4.1
# This script ensures PYTHONPATH is set correctly before starting the backend

# Navigate to project root
cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

# Set PYTHONPATH to include project root and backend directory
export PYTHONPATH="${PROJECT_ROOT}:${PROJECT_ROOT}/backend:${PYTHONPATH}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Starting Mind-Q Backend..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 Project Root: ${PROJECT_ROOT}"
echo "🐍 PYTHONPATH: ${PYTHONPATH}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Start backend using direct Python import (most reliable method)
python3 -c "
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'backend')
from backend.src.app.services.pipeline_api.app import app
import uvicorn
uvicorn.run(app, host='0.0.0.0', port=9000)
"
