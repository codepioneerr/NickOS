"""
bot/auth.py — NickOS Telegram authentication middleware.

Extracted from bot/main.py so both main.py and bot/registry.py can import it
without creating circular dependencies.
"""

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes

load_dotenv()

logger = logging.getLogger(__name__)

ALLOWED_ID: int = int(os.environ.get("TELEGRAM_ALLOWED_USER_ID", "0"))


async def auth_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if the sender is the authorised user, else reply 🚫 and return False."""
    if ALLOWED_ID and update.effective_user.id != ALLOWED_ID:
        logger.warning(f"[auth] Blocked unauthorised user {update.effective_user.id}")
        await update.message.reply_text("🚫 Unauthorized.")
        return False
    return True


def guarded(handler):
    """Wrap a Telegram handler function with auth_check."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await auth_check(update, context):
            return
        await handler(update, context)
    return wrapper
