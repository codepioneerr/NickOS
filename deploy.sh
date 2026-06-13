#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  deploy.sh — NickOS deployment helper
#
#  Run from the NickOS root directory:
#    chmod +x deploy.sh && ./deploy.sh
#
#  This script:
#    1. Base64-encodes all local token files
#    2. Prints every env var you need to set in Railway
#    3. Prints the exact Railway + Vercel CLI commands to run
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail
cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

header()  { echo -e "\n${BOLD}${CYAN}▶ $*${RESET}"; }
ok()      { echo -e "  ${GREEN}✓${RESET} $*"; }
warn()    { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
missing() { echo -e "  ${RED}✗${RESET} $*"; }

# ── Source .env ───────────────────────────────────────────────────────────────
if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║       NickOS Deploy Config Generator     ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"

# ── 1. Encode token files ─────────────────────────────────────────────────────
header "Encoding local token files to base64"

declare -A TOKEN_VARS=(
  ["gmail/credentials.json"]="GMAIL_CREDENTIALS_B64"
  ["gmail/tokens/account1_token.json"]="GMAIL_TOKEN_1_B64"
  ["gmail/tokens/account2_token.json"]="GMAIL_TOKEN_2_B64"
  ["gmail/tokens/account3_token.json"]="GMAIL_TOKEN_3_B64"
  ["gmail/tokens/calendar_token.json"]="CALENDAR_TOKEN_B64"
)

declare -A TOKEN_VALUES=()
for file in "${!TOKEN_VARS[@]}"; do
  var="${TOKEN_VARS[$file]}"
  if [ -f "$file" ]; then
    TOKEN_VALUES[$var]=$(base64 < "$file" | tr -d '\n')
    ok "$file → \$$var"
  else
    warn "$file not found — $var will be empty"
    TOKEN_VALUES[$var]=""
  fi
done

# Optional: encode MEMORY.md so Railway can restore it on first deploy
MEMORY_B64=""
if [ -f "memory/MEMORY.md" ]; then
  MEMORY_B64=$(base64 < "memory/MEMORY.md" | tr -d '\n')
  ok "memory/MEMORY.md → \$MEMORY_MD_B64"
fi

# ── 2. Print Railway env vars ─────────────────────────────────────────────────
header "Railway environment variables"
echo -e "  Copy-paste these into Railway Dashboard → Service → Variables\n"
echo -e "  ${YELLOW}(or use the Railway CLI commands in section 4 below)${RESET}\n"

cat <<ENVBLOCK
# ── Core credentials ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-REPLACE_ME}
TELEGRAM_ALLOWED_USER_ID=${TELEGRAM_ALLOWED_USER_ID:-REPLACE_ME}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-REPLACE_ME}
NICKOS_API_KEY=${NICKOS_API_KEY:-REPLACE_ME}

# ── Storage — add a Railway volume mounted at /data ───────────────────────────
DATA_DIR=/data
GOOGLE_CALENDAR_ID=primary

# ── Gmail token files (base64-encoded) ────────────────────────────────────────
GMAIL_CREDENTIALS_B64=${TOKEN_VALUES[GMAIL_CREDENTIALS_B64]:-}
GMAIL_TOKEN_1_B64=${TOKEN_VALUES[GMAIL_TOKEN_1_B64]:-}
GMAIL_TOKEN_2_B64=${TOKEN_VALUES[GMAIL_TOKEN_2_B64]:-}
GMAIL_TOKEN_3_B64=${TOKEN_VALUES[GMAIL_TOKEN_3_B64]:-}
CALENDAR_TOKEN_B64=${TOKEN_VALUES[CALENDAR_TOKEN_B64]:-}

# ── MEMORY.md — paste your current MEMORY.md (base64) to restore it ──────────
MEMORY_MD_B64=${MEMORY_B64:-}
ENVBLOCK

# ── 3. Print Vercel env vars ──────────────────────────────────────────────────
header "Vercel environment variables (set after you get the Railway API URL)"

cat <<VERCELENV
# In Vercel Dashboard → Project → Settings → Environment Variables:
VITE_API_URL=https://YOUR-nickos-api.railway.app
VITE_API_KEY=${NICKOS_API_KEY:-REPLACE_ME}
VERCELENV

# ── 4. Deployment commands ────────────────────────────────────────────────────
header "Step-by-step deployment commands"

