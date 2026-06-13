"""
api/routers/gmail.py
GET  /api/emails              — fetch + classify all inboxes (cached 15 min)
POST /api/emails/{id}/dismiss — mark email as read in Gmail
POST /api/emails/{id}/draft-reply — generate a draft reply via Claude Haiku
POST /api/emails/add-to-calendar  — add email-derived event to Google Calendar
"""

import time
import os
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")   # ensure env vars available even when module loaded standalone

from api.models import DraftReplyRequest, CalendarEventCreate

router = APIRouter(prefix="/api/emails", tags=["gmail"])

# ── Simple in-memory cache (TTL = 15 min) ────────────────────────────────────
_cache: dict = {"data": None, "ts": 0}
CACHE_TTL = 15 * 60  # seconds


def _get_cached_emails():
    if _cache["data"] and (time.time() - _cache["ts"] < CACHE_TTL):
        return _cache["data"]
    return None


def _set_cache(data):
    _cache["data"] = data
    _cache["ts"]   = time.time()


# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
def get_emails(force: bool = False):
    """
    Fetch and classify emails from all configured Gmail accounts.
    Cached for 15 minutes. Pass ?force=true to bypass cache.
    """
    if not force:
        cached = _get_cached_emails()
        if cached is not None:
            return cached

    try:
        from gmail.fetcher import fetch_all_accounts, load_accounts
        from gmail.classifier import classify_emails, merge_classifications, group_by_tier
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Gmail module error: {e}")

    accounts = load_accounts()
    if not accounts:
        return []

    all_emails, _ = fetch_all_accounts(max_per_account=30, hours_back=24)
    if not all_emails:
        _set_cache([])
        return []

    classifications = classify_emails(all_emails)
    enriched        = merge_classifications(all_emails, classifications)
    groups          = group_by_tier(enriched)

    # Flatten + normalise for dashboard
    tier_order = {"ACT_NOW": 0, "OPPORTUNITY": 1, "FYI": 2, "JUNK": 3}
    result = []
    for email in enriched:
        tier = email.get("tier", "FYI")
        if tier == "JUNK":
            continue  # skip junk on dashboard
        result.append({
            "id":       email.get("id", ""),
            "msg_id":   email.get("message_id", email.get("id", "")),
            "tag":      tier.lower(),
            "account":  email.get("account_name", ""),
            "account_idx": email.get("account_index", 1),
            "from":     email.get("sender", ""),
            "subject":  email.get("subject", "(no subject)"),
            "preview":  email.get("snippet", "")[:120],
            "reason":   email.get("reason", ""),
            "time":     email.get("date", ""),
            "thread_id": email.get("thread_id", ""),
        })

    result.sort(key=lambda e: tier_order.get(e["tag"].upper(), 99))
    _set_cache(result)
    return result


@router.post("/{email_id}/dismiss")
def dismiss_email(email_id: str, account_idx: int = 1):
    """Mark email as read in Gmail (removes UNREAD label)."""
    try:
        from gmail.fetcher import get_service_for_account, load_accounts
        accounts = load_accounts()
        account  = next((a for a in accounts if a["index"] == account_idx), None)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        svc = get_service_for_account(account)
        svc.users().messages().modify(
            userId="me",
            id=email_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()

        # Invalidate cache
        _cache["data"] = None
        return {"ok": True, "email_id": email_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DraftReplyBody(BaseModel):
    account_idx: int = 1
    subject:     str = ""
    sender:      str = ""
    snippet:     str = ""


@router.post("/{email_id}/draft-reply")
def draft_reply(email_id: str, body: DraftReplyBody):
    """Generate a reply draft using Claude Haiku based on email content."""
    try:
        import anthropic
        from security import sanitize_email

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

        clean   = sanitize_email(body.subject, body.snippet, body.sender)
        client  = anthropic.Anthropic(api_key=api_key)
        model   = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")

        prompt = (
            f"Write a short, professional reply to this email.\n\n"
            f"From: {clean['sender']}\n"
            f"Subject: {clean['subject']}\n"
            f"Message: {clean['body']}\n\n"
            f"Nick is a 21-year-old CS student at Fordham (Dean's List), "
            f"quant/SWE career focus. Keep the reply concise (2–4 sentences), "
            f"professional but direct. Do not add a signature line."
        )

        msg = client.messages.create(
            model=model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        draft = msg.content[0].text.strip()
        return {"draft": draft, "email_id": email_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
