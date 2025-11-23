#!/bin/bash
set -e

# Function to cleanup background processes on exit
cleanup() {
    echo "Stopping services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

PROJECT_ROOT=$(pwd)
export PYTHONPATH=$PROJECT_ROOT

echo "🚀 Starting Mind-Q Dashboard..."

# 1. Start Backend
echo "🔹 Starting Backend API (Port 9000)..."
# Check if port 9000 is already in use
if lsof -i :9000 >/dev/null; then
    echo "⚠️  Port 9000 is already in use. Attempting to kill..."
    lsof -ti:9000 | xargs kill -9 2>/dev/null || true
fi

python3 -m uvicorn backend.src.app.services.pipeline_api.app:app --host 0.0.0.0 --port 9000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID). Logs: backend.log"

# 2. Setup & Start Frontend
echo "🔹 Setting up Frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
else
    echo "✅ Dependencies found."
fi

echo "🔹 Starting Frontend Dev Server (Port 3000)..."
# Check if port 3000 is already in use
if lsof -i :3000 >/dev/null; then
    echo "⚠️  Port 3000 is already in use. Attempting to kill..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
fi

npm run dev
