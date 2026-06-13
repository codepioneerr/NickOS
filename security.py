"""
security.py — Security hardening for NickOS.

Provides:
  1. Email content sanitization before sending to Claude API
  2. API key scrubbing from logs / daily files
  3. Telegram rate limiter (max 30 commands/min per user)
  4. Input validation for all DB writes

Usage:
    from security import sanitize_email, scrub_keys, rate_limit, validate_log_input
"""

import re
import os
import time
import html
import hashlib
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ─── 1. Email content sanitization ───────────────────────────────────────────

# Patterns to strip before sending email content to Claude
_STRIP_PATTERNS = [
    # Tracking pixels / invisible content
    re.compile(r'<img[^>]*width=["\']?[01]["\']?[^>]*>', re.IGNORECASE),
    re.compile(r'<img[^>]*height=["\']?[01]["\']?[^>]*>', re.IGNORECASE),
    # Script / style tags
    re.compile(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>',   re.IGNORECASE | re.DOTALL),
    # Hidden elements
    re.compile(r'<[^>]*style=["\'][^"\']*display\s*:\s*none[^"\']*["\'][^>]*>.*?</[^>]+>',
               re.IGNORECASE | re.DOTALL),
    # Comment injection attempts
    re.compile(r'<!--.*?-->', re.DOTALL),
    # Prompt injection patterns (text directing the AI)
    re.compile(r'(ignore previous instructions?|system prompt|you are now|new instructions?'
               r'|disregard all|forget everything|act as|roleplay as)',
               re.IGNORECASE),
]

# Max email body length to send to Claude (prevents token bombing)
MAX_EMAIL_BODY_CHARS = 2000


def sanitize_email(subject: str, body: str, sender: str = "") -> dict:
    """
    Clean email content before sending to Claude API.
    Returns dict with sanitized fields.
    """
    # HTML decode
    body = html.unescape(body)

    # Strip HTML tags (keep text)
    body = re.sub(r'<[^>]+>', ' ', body)

    # Apply strip patterns
    for pattern in _STRIP_PATTERNS:
        body = pattern.sub('[REMOVED]', body)

    # Collapse whitespace
    body    = re.sub(r'\s+', ' ', body).strip()
    subject = re.sub(r'\s+', ' ', html.unescape(subject)).strip()[:200]
    sender  = sender.strip()[:100]

    # Truncate body
    if len(body) > MAX_EMAIL_BODY_CHARS:
        body = body[:MAX_EMAIL_BODY_CHARS] + "... [truncated]"

    return {
        "subject": subject,
        "body":    body,
        "sender":  sender,
        "hash":    hashlib.sha256(f"{subject}{body}".encode()).hexdigest()[:8],
    }


def build_safe_email_prompt(emails: list[dict]) -> str:
    """Build a Claude prompt from sanitized email list."""
    lines = ["Triage these emails. For each: assign tag (act_now/opportunity/fyi/junk), "
             "1-line summary, suggest action if needed.\n"]
    for i, e in enumerate(emails[:20], 1):  # max 20 emails per batch
        clean = sanitize_email(e.get("subject", ""), e.get("body", e.get("snippet", "")),
                                e.get("sender", e.get("from", "")))
        lines.append(f"{i}. From: {clean['sender']}\n   Subject: {clean['subject']}\n"
                     f"   Body: {clean['body']}\n")
    return "\n".join(lines)


# ─── 2. API key scrubbing ──────────────────────────────────────────────────────

# Patterns that look like API keys / secrets
_KEY_PATTERNS = [
    re.compile(r'sk-[A-Za-z0-9\-_]{20,}'),              # Anthropic / OpenAI
    re.compile(r'TELEGRAM[_\-]?BOT[_\-]?TOKEN\s*=\s*\S+', re.IGNORECASE),
    re.compile(r'[0-9]{8,10}:[A-Za-z0-9\-_]{35}'),      # Telegram bot token format
    re.compile(r'ya29\.[A-Za-z0-9\-_\.]{50,}'),          # Google OAuth access token
    re.compile(r'1\/\/[A-Za-z0-9\-_]{30,}'),             # Google refresh token
    re.compile(r'AIza[A-Za-z0-9\-_]{35}'),               # Google API key
    re.compile(r'(?:password|secret|token|key)\s*[=:]\s*["\']?[^\s"\']{8,}["\']?',
               re.IGNORECASE),
]


def scrub_keys(text: str) -> str:
    """Remove API keys and secrets from text before writing to log files."""
    for pattern in _KEY_PATTERNS:
        text = pattern.sub('[REDACTED]', text)
    return text


def safe_write_log(path: Path, content: str):
    """Write to a log file after scrubbing sensitive data."""
    path.write_text(scrub_keys(content), encoding="utf-8")


def audit_logs_for_keys(log_dir: Path) -> list[str]:
    """
    Scan log files for accidentally-logged secrets.
    Returns list of (file, line_number) findings.
    """
    findings = []
    for f in log_dir.rglob("*.md"):
        try:
            for i, line in enumerate(f.read_text().splitlines(), 1):
                for pattern in _KEY_PATTERNS:
                    if pattern.search(line):
                        findings.append(f"{f.name}:{i} — possible key detected")
                        break
        except Exception:
            pass
    return findings


# ─── 3. Telegram rate limiter ─────────────────────────────────────────────────

class RateLimiter:
    """
    Sliding window rate limiter.
    Default: 30 commands per 60 seconds per user.
    """
    def __init__(self, max_calls: int = 30, window_secs: int = 60):
        self.max_calls    = max_calls
        self.window_secs  = window_secs
        self._windows: dict[int, deque] = defaultdict(deque)

    def is_allowed(self, user_id: int) -> bool:
        now    = time.monotonic()
        window = self._windows[user_id]

        # Evict entries outside the window
        while window and now - window[0] > self.window_secs:
            window.popleft()

        if len(window) >= self.max_calls:
            return False

        window.append(now)
        return True

    def remaining(self, user_id: int) -> int:
        now    = time.monotonic()
        window = self._windows[user_id]
        while window and now - window[0] > self.window_secs:
            window.popleft()
        return max(0, self.max_calls - len(window))

    def reset_after(self, user_id: int) -> float:
        """Seconds until oldest entry expires (approx time until limit resets)."""
        window = self._windows.get(user_id)
        if not window:
            return 0
        oldest = window[0]
        return max(0, self.window_secs - (time.monotonic() - oldest))


# Singleton rate limiter
_rate_limiter = RateLimiter(max_calls=30, window_secs=60)


def rate_limit(user_id: int) -> tuple[bool, str]:
    """
    Check if user is within rate limit.
    Returns (allowed, message).
    """
    if _rate_limiter.is_allowed(user_id):
        return True, ""
    wait = _rate_limiter.reset_after(user_id)
    return False, f"⚠️ Slow down — rate limit hit. Try again in {wait:.0f}s."


# ─── 4. Input validation ──────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def validate_sleep_hours(value: Any) -> float:
    """Validate sleep hours input (0–24)."""
    try:
        h = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"Sleep hours must be a number, got: {value!r}")
    if not (0 <= h <= 24):
        raise ValidationError(f"Sleep hours must be 0–24, got: {h}")
    return round(h, 1)


