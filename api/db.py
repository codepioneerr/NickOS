"""
api/db.py — Data access layer for NickOS API.

Primary storage: SQLite (db/nickos.db)
  - sleep_logs, meal_logs, water_logs, workout_logs

On first run the DB is auto-created and seeded from today's markdown log
so you don't lose data already written by the Telegram bot.

Writes go to BOTH SQLite AND the markdown daily log so the bot stays in sync.
"""

import re
import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from bot.utils import (
    ET, today_str, today_label,
    SLEEP_TARGET, WATER_GOAL, WORKOUT_DAYS, WORKOUT_PLAN,
    read_daily_log, append_daily_log,
    get_today_focus, get_weekly_stats,
    update_memory_field, log_water_glass,
    MEMORY_FILE, DAILY_LOGS,
)
from db.schema import get_conn, init_db, seed_from_log


def _notify():
    """Fire SSE event to all connected dashboard clients after a health write."""
    try:
        from api.main import notify_health_update
        notify_health_update("health_updated")
    except Exception:
        pass  # SSE is best-effort — never block a write


# ── Auto-init on first import ─────────────────────────────────────────────────

def _bootstrap():
    try:
        init_db()
        date = today_str()
        log  = read_daily_log(date)
        if log:
            seed_from_log(date, log)
    except Exception:
        pass  # Never crash the API on DB issues


_bootstrap()


# ─────────────────────────────────────────────────────────────────────────────
# TODAY DATA
# ─────────────────────────────────────────────────────────────────────────────

def get_today_health() -> dict:
    """Read today's health state from SQLite (fallback: markdown)."""
    now     = datetime.now(ET)
    weekday = now.strftime("%A")
    date    = today_str()

    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT hours FROM sleep_logs WHERE date = ?", (date,)
            ).fetchone()
            sleep_h = float(row["hours"]) if row else 0.0

            meals_logged = conn.execute(
                "SELECT COUNT(*) as c FROM meal_logs WHERE date = ?", (date,)
            ).fetchone()["c"]

            water_count = conn.execute(
                "SELECT COUNT(*) as c FROM water_logs WHERE date = ?", (date,)
            ).fetchone()["c"]

            workout_row = conn.execute(
                "SELECT notes FROM workout_logs WHERE date = ? LIMIT 1", (date,)
            ).fetchone()
            workout_done = workout_row is not None

    except Exception:
        return _get_today_health_fallback()

    sleep_pct      = min(100, round(sleep_h / SLEEP_TARGET * 100))
    meal_pct       = min(100, round(meals_logged / 3 * 100))
    water_pct      = min(100, round(water_count / WATER_GOAL * 100))
    workout_pct    = 100 if workout_done else 0
    is_workout_day = weekday in WORKOUT_DAYS

    return {
        "sleep":   {"value": sleep_h,      "goal": SLEEP_TARGET, "pct": sleep_pct,   "unit": "h"},
        "meals":   {"value": meals_logged,  "goal": 3,            "pct": meal_pct,    "unit": "meals"},
        "water":   {"value": water_count,   "goal": WATER_GOAL,   "pct": water_pct,   "unit": "glasses"},
        "workout": {"value": 1 if workout_done else 0, "goal": 1, "pct": workout_pct, "unit": "done"},
        "is_workout_day": is_workout_day,
        "workout_plan":   WORKOUT_PLAN.get(weekday, "") if is_workout_day else "",
        "workout_done":   workout_done,
    }


def _get_today_health_fallback() -> dict:
    """Parse today's markdown log — used when SQLite is unavailable."""
    log     = read_daily_log()
    now     = datetime.now(ET)
    weekday = now.strftime("%A")

    sleep_m      = re.search(r"Sleep: ([\d.]+)h", log)
    sleep_h      = float(sleep_m.group(1)) if sleep_m else 0.0
    meals_logged = len(re.findall(r"^- Meal:", log, re.MULTILINE))
    water_count  = len(re.findall(r"^- Water", log, re.MULTILINE))
    workout_done = bool(re.search(r"Workout.*done|Workout.*logged|Workout:", log, re.IGNORECASE))
    is_workout_day = weekday in WORKOUT_DAYS

    return {
        "sleep":   {"value": sleep_h,     "goal": SLEEP_TARGET, "pct": min(100, round(sleep_h/SLEEP_TARGET*100)),   "unit": "h"},
        "meals":   {"value": meals_logged, "goal": 3,            "pct": min(100, round(meals_logged/3*100)),          "unit": "meals"},
        "water":   {"value": water_count,  "goal": WATER_GOAL,   "pct": min(100, round(water_count/WATER_GOAL*100)), "unit": "glasses"},
        "workout": {"value": 1 if workout_done else 0, "goal": 1, "pct": 100 if workout_done else 0,                 "unit": "done"},
        "is_workout_day": is_workout_day,
        "workout_plan":   WORKOUT_PLAN.get(weekday, "") if is_workout_day else "",
        "workout_done":   workout_done,
    }


