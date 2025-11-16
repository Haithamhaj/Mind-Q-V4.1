#!/bin/bash
# Frontend Startup Script for Mind-Q V4.1

# Navigate to project root
cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎨 Starting Mind-Q Frontend..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 Project Root: ${PROJECT_ROOT}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Navigate to frontend directory and start
cd frontend
npm run dev
