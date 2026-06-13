"""
session_hooks.py — SessionStart and SessionEnd lifecycle hooks for NickOS bot.

SessionStart: called at bot.main() startup — loads SOUL.md, USER.md, MEMORY.md
              into a shared context dict so every handler has full Nick context.

SessionEnd:   registered via atexit — on any exit (Ctrl+C, crash, restart),
              summarizes the session and appends to daily/YYYY-MM-DD.md.

Usage in bot.main():
    from session_hooks import session_start, register_session_end
    context = session_start()
    register_session_end(context)
"""

import os
import sys
import atexit
import signal
import textwrap
from datetime import datetime
from pathlib import Path
import anthropic

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
SOUL_MD     = BASE_DIR / "SOUL.md"
USER_MD     = BASE_DIR / "USER.md"
MEMORY_MD   = BASE_DIR / "MEMORY.md"
HABITS_MD   = BASE_DIR / "HABITS.md"
DAILY_DIR   = BASE_DIR / "daily"
BOOTSTRAP_MD = BASE_DIR / "BOOTSTRAP.md"

# ─── SessionStart ─────────────────────────────────────────────────────────────

def session_start() -> dict:
    """
    Load all context files into memory. Returns a context dict that should be
    passed to every bot handler so it always knows who Nick is.
    """
    print("🧠 [SessionStart] Loading NickOS context...")

    # Run bootstrap if first time (no USER.md or it's a template)
    if not USER_MD.exists() or _is_uninitialized(USER_MD):
        print("⚠️  USER.md not found or empty — run /bootstrap to set up your profile.")

    ctx = {
        "soul":    _read_file(SOUL_MD,    "SOUL.md not found — run /bootstrap"),
        "user":    _read_file(USER_MD,    "USER.md not found — run /bootstrap"),
        "memory":  _read_file(MEMORY_MD,  "MEMORY.md is empty"),
        "habits":  _read_file(HABITS_MD,  "HABITS.md not found"),
        "session_start": datetime.now(),
        "events":  [],      # list of {time, type, summary} logged during session
        "logs":    [],      # raw user log entries (sleep/meal/water/workout)
        "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    _print_context_summary(ctx)
    return ctx


def _read_file(path: Path, fallback: str) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return f"[{fallback}]"


def _is_uninitialized(path: Path) -> bool:
    content = path.read_text().strip()
    return len(content) < 50 or "FILL IN" in content.upper()


def _print_context_summary(ctx: dict):
    soul_lines = len(ctx["soul"].splitlines())
    user_lines = len(ctx["user"].splitlines())
    mem_lines  = len(ctx["memory"].splitlines())
    hab_lines  = len(ctx["habits"].splitlines())
    print(
        f"   ✓ SOUL.md    ({soul_lines} lines)\n"
        f"   ✓ USER.md    ({user_lines} lines)\n"
        f"   ✓ MEMORY.md  ({mem_lines} lines)\n"
        f"   ✓ HABITS.md  ({hab_lines} lines)\n"
        f"   Started at {ctx['loaded_at']}"
    )


# ─── Context builder for Claude API calls ─────────────────────────────────────

def build_system_prompt(ctx: dict, extra: str = "") -> str:
    """
    Builds a full system prompt from loaded context files.
    Pass this as the 'system' param to every Claude API call.
    """
    today = datetime.now().strftime("%A, %B %d, %Y")
    return textwrap.dedent(f"""
        You are NickOS — a personal AI operating system for Nick.
        Today is {today}.

        ═══ WHO YOU ARE ═══
        {ctx['soul']}

        ═══ WHO NICK IS ═══
        {ctx['user']}

        ═══ CURRENT MEMORY ═══
        {ctx['memory']}

        ═══ HABIT STATUS ═══
        {ctx['habits']}

        {f'═══ ADDITIONAL CONTEXT ═══{chr(10)}{extra}' if extra else ''}

        Always respond as if you know Nick personally. Be direct, specific, and
        reference his actual situation — don't give generic advice.
    """).strip()


# ─── SessionEnd ───────────────────────────────────────────────────────────────

def register_session_end(ctx: dict):
    """
    Register shutdown handler. Call once after session_start().
    Handles: atexit, SIGINT (Ctrl+C), SIGTERM (Railway restart).
    """
    def _handler(signum=None, frame=None):
        _run_session_end(ctx)
        sys.exit(0)

    atexit.register(_run_session_end, ctx)
    signal.signal(signal.SIGINT,  _handler)
    signal.signal(signal.SIGTERM, _handler)
    print("   ✓ SessionEnd handler registered")


def _run_session_end(ctx: dict):
    """Generate and save session summary. Safe to call multiple times (idempotent)."""
    if ctx.get("_session_ended"):
        return
    ctx["_session_ended"] = True

    print("\n📝 [SessionEnd] Saving session summary...")
    try:
        summary = _generate_session_summary(ctx)
        _save_daily_log(ctx, summary)
        print(f"   ✓ Saved to daily/{datetime.now().strftime('%Y-%m-%d')}.md")
    except Exception as e:
        print(f"   ✗ SessionEnd error: {e}")
        # Fallback: save raw log without AI summary
        _save_daily_log(ctx, _raw_session_summary(ctx))


def _generate_session_summary(ctx: dict) -> str:
    """Call Claude Haiku to summarize the session from events + logs."""
    if not ctx["events"] and not ctx["logs"]:
        return "No activity logged this session."

    events_text = "\n".join(
        f"- [{e['time']}] {e['type']}: {e['summary']}"
        for e in ctx["events"]
    ) or "None"

    logs_text = "\n".join(
        f"- {l['type']}: {l['value']} at {l['time']}"
        for l in ctx["logs"]
    ) or "None"

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=build_system_prompt(ctx),
        messages=[{
            "role": "user",
            "content": f"""Summarize this NickOS session in 3–5 bullet points.
Be specific, reference real actions. No fluff.

Session events:
{events_text}

Health logs:
{logs_text}

Format:
**Session Summary — [date]**
- [bullet 1]
- [bullet 2]
...
**Tomorrow's priority:** [one thing]"""
        }]
    )
    return msg.content[0].text


