"""
skills/schedule/handler.py
Commands: /schedule, /nudge
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.utils import (
    ET, now_et, today_str, WORKOUT_DAYS, WORKOUT_PLAN,
    get_water_today, get_sleep_streak, get_meals_today,
    get_workout_this_week,
)


# ── Full daily nudge schedule ─────────────────────────────────────────────────
DAILY_SCHEDULE = [
    ("08:00", "⏰ Wake up nudge"),
    ("09:00", "🌅 Breakfast reminder"),
    ("09:30", "💧 Water nudge #1"),
    ("11:00", "💧 Water nudge #2"),
    ("12:00", "🕛 Midday check-in"),
    ("13:00", "💧 Water nudge #3"),
    ("14:00", "☀️ Lunch reminder"),
    ("15:00", "💧 Water nudge #4"),
    ("16:00", "⚡ Afternoon reset"),
    ("17:00", "💧 Water nudge #5"),
    ("18:00", "💪 Workout nudge (workout days only)"),
    ("19:00", "🌙 Dinner reminder"),
    ("20:00", "💧 Water nudge #6"),
    ("21:00", "🔥 Evening accountability"),
    ("22:00", "💧 Water nudge #7"),
    ("23:00", "🌙 Wind-down nudge"),
    ("00:30", "😴 Late-night check"),
]


# ── /schedule ─────────────────────────────────────────────────────────────────
async def schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now          = now_et()
    weekday      = now.strftime("%A")
    current_time = now.strftime("%H:%M")

    lines      = []
    past_count = 0

    for time_str, label in DAILY_SCHEDULE:
        if "Workout nudge" in label and weekday not in WORKOUT_DAYS:
            continue
        if time_str > current_time:
            lines.append(f"  {time_str} — {label}")
        else:
            past_count += 1

    workout_note = ""
    if weekday in WORKOUT_DAYS:
        plan = WORKOUT_PLAN.get(weekday, "")
        workout_note = f"\n\n<b>💪 Today's workout:</b> <i>{plan}</i>"

    if lines:
        msg = (
            f"📅 <b>Today's Remaining Schedule</b>\n"
            f"<i>{weekday}, {today_str()} — {past_count} nudges already sent</i>\n\n"
            + "\n".join(lines)
            + workout_note
        )
    else:
        msg = (
            f"✅ <b>All nudges sent for today.</b>\n"
            f"Last one was bedtime. You going to bed on time tonight?"
            + workout_note
        )

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ── /nudge ────────────────────────────────────────────────────────────────────
async def nudge_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import os
    import anthropic
    from dotenv import load_dotenv
    load_dotenv()

    now      = now_et()
    weekday  = now.strftime("%A")
    water    = get_water_today()
    meals    = get_meals_today()
    workouts = get_workout_this_week()
    sleep    = get_sleep_streak()

    prompt = (
        f"You are NickOS — Nick's personal AI operating system. Aggressive tough-love tone. Short. Direct.\n\n"
        f"Current status:\n"
        f"- Time: {now.strftime('%I:%M %p ET')}, {weekday}\n"
        f"- Water today: {water}/8 glasses\n"
        f"- Meals today: {meals}\n"
        f"- Workouts this week: {workouts}/5\n"
        f"- Sleep streak: {sleep} days\n"
        f"- Today is {'a workout day' if weekday in WORKOUT_DAYS else 'a rest day'}\n\n"
        f"Give Nick a 2-3 line status check nudge. Start with an emoji. "
        f"Call out whatever is most behind. Tough love, no softening. "
        f"End with one specific action he should do RIGHT NOW."
    )

    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp   = client.messages.create(
            model=os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=150,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        nudge_text = resp.content[0].text.strip()
    except Exception:
        nudge_text = (
            f"⚡ <b>Status check:</b>\n"
            f"Water: {water}/8 | Meals: {meals} | Workouts: {workouts}/5\n"
            f"Pick the worst number and fix it right now."
        )

    await update.message.reply_text(nudge_text, parse_mode=ParseMode.HTML)
