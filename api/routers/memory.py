"""
api/routers/memory.py
GET /api/affirmation  — fresh affirmation from Claude Haiku
GET /api/today        — aggregated today endpoint
"""

import os
import sys
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from bot.utils import ET, today_label, get_today_focus, WORKOUT_DAYS, WORKOUT_PLAN
from api.db import get_today_health, get_next_nudge, get_goals
from datetime import datetime

router = APIRouter(prefix="/api", tags=["memory"])

# Affirmation cache — refresh every 4 hours
_aff_cache: dict = {"text": None, "ts": 0}
AFFIRMATION_TTL = 4 * 3600


def _generate_affirmation() -> str:
    """Call Claude Haiku to generate a personalized affirmation for Nick."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        model  = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")

        now     = datetime.now(ET)
        weekday = now.strftime("%A")

        msg = client.messages.create(
            model=model,
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": (
                    f"Generate one short, powerful affirmation for Nick — "
                    f"21-year-old CS student at Fordham, aspiring quant/SWE, "
                    f"working on his algo trading bot, studying abroad appeal for London, "
                    f"building NickOS. Today is {weekday}. "
                    f"Be specific, direct, motivating. One sentence. No fluff. No quotes."
                )
            }],
        )
        return msg.content[0].text.strip().strip('"')
    except Exception:
        defaults = [
            "Every line of code you write today compounds into the engineer you're becoming.",
            "The grind is quiet — keep showing up.",
            "London, quant, Dean's List — you're building it all in parallel.",
            "Discipline is just doing the thing when you don't feel like it.",
            "Your future self is watching. Make him proud.",
        ]
        import random
        return random.choice(defaults)


@router.get("/affirmation")
def get_affirmation(force: bool = False):
    if not force and _aff_cache["text"] and (time.time() - _aff_cache["ts"] < AFFIRMATION_TTL):
        return {"text": _aff_cache["text"], "cached": True}

    text = _generate_affirmation()
    _aff_cache["text"] = text
    _aff_cache["ts"]   = time.time()
    return {"text": text, "cached": False}


@router.get("/today")
def get_today():
    """
    Aggregated today endpoint — everything the Today page needs in one shot.
    Avoids multiple round trips from the dashboard.
    """
    now     = datetime.now(ET)
    weekday = now.strftime("%A")

    health = get_today_health()
    nudge  = get_next_nudge()
    focus  = get_today_focus()
    goals  = get_goals()[:3]  # top 3

    # Calendar (graceful if not configured)
    calendar_events = []
    try:
        from gmail.calendar_client import get_today_events, calendar_ready
        if calendar_ready():
            calendar_events = get_today_events()
    except Exception:
        pass

    # Affirmation (use cache, don't block)
    aff_text = _aff_cache.get("text") or "Discipline is just doing the thing when you don't feel like it."

    is_workout_day = weekday in WORKOUT_DAYS

    return {
        "date":          today_label(),
        "greeting":      f"Good {'morning' if now.hour < 12 else 'afternoon' if now.hour < 17 else 'evening'}, Nick",
        "health":        health,
        "focus":         focus if focus and focus != "—" else "Set your focus for today",
        "nextNudge":     nudge,
        "isWorkoutDay":  is_workout_day,
        "workout":       WORKOUT_PLAN.get(weekday, "") if is_workout_day else "",
        "affirmation":   {"text": aff_text},
        "calendar":      calendar_events[:5],
        "goals":         goals,
    }
