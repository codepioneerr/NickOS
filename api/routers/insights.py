"""
api/routers/insights.py
GET /api/insights — AI Insights panel for the Today page.

Claude Haiku analyzes today's health + goals + email urgency and returns
3 short insights (focus, health, goals). Cached 1h; ?force=true refreshes.
Heuristic fallback means the endpoint never fails or blocks the dashboard.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from bot.utils import ET, get_today_focus, SLEEP_TARGET, WATER_GOAL
from api.db import get_today_health, get_goals

router = APIRouter(prefix="/api", tags=["insights"])

_cache: dict = {"data": None, "ts": 0}
INSIGHTS_TTL = 3600


def _email_urgency() -> dict:
    """Counts of classified emails from the gmail router's cache (best-effort)."""
    try:
        from api.routers.gmail import _cache as _gmail_cache  # type: ignore
        data = _gmail_cache.get("data") or []
        emails = data.get("emails", []) if isinstance(data, dict) else data
        counts = {"act_now": 0, "opportunity": 0, "fyi": 0}
        for e in emails:
            tag = e.get("tag", "fyi") if isinstance(e, dict) else "fyi"
            counts[tag] = counts.get(tag, 0) + 1
        return counts
    except Exception:
        return {}


def _heuristic_insights(health: dict, goals: list, focus: str) -> list[dict]:
    out = []
    # Focus
    active = [g for g in goals if not g.get("done")]
    if focus and focus != "—":
        out.append({"icon": "🎯", "title": "Focus", "text": f"Lock in on: {focus}. One 25-min focus session before anything else."})
    elif active:
        out.append({"icon": "🎯", "title": "Focus", "text": f"No focus set — make it \"{active[0]['name']}\" and start a focus session."})
    else:
        out.append({"icon": "🎯", "title": "Focus", "text": "No focus set. Pick one thing and commit to it before noon."})
    # Health
    sleep = health.get("sleep", {}).get("value", 0)
    water = health.get("water", {}).get("value", 0)
    if sleep and sleep < SLEEP_TARGET - 1:
        out.append({"icon": "😴", "title": "Health", "text": f"Only {sleep}h sleep logged — wind down early tonight, aim for {SLEEP_TARGET}h."})
    elif water < WATER_GOAL // 2:
        out.append({"icon": "💧", "title": "Health", "text": f"{water}/{WATER_GOAL} glasses — drink one now."})
    else:
        out.append({"icon": "💪", "title": "Health", "text": "Health is on track today — keep the rings closing."})
    # Goals
    if active:
        out.append({"icon": "🏁", "title": "Goals", "text": f"{len(active)} active goal{'s' if len(active) != 1 else ''} — next target: {active[0].get('target', 'soon')}."})
    else:
        out.append({"icon": "🏁", "title": "Goals", "text": "No active goals — add one with /goal on Telegram."})
    return out


def _generate_insights() -> list[dict]:
    health = get_today_health()
    goals  = get_goals()
    focus  = get_today_focus()
    emails = _email_urgency()

    try:
        import anthropic
        client = anthropic.Anthropic()
        model  = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")
        now    = datetime.now(ET)

        msg = client.messages.create(
            model=model,
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": (
                    "You are NickOS, the personal OS of Nick — 21, CS student at Fordham, ADHD, "
                    "aspiring quant/SWE. Analyze his day and return EXACTLY a JSON array of 3 objects "
                    'with keys "icon" (one emoji), "title" (1-2 words), "text" (one direct, specific, '
                    "actionable sentence, max 140 chars). One insight each for: today's focus, health, "
                    "goal progress. Be signal-only, no fluff. JSON only, no markdown.\n\n"
                    f"Now: {now.strftime('%A %H:%M ET')}\n"
                    f"Today's focus: {focus}\n"
                    f"Health rings: {json.dumps({k: v for k, v in health.items() if isinstance(v, dict)})}\n"
                    f"Goals: {json.dumps([{ 'name': g['name'], 'target': g['target'], 'done': g['done']} for g in goals[:5]])}\n"
                    f"Email urgency counts: {json.dumps(emails)}"
                ),
            }],
        )
        raw = msg.content[0].text.strip()
        raw = raw[raw.index("["): raw.rindex("]") + 1]  # tolerate stray text
        data = json.loads(raw)
        if isinstance(data, list) and len(data) >= 3:
            return [
                {"icon": str(d.get("icon", "💡"))[:4], "title": str(d.get("title", "Insight"))[:24],
                 "text": str(d.get("text", ""))[:200]}
                for d in data[:3]
            ]
    except Exception:
        pass
    return _heuristic_insights(health, goals, focus)


@router.get("/insights")
def get_insights(force: bool = False):
    if not force and _cache["data"] and (time.time() - _cache["ts"] < INSIGHTS_TTL):
        return {"insights": _cache["data"], "cached": True}
    data = _generate_insights()
    _cache["data"] = data
    _cache["ts"]   = time.time()
    return {"insights": data, "cached": False}
