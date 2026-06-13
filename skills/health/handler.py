"""
skills/health/handler.py
Commands: /slept, /ate, /water, /workout, /health
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime

from bot.utils import (
    ET, today_str, append_daily_log,
    get_sleep_streak, update_memory_field, MEMORY_FILE,
    SLEEP_TARGET, WATER_GOAL, WORKOUT_DAYS, WORKOUT_PLAN,
    get_water_today, log_water_glass,
    now_et, get_meals_today, get_workout_this_week, get_weekly_stats,
)

import re


# ── /slept ────────────────────────────────────────────────────────────────────
async def slept_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "😴 How many hours did you sleep?\n"
            "Usage: <code>/slept 7.5</code>",
            parse_mode=ParseMode.HTML
        )
        return
    try:
        hours = float(args[0])
    except ValueError:
        await update.message.reply_text(
            "⚠️ Give me a number. e.g. <code>/slept 7.5</code>",
            parse_mode=ParseMode.HTML
        )
        return

    timestamp = datetime.now(ET).strftime("%H:%M")
    append_daily_log("Health", f"Sleep: {hours}h (logged {timestamp} ET)")

    if MEMORY_FILE.exists():
        text = MEMORY_FILE.read_text()
        text = re.sub(
            r"- Last logged sleep: `.+`.*",
            f"- Last logged sleep: `{hours}h` on {today_str()}",
            text
        )
        MEMORY_FILE.write_text(text)

    if hours >= SLEEP_TARGET:
        msg = (
            f"✅ <b>{hours}h. That's what I'm talking about.</b>\n"
            f"Hit your {SLEEP_TARGET}h target. Keep this up — it's the foundation. 💪"
        )
    elif hours >= 6:
        msg = (
            f"😐 <b>{hours}h. Under target.</b>\n"
            f"You need {SLEEP_TARGET}h. Don't let this slide two nights in a row."
        )
    else:
        msg = (
            f"🔴 <b>{hours}h. That's bad, Nick.</b>\n"
            f"Running on fumes degrades everything. In bed by midnight TONIGHT — no excuses."
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ── /ate ──────────────────────────────────────────────────────────────────────
VALID_MEALS = {"breakfast", "lunch", "dinner", "snack"}

async def ate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "🍽 What did you eat?\n"
            "Usage: <code>/ate breakfast</code> or <code>/ate lunch chicken rice</code>",
            parse_mode=ParseMode.HTML
        )
        return

    meal_type = args[0].lower()
    note      = " ".join(args[1:]) if len(args) > 1 else ""
    timestamp = datetime.now(ET).strftime("%H:%M")
    label     = meal_type.capitalize() + (f" — {note}" if note else "")

    append_daily_log("Health", f"Meal: {label} (logged {timestamp} ET)")

    if MEMORY_FILE.exists():
        text = MEMORY_FILE.read_text()
        m = re.search(r"Meals today: (\d+)/3", text)
        if m:
            new_count = min(int(m.group(1)) + 1, 3)
            text = re.sub(r"Meals today: \d+/3", f"Meals today: {new_count}/3", text)
            MEMORY_FILE.write_text(text)

    meal_emojis = {"breakfast": "🌅", "lunch": "☀️", "dinner": "🌙", "snack": "🍎"}
    emoji = meal_emojis.get(meal_type, "🍽")
    msg   = f"{emoji} <b>{label}</b> logged at {timestamp}."
    if meal_type not in VALID_MEALS:
        msg += "\n<i>(Tip: use breakfast/lunch/dinner/snack for tracking)</i>"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ── /water ────────────────────────────────────────────────────────────────────
async def water_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total     = log_water_glass()
    remaining = max(0, WATER_GOAL - total)

    if total >= WATER_GOAL:
        msg = f"💧 <b>Glass #{total} — goal hit!</b>\n8/8 glasses today. You're actually doing it."
    elif remaining == 1:
        msg = f"💧 <b>Glass #{total}/{WATER_GOAL}</b>\nOne more and you're done. Go drink it."
    else:
        msg = (
            f"💧 <b>Glass #{total}/{WATER_GOAL}</b>\n"
            f"{remaining} more to go. You're a smoker — water is non-negotiable."
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ── /workout ──────────────────────────────────────────────────────────────────
async def workout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now     = datetime.now(ET)
    weekday = now.strftime("%A")
    timestamp = now.strftime("%H:%M")
    plan    = WORKOUT_PLAN.get(weekday)
    log_line = f"Workout done: {plan} ({timestamp} ET)" if plan else f"Workout done: rest day session ({timestamp} ET)"
    append_daily_log("Health", log_line)

    if MEMORY_FILE.exists():
        text = MEMORY_FILE.read_text()
        m = re.search(r"This week: (\d+)/5", text)
        if m:
            new_count = min(int(m.group(1)) + 1, 5)
            text = re.sub(r"This week: \d+/5", f"This week: {new_count}/5", text)
            MEMORY_FILE.write_text(text)

    if weekday in WORKOUT_DAYS:
        msg = f"💪 <b>Workout logged — {weekday}.</b>\n<i>{plan}</i>\nThat's how it's done. Don't miss tomorrow."
    else:
        msg = "🔥 <b>Rest day workout logged.</b>\nWasn't even scheduled. That's the mindset."
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ── /health ───────────────────────────────────────────────────────────────────
async def health_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats   = get_weekly_stats()
    now     = now_et()
    weekday = now.strftime("%A")
    water_today = get_water_today()

    sleep_avg = stats["sleep_avg"]
    water_avg = stats["water_avg"]
    workouts  = stats["workouts"]
    meals     = stats["meals_total"]
    expected  = stats["days_counted"] * 3

    sleep_icon   = "✅" if sleep_avg >= SLEEP_TARGET else ("😐" if sleep_avg >= 6.5 else "🔴")
    water_icon   = "✅" if water_avg >= WATER_GOAL   else ("😐" if water_avg >= 5   else "🔴")
    workout_icon = "✅" if workouts  >= 5            else ("😐" if workouts  >= 3   else "🔴")
    meal_icon    = "✅" if meals >= expected * 0.9   else ("😐" if meals >= expected * 0.6 else "🔴")

    score  = min(25, int((sleep_avg / SLEEP_TARGET)      * 25))
    score += min(25, int((water_avg / WATER_GOAL)        * 25))
    score += min(25, int((workouts  / 5)                 * 25))
    score += min(25, int((meals     / max(expected, 1))  * 25))

    if score >= 85:   score_label = "🔥 Locked in"
    elif score >= 65: score_label = "👍 Decent"
    elif score >= 45: score_label = "⚠️ Slipping"
    else:             score_label = "🚨 Fix this now"

    msg = (
        f"📊 <b>Weekly Health Report</b>\n"
        f"<i>{stats['days_counted']} days logged</i>\n\n"
        f"{sleep_icon} <b>Sleep avg:</b> {sleep_avg}h (target: {SLEEP_TARGET}h)\n"
        f"{water_icon} <b>Water avg:</b> {water_avg}/day (today: {water_today}/8)\n"
        f"{meal_icon} <b>Meals:</b> {meals}/{expected} logged\n"
        f"{workout_icon} <b>Workouts:</b> {workouts}/5 this week\n\n"
        f"<b>Health Score: {score}/100</b> — {score_label}"
    )
    if weekday in WORKOUT_DAYS:
        plan = WORKOUT_PLAN.get(weekday, "")
        msg += f"\n\n<b>Today:</b> <i>{plan}</i>"

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
