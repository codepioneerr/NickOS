# NickOS Dashboard — Deployment Guide

## 1. Install dependencies
```bash
cd nickos-dashboard
npm install
```

## 2. Local dev
```bash
cp .env.example .env.local
# Edit .env.local: set VITE_API_URL=http://localhost:8000 for local backend
npm run dev
# → http://localhost:5173
```

## 3. Deploy to Vercel (free)

### Option A: Vercel CLI
```bash
npm i -g vercel
vercel --prod
# Follow prompts: link to new project, set env var VITE_API_URL
```

### Option B: GitHub → Vercel (recommended)
1. Push `nickos-dashboard/` folder to a GitHub repo
2. Go to vercel.com → New Project → Import repo
3. Framework: Vite  
4. Root directory: `nickos-dashboard` (if in a monorepo)
5. Add env var: `VITE_API_URL` = your Railway URL
6. Deploy → get URL like `https://nickos.vercel.app`

## 4. iPhone PWA install
1. Open the Vercel URL in Safari on your iPhone
2. Tap Share → "Add to Home Screen"
3. Name it "NickOS" → Add
4. App icon appears — works offline (cached), looks native

## 5. Apple Health integration (free, no HealthKit dev account needed)

### iPhone Shortcuts automation:
1. Open Shortcuts app → Automation → New Automation → Time of Day (7am daily)
2. Add action: "Get My Health Samples" → Steps (Today)
3. Add action: "Get My Health Samples" → Sleep Analysis (last night)
4. Add action: "Get Contents of URL"
   - URL: `https://nickos-backend.railway.app/api/log/health`
   - Method: POST
   - Body JSON: `{ "steps": [Steps Result], "sleep": [Sleep Result] }`
5. Done — runs every morning automatically

### FastAPI endpoint to add:
```python
@app.post("/api/log/health")
async def log_health(steps: int = 0, sleep: float = 0):
    # Save to SQLite alongside existing health data
    db.log_health(date=today(), steps=steps, sleep_hours=sleep)
    return {"status": "ok"}
```

## 6. Affirmation engine (add to Railway backend)

```python
import anthropic
from datetime import datetime, timedelta

@app.get("/api/affirmation")
async def get_affirmation():
    # Load USER.md context
    user_context = open("USER.md").read()
    # Load recent affirmations to avoid repeats
    recent = db.get_recent_affirmations(days=7)
    
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""You are Nick's personal coach. Write ONE direct, 2-3 sentence affirmation.

Context about Nick:
{user_context}

Recent affirmations (do NOT repeat these themes):
{chr(10).join(recent)}

Rules:
- Direct and specific to Nick's actual situation (trading bot, study abroad appeal, fitness journey)
- No generic motivational poster quotes
- Reference his real goals/challenges
- Tone: confident, no fluff

Write only the affirmation, no intro."""
        }]
    )
    text = msg.content[0].text
    db.save_affirmation(text, datetime.now())
    return {"text": text, "refreshIn": 1800}
```

## 7. Google Calendar integration

Add to your existing OAuth project (same one as Gmail):
1. Enable Google Calendar API in Google Cloud Console
2. Add scope: `https://www.googleapis.com/auth/calendar.events`
3. Re-run OAuth flow to get updated refresh token

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

@app.get("/api/calendar")
async def get_calendar():
    creds = Credentials(token=None, refresh_token=REFRESH_TOKEN,
                        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
                        token_uri="https://oauth2.googleapis.com/token")
    service = build("calendar", "v3", credentials=creds)
    now = datetime.utcnow().isoformat() + 'Z'
    end = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'
    events = service.events().list(
        calendarId='primary', timeMin=now, timeMax=end,
        maxResults=10, singleEvents=True, orderBy='startTime'
    ).execute()
    return [format_event(e) for e in events.get('items', [])]

@app.post("/api/calendar/add")
async def add_calendar_event(title: str, date: str, time: str, duration: int = 60):
    # Parse and create event
    ...
```