def validate_water_glasses(value: Any) -> int:
    """Validate water glasses input (0–30)."""
    try:
        g = int(float(value))
    except (TypeError, ValueError):
        raise ValidationError(f"Water glasses must be a number, got: {value!r}")
    if not (0 <= g <= 30):
        raise ValidationError(f"Water glasses must be 0–30, got: {g}")
    return g


def validate_meal_text(value: Any) -> str:
    """Validate meal description (non-empty string, max 200 chars)."""
    if not isinstance(value, str):
        raise ValidationError("Meal must be a string")
    text = value.strip()[:200]
    if not text:
        raise ValidationError("Meal description cannot be empty")
    # Strip potential injection
    text = re.sub(r'[<>]', '', text)
    return text


def validate_workout_notes(value: Any) -> str:
    """Validate workout notes (optional string, max 500 chars)."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError("Workout notes must be a string")
    return value.strip()[:500]


def validate_habit_value(habit_id: str, value: Any) -> float:
    """Validate habit log value based on habit type."""
    HABIT_RANGES = {
        "water":   (0, 30),   # glasses
        "wake_up": (0, 1),    # binary
        "meal_1":  (0, 1),
        "meal_2":  (0, 1),
        "meal_3":  (0, 1),
        "workout": (0, 1),
        "sleep":   (0, 1),
        "no_smoke_preworkout": (0, 1),
    }
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"Habit value must be a number, got: {value!r}")

    lo, hi = HABIT_RANGES.get(habit_id, (0, 100))
    if not (lo <= v <= hi):
        raise ValidationError(f"Habit '{habit_id}' value must be {lo}–{hi}, got: {v}")
    return v


def validate_calendar_event(data: dict) -> dict:
    """Validate and sanitize calendar event fields."""
    title = str(data.get("title", "")).strip()[:100]
    if not title:
        raise ValidationError("Event title is required")

    date_str = str(data.get("date", "")).strip()
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValidationError(f"Invalid date format: {date_str!r} (expected YYYY-MM-DD)")

    time_str = str(data.get("time", "09:00")).strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        raise ValidationError(f"Invalid time format: {time_str!r} (expected HH:MM)")

    duration = int(data.get("duration", 60))
    if not (5 <= duration <= 480):
        raise ValidationError(f"Duration must be 5–480 minutes, got: {duration}")

    return {
        "title":    re.sub(r'[<>]', '', title),
        "date":     date_str,
        "time":     time_str,
        "duration": duration,
    }
