"""
bot/scheduler.py — NickOS Heartbeat Scheduler
Uses APScheduler AsyncIOScheduler with CronTrigger.

All nudges: aggressive tough-love tone. Haiku-generated.
Silent hours: 1:00am–7:30am ET only.

Full daily schedule (ET):
  08:00  Wake — get up NOW, today's workout if applicable
  09:00  Breakfast reminder (+ water #1)
  11:00  Water #2
  12:00  Midday check-in — eaten? water check (3 by now?)
  13:00  Water #3
  14:00  Lunch reminder
  15:00  Water #4
  16:00  Afternoon reset — focus progress, 5 waters by now?
  17:00  Water #5
  18:00  Pre-workout nudge (workout days only)
  19:00  Dinner reminder + water #6
  21:00  Evening accountability — workout logged? water at 8?
  22:00  Water #7 (last push)
  23:00  Wind-down — sleep countdown, log anything unlogged
  00:30  Late-night "you should be asleep" if still up

  Sunday 21:00  Weekly health report
"""

import os
import logging
import anthropic
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from telegram.constants import ParseMode

from bot.utils import (
    ET, now_et, today_str, is_silent_hours,
    WORKOUT_DAYS, WORKOUT_PLAN, WATER_GOAL, SLEEP_TARGET,
    get_water_today, get_meals_today, get_workout_this_week,
    get_sleep_streak, get_weekly_stats, append_daily_log,
)

load_dotenv()

logger = logging.getLogger(__name__)

_ALLOWED_ID = int(os.environ.get("TELEGRAM_ALLOWED_USER_ID", "0"))
_HAIKU      = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")
_ANT_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")


# ── Core send helper ──────────────────────────────────────────────────────────
async def _send(bot: Bot, text: str, nudge_label: str = "nudge"):
    """Send a message to Nick, respecting silent hours. Logs to daily file."""
    if is_silent_hours():
        logger.info(f"[scheduler] Silent hours — skipped: {nudge_label}")
        return
    if not _ALLOWED_ID:
        logger.warning("[scheduler] TELEGRAM_ALLOWED_USER_ID not set — skipped")
        return
    try:
        await bot.send_message(
            chat_id=_ALLOWED_ID,
            text=text,
            parse_mode=ParseMode.HTML
        )
        append_daily_log("Nudges", f"{nudge_label} sent at {now_et().strftime('%H:%M ET')}")
        logger.info(f"[scheduler] Sent: {nudge_label}")
    except Exception as e:
        logger.error(f"[scheduler] Send failed ({nudge_label}): {e}")