def _raw_session_summary(ctx: dict) -> str:
    lines = [f"**Session — {datetime.now().strftime('%Y-%m-%d %H:%M')}** (no AI summary)\n"]
    for e in ctx["events"]:
        lines.append(f"- [{e['time']}] {e['type']}: {e['summary']}")
    for l in ctx["logs"]:
        lines.append(f"- logged {l['type']}: {l['value']}")
    return "\n".join(lines) if len(lines) > 1 else "No activity logged."


def _save_daily_log(ctx: dict, summary: str):
    DAILY_DIR.mkdir(exist_ok=True)
    date_str  = datetime.now().strftime("%Y-%m-%d")
    log_file  = DAILY_DIR / f"{date_str}.md"

    start     = ctx["session_start"].strftime("%H:%M")
    end       = datetime.now().strftime("%H:%M")
    duration  = _format_duration(ctx["session_start"], datetime.now())

    entry = textwrap.dedent(f"""
        ## Session {start}–{end} ({duration})

        {summary}

        ---
    """).strip() + "\n\n"

    if log_file.exists():
        existing = log_file.read_text()
        log_file.write_text(existing + entry)
    else:
        header = f"# Daily Log — {date_str}\n\n"
        log_file.write_text(header + entry)


def _format_duration(start: datetime, end: datetime) -> str:
    secs = int((end - start).total_seconds())
    h, m = divmod(secs // 60, 60)
    return f"{h}h {m}m" if h else f"{m}m"


# ─── Context event logging (call from handlers) ───────────────────────────────

def log_event(ctx: dict, event_type: str, summary: str):
    """Record a noteworthy event during the session."""
    ctx["events"].append({
        "time":    datetime.now().strftime("%H:%M"),
        "type":    event_type,
        "summary": summary,
    })


def log_health_entry(ctx: dict, entry_type: str, value):
    """Record a health log (sleep/meal/water/workout) during the session."""
    ctx["logs"].append({
        "type":  entry_type,
        "value": value,
        "time":  datetime.now().strftime("%H:%M"),
    })
