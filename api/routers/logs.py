"""
api/routers/logs.py
POST /api/log/sleep   — log sleep hours
POST /api/log/meal    — log a meal
POST /api/log/water   — log water glass(es)
POST /api/log/workout — log a workout
POST /api/log/focus   — log a completed focus (pomodoro) session
POST /api/log/habit   — toggle a habit for today
"""

from fastapi import APIRouter, HTTPException
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from api.models import SleepLog, MealLog, WaterLog, WorkoutLog, FocusLog, HabitLog
from api.db import log_sleep, log_meal, log_water, log_workout, log_focus, log_habit
from security import (
    validate_sleep_hours, validate_meal_text,
    validate_water_glasses, validate_workout_notes, ValidationError
)

router = APIRouter(prefix="/api/log", tags=["logs"])


@router.post("/sleep")
def post_sleep(body: SleepLog):
    try:
        hours = validate_sleep_hours(body.hours)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    health = log_sleep(hours)
    return {"ok": True, "logged": hours, "health": health}


@router.post("/meal")
def post_meal(body: MealLog):
    try:
        meal = validate_meal_text(body.meal)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    health = log_meal(meal)
    return {"ok": True, "logged": meal, "health": health}


@router.post("/water")
def post_water(body: WaterLog):
    try:
        glasses = validate_water_glasses(body.glasses)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    health = log_water(glasses)
    return {"ok": True, "logged": glasses, "health": health}


@router.post("/workout")
def post_workout(body: WorkoutLog):
    try:
        notes = validate_workout_notes(body.notes)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    health = log_workout(notes)
    return {"ok": True, "logged": True, "health": health}


@router.post("/focus")
def post_focus(body: FocusLog):
    stats = log_focus(body.minutes, body.label or "")

    # Telegram nudge — best-effort, never blocks the response
    try:
        import os, httpx
        token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")
        if token and chat_id:
            httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": (
                        f"🎯 Focus session done — {body.minutes}min"
                        + (f" — {body.label}" if body.label else "")
                        + f"\n🔥 {stats['sessionsToday']} session(s) / {stats['minutesToday']}min today"
                    ),
                },
                timeout=5,
            )
    except Exception:
        pass

    return {"ok": True, "logged": body.minutes, **stats}


@router.post("/habit")
def post_habit(body: HabitLog):
    result = log_habit(body.habit_id.strip(), body.done)
    return {"ok": True, **result}
