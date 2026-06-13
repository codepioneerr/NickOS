"""
bot/handlers/goals.py
Command: /goal
"""

import re
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime

from bot.utils import ET, today_str, MEMORY_FILE


async def goal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /goal            — list current active goals
    /goal [text]     — add a new goal
    /goal done [n]   — mark goal #n complete
    """
    args = context.args

    # ── List goals ────────────────────────────────────────────────────────────
    if not args:
        goals = _read_goals()
        if not goals:
            await update.message.reply_text(
                "🎯 No active goals yet.\n"
                "Add one: <code>/goal land a CS internship by Oct 2026</code>",
                parse_mode=ParseMode.HTML
            )
            return

        lines = [f"  {i}. {g['text']}" for i, g in enumerate(goals, 1)]
        msg = (
            "<b>🎯 Active Goals</b>\n\n"
            + "\n".join(lines)
            + "\n\n<i>Mark done: /goal done 1 · Add: /goal [text]</i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return

    # ── Mark done ─────────────────────────────────────────────────────────────
    if args[0].lower() == "done":
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: <code>/goal done 2</code>", parse_mode=ParseMode.HTML
            )
            return
        try:
            idx = int(args[1]) - 1
        except ValueError:
            await update.message.reply_text(
                "⚠️ Give me a goal number.", parse_mode=ParseMode.HTML
            )
            return

        goals = _read_goals()
        if idx < 0 or idx >= len(goals):
            await update.message.reply_text(
                "⚠️ That goal number doesn't exist.", parse_mode=ParseMode.HTML
            )
            return

        completed = goals[idx]["text"]
        _remove_goal(goals[idx]["raw"])
        await update.message.reply_text(
            f"🏆 <b>Crushed it:</b> <i>{completed}</i>\n\nRemoved from active goals.",
            parse_mode=ParseMode.HTML
        )
        return

    # ── Add new goal ──────────────────────────────────────────────────────────
    goal_text = " ".join(args)
    _add_goal(goal_text)
    await update.message.reply_text(
        f"✅ <b>Goal added:</b>\n<i>{goal_text}</i>\n\nTracked in your memory.",
        parse_mode=ParseMode.HTML
    )


# ── MEMORY.md helpers ─────────────────────────────────────────────────────────

def _read_goals() -> list[dict]:
    """Parse active goals from MEMORY.md. Returns list of {text, raw}."""
    if not MEMORY_FILE.exists():
        return []
    text = MEMORY_FILE.read_text()
    # Find the Active Goals section
    m = re.search(r"## Active Goals\n(.+?)(?=\n---|\n## )", text, re.DOTALL)
    if not m:
        return []
    block = m.group(1)
    goals = []
    for line in block.splitlines():
        # Match unchecked items: - [ ] Goal text | ...
        if re.match(r"^- \[ \]", line):
            goal_text = re.sub(r"^- \[ \] (.+?)(\s*\|.*)?$", r"\1", line).strip()
            goals.append({"text": goal_text, "raw": line})
    return goals


def _add_goal(text: str):
    if not MEMORY_FILE.exists():
        return
    content = MEMORY_FILE.read_text()
    new_line = f"- [ ] {text} | Added: {today_str()}"
    # Insert after the Active Goals header + comment line
    content = re.sub(
        r"(## Active Goals\n\n<!-- .+?-->\n\n)",
        lambda m: m.group(1) + new_line + "\n",
        content
    )
    # Fallback: insert after header if comment not present
    if new_line not in content:
        content = re.sub(
            r"(## Active Goals\n\n)",
            lambda m: m.group(1) + new_line + "\n",
            content
        )
    MEMORY_FILE.write_text(content)


def _remove_goal(raw_line: str):
    if not MEMORY_FILE.exists():
        return
    content = MEMORY_FILE.read_text()
    content = content.replace(raw_line + "\n", "")
    MEMORY_FILE.write_text(content)
