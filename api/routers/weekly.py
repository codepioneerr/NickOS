"""
api/routers/weekly.py
GET /api/weekly — real weekly review data for the Weekly page.

Everything is computed from SQLite (db/nickos.db). Grades follow the
report-card style the Weekly page already renders. "One thing to improve"
uses Claude Haiku with a heuristic fallback so the endpoint never fails.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

from fastapi import APIRouter

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from bot.utils import ET, SLEEP_TARGET, WATER_GOAL
from db.schema import get_conn
from api.db import get_goals

router = APIRouter(prefix="/api", tags=["weekly"])

WORKOUT_GOAL = 5  # sessions per week


# ── Aggregation helpers ───────────────────────────────────────────────────────

def _day_range(start, days):
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


def _week_aggregates(conn, dates: list[str]) -> dict:
    """Aggregate health stats over a list of YYYY-MM-DD dates."""
    qmarks = ",".join("?" * len(dates))

    sleep_rows = conn.execute(
        f"SELECT date, hours FROM sleep_logs WHERE date IN ({qmarks})", dates
    ).fetchall()
    sleep_hours = [float(r["hours"]) for r in sleep_rows if r["hours"]]

    meal_rows = conn.execute(
        f"SELECT date, COUNT(*) c FROM meal_logs WHERE date IN ({qmarks}) GROUP BY date", dates
    ).fetchall()
    meals_by_day = {r["date"]: r["c"] for r in meal_rows}

    water_rows = conn.execute(
        f"SELECT date, COUNT(*) c FROM water_logs WHERE date IN ({qmarks}) GROUP BY date", dates
    ).fetchall()
    water_by_day = {r["date"]: r["c"] for r in water_rows}

    workouts = conn.execute(
        f"SELECT COUNT(DISTINCT date) c FROM workout_logs WHERE date IN ({qmarks})", dates
    ).fetchone()["c"]

    days_with_data = len(set(
        [r["date"] for r in sleep_rows]
        + list(meals_by_day) + list(water_by_day)
    ))

    full_meal_days = sum(1 for c in meals_by_day.values() if c >= 3)

    return {
        "sleep_avg":      round(sum(sleep_hours) / len(sleep_hours), 1) if sleep_hours else 0.0,
        "sleep_days":     len(sleep_hours),
        "meals_total":    sum(meals_by_day.values()),
        "meals_avg":      round(sum(meals_by_day.values()) / max(len(dates), 1), 1),
        "full_meal_days": full_meal_days,
        "water_avg":      round(sum(water_by_day.values()) / max(len(dates), 1), 1),
        "workouts":       workouts,
        "days_with_data": days_with_data,
    }


def _grade(pct: float) -> str:
    scale = [(97, "A+"), (93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"),
             (77, "C+"), (73, "C"), (70, "C-"), (60, "D")]
    for cutoff, g in scale:
        if pct >= cutoff:
            return g
    return "F"


def _trend(cur: float, prev: float, unit: str = "", invert: bool = False) -> str:
    diff = round(cur - prev, 1)
    if abs(diff) < 0.05:
        return "Same as last week"
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff}{unit} vs last week"


def _overall_score(agg: dict) -> int:
    sleep_pct   = min(1.0, agg["sleep_avg"] / SLEEP_TARGET)
    meal_pct    = min(1.0, agg["meals_total"] / 21)
    workout_pct = min(1.0, agg["workouts"] / WORKOUT_GOAL)
    water_pct   = min(1.0, agg["water_avg"] / WATER_GOAL)
    return round(sleep_pct * 40 + meal_pct * 30 + workout_pct * 20 + water_pct * 10)


# ── "One thing to improve" (Haiku, cached 6h, never fails) ───────────────────

_improve_cache: dict = {"text": None, "ts": 0}
IMPROVE_TTL = 6 * 3600


def _heuristic_improve(cur: dict) -> str:
    if cur["sleep_avg"] < SLEEP_TARGET - 1:
        return f"😴 Sleep avg is {cur['sleep_avg']}h — protect a {SLEEP_TARGET}h window every night this week."
    if cur["full_meal_days"] < 4:
        return f"🍽️ Only {cur['full_meal_days']}/7 days hit all 3 meals — prep Sunday, eat Sunday."
    if cur["workouts"] < WORKOUT_GOAL:
        return f"💪 {cur['workouts']}/{WORKOUT_GOAL} workouts — schedule the missing sessions as calendar blocks."
    if cur["water_avg"] < WATER_GOAL:
        return f"💧 Water avg {cur['water_avg']}/{WATER_GOAL} glasses — keep a bottle on the desk."
    return "🏆 All systems green — raise one target next week."


def _generate_improve(cur: dict, prev: dict) -> str:
    if _improve_cache["text"] and (time.time() - _improve_cache["ts"] < IMPROVE_TTL):
        return _improve_cache["text"]
    text = None
    try:
        import anthropic
        client = anthropic.Anthropic()
        model = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")
        msg = client.messages.create(
            model=model,
            max_tokens=120,
            messages=[{
                "role": "user",
                "content": (
                    "You are NickOS, Nick's personal OS. Given this week's health stats vs last week, "
                    "pick the ONE highest-leverage thing to improve and say it in one direct, specific, "
                    "actionable sentence. Start with one emoji. No preamble.\n"
                    f"This week: {cur}\nLast week: {prev}\n"
                    f"Targets: sleep {SLEEP_TARGET}h/night, 3 meals/day, {WORKOUT_GOAL} workouts, {WATER_GOAL} glasses water/day."
                ),
            }],
        )
        text = msg.content[0].text.strip()
    except Exception:
        pass
    if not text:
        text = _heuristic_improve(cur)
    _improve_cache["text"] = text
    _improve_cache["ts"] = time.time()
    return text


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/weekly")
def get_weekly():
    now   = datetime.now(ET)
    today = now.date()

    # Week starts Monday
    week_start      = today - timedelta(days=today.weekday())
    last_week_start = week_start - timedelta(days=7)

    this_week_dates = _day_range(week_start, 7)
    last_week_dates = _day_range(last_week_start, 7)

    with get_conn() as conn:
        cur  = _week_aggregates(conn, this_week_dates)
        prev = _week_aggregates(conn, last_week_dates)

        # ── 30-day sleep trend ───────────────────────────────────────────
        sleep_trend = []
        for i in range(29, -1, -1):
            d   = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            row = conn.execute("SELECT hours FROM sleep_logs WHERE date = ?", (d,)).fetchone()
            sleep_trend.append({
                "date":  d,
                "day":   (today - timedelta(days=i)).strftime("%-m/%-d"),
                "hours": float(row["hours"]) if row else 0.0,
            })

        # ── Meal consistency, last 30 days ───────────────────────────────
        d30 = _day_range(today - timedelta(days=29), 30)
        qmarks = ",".join("?" * len(d30))
        meal_rows = conn.execute(
            f"SELECT date, COUNT(*) c FROM meal_logs WHERE date IN ({qmarks}) GROUP BY date", d30
        ).fetchall()
        days_logged    = len(meal_rows)
        three_meal_days = sum(1 for r in meal_rows if r["c"] >= 3)
        meal_consistency = {
            "pct":           round(three_meal_days / max(days_logged, 1) * 100),
            "threeMealDays": three_meal_days,
            "daysLogged":    days_logged,
            "byDay": [
                {"date": d, "day": datetime.strptime(d, "%Y-%m-%d").strftime("%-m/%-d"),
                 "meals": next((r["c"] for r in meal_rows if r["date"] == d), 0)}
                for d in d30
            ],
        }

        # ── 5-week overall score trend ───────────────────────────────────
        trend_chart = []
        for w in range(4, -1, -1):
            ws = week_start - timedelta(days=7 * w)
            agg = _week_aggregates(conn, _day_range(ws, 7))
            trend_chart.append({
                "week":  ws.strftime("%-m/%-d"),
                "score": _overall_score(agg),
            })

        # ── Focus sessions this week ─────────────────────────────────────
        qm7 = ",".join("?" * 7)
        focus_count = conn.execute(
            f"SELECT COUNT(*) c FROM focus_logs WHERE date IN ({qm7})", this_week_dates
        ).fetchone()["c"]
        focus_minutes = conn.execute(
            f"SELECT COALESCE(SUM(minutes),0) m FROM focus_logs WHERE date IN ({qm7})", this_week_dates
        ).fetchone()["m"]

    # ── Report card ──────────────────────────────────────────────────────
    cur_score, prev_score = _overall_score(cur), _overall_score(prev)
    report_card = {
        "sleep": {
            "grade": _grade(min(100, cur["sleep_avg"] / SLEEP_TARGET * 100)),
            "avg":   cur["sleep_avg"],
            "trend": _trend(cur["sleep_avg"], prev["sleep_avg"], "h"),
        },
        "meals": {
            "grade": _grade(min(100, cur["meals_avg"] / 3 * 100)),
            "avg":   f"{cur['meals_avg']}/3",
            "trend": _trend(cur["meals_avg"], prev["meals_avg"]),
        },
        "water": {
            "grade": _grade(min(100, cur["water_avg"] / WATER_GOAL * 100)),
            "avg":   f"{cur['water_avg']} glasses",
            "trend": _trend(cur["water_avg"], prev["water_avg"]),
        },
        "workout": {
            "grade": _grade(min(100, cur["workouts"] / WORKOUT_GOAL * 100)),
            "done":  cur["workouts"],
            "goal":  WORKOUT_GOAL,
            "trend": _trend(cur["workouts"], prev["workouts"]),
        },
        "overall": {
            "grade": _grade(cur_score),
            "score": cur_score,
            "trend": _trend(cur_score, prev_score, " pts"),
        },
    }

    # ── Goals burndown ───────────────────────────────────────────────────
    goals = get_goals()
    goals_summary = {
        "total":  len(goals),
        "done":   sum(1 for g in goals if g.get("done")),
        "active": [g for g in goals if not g.get("done")][:5],
    }

    week_label = f"Week of {week_start.strftime('%b %-d')} – {(week_start + timedelta(days=6)).strftime('%b %-d')}"

    return {
        "weekLabel":          week_label,
        "reportCard":         report_card,
        "oneThingToImprove":  _generate_improve(cur, prev),
        "sleepTrend":         sleep_trend,
        "mealConsistency":    meal_consistency,
        "workoutFreq": {
            "thisWeek": cur["workouts"],
            "lastWeek": prev["workouts"],
            "goal":     WORKOUT_GOAL,
        },
        "focus": {
            "sessions": focus_count,
            "minutes":  focus_minutes,
        },
        "goals":      goals_summary,
        "trendChart": trend_chart,
    }
