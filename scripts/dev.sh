#!/usr/bin/env bash
# Run the backend (FastAPI) and frontend (Vite) together for local development.
# Usage: ./scripts/dev.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# --- backend ---
if [ ! -d "$ROOT/backend/.venv" ]; then
  echo "Creating backend venv..."
  python3 -m venv "$ROOT/backend/.venv"
  "$ROOT/backend/.venv/bin/pip" install -r "$ROOT/backend/requirements.txt"
fi

# Build the reference dataset if missing.
if [ ! -f "$ROOT/data/processed/shiller_returns.parquet" ]; then
  echo "Building shiller_returns dataset..."
  (cd "$ROOT/backend" && .venv/bin/python -m app.cli acquire shiller_returns \
     && .venv/bin/python -m app.cli compile shiller_returns)
fi

echo "Starting FastAPI on :8000 ..."
(cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --reload --port 8000) &
BACK=$!

# --- frontend ---
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "Installing frontend deps..."
  (cd "$ROOT/frontend" && npm install)
fi
echo "Starting Vite on :5173 ..."
(cd "$ROOT/frontend" && npm run dev)

kill $BACK 2>/dev/null || true
