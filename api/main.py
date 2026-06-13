"""
api/main.py — NickOS FastAPI backend

Run locally:
    uvicorn api.main:app --reload --port 8000

Deploy on Railway:
    Start command: uvicorn api.main:app --host 0.0.0.0 --port $PORT
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import AsyncGenerator

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv

load_dotenv()

# ── API key auth ──────────────────────────────────────────────────────────────

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_NICKOS_KEY     = os.environ.get("NICKOS_API_KEY", "")


def require_api_key(key: str = Depends(_API_KEY_HEADER)):
    """Dependency: reject requests missing or with wrong X-API-Key."""
    if not _NICKOS_KEY:
        return  # key not configured — open (dev mode)
    if key != _NICKOS_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or missing API key")


# ── SSE event queue (singleton) ───────────────────────────────────────────────

_sse_listeners: list[asyncio.Queue] = []


def notify_health_update(event: str = "health_updated"):
    """Push an event to all connected SSE clients. Call after any health write."""
    dead = []
    for q in _sse_listeners:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _sse_listeners.remove(q)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NickOS API",
    version="1.0.0",
    description="Personal OS backend — health, email, calendar, goals",
)

# ── CORS — allow Vercel + local dev ──────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://nickos-dashboard.vercel.app",
        "https://*.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

from api.routers.health   import router as health_router
from api.routers.gmail    import router as gmail_router
from api.routers.goals    import router as goals_router
from api.routers.calendar import router as calendar_router
from api.routers.logs     import router as logs_router
from api.routers.memory   import router as memory_router
from api.routers.weekly   import router as weekly_router
from api.routers.obsidian import router as obsidian_router
from api.routers.insights import router as insights_router

_auth = Depends(require_api_key)

app.include_router(health_router,   dependencies=[_auth])
app.include_router(gmail_router,    dependencies=[_auth])
app.include_router(goals_router,    dependencies=[_auth])
app.include_router(calendar_router, dependencies=[_auth])
app.include_router(logs_router,     dependencies=[_auth])
app.include_router(memory_router,   dependencies=[_auth])
app.include_router(weekly_router,   dependencies=[_auth])
app.include_router(obsidian_router, dependencies=[_auth])
app.include_router(insights_router, dependencies=[_auth])


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    from datetime import datetime
    from bot.utils import ET
    return {
        "status": "ok",
        "service": "NickOS API",
        "time": datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"),
    }


@app.get("/api/stream")
async def sse_stream(key: str = None, x_api_key: str = Depends(_API_KEY_HEADER)):
    """
    Server-Sent Events endpoint.
    Accepts key via X-API-Key header OR ?key= query param (EventSource can't set headers).
    """
    supplied = key or x_api_key
    if _NICKOS_KEY and supplied != _NICKOS_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    q: asyncio.Queue = asyncio.Queue(maxsize=20)
    _sse_listeners.append(q)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Send initial heartbeat
            yield "event: connected\ndata: ok\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=25)
                    yield f"event: {event}\ndata: ok\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"  # keep-alive comment
        finally:
            if q in _sse_listeners:
                _sse_listeners.remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
def health_check():
    from datetime import datetime
    from bot.utils import ET
    from gmail.calendar_client import calendar_ready

    # Check which Gmail accounts are configured
    try:
        from gmail.fetcher import load_accounts
        accounts = [a["email"] for a in load_accounts()]
    except Exception:
        accounts = []

    return {
        "status":           "ok",
        "time":             datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"),
        "gmail_accounts":   accounts,
        "calendar_ready":   calendar_ready(),
        "memory_exists":    (ROOT / "memory/MEMORY.md").exists(),
        "daily_log_today":  (ROOT / f"memory/daily_logs/{datetime.now(ET).strftime('%Y-%m-%d')}.md").exists(),
    }
