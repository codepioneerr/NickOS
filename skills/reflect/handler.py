"""
bot/handlers/reflect.py — /reflect command + NLU memory search

Two entry points:
  reflect_handler(update, context)
    → /reflect [optional topic]
    → Reads today's daily log, searches memory for context,
      feeds both to Claude Haiku for an end-of-day reflection

  memory_search_handler(update, context)
    → Called by NLU MessageHandler when user asks things like
      "what did I decide about X" / "what happened with Y"
    → Extracts the query, runs hybrid search, replies with top hits
"""

import logging
import os
import re
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import MEMORY_FILE, DAILY_LOGS
from bot.utils import ET, today_str, read_daily_log

load_dotenv()

logger  = logging.getLogger(__name__)
_HAIKU  = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")
_ANT_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── NLU patterns that trigger a memory search ─────────────────────────────────
_NLU_PATTERNS = [
    # Original 6
    r"what did i (?:decide|say|think|write|note|conclude|figure out) (?:about|regarding|on|for)\s+(.+)",
    r"what (?:happened|did i do|was (?:the plan|my plan)) (?:with|about|regarding|on)\s+(.+)",
    r"remind me (?:about|what i said about|what happened with)\s+(.+)",
    r"(?:did i|have i) (?:ever|already) (?:decide[d]?|figure[d]? out|note[d]?|write|written) (?:about|anything about)\s+(.+)",
    r"(?:search|find|look up)(?: in my memory| in memory| my notes?)? (?:for\s+)?(.+)",
    r"what(?:'s| is) (?:my|the) (?:plan|goal|decision|thinking) (?:on|about|for)\s+(.+)",
    # Added
    r"last time i\s+(.+)",
    r"when did i\s+(.+)",
    r"what(?:'s| is) the status of\s+(.+)",
]
_NLU_RE = [re.compile(p, re.IGNORECASE) for p in _NLU_PATTERNS]


def _extract_nlu_query(text: str) -> str | None:
    """Return the search query if the message matches an NLU pattern, else None."""
    for pattern in _NLU_RE:
        m = pattern.search(text.strip())
        if m:
            return m.group(1).strip().rstrip("?.")
    return None


def _get_indexer():
    """Lazy-import the indexer to avoid circular imports at bot startup."""
    try:
        from memory.search import get_indexer
        return get_indexer()
    except Exception as e:
        logger.warning(f"[reflect] Could not load memory indexer: {e}")
        return None


def _format_search_hits(results: list[dict]) -> str:
    """Format search results into a clean Telegram message."""
    if not results:
        return "🔍 <i>No relevant memories found.</i>"

    lines = ["🔍 <b>Memory search results:</b>\n"]
    for i, r in enumerate(results, 1):
        score   = r.get("score", 0)
        source  = r.get("source", "unknown")
        section = r.get("section", "")
        date_s  = r.get("date_str", "")
        text    = r.get("text", "").strip()

        # Truncate long chunks for Telegram
        if len(text) > 280:
            text = text[:277] + "…"

        meta = " | ".join(filter(None, [date_s, section, f"score {score:.2f}"]))
        lines.append(f"<b>{i}.</b> <i>{source}</i> — {meta}\n{text}\n")

    return "\n".join(lines)


