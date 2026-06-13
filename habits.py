"""
habits.py — Habit tracking engine for NickOS.

Stores streaks in SQLite (same DB as health data).
Provides:
  - log_habit(habit_id, date) → update streak
  - get_streaks() → dict of current/best streaks
  - get_today_status() → which habits hit/missed today
  - check_missed_habits() → call at midnight to reset streaks
  - FastAPI router with /api/habits endpoints
"""

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from fastapi import APIRouter

# ─── Config ───────────────────────────────────────────────────────────────────

DB_PATH    = Path(__file__).parent / "nickos.db"
HABITS_MD  = Path(__file__).parent / "HABITS.md"

HABITS = {
    "wake_up":              {"label": "Wake up by 8am",          "emoji": "⏰", "category": "sleep"},
    "water":                {"label": "8 glasses water",          "emoji": "💧", "category": "health",    "goal": 8},
    "meal_1":               {"label": "Breakfast by 9:30am",      "emoji": "🍳", "category": "nutrition"},
    "meal_2":               {"label": "Lunch by 2:30pm",          "emoji": "🥗", "category": "nutrition"},
    "meal_3":               {"label": "Dinner by 7:30pm",         "emoji": "🍽️", "category": "nutrition"},
    "workout":              {"label": "Workout",                   "emoji": "💪", "category": "fitness",  "weekly_goal": 5},
    "sleep":                {"label": "Sleep by midnight",         "emoji": "😴", "category": "sleep"},
    "no_smoke_preworkout":  {"label": "No smoke pre-workout",      "emoji": "🚭", "category": "health"},
}

# ─── Database setup ───────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_habits_db():
    """Create habit tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id    TEXT    NOT NULL,
                logged_date TEXT    NOT NULL,   -- YYYY-MM-DD
                logged_at   TEXT    NOT NULL,   -- ISO timestamp
                value       REAL    DEFAULT 1,  -- for water: glasses count
                note        TEXT,
                UNIQUE(habit_id, logged_date)   -- one log per habit per day
            );

            CREATE TABLE IF NOT EXISTS habit_streaks (
                habit_id    TEXT PRIMARY KEY,
                current     INTEGER DEFAULT 0,
                best        INTEGER DEFAULT 0,
                last_hit    TEXT,               -- YYYY-MM-DD
                updated_at  TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_habit_logs_date
                ON habit_logs(logged_date);
        """)


# ─── Core streak logic ────────────────────────────────────────────────────────

def log_habit(habit_id: str, value: float = 1.0, note: str = None,
              log_date: Optional[date] = None) -> dict:
    """
    Log a habit completion. Handles upsert + streak update.
    Returns updated streak info.
    """
    if habit_id not in HABITS:
        raise ValueError(f"Unknown habit: {habit_id}")

    target_date = log_date or date.today()
    date_str    = target_date.isoformat()
    now_iso     = datetime.now().isoformat()

    with get_db() as conn:
        # Upsert the log
        conn.execute("""
            INSERT INTO habit_logs (habit_id, logged_date, logged_at, value, note)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(habit_id, logged_date) DO UPDATE SET
                value      = MAX(value, excluded.value),
                logged_at  = excluded.logged_at,
                note       = COALESCE(excluded.note, note)
        """, (habit_id, date_str, now_iso, value, note))

        # Recalculate streak
        streak = _calculate_streak(conn, habit_id, target_date)
        best   = _get_best_streak(conn, habit_id)
        new_best = max(streak, best)

        conn.execute("""
            INSERT INTO habit_streaks (habit_id, current, best, last_hit, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(habit_id) DO UPDATE SET
                current    = excluded.current,
                best       = MAX(best, excluded.best),
                last_hit   = excluded.last_hit,
                updated_at = excluded.updated_at
        """, (habit_id, streak, new_best, date_str, now_iso))

    # Sync back to HABITS.md
    _sync_streaks_to_md()

    return {"habit_id": habit_id, "current": streak, "best": new_best, "last_hit": date_str}


def _calculate_streak(conn: sqlite3.Connection, habit_id: str, from_date: date) -> int:
    """Count consecutive days going backwards from from_date."""
    streak = 0
    check  = from_date
    while True:
        row = conn.execute(
            "SELECT 1 FROM habit_logs WHERE habit_id=? AND logged_date=?",
            (habit_id, check.isoformat())
        ).fetchone()
        if row:
            streak += 1
            check  -= timedelta(days=1)
        else:
            break
    return streak


def _get_best_streak(conn: sqlite3.Connection, habit_id: str) -> int:
    row = conn.execute(
        "SELECT best FROM habit_streaks WHERE habit_id=?", (habit_id,)
    ).fetchone()
    return row["best"] if row else 0


