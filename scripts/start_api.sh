#!/bin/bash
# Run NickOS FastAPI backend locally
# Usage: bash scripts/start_api.sh

cd "$(dirname "$0")/.."
echo "Starting NickOS API on http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo ""
uvicorn api.main:app --reload --port 8000 --host 0.0.0.0
