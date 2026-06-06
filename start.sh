#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== BP Maintenance Demo ==="
echo ""

# Load .env if present
if [ -f "$DIR/backend/.env" ]; then
  export $(grep -v '^#' "$DIR/backend/.env" | xargs)
fi

# ── Frontend ──────────────────────────────────────────────────────────────────
echo "==> Installing frontend dependencies..."
cd "$DIR/frontend"
npm install --silent

echo "==> Building frontend..."
VITE_API_URL="" npm run build

# ── Backend ───────────────────────────────────────────────────────────────────
cd "$DIR/backend"

if [ ! -d "venv" ]; then
  echo ""
  echo "==> Creating Python virtual environment..."
  python3 -m venv venv
fi

echo ""
echo "==> Installing backend dependencies..."
source venv/bin/activate
pip install -r requirements.txt -q

echo ""
echo "==> Starting server at http://localhost:8000"
echo "    Press Ctrl+C to stop"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000
