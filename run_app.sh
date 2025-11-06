#!/bin/bash

echo "🚀 Starting Mind-Q Application..."

# Start Backend in background on port 9000
echo "🔧 Starting Backend API on port 9000..."
python start_server.py > backend.log 2>&1 &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"

# Wait for backend
sleep 3

# Start Frontend on port 5000
echo "🎨 Starting Frontend on port 5000..."
cd frontend

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install --legacy-peer-deps
fi

# Run Next.js on port 5000
PORT=5000 npm run dev
