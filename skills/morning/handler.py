"""
bot/handlers/morning.py
Command: /morning
Returns a formatted daily brief — HTML parse mode (no escaping headaches).
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime

from bot.utils import (
    ET, today_label,
    get_sleep_streak, get_meals_today, get_workout_this_week,
    get_today_focus, get_active_goals, append_daily_log,
    WORKOUT_DAYS, WORKOUT_PLAN, get_water_today, WATER_GOAL,
)


_FALLBACK_PRIORITIES = [
    "Review algo trading bot — push any pending commits",
    "Check email inbox triage",
    "Work on top active project (see /goal for list)",
]


def _build_brief() -> str:
    now     = datetime.now(ET)
    label   = today_label()
    weekday = now.strftime("%A")

    # ── Health snapshot ───────────────────────────────────────────────────────
    sleep_streak = get_sleep_streak()
    meals_today  = get_meals_today()
    workouts     = get_workout_this_week()
    water_today  = get_water_today()

    if weekday in WORKOUT_DAYS:
        plan = WORKOUT_PLAN.get(weekday, "workout")
        workout_nudge = f"\n<i>💪 Today: {plan}</i>"
    else:
        workout_nudge = ""

    # ── Priorities — today's focus > MEMORY.md goals > static fallback ───────
    stored_focus = get_today_focus()
    if stored_focus and stored_focus != "—" and "Not yet set" not in stored_focus:
        # Focus is set — lead with it, pad with top goals
        goals = get_active_goals(2)
        priorities = [f"🎯 {stored_focus}"] + goals if goals else [stored_focus]
    else:
        # No focus set — pull live goals from MEMORY.md
        priorities = get_active_goals(3) or _FALLBACK_PRIORITIES

    priority_lines = "\n".join(
        f"  {i+1}. {p}" for i, p in enumerate(priorities[:3])
    )

    # ── Assemble (HTML) ───────────────────────────────────────────────────────
    return (
        f"☀️ <b>Good morning, Nick!</b>\n"
        f"<i>{label}</i>\n"
        f"\n"
        f"<b>📊 Health</b>\n"
        f"😴 Sleep streak: <b>{sleep_streak}</b> days\n"
        f"🍽 Meals today: <b>{meals_today}</b>\n"
        f"💧 Water today: <b>{water_today}/{WATER_GOAL}</b> glasses\n"
        f"💪 Workouts this week: <b>{workouts}/5</b>"
        f"{workout_nudge}\n"
        f"\n"
        f"<b>🎯 Top Priorities</b>\n"
        f"{priority_lines}\n"
        f"\n"
        f"<b>⚡ Quick actions</b>\n"
        f"  • /slept [hrs] — log last night's sleep\n"
        f"  • /focus [task] — lock in your #1 thing\n"
        f"  • /email — triage your inbox\n"
        f"\n"
        f"<i>Let's get it. 🚀</i>"
    )


async def morning_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    append_daily_log("Morning Brief", f"Brief sent at {datetime.now(ET).strftime('%H:%M ET')}")
    await update.message.reply_text(_build_brief(), parse_mode=ParseMode.HTML)