def get_sleep_chart(days: int = 7) -> list[dict]:
    """Last N days of sleep for the chart, oldest first."""
    today = datetime.now(ET).date()
    result = []
    try:
        with get_conn() as conn:
            for i in range(days - 1, -1, -1):
                d    = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                row  = conn.execute("SELECT hours FROM sleep_logs WHERE date = ?", (d,)).fetchone()
                result.append({
                    "day":   (today - timedelta(days=i)).strftime("%a"),
                    "hours": float(row["hours"]) if row else 0.0,
                    "date":  d,
                })
    except Exception:
        for i in range(days - 1, -1, -1):
            d   = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            log = read_daily_log(d)
            m   = re.search(r"Sleep: ([\d.]+)h", log) if log else None
            result.append({
                "day":   (today - timedelta(days=i)).strftime("%a"),
                "hours": float(m.group(1)) if m else 0.0,
                "date":  d,
            })
    return result


def get_next_nudge() -> dict:
    now = datetime.now(ET)
    schedule = [
        (8,  0,  "Morning brief — rise and grind"),
        (9,  0,  "Breakfast reminder"),
        (10, 30, "Focus check-in"),
        (12, 30, "Midday check-in + lunch"),
        (14, 0,  "Lunch reminder"),
        (15, 0,  "Afternoon push"),
        (17, 0,  "Wind-down check-in"),
        (19, 0,  "Dinner reminder"),
        (21, 0,  "Night check-in"),
        (22, 0,  "Pre-sleep wind-down"),
        (23, 30, "Sleep reminder"),
    ]
    for h, m, label in schedule:
        nudge_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if nudge_dt > now:
            return {"label": label, "time": f"{h:02d}:{m:02d}", "seconds_left": int((nudge_dt - now).total_seconds())}
    return {"label": "Morning brief", "time": "08:00", "seconds_left": 3600}


def get_goals() -> list[dict]:
    if not MEMORY_FILE.exists():
        return []
    text      = MEMORY_FILE.read_text()
    section_m = re.search(r"## Active Goals\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if not section_m:
        return []
    section_text = re.sub(r"<!--.*?-->", "", section_m.group(1), flags=re.DOTALL)
    pattern = re.compile(r"- \[( |x)\] (.+?) \| Added: (\S+) \| Target: (\S+)")
    goals   = []
    for i, m in enumerate(pattern.finditer(section_text)):
        done, text_raw, added, target = m.groups()
        goals.append({
            "id":       f"goal_{i+1}",
            "name":     text_raw.strip(),
            "added":    added,
            "target":   target,
            "done":     done == "x",
            "progress": 0,
            "wins":     [],
        })
    return goals


def get_recent_wins() -> list[str]:
    if not MEMORY_FILE.exists():
        return []
    text = MEMORY_FILE.read_text()
    m    = re.search(r"## Recent Wins 🏆\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if not m:
        return []
    return [l.strip().lstrip("- ") for l in m.group(1).splitlines() if l.strip().startswith("-")][:10]


# ─────────────────────────────────────────────────────────────────────────────
# WRITE / LOG
# ─────────────────────────────────────────────────────────────────────────────

def log_sleep(hours: float) -> dict:
    now  = datetime.now(ET)
    ts   = now.strftime("%H:%M")
    date = today_str()

    # SQLite
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sleep_logs (date, hours, logged_at) VALUES (?, ?, ?)",
                (date, hours, ts),
            )
    except Exception:
        pass

    # Markdown (bot sync)
    log   = read_daily_log()
    entry = f"Sleep: {hours}h (logged {ts} ET)"
    if re.search(r"^- Sleep:", log, re.MULTILINE):
        log = re.sub(r"^- Sleep:.*$", f"- {entry}", log, flags=re.MULTILINE)
        (DAILY_LOGS / f"{date}.md").write_text(log)
    else:
        append_daily_log("Health", entry)

    if MEMORY_FILE.exists():
        old = re.search(r"- Last logged sleep: `.+?`.*", MEMORY_FILE.read_text())
        if old:
            update_memory_field(old.group(0), f"- Last logged sleep: `{hours}h` on {date}")

    _notify()
    return get_today_health()


def log_meal(meal: str) -> dict:
    now  = datetime.now(ET)
    ts   = now.strftime("%H:%M")
    date = today_str()

    try:
        with get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as c FROM meal_logs WHERE date = ?", (date,)
            ).fetchone()["c"]
    except Exception:
        count = len(re.findall(r"^- Meal:", read_daily_log(), re.MULTILINE))

    count += 1
    labels = {1: "Breakfast", 2: "Lunch", 3: "Dinner"}
    label  = labels.get(count, f"Meal {count}")

    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO meal_logs (date, label, description, logged_at) VALUES (?, ?, ?, ?)",
                (date, label, meal, ts),
            )
    except Exception:
        pass

    append_daily_log("Health", f"Meal: {label} — {meal} (logged {ts} ET)")

    if MEMORY_FILE.exists():
        text = MEMORY_FILE.read_text()
        old  = re.search(r"- Meals today: \S+", text)
        if old:
            update_memory_field(old.group(0), f"- Meals today: {count}/3")

    _notify()
    return get_today_health()


