"""
bot/handlers/health.py
Commands: /slept, /ate, /water, /workout
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
)

import re


# ── /slept ────────────────────────────────────────────────────────────────────
async def slept_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /slept [hours]
    Examples: /slept 7.5   /slept 8
    """
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
    """
    /ate [meal] [optional note]
    Examples: /ate breakfast   /ate lunch chicken and rice
    """
    args = context.args

    if not args:
        await update.message.reply_text(
            "🍽 What did you eat?\n"
            "Usage: <code>/ate breakfast</code> or <code>/ate lunch chicken rice</code>",
            parse_mode=ParseMode.HTML
        )
        return

    meal_type = args[0].lower()
    note = " ".join(args[1:]) if len(args) > 1 else ""
    timestamp = datetime.now(ET).strftime("%H:%M")

    label = meal_type.capitalize()
    if note:
        label += f" — {note}"

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

    msg = f"{emoji} <b>{label}</b> logged at {timestamp}."
    if meal_type not in VALID_MEALS:
        msg += "\n<i>(Tip: use breakfast/lunch/dinner/snack for tracking)</i>"

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ── /water ────────────────────────────────────────────────────────────────────
async def water_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /water — log one glass of water (+1 toward 8/day goal)
    """
    total = log_water_glass()
    remaining = max(0, WATER_GOAL - total)

    if total >= WATER_GOAL:
        msg = (
            f"💧 <b>Glass #{total} — goal hit!</b>\n"
            f"8/8 glasses today. You're actually doing it."
        )
    elif remaining == 1:
        msg = (
            f"💧 <b>Glass #{total}/{WATER_GOAL}</b>\n"
            f"One more and you're done. Go drink it."
        )
    else:
        msg = (
            f"💧 <b>Glass #{total}/{WATER_GOAL}</b>\n"
            f"{remaining} more to go. You're a smoker — water is non-negotiable."
        )

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ── /workout ──────────────────────────────────────────────────────────────────
async def workout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /workout — log today's workout as done
    """
    now     = datetime.now(ET)
    weekday = now.strftime("%A")
    timestamp = now.strftime("%H:%M")

    # Determine plan for today
    plan = WORKOUT_PLAN.get(weekday)

    # Log it
    if plan:
        log_line = f"Workout done: {plan} ({timestamp} ET)"
    else:
        log_line = f"Workout done: rest day session ({timestamp} ET)"

    append_daily_log("Health", log_line)

    # Update MEMORY.md workout count
    if MEMORY_FILE.exists():
        text = MEMORY_FILE.read_text()
        m = re.search(r"This week: (\d+)/5", text)
        if m:
            new_count = min(int(m.group(1)) + 1, 5)
            text = re.sub(r"This week: \d+/5", f"This week: {new_count}/5", text)
            MEMORY_FILE.write_text(text)

    if weekday in WORKOUT_DAYS:
        msg = (
            f"💪 <b>Workout logged — {weekday}.</b>\n"
            f"<i>{plan}</i>\n"
            f"That's how it's done. Don't miss tomorrow."
        )
    else:
        # Rest day but they still worked out — bonus
        msg = (
            f"🔥 <b>Rest day workout logged.</b>\n"
            f"Wasn't even scheduled. That's the mindset."
        )

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
