"""
bot/main.py — NickOS Telegram Bot entry point

Run:
    python -m bot.main

Skills are loaded from skills/*/skill.json + skills/*/handler.py at startup.
Adding a new skill folder with skill.json + handler.py is automatically
picked up on next bot start — no changes required here.
"""

import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.auth     import auth_check, guarded
from bot.registry import SkillRegistry
from bot.scheduler import create_scheduler
from bot.utils    import ET

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Load env ──────────────────────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]


# ── /start ────────────────────────────────────────────────────────────────────
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update, context):
        return
    await update.message.reply_text(
        "👋 <b>NickOS online.</b>\n\n"
        "<b>Daily flow:</b>\n"
        "  /morning — start your day\n"
        "  /slept [hrs] — log sleep\n"
        "  /ate [meal] — log a meal\n"
        "  /water — +1 glass toward 8/day\n"
        "  /workout — log workout done\n\n"
        "<b>Work:</b>\n"
        "  /focus [task] — lock in your #1 thing\n"
        "  /done [thing] — log a win\n"
        "  /goal — manage goals\n"
        "  /email — triage inbox\n\n"
        "<b>Stats:</b>\n"
        "  /health — weekly health dashboard\n"
        "  /schedule — today's remaining nudge times\n"
        "  /nudge — get an immediate status check\n"
        "  /reflect — end-of-day reflection + memory search\n\n"
        "<i>Start with /morning</i>",
        parse_mode="HTML",
    )


# ── /remind stub (Phase 5) ────────────────────────────────────────────────────
async def remind_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update, context):
        return
    await update.message.reply_text(
        "⏰ <b>Custom reminders coming in Phase 5.</b>",
        parse_mode="HTML",
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Load all skills ───────────────────────────────────────────────────────
    registry = SkillRegistry()
    registry.load_all()

    # ── Register built-in handlers (not owned by any skill) ───────────────────
    app.add_handler(CommandHandler("start",  start_handler))
    app.add_handler(CommandHandler("remind", remind_handler))

    # ── Register all skill handlers (commands + NLU) ──────────────────────────
    registry.register(app)

    # ── post_init: set command menu + start scheduler ─────────────────────────
    async def post_init(application: Application):
        # Built-in commands that live in main.py
        builtin_commands = [
            BotCommand("start",  "NickOS help + command list"),
            BotCommand("remind", "Custom reminders (coming soon)"),
        ]
        all_commands = builtin_commands + registry.bot_commands
        await application.bot.set_my_commands(all_commands)

        scheduler = create_scheduler(application.bot)
        scheduler.start()
        application._scheduler = scheduler  # keep reference alive

        logger.info(
            f"NickOS bot started — "
            f"{datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')}"
        )
        logger.info(
            f"Scheduler running: {len(scheduler.get_jobs())} jobs"
        )
        logger.info(
            f"Skills loaded ({len(registry._loaded)}): "
            + ", ".join(
                f"{s['name']} v{s['version']} [{', '.join(s['commands'])}]"
                for s in registry.list_skills()
            )
        )
        if registry._failed:
            logger.warning(
                f"Skills failed to load: {registry._failed}"
            )

    app.post_init = post_init

    logger.info("Starting NickOS bot — polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
