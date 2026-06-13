"""
db/schema.py — SQLite setup for NickOS health tracking.

Tables
------
sleep_logs   : one row per sleep entry (date, hours)
meal_logs    : one row per meal (date, label, description)
water_logs   : one row per glass of water (date)
workout_logs : one row per workout session (date, notes)

All dates are stored as TEXT in YYYY-MM-DD format (ET).
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import DB_PATH  # noqa: E402


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # Don't use WAL — keeps the DB as a single file, more compatible
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    """Create tables if they don't already exist."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sleep_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,          -- YYYY-MM-DD
                hours       REAL NOT NULL,
                logged_at   TEXT NOT NULL           -- HH:MM ET
            );

            CREATE TABLE IF NOT EXISTS meal_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                label       TEXT NOT NULL,          -- Breakfast / Lunch / Dinner
                description TEXT NOT NULL DEFAULT '',
                logged_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS water_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                logged_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workout_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                notes       TEXT NOT NULL DEFAULT '',
                logged_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS focus_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                minutes     INTEGER NOT NULL DEFAULT 25,
                label       TEXT NOT NULL DEFAULT '',
                logged_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS habit_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                habit_id    TEXT NOT NULL,
                done        INTEGER NOT NULL DEFAULT 1,
                logged_at   TEXT NOT NULL,
                UNIQUE(date, habit_id)
            );

            -- Ensure at most one sleep entry per day (replace strategy)
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sleep_date ON sleep_logs(date);
        """)


def seed_from_log(date_str: str, log_text: str):
    """
    Parse a markdown daily log and insert records into SQLite.
    Safe to call multiple times — uses INSERT OR REPLACE / INSERT OR IGNORE.
    """
    import re
    from datetime import datetime

    with get_conn() as conn:
        # ── Sleep ──────────────────────────────────────────────────────────
        m = re.search(r"Sleep: ([\d.]+)h.*?logged (\d+:\d+)", log_text)
        if m:
            conn.execute(
                "INSERT OR REPLACE INTO sleep_logs (date, hours, logged_at) VALUES (?, ?, ?)",
                (date_str, float(m.group(1)), m.group(2)),
            )

        # ── Meals ──────────────────────────────────────────────────────────
        # Lines like: - Meal: Dinner — Test meal (logged 15:12 ET)
        meal_pattern = re.compile(
            r"- Meal: (\w+) — (.+?) \(logged (\d+:\d+)", re.MULTILINE
        )
        # Also handle: - Meal: Eggs — grits and sausage (logged 14:47 ET)
        # (first meal may not have a label prefix like Breakfast/Lunch/Dinner)
        existing_meals = {
            row["label"]
            for row in conn.execute(
                "SELECT label FROM meal_logs WHERE date = ?", (date_str,)
            )
        }
        for meal_m in meal_pattern.finditer(log_text):
            label, desc, ts = meal_m.group(1), meal_m.group(2), meal_m.group(3)
            # Normalise label
            if label.lower() not in ("breakfast", "lunch", "dinner", "meal"):
                # First meal logged without a proper label — call it Breakfast
                label = "Breakfast"
            label = label.capitalize()
            if label not in existing_meals:
                conn.execute(
                    "INSERT OR IGNORE INTO meal_logs (date, label, description, logged_at) VALUES (?, ?, ?, ?)",
                    (date_str, label, desc.strip(), ts),
                )
                existing_meals.add(label)

        # ── Water ──────────────────────────────────────────────────────────
        # Lines like: - Water glass #N logged at HH:MM ET
        water_pattern = re.compile(r"- Water glass #(\d+) logged at (\d+:\d+)", re.MULTILINE)
        existing_count = conn.execute(
            "SELECT COUNT(*) as c FROM water_logs WHERE date = ?", (date_str,)
        ).fetchone()["c"]
        for wm in water_pattern.finditer(log_text):
            glass_num = int(wm.group(1))
            ts        = wm.group(2)
            if glass_num > existing_count:
                conn.execute(
                    "INSERT INTO water_logs (date, logged_at) VALUES (?, ?)",
                    (date_str, ts),
                )
                existing_count += 1

        # ── Workouts ───────────────────────────────────────────────────────
        # Lines like: - Workout done: Upper body session (15:11 ET)
        workout_pattern = re.compile(
            r"- Workout done: (.+?) \((\d+:\d+)", re.MULTILINE
        )
        existing_workouts = conn.execute(
            "SELECT COUNT(*) as c FROM workout_logs WHERE date = ?", (date_str,)
        ).fetchone()["c"]
        for wm in workout_pattern.finditer(log_text):
            notes, ts = wm.group(1).strip(), wm.group(2)
            if existing_workouts == 0:
                conn.execute(
                    "INSERT INTO workout_logs (date, notes, logged_at) VALUES (?, ?, ?)",
                    (date_str, notes, ts),
                )
                existing_workouts += 1  # only insert first workout per day


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    from bot.utils import today_str, read_daily_log

    init_db()
    date = today_str()
    log  = read_daily_log(date)
    if log:
        seed_from_log(date, log)
        print(f"✓ Seeded {date} into {DB_PATH}")
    else:
        print(f"No daily log found for {date}")

    # Show what's in the DB
    with get_conn() as conn:
        print("\nSleep:",  list(conn.execute("SELECT * FROM sleep_logs ORDER BY date DESC LIMIT 3")))
        print("Meals:",   list(conn.execute("SELECT * FROM meal_logs  ORDER BY date DESC, id")))
        print("Water:",   conn.execute("SELECT date, COUNT(*) c FROM water_logs GROUP BY date").fetchall())
        print("Workout:", list(conn.execute("SELECT * FROM workout_logs ORDER BY date DESC LIMIT 3")))
