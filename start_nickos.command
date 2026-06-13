#!/bin/bash
# NickOS startup — double-click this file from Finder to launch everything.
# (If "permission denied", run once in Terminal: chmod +x start_nickos.command)

NICKOS_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Starting NickOS from: $NICKOS_DIR"
echo ""

# ── Initialize SQLite DB from today's markdown log ────────────────────────────
echo "▶ Initializing database..."
cd "$NICKOS_DIR"
python3 db/schema.py 2>&1 | tail -5

# ── Start FastAPI backend in background ───────────────────────────────────────
echo ""
echo "▶ Starting FastAPI backend on :8000..."
cd "$NICKOS_DIR"
python3 -m uvicorn api.main:app --reload --port 8000 --host 127.0.0.1 &
API_PID=$!
echo "  API PID: $API_PID"

# ── Wait for API to come up ───────────────────────────────────────────────────
echo "  Waiting for API..."
for i in {1..15}; do
    sleep 1
    if curl -s http://localhost:8000/ > /dev/null 2>&1; then
        echo "  ✓ API ready"
        break
    fi
    echo -n "."
done

# ── Test key endpoint ─────────────────────────────────────────────────────────
echo ""
echo "▶ Testing /api/today..."
curl -s http://localhost:8000/api/today | python3 -m json.tool 2>/dev/null | head -40

# ── Start Vite frontend ───────────────────────────────────────────────────────
echo ""
echo "▶ Starting Vite dashboard on :5173..."
cd "$NICKOS_DIR/nickos-dashboard"
npm run dev &
VITE_PID=$!
echo "  Vite PID: $VITE_PID"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  NickOS running:"
echo "  Dashboard → http://localhost:5173"
echo "  API docs  → http://localhost:8000/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Press Ctrl+C to stop both servers."
echo ""

# ── Keep terminal open — stop both on Ctrl+C ─────────────────────────────────
trap "echo 'Stopping...'; kill $API_PID $VITE_PID 2>/dev/null; exit" INT TERM
wait