# ── /reflect handler ──────────────────────────────────────────────────────────
async def reflect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /reflect [topic]

    With no args: generates a full end-of-day reflection using today's log
    + the top 3 memory search results for "day review".

    With args: searches memory for that topic and generates a focused reflection.
    """
    topic = " ".join(context.args) if context.args else ""

    await update.message.reply_text(
        "🌙 <i>Thinking…</i>",
        parse_mode=ParseMode.HTML
    )

    # ── 1. Get today's daily log ───────────────────────────────────────────────
    today_log = read_daily_log()
    if not today_log.strip():
        today_log = "(no entries logged yet today)"

    # ── 2. Search memory for context ──────────────────────────────────────────
    search_query = topic if topic else f"daily review {today_str()}"
    indexer      = _get_indexer()
    context_chunks = []

    if indexer:
        try:
            results = indexer.search(search_query, k=3)
            if results:
                context_chunks = [
                    f"[{r.get('source', '')} | {r.get('date_str', '')}]\n{r.get('text', '').strip()}"
                    for r in results
                ]
        except Exception as e:
            logger.warning(f"[reflect] Memory search failed: {e}")

    # ── 3. Read active goals from MEMORY.md ───────────────────────────────────
    active_goals: list[str] = []
    try:
        from bot.utils import get_active_goals
        active_goals = get_active_goals(limit=3)
    except Exception:
        pass

    # ── 4. Build Claude prompt ────────────────────────────────────────────────
    now_str = datetime.now(ET).strftime("%A, %B %-d at %-I:%M %p ET")

    goals_block = ""
    if active_goals:
        goals_block = "\n\nActive goals:\n" + "\n".join(f"- {g}" for g in active_goals)

    memory_block = ""
    if context_chunks:
        memory_block = "\n\nRelevant past context:\n" + "\n\n".join(context_chunks)

    if topic:
        task_prompt = (
            f"Nick asked to reflect on: \"{topic}\"\n"
            f"Search the context above and give a focused, honest response about this topic. "
            f"Pull in any relevant past decisions or patterns you see."
        )
    else:
        task_prompt = (
            "Generate an end-of-day reflection. Be direct, honest, and specific. "
            "Call out wins, missed targets, and the one thing Nick should focus on tomorrow. "
            "3-5 sentences max. Tough-love tone — no fluff."
        )

    prompt = (
        f"You are NickOS — Nick's personal AI OS.\n"
        f"Current time: {now_str}\n"
        f"\nToday's log:\n{today_log}"
        f"{goals_block}"
        f"{memory_block}"
        f"\n\n{task_prompt}"
    )

    # ── 5. Call Claude Haiku ──────────────────────────────────────────────────
    if not _ANT_KEY:
        await update.message.reply_text(
            "⚠️ <b>ANTHROPIC_API_KEY not set.</b> Cannot generate reflection.",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        client = anthropic.Anthropic(api_key=_ANT_KEY)
        resp   = client.messages.create(
            model=_HAIKU,
            max_tokens=300,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        reflection = resp.content[0].text.strip()
    except Exception as e:
        logger.error(f"[reflect] Claude call failed: {e}")
        await update.message.reply_text(
            f"⚠️ <b>Reflection failed:</b> {e}",
            parse_mode=ParseMode.HTML
        )
        return

    # ── 6. Send result ────────────────────────────────────────────────────────
    header = f"🌙 <b>Reflection</b>" + (f" — {topic}" if topic else f" — {today_str()}")
    await update.message.reply_text(
        f"{header}\n\n{reflection}",
        parse_mode=ParseMode.HTML
    )


# ── NLU memory search handler ─────────────────────────────────────────────────
async def memory_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggered by MessageHandler when user sends a plain-text NLU query like
    "what did I decide about study abroad?" or "what happened with the gym plan?"
    """
    text  = update.message.text or ""
    query = _extract_nlu_query(text)

    if not query:
        # Shouldn't happen if filters are wired correctly — silently ignore
        return

    await update.message.reply_text(
        f"🔍 <i>Searching memory for: {query}…</i>",
        parse_mode=ParseMode.HTML
    )

    indexer = _get_indexer()
    if not indexer:
        await update.message.reply_text(
            "⚠️ <i>Memory index not available right now.</i>",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        results = indexer.search(query, k=5)
    except Exception as e:
        logger.error(f"[memory_search] Search failed: {e}")
        await update.message.reply_text(
            f"⚠️ <i>Search failed: {e}</i>",
            parse_mode=ParseMode.HTML
        )
        return

    reply = _format_search_hits(results)

    # If we have results + Anthropic key, generate a synthesized answer
    if results and _ANT_KEY:
        chunks_text = "\n\n".join(
            f"[{r.get('source','')} | {r.get('date_str','')}]\n{r.get('text','').strip()}"
            for r in results
        )
        synth_prompt = (
            f"Nick asked: \"{text}\"\n\n"
            f"Here are the most relevant entries from his personal memory system:\n\n"
            f"{chunks_text}\n\n"
            "Answer his question directly and concisely based on these entries. "
            "If the answer isn't clear from the context, say so honestly. 2-4 sentences."
        )
        try:
            client  = anthropic.Anthropic(api_key=_ANT_KEY)
            resp    = client.messages.create(
                model=_HAIKU,
                max_tokens=200,
                temperature=0.3,
                messages=[{"role": "user", "content": synth_prompt}]
            )
            answer = resp.content[0].text.strip()
            reply  = f"💡 <b>Answer:</b> {answer}\n\n{reply}"
        except Exception as e:
            logger.warning(f"[memory_search] Synthesis failed: {e}")
            # Fall through — still show raw results

    await update.message.reply_text(reply, parse_mode=ParseMode.HTML)