def get_streaks() -> dict:
    """Return current streaks for all habits."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT habit_id, current, best, last_hit FROM habit_streaks"
        ).fetchall()

    streaks = {h: {"current": 0, "best": 0, "last_hit": None} for h in HABITS}
    for row in rows:
        if row["habit_id"] in streaks:
            streaks[row["habit_id"]] = {
                "current": row["current"],
                "best":    row["best"],
                "last_hit": row["last_hit"],
            }
    return streaks


def get_today_status() -> dict:
    """Return today's habit hit/miss status."""
    today_str = date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT habit_id, value FROM habit_logs WHERE logged_date=?",
            (today_str,)
        ).fetchall()

    logged = {row["habit_id"]: row["value"] for row in rows}
    streaks = get_streaks()

    result = {}
    for hid, meta in HABITS.items():
        result[hid] = {
            "label":    meta["label"],
            "emoji":    meta["emoji"],
            "category": meta["category"],
            "hit":      hid in logged,
            "value":    logged.get(hid, 0),
            "current_streak": streaks[hid]["current"],
            "best_streak":    streaks[hid]["best"],
            "last_hit":       streaks[hid]["last_hit"],
        }
    return result


def check_missed_habits():
    """
    Call at midnight ET to reset streaks for habits not hit today.
    Should be run by a scheduled task.
    """
    today    = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    now_iso  = datetime.now().isoformat()

    with get_db() as conn:
        for hid in HABITS:
            # Check if yesterday was logged
            row = conn.execute(
                "SELECT 1 FROM habit_logs WHERE habit_id=? AND logged_date=?",
                (hid, yesterday)
            ).fetchone()

            if not row:
                # Missed yesterday → streak resets to 0
                conn.execute("""
                    INSERT INTO habit_streaks (habit_id, current, best, last_hit, updated_at)
                    VALUES (?, 0, 0, ?, ?)
                    ON CONFLICT(habit_id) DO UPDATE SET current=0, updated_at=excluded.updated_at
                """, (hid, None, now_iso))

    _sync_streaks_to_md()


def _sync_streaks_to_md():
    """Update the JSON streak block in HABITS.md."""
    streaks = get_streaks()
    json_str = json.dumps(streaks, indent=2)

    if not HABITS_MD.exists():
        return

    content   = HABITS_MD.read_text()
    start_tag = "<!-- DO NOT EDIT BELOW — updated by habits.py -->\n```json"
    end_tag   = "```"

    start_idx = content.find(start_tag)
    if start_idx == -1:
        return

    json_start = content.find("\n", start_idx + len(start_tag)) + 1
    json_end   = content.find(end_tag, json_start)

    if json_end == -1:
        return

    new_content = content[:json_start] + json_str + "\n" + content[json_end:]
    HABITS_MD.write_text(new_content)


# ─── FastAPI router ────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/habits", tags=["habits"])


@router.get("")
async def api_get_habits():
    """Return today's habit status + streaks."""
    return get_today_status()


@router.post("/log/{habit_id}")
async def api_log_habit(habit_id: str, value: float = 1.0, note: str = None):
    """Log a habit completion. For water, value = number of glasses."""
    if habit_id not in HABITS:
        return {"error": f"Unknown habit: {habit_id}"}
    result = log_habit(habit_id, value=value, note=note)
    return {"status": "ok", **result}


@router.get("/streaks")
async def api_get_streaks():
    return get_streaks()


@router.post("/midnight-reset")
async def api_midnight_reset():
    """Call this at midnight to reset missed habit streaks."""
    check_missed_habits()
    return {"status": "ok", "message": "Streaks updated for missed habits"}


# ─── Telegram bot commands ─────────────────────────────────────────────────────

HABIT_ALIASES = {
    "wake":    "wake_up",
    "woke":    "wake_up",
    "water":   "water",
    "h2o":     "water",
    "meal1":   "meal_1",
    "breakfast": "meal_1",
    "meal2":   "meal_2",
    "lunch":   "meal_2",
    "meal3":   "meal_3",
    "dinner":  "meal_3",
    "workout": "workout",
    "gym":     "workout",
    "lift":    "workout",
    "sleep":   "sleep",
    "bed":     "sleep",
    "nsmoke":  "no_smoke_preworkout",
}


def parse_habit_command(text: str) -> Optional[tuple[str, float]]:
    """
    Parse a Telegram habit command.
    Examples:
      /habit water 3      → log 3 glasses water
      /habit workout      → log workout done
      /habit meal1        → log meal 1
    Returns (habit_id, value) or None if not recognized.
    """
    parts = text.strip().lower().split()
    if not parts:
        return None

    key   = parts[0].lstrip("/")
    value = float(parts[1]) if len(parts) > 1 and parts[1].replace(".","").isdigit() else 1.0

    habit_id = HABIT_ALIASES.get(key)
    return (habit_id, value) if habit_id else None


def format_habits_message(status: dict) -> str:
    """Format today's habits as a Telegram message."""
    lines = ["**📋 Today's Habits**\n"]
    categories = {}
    for hid, data in status.items():
        cat = data["category"]
        categories.setdefault(cat, []).append((hid, data))

    for cat, items in sorted(categories.items()):
        for hid, data in items:
            tick   = "✅" if data["hit"] else "⬜"
            streak = data["current_streak"]
            fire   = f" 🔥{streak}" if streak >= 3 else (f" ({streak}d)" if streak > 0 else "")
            lines.append(f"{tick} {data['emoji']} {data['label']}{fire}")

    lines.append(f"\n_Log: /habit [name] — e.g. /habit water 3_")
    return "\n".join(lines)


# ─── Init on import ───────────────────────────────────────────────────────────
init_habits_db()
