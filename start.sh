#!/bin/bash

echo "🚀 Starting Mind-Q Application..."
echo "=================================="

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Start Backend in background
echo -e "${BLUE}🔧 Starting Backend (FastAPI)...${NC}"
python start_server.py > backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"

# Wait for backend to be ready
echo -e "${YELLOW}⏳ Waiting for backend to be ready...${NC}"
sleep 8

# Check if backend is running
if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✓ Backend is ready!${NC}"
else
    echo -e "${YELLOW}⚠ Backend might need more time to start${NC}"
fi

# Start Frontend
echo -e "${BLUE}🎨 Starting Frontend (Next.js)...${NC}"
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}📦 Installing frontend dependencies...${NC}"
    npm install
fi

npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"

cd ..

echo ""
echo -e "${GREEN}=================================="
echo -e "✅ Application started successfully!"
echo -e "==================================${NC}"
echo ""
echo -e "${BLUE}📊 Backend API:${NC}       http://localhost:8000"
echo -e "${BLUE}📚 API Docs:${NC}          http://localhost:8000/docs"
echo -e "${BLUE}🎨 Frontend:${NC}          http://localhost:3000"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Stopping services...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}✓ All services stopped${NC}"
    exit 0
}

# Trap Ctrl+C
trap cleanup INT TERM

# Keep script running
wait $BACKEND_PID $FRONTEND_PID
