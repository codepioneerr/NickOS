"""
precompact.py — Memory compression hook for NickOS.

Runs before the daily log or MEMORY.md gets too large.
Summarizes old daily logs into compact entries, keeping key decisions.

Triggers:
  - Automatically when daily log for a date is >7 days old
  - Manually via /compact command in Telegram
  - Can be run as a weekly cron task

Usage:
    from precompact import run_precompact
    run_precompact()  # compresses anything older than 7 days
"""

import re
import textwrap
from datetime import date, datetime, timedelta
from pathlib import Path
import anthropic

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DAILY_DIR  = BASE_DIR / "daily"
ARCHIVE_DIR = BASE_DIR / "daily" / "archive"
MEMORY_MD  = BASE_DIR / "MEMORY.md"

COMPRESS_AFTER_DAYS = 7    # compress logs older than this
MAX_MEMORY_LINES    = 300  # if MEMORY.md exceeds this, compact it too


# ─── Main entry point ─────────────────────────────────────────────────────────

def run_precompact(force: bool = False) -> str:
    """
    Scan daily/ for old logs and compress them.
    Returns a summary of what was done.
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    if not DAILY_DIR.exists():
        return "No daily logs found."

    cutoff = date.today() - timedelta(days=COMPRESS_AFTER_DAYS)

    for log_file in sorted(DAILY_DIR.glob("*.md")):
        # Skip archive folder
        if log_file.parent.name == "archive":
            continue
        try:
            log_date = date.fromisoformat(log_file.stem)
        except ValueError:
            continue

        if log_date < cutoff or force:
            result = _compress_daily_log(log_file, log_date)
            results.append(result)

    # Also compact MEMORY.md if it's grown too large
    mem_result = _check_memory_md()
    if mem_result:
        results.append(mem_result)

    if not results:
        return f"Nothing to compact (all logs ≤{COMPRESS_AFTER_DAYS} days old)."

    return "Compacted:\n" + "\n".join(f"  • {r}" for r in results)


# ─── Daily log compression ────────────────────────────────────────────────────

def _compress_daily_log(log_file: Path, log_date: date) -> str:
    """
    Summarize a daily log file to ~5 bullet points.
    Move original to archive/, replace with compact version.
    """
    content = log_file.read_text(encoding="utf-8").strip()
    if len(content) < 200:
        return f"{log_date} — already short, skipped"

    summary = _summarize_daily(content, log_date)

    # Archive the original
    archive_file = ARCHIVE_DIR / log_file.name
    log_file.rename(archive_file)

    # Write compact version
    compact = textwrap.dedent(f"""
        # Daily Log — {log_date} [COMPACTED]
        _Original archived. Summarized by PreCompact on {datetime.now().strftime('%Y-%m-%d')}_

        {summary}
    """).strip() + "\n"

    log_file.write_text(compact)
    return f"{log_date} compressed ({len(content)} → {len(compact)} chars)"


def _summarize_daily(content: str, log_date: date) -> str:
    """Call Claude Haiku to extract key facts from a daily log."""
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"""Compress this daily log to 3–5 bullet points.
Keep: key decisions made, goals progressed, health highlights, anything Nick should remember.
Drop: routine logs (e.g. "logged water: 6"), timestamps, repetitive info.
Be specific. No filler.

Date: {log_date}

Log content:
{content[:3000]}

Output format:
- [bullet 1]
- [bullet 2]
..."""
        }]
    )
    return msg.content[0].text.strip()


# ─── MEMORY.md compaction ─────────────────────────────────────────────────────

def _check_memory_md() -> Optional[str]:
    """If MEMORY.md is too long, summarize older sections."""
    if not MEMORY_MD.exists():
        return None

    content = MEMORY_MD.read_text()
    lines   = content.splitlines()

    if len(lines) <= MAX_MEMORY_LINES:
        return None

    return _compact_memory_md(content, lines)


def _compact_memory_md(content: str, lines: list) -> str:
    """
    Keep the most recent MAX_MEMORY_LINES/2 lines verbatim.
    Summarize everything older into a compact 'Archived Context' section.
    """
    keep_from  = len(lines) - MAX_MEMORY_LINES // 2
    old_block  = "\n".join(lines[:keep_from])
    new_block  = "\n".join(lines[keep_from:])

    # Summarize the old block
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Compress this section of Nick's MEMORY.md.
Keep key facts, decisions, project milestones, important context.
Drop: redundant info, old health logs, completed tasks.
Output as clean markdown bullet points grouped by topic.

Content to compress:
{old_block[:4000]}"""
        }]
    )

    archive_section = textwrap.dedent(f"""
        ## Archived Context
        _Compacted {datetime.now().strftime('%Y-%m-%d')} — {keep_from} lines → summary_

        {msg.content[0].text.strip()}

        ---

    """).strip()

    new_content = archive_section + "\n\n" + new_block
    MEMORY_MD.write_text(new_content)

    original_lines = len(lines)
    new_lines = len(new_content.splitlines())
    return f"MEMORY.md compacted ({original_lines} → {new_lines} lines)"


# ─── Should-compact check (call before sessions) ──────────────────────────────

def should_compact() -> bool:
    """Returns True if any daily logs are due for compaction."""
    if not DAILY_DIR.exists():
        return False

    cutoff = date.today() - timedelta(days=COMPRESS_AFTER_DAYS)
    for f in DAILY_DIR.glob("*.md"):
        if f.parent.name == "archive":
            continue
        try:
            if date.fromisoformat(f.stem) < cutoff:
                return True
        except ValueError:
            pass

    # Check MEMORY.md size
    if MEMORY_MD.exists():
        if len(MEMORY_MD.read_text().splitlines()) > MAX_MEMORY_LINES:
            return True

    return False
