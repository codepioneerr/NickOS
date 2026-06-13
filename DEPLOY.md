# NickOS — Deploy Guide

Two services, one repo:
- **API** (FastAPI/Python) → Railway
- **Dashboard** (React/Vite) → Vercel

---

## 1. Push to GitHub

```bash
cd /path/to/NickOS
git add -A
git commit -m "feat: weekly, insights, focus timer, obsidian search, habits API"
git push origin main
```

---

## 2. Deploy API → Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → select `NickOS`
2. Railway auto-detects `nixpacks.toml` — no config needed
3. Set environment variables in **Variables** tab (copy from your `.env`):

| Key | Value |
|-----|-------|
| `ANTHROPIC_API_KEY` | your key |
| `ANTHROPIC_HAIKU_MODEL` | `claude-haiku-4-5-20251001` |
| `TELEGRAM_BOT_TOKEN` | your bot token |
| `TELEGRAM_ALLOWED_USER_ID` | your Telegram user ID |
| `NICKOS_API_KEY` | pick a secret string (e.g. `openssl rand -hex 24`) |
| `GMAIL_CREDENTIALS_PATH` | `/app/gmail/credentials.json` |
| `GOOGLE_CALENDAR_ID` | your calendar ID |
| `GMAIL_ACCOUNT_2_EMAIL` | nickdagod3@gmail.com |
| `GMAIL_ACCOUNT_2_TOKEN` | `/app/gmail/tokens/nickdagod3.json` |
| `GMAIL_ACCOUNT_3_EMAIL` | nblack10@fordham.edu |
| `GMAIL_ACCOUNT_3_TOKEN` | `/app/gmail/tokens/nblack10.json` |
| `OBSIDIAN_VAULT_PATH` | leave blank for now (set when you have a vault) |
| `TIMEZONE` | `America/New_York` |
| `PORT` | Railway sets this automatically |

4. Start command (already in `nixpacks.toml`):
   ```
   python db/schema.py && uvicorn api.main:app --host 0.0.0.0 --port $PORT
   ```
5. After deploy, note your Railway URL: `https://nickos-api-xxxx.railway.app`
6. Hit `https://nickos-api-xxxx.railway.app/health` — should return `{"status":"ok"}`

---

## 3. Deploy Dashboard → Vercel

```bash
cd nickos-dashboard
# Create .env.local (not committed)
echo "VITE_API_URL=https://nickos-api-xxxx.railway.app" > .env.local
echo "VITE_API_KEY=<same NICKOS_API_KEY from Railway>" >> .env.local

npm run build   # verify it builds locally first
```

Then in Vercel:
1. **New Project** → import `NickOS` repo
2. Set **Root Directory** to `nickos-dashboard`
3. Add environment variables:
   - `VITE_API_URL` = your Railway API URL
   - `VITE_API_KEY` = your NICKOS_API_KEY
4. Deploy → get URL like `https://nickos-dashboard.vercel.app`

Add that URL to CORS in `api/main.py` (already has `*.vercel.app` wildcard — no change needed).

---

## 4. Deploy Telegram Bot → Railway (second service)

In the same Railway project, add a **new service** from the same repo:
- Start command: `python -m bot.main`
- Same env vars as the API service

---

## 5. Smoke test

```bash
API=https://nickos-api-xxxx.railway.app
KEY=your_nickos_api_key

curl -H "X-API-Key: $KEY" $API/api/today | python3 -m json.tool | head -20
curl -H "X-API-Key: $KEY" $API/api/weekly | python3 -m json.tool | head -20
curl -H "X-API-Key: $KEY" $API/api/insights | python3 -m json.tool
curl -H "X-API-Key: $KEY" "$API/api/obsidian/search?q=test" | python3 -m json.tool
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"hours":8}' $API/api/log/sleep
```

---

## 6. New env vars added this sprint

These need to be set in Railway if you want the new features:

| Key | Purpose | Default |
|-----|---------|---------|
| `OBSIDIAN_VAULT_PATH` | Path to Obsidian vault | `~/Obsidian` (graceful empty if missing) |

No other new env vars — everything else uses existing keys.

---

## What was built this sprint

| Feature | Backend | Frontend |
|---------|---------|---------|
| `/api/weekly` — real grades, 30d sleep trend, meal %, workout freq | ✅ | ✅ Weekly page live data |
| `/api/insights` — Claude Haiku daily insights, 1h cache | ✅ | ✅ InsightsPanel on Today |
| `/api/obsidian/search` — vault search with `obsidian://` links | ✅ | ✅ ObsidianSearch on Today |
| `/api/log/focus` — log pomodoro sessions, Telegram notify | ✅ | ✅ FocusTimer component |
| `/api/log/habit` — persist habit toggles to SQLite | ✅ | ✅ HabitsWidget now real |
| DB schema: `focus_logs`, `habit_logs` tables | ✅ | — |
| Weekly page: sleep trend chart, meal consistency, workout freq, goals burndown | — | ✅ |
