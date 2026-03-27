FROM python:3.11-slim

# ── System deps: Node.js for frontend build ───────────────────────────────────
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# ── Frontend build ────────────────────────────────────────────────────────────
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm ci

COPY frontend/ ./frontend/
RUN cd frontend && VITE_API_URL="" npm run build

# ── Backend source ────────────────────────────────────────────────────────────
COPY backend/ ./backend/

# ── Pre-generate demo data (baked into image — fast startup) ──────────────────
RUN cd backend && python3 -c "from data_generator import generate_all; generate_all('../demo_data')"

# ── Run ───────────────────────────────────────────────────────────────────────
EXPOSE 8080
CMD sh -c "cd /app/backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"