cat <<'COMMANDS'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PREREQUISITES (one-time)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # Install CLIs if needed
  npm install -g @railway/cli vercel

  # Authenticate
  railway login
  vercel login

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 1 — Push code to GitHub
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # If repo doesn't exist yet:
  gh repo create nickos --private --source=. --push

  # If it does:
  git add -A
  git commit -m "chore: production deploy config"
  git push

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 2 — Railway: Create project + services
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # Create Railway project
  railway init --name nickos

  # === SERVICE 1: nickos-api (FastAPI) ===
  # In Railway Dashboard:
  #   New Service → GitHub Repo → select your repo
  #   Name: nickos-api
  #   Start command: python db/schema.py && uvicorn api.main:app --host 0.0.0.0 --port $PORT

  # Add a persistent volume:
  #   Service Settings → Volumes → Add Volume
  #   Mount Path: /data
  #   (This stores SQLite DB + MEMORY.md + daily logs)

  # === SERVICE 2: nickos-bot (Telegram) ===
  # In Railway Dashboard:
  #   New Service → GitHub Repo → same repo
  #   Name: nickos-bot
  #   Start command: python -m bot.main
  #   (No port needed — this is a worker, not a web service)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 3 — Set env vars in Railway (use values from above)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # Via Railway CLI (run from NickOS root after railway link):
  railway variables set \
    TELEGRAM_BOT_TOKEN="..." \
    TELEGRAM_ALLOWED_USER_ID="..." \
    ANTHROPIC_API_KEY="..." \
    NICKOS_API_KEY="..." \
    DATA_DIR=/data \
    GOOGLE_CALENDAR_ID=primary \
    GMAIL_CREDENTIALS_B64="..." \
    GMAIL_TOKEN_1_B64="..." \
    GMAIL_TOKEN_2_B64="..." \
    GMAIL_TOKEN_3_B64="..." \
    CALENDAR_TOKEN_B64="..." \
    MEMORY_MD_B64="..."

  # NOTE: Set these on BOTH services (nickos-api and nickos-bot)
  # The Telegram vars only matter for nickos-bot, but having them
  # on both services is harmless and simpler to manage.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 4 — Get the Railway API URL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # In Railway Dashboard → nickos-api service → Settings → Domains
  # Generate a domain — it'll look like:
  #   nickos-api-production-xxxx.up.railway.app
  # Copy it — you need it for Vercel in step 5.

  # Test it:
  curl https://YOUR-nickos-api.railway.app/health

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 5 — Vercel: Deploy the React dashboard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  cd nickos-dashboard

  # First deploy (interactive — sets Root Directory to nickos-dashboard)
  vercel

  # When prompted:
  #   Set up and deploy? Y
  #   Which scope? (your account)
  #   Link to existing project? N
  #   Project name: nickos-dashboard
  #   In which directory is your code? ./  (you're already in nickos-dashboard/)
  #   Detected Vite — override? N

  # Set env vars on Vercel:
  vercel env add VITE_API_URL production
  # → paste: https://YOUR-nickos-api.railway.app

  vercel env add VITE_API_KEY production
  # → paste your NICKOS_API_KEY value

  # Re-deploy with env vars:
  vercel --prod

  # Your dashboard is now live at:
  #   https://nickos-dashboard.vercel.app  (or your custom Vercel URL)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 6 — Add to iPhone home screen (PWA)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Open Safari on iPhone
  2. Navigate to https://nickos-dashboard.vercel.app
  3. Tap the Share button (box with arrow)
  4. Scroll down → "Add to Home Screen"
  5. Name it "NickOS" → Add
  6. App icon appears on home screen, launches full-screen

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 7 — Verify everything works
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # API health check
  curl https://YOUR-nickos-api.railway.app/health

  # Authenticated endpoint (replace KEY with your NICKOS_API_KEY)
  curl -H "X-API-Key: KEY" https://YOUR-nickos-api.railway.app/api/today

  # Bot: send /morning in Telegram — should get a live response
  # Dashboard: open the Vercel URL — should show real health data

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Token errors:
    → Run deploy.sh again to regenerate base64 values
    → Make sure you set them on BOTH Railway services

  MEMORY.md missing (goals show empty):
    → The MEMORY_MD_B64 var restores it on first boot
    → Or: railway run --service nickos-api \
           sh -c 'mkdir -p /data/memory && cat > /data/memory/MEMORY.md' < memory/MEMORY.md

  SQLite "disk I/O error":
    → Make sure the /data volume is mounted on the service
    → Check Railway Dashboard → Service → Volumes

  Gmail auth expired (token refresh fails):
    → Re-run OAuth locally: python scripts/setup_gmail_oauth.py --account N
    → Re-run deploy.sh to generate new base64 values
    → Update Railway env vars

COMMANDS

echo ""
echo -e "${GREEN}${BOLD}Done! Copy the env vars above and follow the steps.${RESET}"
echo ""
