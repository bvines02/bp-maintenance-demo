#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== BP Maintenance Demo ==="
echo ""

# Load .env if present
if [ -f "$DIR/backend/.env" ]; then
  export $(grep -v '^#' "$DIR/backend/.env" | xargs)
fi

echo "==> Building frontend..."
cd "$DIR/frontend"
VITE_API_URL="" npm run build

echo ""
echo "==> Starting server at http://localhost:8000"
echo "    Press Ctrl+C to stop"
echo ""

cd "$DIR/backend"
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
