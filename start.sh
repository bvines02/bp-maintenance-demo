#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== BP Maintenance Demo ==="
echo ""

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ] && [ ! -f "$ROOT/backend/.env" ]; then
  echo "⚠️  ANTHROPIC_API_KEY not set."
  echo "   Create backend/.env with: ANTHROPIC_API_KEY=your_key_here"
  echo "   (The app will still work without it, but the Analyst Chat will be disabled)"
  echo ""
fi

# Load .env if present
if [ -f "$ROOT/backend/.env" ]; then
  export $(grep -v '^#' "$ROOT/backend/.env" | xargs)
fi

# Start backend
echo "Starting backend..."
cd "$ROOT/backend"
source venv/bin/activate
python -c "from dotenv import load_dotenv; load_dotenv()" 2>/dev/null || true
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "  Backend running at http://localhost:8000"

# Start frontend
echo "Starting frontend..."
cd "$ROOT/frontend"
npm run dev -- --port 5173 &
FRONTEND_PID=$!
echo "  Frontend running at http://localhost:5173"

echo ""
echo "✅ App ready → http://localhost:5173"
echo "   Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" INT TERM
wait
