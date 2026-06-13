#!/bin/bash
# NickOS — scaffold_nickos.sh
# Run: chmod +x scaffold_nickos.sh && ./scaffold_nickos.sh
# Creates the full NickOS project tree in ~/nickos

set -e

ROOT="/Users/nick/Documents/Agentic Workflows/NickOS"
echo "🧠 Scaffolding NickOS at $ROOT ..."

# ── Memory vault ─────────────────────────────────────────────────────────────
mkdir -p "$ROOT/memory/daily_logs"
mkdir -p "$ROOT/memory/weekly_reflections"

# ── Telegram bot ─────────────────────────────────────────────────────────────
mkdir -p "$ROOT/bot/handlers"
touch    "$ROOT/bot/__init__.py"
touch    "$ROOT/bot/main.py"
touch    "$ROOT/bot/handlers/__init__.py"
touch    "$ROOT/bot/handlers/morning.py"
touch    "$ROOT/bot/handlers/health.py"
touch    "$ROOT/bot/handlers/focus.py"
touch    "$ROOT/bot/handlers/goals.py"
touch    "$ROOT/bot/utils.py"

# ── Gmail triage ─────────────────────────────────────────────────────────────
mkdir -p "$ROOT/gmail"
touch    "$ROOT/gmail/__init__.py"
touch    "$ROOT/gmail/classifier.py"
touch    "$ROOT/gmail/fetcher.py"
touch    "$ROOT/gmail/labels.py"

# ── Heartbeat / cron ─────────────────────────────────────────────────────────
mkdir -p "$ROOT/heartbeat"
touch    "$ROOT/heartbeat/__init__.py"
touch    "$ROOT/heartbeat/scheduler.py"
touch    "$ROOT/heartbeat/nudges.py"

# ── Health layer ─────────────────────────────────────────────────────────────
mkdir -p "$ROOT/health"
touch    "$ROOT/health/__init__.py"
touch    "$ROOT/health/tracker.py"
touch    "$ROOT/health/streaks.py"
touch    "$ROOT/health/score.py"

# ── Goals layer ──────────────────────────────────────────────────────────────
mkdir -p "$ROOT/goals"
touch    "$ROOT/goals/__init__.py"
touch    "$ROOT/goals/manager.py"

# ── Fordham intelligence ─────────────────────────────────────────────────────
mkdir -p "$ROOT/fordham"
touch    "$ROOT/fordham/__init__.py"
touch    "$ROOT/fordham/calendar_aware.py"
touch    "$ROOT/fordham/scholarship_scanner.py"
touch    "$ROOT/fordham/gpa_tracker.py"

# ── FastAPI backend ───────────────────────────────────────────────────────────
mkdir -p "$ROOT/api/routers"
touch    "$ROOT/api/__init__.py"
touch    "$ROOT/api/main.py"
touch    "$ROOT/api/routers/__init__.py"
touch    "$ROOT/api/routers/health.py"
touch    "$ROOT/api/routers/goals.py"
touch    "$ROOT/api/routers/gmail.py"
touch    "$ROOT/api/routers/memory.py"
touch    "$ROOT/api/db.py"
touch    "$ROOT/api/models.py"

# ── React dashboard ───────────────────────────────────────────────────────────
mkdir -p "$ROOT/dashboard/src/components"
mkdir -p "$ROOT/dashboard/src/pages"
mkdir -p "$ROOT/dashboard/public"
touch    "$ROOT/dashboard/src/App.jsx"
touch    "$ROOT/dashboard/src/index.jsx"
touch    "$ROOT/dashboard/src/components/DailyBrief.jsx"
touch    "$ROOT/dashboard/src/components/HealthPanel.jsx"
touch    "$ROOT/dashboard/src/components/GoalsPanel.jsx"
touch    "$ROOT/dashboard/src/components/InboxTriage.jsx"
touch    "$ROOT/dashboard/src/components/WeeklyReflection.jsx"
touch    "$ROOT/dashboard/package.json"
touch    "$ROOT/dashboard/tailwind.config.js"
touch    "$ROOT/dashboard/vite.config.js"

# ── Config / infra ────────────────────────────────────────────────────────────
mkdir -p "$ROOT/config"
touch    "$ROOT/config/schedule.yaml"
touch    "$ROOT/config/email_rules.yaml"
touch    "$ROOT/config/fordham_dates.yaml"

# ── Scripts ───────────────────────────────────────────────────────────────────
mkdir -p "$ROOT/scripts"
touch    "$ROOT/scripts/setup_gmail_oauth.py"
touch    "$ROOT/scripts/test_telegram.py"
touch    "$ROOT/scripts/seed_db.py"

# ── Data / storage ────────────────────────────────────────────────────────────
mkdir -p "$ROOT/data"
touch    "$ROOT/data/.gitkeep"

# ── Root files ────────────────────────────────────────────────────────────────
touch "$ROOT/.env"
touch "$ROOT/.env.example"
touch "$ROOT/requirements.txt"
touch "$ROOT/README.md"

# ── Memory files ─────────────────────────────────────────────────────────────
touch "$ROOT/memory/SOUL.md"
touch "$ROOT/memory/USER.md"
touch "$ROOT/memory/MEMORY.md"

# ── .gitignore ────────────────────────────────────────────────────────────────
cat > "$ROOT/.gitignore" << 'EOF'
# Environment
.env
*.env

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
dist/
build/

# Node
node_modules/
.next/
dist/
.DS_Store

# SQLite
data/*.db
data/*.sqlite

# Gmail credentials
token.json
credentials.json
gmail/token.json

# Logs
*.log
logs/
EOF

# ── requirements.txt ──────────────────────────────────────────────────────────
cat > "$ROOT/requirements.txt" << 'EOF'
# Core
python-telegram-bot==21.3
anthropic>=0.28.0
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
python-dotenv>=1.0.0

# Gmail
google-api-python-client>=2.130.0
google-auth-httplib2>=0.2.0
google-auth-oauthlib>=1.2.0

# Scheduling
apscheduler>=3.10.4

# DB / data
sqlalchemy>=2.0.30
aiosqlite>=0.20.0

# Utilities
httpx>=0.27.0
pyyaml>=6.0.1
pytz>=2024.1
rich>=13.7.0
EOF

echo ""
echo "✅  NickOS scaffolded at $ROOT"
echo ""
echo "Next steps:"
echo "  1. cd $ROOT"
echo "  2. cp .env.example .env  (fill in your keys)"
echo "  3. python -m venv .venv && source .venv/bin/activate"
echo "  4. pip install -r requirements.txt"
echo "  5. python scripts/test_telegram.py"