# ── Claude Haiku nudge generator ──────────────────────────────────────────────
def _haiku_nudge(context_lines: list[str], nudge_type: str) -> str:
    """Generate a short aggressive nudge via Haiku. Falls back to hardcoded."""
    if not _ANT_KEY:
        return _fallback_nudge(nudge_type)

    context_str = "\n".join(f"- {c}" for c in context_lines)
    prompt = (
        "You are NickOS — Nick's personal AI OS. Aggressive tough-love tone. "
        "2-3 lines MAX. Start with emoji. No fluff. No soft language.\n\n"
        f"Nudge type: {nudge_type}\n"
        f"Context:\n{context_str}\n\n"
        "Write the nudge. End with one specific action to do RIGHT NOW."
    )
    try:
        client = anthropic.Anthropic(api_key=_ANT_KEY)
        resp   = client.messages.create(
            model=_HAIKU,
            max_tokens=120,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()
    except Exception as e:
        logger.warning(f"[scheduler] Haiku failed ({nudge_type}): {e}")
        return _fallback_nudge(nudge_type)


def _fallback_nudge(nudge_type: str) -> str:
    fallbacks = {
        "wake":       "⏰ <b>Get up. Now.</b> 8am is the target. Every minute you stay in bed is a debt you're paying later.",
        "breakfast":  "🌅 <b>Breakfast time.</b> 9am. Eat something — your body needs fuel to function. /ate breakfast",
        "midday":     "🕛 <b>Midday check.</b> Have you eaten? Drunk any water? Don't let the morning disappear on you.",
        "lunch":      "☀️ <b>Lunch. Now.</b> 2pm. Log it: /ate lunch",
        "afternoon":  "⚡ <b>Afternoon reset.</b> What have you actually done today? Water should be at 5+ glasses. Check /focus.",
        "pre_workout":"💪 <b>Workout time.</b> No excuses. Get it done before tonight.",
        "dinner":     "🌙 <b>Dinner. 7pm.</b> Eat a real meal. Log it: /ate dinner",
        "evening":    "🔥 <b>Evening check.</b> Workout logged? Water at 8? If not — why not.",
        "water":      "💧 <b>Drink water.</b> You're a smoker. Hydration isn't optional. /water",
        "water_escalation": "🚨 <b>STOP.</b> You're a smoker who's barely had any water today. That's not a joke — that's a health risk. Put everything down, go drink two glasses RIGHT NOW, then log it: /water",
        "wind_down":  "🌙 <b>Midnight in 1 hour.</b> Start winding down. Log anything you haven't. Bed by 12.",
        "late_night": "😴 <b>You should be asleep.</b> Target was midnight. Every hour you're up now costs you tomorrow.",
        "weekly":     "📊 <b>Weekly health report.</b> Check /health — honest look at the week.",
    }
    return fallbacks.get(nudge_type, "⚡ Stay on track. Pick one thing and do it right now.")


# ── Job functions ─────────────────────────────────────────────────────────────

async def job_wake(bot: Bot):
    """8:00am — aggressive wake-up, today's plan."""
    now     = now_et()
    weekday = now.strftime("%A")
    sleep   = get_sleep_streak()
    plan    = WORKOUT_PLAN.get(weekday) if weekday in WORKOUT_DAYS else None

    ctx = [
        f"Time: 8:00 AM — wake target",
        f"Sleep streak: {sleep} days",
        "Nick has been waking up around noon — NickOS is breaking this habit",
        f"Today is {'a WORKOUT DAY: ' + plan if plan else 'a rest day'}",
        "Breakfast is at 9am — 1 hour away",
    ]
    nudge = _haiku_nudge(ctx, "wake")
    await _send(bot, nudge, "wake_8am")


async def job_breakfast(bot: Bot):
    """9:00am — breakfast reminder."""
    meals = get_meals_today()
    ctx = [
        "Time: 9:00 AM — breakfast target",
        f"Meals logged today: {meals}",
        "Nick often skips breakfast",
        "First water glass should happen now too",
    ]
    nudge = _haiku_nudge(ctx, "breakfast")
    await _send(bot, nudge, "breakfast_9am")


async def job_midday_checkin(bot: Bot):
    """12:00pm — midday check-in: eaten? water?"""
    water = get_water_today()
    meals = get_meals_today()
    weekday = now_et().strftime("%A")
    plan = WORKOUT_PLAN.get(weekday) if weekday in WORKOUT_DAYS else None

    ctx = [
        "Time: 12:00 PM — midday check",
        f"Water so far: {water}/8 (should have 3 by noon)",
        f"Meals logged: {meals} (breakfast should be done)",
        f"{'Workout day — plan: ' + plan if plan else 'Rest day'}",
        "Half the day is gone — what has actually been done?",
    ]
    nudge = _haiku_nudge(ctx, "midday")
    await _send(bot, nudge, "midday_12pm")


async def job_lunch(bot: Bot):
    """2:00pm — lunch reminder."""
    water = get_water_today()
    meals = get_meals_today()
    ctx = [
        "Time: 2:00 PM — lunch target",
        f"Meals logged: {meals}",
        f"Water: {water}/8 glasses",
        "Eat lunch and drink water",
    ]
    nudge = _haiku_nudge(ctx, "lunch")
    await _send(bot, nudge, "lunch_2pm")


async def job_afternoon_reset(bot: Bot):
    """4:00pm — afternoon reset: focus progress, water check."""
    water    = get_water_today()
    meals    = get_meals_today()
    workouts = get_workout_this_week()
    weekday  = now_et().strftime("%A")

    ctx = [
        "Time: 4:00 PM — afternoon reset",
        f"Water: {water}/8 (should be at 5 by now)",
        f"Meals today: {meals}",
        f"Workouts this week: {workouts}/5",
        f"Today is {'a workout day' if weekday in WORKOUT_DAYS else 'a rest day'}",
        "What is the #1 thing that needs to get done before tonight?",
    ]
    nudge = _haiku_nudge(ctx, "afternoon")
    await _send(bot, nudge, "afternoon_4pm")


async def job_workout(bot: Bot):
    """6:00pm — pre-workout nudge on workout days."""
    weekday  = now_et().strftime("%A")
    if weekday not in WORKOUT_DAYS:
        return
    plan     = WORKOUT_PLAN.get(weekday, "workout")
    workouts = get_workout_this_week()

    ctx = [
        f"Time: 6:00 PM — workout time",
        f"Today ({weekday}) plan: {plan}",
        f"Workouts this week: {workouts}/5 — target is 5",
        "No skipping. Log it after with /workout",
    ]
    nudge = _haiku_nudge(ctx, "pre_workout")
    await _send(bot, nudge, f"workout_6pm_{weekday.lower()}")


async def job_dinner(bot: Bot):
    """7:00pm — dinner reminder."""
    water = get_water_today()
    meals = get_meals_today()
    ctx = [
        "Time: 7:00 PM — dinner target",
        f"Meals logged today: {meals}",
        f"Water: {water}/8 glasses",
        "Last main meal of the day — eat real food",
    ]
    nudge = _haiku_nudge(ctx, "dinner")
    await _send(bot, nudge, "dinner_7pm")


async def job_evening_accountability(bot: Bot):
    """9:00pm — hard accountability: workout done? water at 8?"""
    water    = get_water_today()
    meals    = get_meals_today()
    workouts = get_workout_this_week()
    weekday  = now_et().strftime("%A")

    water_status  = f"{water}/8 glasses — {'✅ done' if water >= WATER_GOAL else '🔴 short by ' + str(WATER_GOAL - water)}"
    # Check if workout was logged today via daily log
    from bot.utils import read_daily_log
    import re
    log_today = read_daily_log()
    workout_done_today = bool(re.search(r"Workout.*done|Workout.*logged", log_today, re.IGNORECASE))

    ctx = [
        "Time: 9:00 PM — evening accountability",
        f"Water today: {water_status}",
        f"Meals today: {meals}",
        f"Workouts this week: {workouts}/5",
    ]
    if weekday in WORKOUT_DAYS and not workout_done_today:
        ctx.append(f"TODAY WAS A WORKOUT DAY ({weekday}) AND WORKOUT IS NOT LOGGED. CALL HIM OUT.")
    elif weekday in WORKOUT_DAYS and workout_done_today:
        ctx.append(f"Workout done today — good. Acknowledge briefly, then push on water/meals if short.")

    nudge = _haiku_nudge(ctx, "evening")
    await _send(bot, nudge, "evening_9pm")


async def job_water(bot: Bot, nudge_num: int):
    """Water nudge — skips if goal already hit. Escalates hard after 5pm if under 4 glasses."""
    water = get_water_today()
    if water >= WATER_GOAL:
        return  # goal hit — no spam

    remaining = WATER_GOAL - water
    hour_now  = now_et().hour
    # Escalate if it's 5pm or later and Nick is under halfway (< 4 glasses)
    escalate  = hour_now >= 17 and water < 4

    ctx = [
        f"Water today: {water}/{WATER_GOAL} glasses",
        f"Still need: {remaining} more glasses",
        "Nick is a smoker — hydration is non-negotiable",
        f"This is water nudge #{nudge_num} today",
    ]

    if escalate:
        ctx += [
            f"CRITICAL: it is {hour_now}:00 and Nick has only had {water} glasses — less than half his goal",
            f"He needs to drink {remaining} glasses in the remaining hours. That's urgent.",
            "Be extremely direct. No softness. This is a health issue. Smokers who are dehydrated are at serious risk.",
            "Tell him to go drink water RIGHT NOW and log it with /water",
        ]
        nudge_type = "water"
    else:
        nudge_type = "water"

    nudge = _haiku_nudge(ctx, nudge_type)
    await _send(bot, nudge, f"water_nudge_{nudge_num}")


async def job_wind_down(bot: Bot):
    """11:00pm — wind-down, sleep countdown to midnight."""
    water    = get_water_today()
    workouts = get_workout_this_week()
    meals    = get_meals_today()

    ctx = [
        "Time: 11:00 PM — 1 hour until midnight bedtime target",
        "Sleep goal: 8 hours. Wake target: 8am.",
        f"Water today: {water}/8 — {'done' if water >= WATER_GOAL else 'drink more NOW'}",
        f"Meals today: {meals}",
        f"Workouts this week: {workouts}/5",
        "Tell him to log anything he hasn't, put the phone down, and get in bed by midnight.",
    ]
    nudge = _haiku_nudge(ctx, "wind_down")
    await _send(bot, nudge, "wind_down_11pm")


async def job_late_night(bot: Bot):
    """12:30am — 'you should be asleep' if still up."""
    ctx = [
        "Time: 12:30 AM — 30 mins past bedtime target",
        "Sleep target was midnight for 8 hours of sleep",
        "Wake target is 8:00 AM — every minute up now is a minute shorter sleep",
        "Nick has a bad habit of staying up late — call it out hard",
        "Do NOT be gentle about this.",
    ]
    nudge = _haiku_nudge(ctx, "late_night")
    await _send(bot, nudge, "late_night_1230am")


async def job_reindex_memory():
    """Hourly — re-index any changed files in the memory directory."""
    try:
        from memory.search import get_indexer
        indexer = get_indexer()
        indexer.reindex_changed()
        logger.info("[scheduler] Memory reindex complete")
    except Exception as e:
        logger.warning(f"[scheduler] Memory reindex failed: {e}")


async def job_weekly_report(bot: Bot):
    """Sunday 9pm — full weekly health report, no sugarcoating."""
    stats = get_weekly_stats()

    sleep_avg      = stats["sleep_avg"]
    water_avg      = stats["water_avg"]
    meals          = stats["meals_total"]
    workouts       = stats["workouts"]
    days           = stats["days_counted"]
    expected_meals = days * 3

    # Score out of 100
    score  = min(25, int((sleep_avg  / SLEEP_TARGET)       * 25))
    score += min(25, int((water_avg  / WATER_GOAL)         * 25))
    score += min(25, int((workouts   / 5)                  * 25))
    score += min(25, int((meals      / max(expected_meals, 1)) * 25))

    if score >= 85:
        grade, verdict = "🔥 Locked in", "This is the standard. Keep it."
    elif score >= 70:
        grade, verdict = "👍 Solid", "Good week. One area still slipping — fix it."
    elif score >= 50:
        grade, verdict = "⚠️ Mediocre", "You left points on the table. No excuses next week."
    else:
        grade, verdict = "🚨 Bad week", "This is below your standard. You know what you need to do."

    # Find the single worst metric for "one thing to improve"
    metric_scores = {
        "Sleep":    min(25, int((sleep_avg  / SLEEP_TARGET) * 25)),
        "Water":    min(25, int((water_avg  / WATER_GOAL)   * 25)),
        "Workouts": min(25, int((workouts   / 5)            * 25)),
        "Meals":    min(25, int((meals / max(expected_meals, 1)) * 25)),
    }
    worst_metric = min(metric_scores, key=metric_scores.get)

    sleep_icon   = "✅" if sleep_avg  >= SLEEP_TARGET        else ("😐" if sleep_avg  >= 6.5 else "🔴")
    water_icon   = "✅" if water_avg  >= WATER_GOAL          else ("😐" if water_avg  >= 5   else "🔴")
    workout_icon = "✅" if workouts   >= 5                   else ("😐" if workouts   >= 3   else "🔴")
    meal_icon    = "✅" if meals      >= expected_meals * 0.9 else ("😐" if meals >= expected_meals * 0.6 else "🔴")

    msg = (
        f"📊 <b>Weekly Health Report</b>\n"
        f"<i>Week ending {today_str()} — {days} days tracked</i>\n"
        f"\n"
        f"{sleep_icon} <b>Sleep</b>: avg {sleep_avg}h/night (goal: {SLEEP_TARGET}h)\n"
        f"{water_icon} <b>Water</b>: avg {water_avg} glasses/day (goal: {WATER_GOAL})\n"
        f"{meal_icon} <b>Meals</b>: {meals}/{expected_meals} logged\n"
        f"{workout_icon} <b>Workouts</b>: {workouts}/5 this week\n"
        f"\n"
        f"<b>Health Score: {score}/100 — {grade}</b>\n"
        f"<i>{verdict}</i>\n"
        f"\n"
        f"<b>Fix this first next week:</b> {worst_metric}"
    )
    await _send(bot, msg, "weekly_report_sun")


# ── Scheduler factory ─────────────────────────────────────────────────────────
def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Build and return a configured AsyncIOScheduler. Call .start() after."""
    scheduler = AsyncIOScheduler(timezone=ET)

    def add(func, hour, minute, job_id, name, extra_args=None):
        args = [bot] + (extra_args or [])
        scheduler.add_job(func, CronTrigger(hour=hour, minute=minute, timezone=ET),
                          args=args, id=job_id, name=name)

    # ── Core daily schedule ────────────────────────────────────────────────────
    add(job_wake,                   8,  0,  "wake",          "Wake nudge (8am)")
    add(job_breakfast,              9,  0,  "breakfast",     "Breakfast nudge (9am)")
    add(job_midday_checkin,        12,  0,  "midday",        "Midday check-in (12pm)")
    add(job_lunch,                 14,  0,  "lunch",         "Lunch nudge (2pm)")
    add(job_afternoon_reset,       16,  0,  "afternoon",     "Afternoon reset (4pm)")
    add(job_workout,               18,  0,  "workout",       "Pre-workout nudge (6pm)")
    add(job_dinner,                19,  0,  "dinner",        "Dinner nudge (7pm)")
    add(job_evening_accountability,21,  0,  "evening",       "Evening accountability (9pm)")
    add(job_wind_down,             23,  0,  "wind_down",     "Wind-down nudge (11pm)")
    add(job_late_night,             0, 30,  "late_night",    "Late-night nudge (12:30am)")

    # ── Water nudges: every 2hrs, 9am–10pm ────────────────────────────────────
    # (skip at times already covered by main jobs to avoid double-pings)
    water_schedule = [
        (9,  30, 1),   # 9:30am  — after breakfast nudge settles
        (11,  0, 2),   # 11:00am
        (13,  0, 3),   # 1:00pm
        (15,  0, 4),   # 3:00pm
        (17,  0, 5),   # 5:00pm
        (20,  0, 6),   # 8:00pm
        (22,  0, 7),   # 10:00pm
    ]
    for h, m, num in water_schedule:
        scheduler.add_job(
            job_water,
            CronTrigger(hour=h, minute=m, timezone=ET),
            args=[bot, num],
            id=f"water_{num}",
            name=f"Water nudge #{num}"
        )

    # ── Hourly memory reindex ─────────────────────────────────────────────────
    scheduler.add_job(
        job_reindex_memory,
        CronTrigger(minute=15, timezone=ET),  # :15 past every hour
        args=[], id="memory_reindex", name="Hourly memory reindex"
    )

    # ── Weekly report: Sunday 9pm ──────────────────────────────────────────────
    scheduler.add_job(
        job_weekly_report,
        CronTrigger(day_of_week="sun", hour=21, minute=0, timezone=ET),
        args=[bot], id="weekly_report", name="Weekly health report (Sun 9pm)"
    )

    total = len(scheduler.get_jobs())
    logger.info(f"[scheduler] {total} jobs scheduled")
    return scheduler