def log_water(glasses: int = 1) -> dict:
    now  = datetime.now(ET)
    ts   = now.strftime("%H:%M")
    date = today_str()

    try:
        with get_conn() as conn:
            for _ in range(glasses):
                conn.execute(
                    "INSERT INTO water_logs (date, logged_at) VALUES (?, ?)", (date, ts)
                )
    except Exception:
        pass

    for _ in range(glasses):
        log_water_glass()

    _notify()
    return get_today_health()


def log_workout(notes: str = "") -> dict:
    now  = datetime.now(ET)
    ts   = now.strftime("%H:%M")
    date = today_str()
    text = notes.strip() or WORKOUT_PLAN.get(now.strftime("%A"), "General workout")

    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO workout_logs (date, notes, logged_at) VALUES (?, ?, ?)",
                (date, text, ts),
            )
    except Exception:
        pass

    append_daily_log("Health", f"Workout done: {text} ({ts} ET)")
    _notify()
    return get_today_health()


def log_focus(minutes: int = 25, label: str = "") -> dict:
    """Log a completed focus (pomodoro) session."""
    now  = datetime.now(ET)
    ts   = now.strftime("%H:%M")
    date = today_str()
    text = (label or "").strip()

    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO focus_logs (date, minutes, label, logged_at) VALUES (?, ?, ?, ?)",
                (date, minutes, text, ts),
            )
            sessions_today = conn.execute(
                "SELECT COUNT(*) c FROM focus_logs WHERE date = ?", (date,)
            ).fetchone()["c"]
            minutes_today = conn.execute(
                "SELECT COALESCE(SUM(minutes),0) m FROM focus_logs WHERE date = ?", (date,)
            ).fetchone()["m"]
    except Exception:
        sessions_today, minutes_today = 1, minutes

    suffix = f" — {text}" if text else ""
    append_daily_log("Focus", f"Focus session: {minutes}min{suffix} (done {ts} ET)")
    _notify()
    return {"sessionsToday": sessions_today, "minutesToday": minutes_today}


def log_habit(habit_id: str, done: bool = True) -> dict:
    """Toggle a habit for today. Returns today's habit states."""
    now  = datetime.now(ET)
    ts   = now.strftime("%H:%M")
    date = today_str()

    try:
        with get_conn() as conn:
            if done:
                conn.execute(
                    "INSERT OR REPLACE INTO habit_logs (date, habit_id, done, logged_at) VALUES (?, ?, 1, ?)",
                    (date, habit_id, ts),
                )
            else:
                conn.execute(
                    "DELETE FROM habit_logs WHERE date = ? AND habit_id = ?", (date, habit_id)
                )
            rows = conn.execute(
                "SELECT habit_id FROM habit_logs WHERE date = ? AND done = 1", (date,)
            ).fetchall()
            today_habits = [r["habit_id"] for r in rows]
    except Exception:
        today_habits = [habit_id] if done else []

    if done:
        append_daily_log("Habits", f"Habit done: {habit_id} ({ts} ET)")
    _notify()
    return {"date": date, "done": today_habits}
