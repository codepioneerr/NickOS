#!/usr/bin/env python3
"""
scripts/test_telegram.py
Quick sanity check — verifies your bot token works and sends a test message.

Usage:
    python scripts/test_telegram.py
"""

import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN")
USER_ID = os.environ.get("TELEGRAM_ALLOWED_USER_ID")

if not TOKEN:
    print("❌  TELEGRAM_BOT_TOKEN not set in .env")
    exit(1)
if not USER_ID:
    print("❌  TELEGRAM_ALLOWED_USER_ID not set in .env")
    exit(1)

async def test():
    from telegram import Bot
    bot = Bot(token=TOKEN)
    me = await bot.get_me()
    print(f"✅  Bot connected: @{me.username} ({me.first_name})")

    await bot.send_message(
        chat_id=int(USER_ID),
        text="🧠 *NickOS test message* — bot is alive and talking to you\\!",
        parse_mode="MarkdownV2"
    )
    print(f"✅  Test message sent to user {USER_ID}")

asyncio.run(test())
