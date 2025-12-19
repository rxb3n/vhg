#!/bin/bash

# Start both frontend and backend servers

echo "Starting Viral Hook Generator..."

# Start backend in background
echo "Starting backend server..."
cd backend
python -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend
echo "Starting frontend server..."
cd ..
npm run dev &
FRONTEND_PID=$!

echo "Backend running on http://localhost:8000 (PID: $BACKEND_PID)"
echo "Frontend running on http://localhost:3000 (PID: $FRONTEND_PID)"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for user interrupt
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait

