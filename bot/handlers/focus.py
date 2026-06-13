"""
bot/handlers/focus.py
Commands: /focus, /done
"""

import re
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime

from bot.utils import (
    ET, today_str, append_daily_log,
    update_memory_field, MEMORY_FILE
)


async def focus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /focus [task description]
    Locks in the #1 focus task for the day. Writes to MEMORY.md + daily log.
    Example: /focus finish PEAD backtest and push to GitHub
    """
    if not context.args:
        await update.message.reply_text(
            "🎯 What are you focusing on?\n"
            "Usage: <code>/focus finish the PEAD backtest</code>",
            parse_mode=ParseMode.HTML
        )
        return

    task = " ".join(context.args)
    timestamp = datetime.now(ET).strftime("%H:%M")

    append_daily_log("Focus Blocks", f"{timestamp} ET — {task}")

    if MEMORY_FILE.exists():
        text = MEMORY_FILE.read_text()
        text = re.sub(
            r"(## Today's Focus\n\n).*?(\n---|\Z)",
            lambda m: f"{m.group(1)}{task}{m.group(2)}",
            text,
            flags=re.DOTALL
        )
        if "Not yet set" in text:
            text = text.replace("*Not yet set for today.*", task)
        MEMORY_FILE.write_text(text)

    await update.message.reply_text(
        f"🎯 <b>Focus locked:</b>\n<i>{task}</i>\n\nClose distractions. You've got this. ⚡",
        parse_mode=ParseMode.HTML
    )


async def done_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /done [what you completed]
    Logs a completed item to today's daily log.
    Example: /done pushed PEAD bot v2 to GitHub
    """
    if not context.args:
        await update.message.reply_text(
            "✅ What did you finish?\n"
            "Usage: <code>/done pushed PEAD bot to GitHub</code>",
            parse_mode=ParseMode.HTML
        )
        return

    item = " ".join(context.args)
    timestamp = datetime.now(ET).strftime("%H:%M")

    append_daily_log("Done Today", f"{item} ✓ ({timestamp} ET)")

    await update.message.reply_text(
        f"✅ <b>Done:</b> <i>{item}</i>\n\nLogged to today's record. 🏆",
        parse_mode=ParseMode.HTML
    )
