"""
bot/utils.py — NickOS shared utilities
"""

import os
import re
import sys
import yaml
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Paths — resolved via config (supports local dev + Railway prod) ───────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import MEMORY_DIR, DAILY_LOGS, MEMORY_FILE, DATA_DIR  # noqa: E402

SOUL_FILE   = MEMORY_DIR / "SOUL.md"
USER_FILE   = MEMORY_DIR / "USER.md"

# ── Timezone ──────────────────────────────────────────────────────────────────
ET = ZoneInfo("America/New_York")

def now_et() -> datetime:
    return datetime.now(ET)

def today_str() -> str:
    return now_et().strftime("%Y-%m-%d")

def today_label() -> str:
    """e.g. 'Monday, June 9'"""
    return now_et().strftime("%A, %B %-d")

# ── Health targets ────────────────────────────────────────────────────────────
SLEEP_TARGET = 8.0  # hours
WATER_GOAL   = 8    # glasses/day

# ── Workout schedule (Mon/Wed/Fri/Sat/Sun) ────────────────────────────────────
WORKOUT_DAYS = {"Monday", "Wednesday", "Friday", "Saturday", "Sunday"}

WORKOUT_PLAN = {
    "Monday":    "Upper body (dumbbells + bench) + jump rope cardio 15min",
    "Wednesday": "Muay Thai drills (jump rope, shadowboxing, stretching) + bike 20min",
    "Friday":    "Full body calisthenics (pushups, squats, lunges, core) + stairmaster 15min",
    "Saturday":  "Lower body (dumbbells) + treadmill 20min",
    "Sunday":    "Active recovery — Muay Thai stretching, yoga ball core, light bike 15min",
}

# ── Silent hours — 1:00am–7:30am ET ONLY ─────────────────────────────────────
def is_silent_hours() -> bool:
    now  = now_et()
    hour = now.hour
    minute = now.minute
    # Silent: 1:00am (01:00) through 7:29am (07:29)
    after_1am  = (hour == 1 and minute >= 0) or (hour > 1)
    before_730 = (hour < 7) or (hour == 7 and minute < 30)
    return after_1am and before_730

# ── Daily log helpers ─────────────────────────────────────────────────────────
def get_daily_log_path(date_str: str | None = None) -> Path:
    d = date_str or today_str()
    return DAILY_LOGS / f"{d}.md"

def read_daily_log(date_str: str | None = None) -> str:
    path = get_daily_log_path(date_str)
    if path.exists():
        return path.read_text()
    return ""

def write_daily_log(content: str, date_str: str | None = None):
    path = get_daily_log_path(date_str)
    DAILY_LOGS.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

def append_daily_log(section: str, line: str, date_str: str | None = None):
    """Append a line under a named section in today's log, creating if needed."""
    path = get_daily_log_path(date_str)
    DAILY_LOGS.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _init_daily_log(path, date_str or today_str())

    text = path.read_text()

    # If section exists, append after it
    if f"## {section}" in text:
        text = text.replace(
            f"## {section}\n",
            f"## {section}\n- {line}\n"
        )
    else:
        text += f"\n## {section}\n- {line}\n"

    path.write_text(text)

def _init_daily_log(path: Path, date_str: str):
    path.write_text(
        f"# Daily Log — {date_str}\n\n"
        f"## Morning Brief\n\n"
        f"## Health\n\n"
        f"## Water\n\n"
        f"## Focus Blocks\n\n"
        f"## Done Today\n\n"
        f"## Notes\n\n"
        f"## End of Day\n"
    )

# ── MEMORY.md quick reads ─────────────────────────────────────────────────────
def _read_memory_field(pattern: str) -> str:
    """Extract a value from MEMORY.md using a regex pattern."""
    if not MEMORY_FILE.exists():
        return "—"
    text = MEMORY_FILE.read_text()
    m = re.search(pattern, text)
    return m.group(1).strip() if m else "—"

def get_sleep_streak() -> str:
    return _read_memory_field(r"Current streak:\s*(\S+)")

def get_meals_today() -> str:
    return _read_memory_field(r"Meals today:\s*(\S+)")

def get_workout_this_week() -> str:
    return _read_memory_field(r"This week:\s*(\S+)")

def get_today_focus() -> str:
    return _read_memory_field(r"## Today's Focus\n\n(.+?)(?:\n|$)")

def get_active_goals(limit: int = 3) -> list[str]:
    """
    Parse MEMORY.md Active Goals section and return top N incomplete goal names.
    Falls back to empty list if MEMORY.md missing or no goals found.
    """
    if not MEMORY_FILE.exists():
        return []
    text      = MEMORY_FILE.read_text()
    section_m = re.search(r"## Active Goals\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if not section_m:
        return []
    section   = re.sub(r"<!--.*?-->", "", section_m.group(1), flags=re.DOTALL)
    pattern   = re.compile(r"- \[ \] (.+?) \| Added:")
    goals     = [m.group(1).strip() for m in pattern.finditer(section)]
    return goals[:limit]


def update_memory_field(old_line: str, new_line: str):
    """Replace a line in MEMORY.md in-place."""
    if not MEMORY_FILE.exists():
        return
    text = MEMORY_FILE.read_text()
    text = text.replace(old_line, new_line)
    MEMORY_FILE.write_text(text)

# ── Water tracking ────────────────────────────────────────────────────────────
def get_water_today() -> int:
    """Count water glasses logged in today's daily log."""
    log = read_daily_log()
    if not log:
        return 0
    # Count lines like "- Water: glass #N" or "- Water glass logged"
    return len(re.findall(r"^- Water", log, re.MULTILINE))

def log_water_glass() -> int:
    """Log one glass of water. Returns new total for today."""
    count = get_water_today() + 1
    timestamp = now_et().strftime("%H:%M")
    append_daily_log("Water", f"Water glass #{count} logged at {timestamp} ET")
    return count

# ── Weekly health stats ───────────────────────────────────────────────────────
def get_weekly_stats() -> dict:
    """
    Scan the last 7 daily logs and compute weekly health stats.
    Returns dict with sleep_avg, meals_total, workouts_logged, water_avg.
    """
    from datetime import timedelta
    today = now_et().date()
    sleep_hours = []
    meals_count = 0
    workouts    = 0
    water_total = 0
    days_counted = 0

    for i in range(7):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        log = read_daily_log(d)
        if not log:
            continue
        days_counted += 1

        # Sleep
        m = re.search(r"Sleep: ([\d.]+)h", log)
        if m:
            sleep_hours.append(float(m.group(1)))

        # Meals (count Meal: lines)
        meals_count += len(re.findall(r"^- Meal:", log, re.MULTILINE))

        # Workouts
        if re.search(r"Workout.*done|Workout.*logged", log, re.IGNORECASE):
            workouts += 1

        # Water
        water_total += len(re.findall(r"^- Water", log, re.MULTILINE))

    sleep_avg = round(sum(sleep_hours) / len(sleep_hours), 1) if sleep_hours else 0
    water_avg = round(water_total / max(days_counted, 1), 1)

    return {
        "sleep_avg":    sleep_avg,
        "sleep_days":   len(sleep_hours),
        "meals_total":  meals_count,
        "workouts":     workouts,
        "water_avg":    water_avg,
        "days_counted": days_counted,
    }

# ── Formatting helpers ────────────────────────────────────────────────────────
def bold(text: str) -> str:
    return f"*{text}*"

def code(text: str) -> str:
    return f"`{text}`"
