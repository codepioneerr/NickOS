"""
gmail/fetcher.py
Gmail API wrapper — auto-detecting multi-account support.

Token discovery (no .env config needed for accounts):
  - Scans gmail/tokens/*_token.json automatically
  - Resolves the email address for each token via Gmail profile API (one-time)
  - Caches results in gmail/tokens/accounts_registry.json

.env still used for GMAIL_CREDENTIALS_PATH only.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=False)

from config import TOKENS_DIR, CREDENTIALS_PATH  # noqa: E402

REGISTRY_FILE = TOKENS_DIR / "accounts_registry.json"
ET            = ZoneInfo("America/New_York")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# ── Account auto-detection ────────────────────────────────────────────────────

def load_accounts() -> list[dict]:
    """
    Auto-detect all Gmail accounts from *_token.json files in gmail/tokens/.
    Email addresses are resolved once via the Gmail API and cached in
    accounts_registry.json — subsequent calls are instant.

    Returns list of: {index, name, email, token_path}
    """
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)

    # Load cached registry {filename: {email, name}}
    registry: dict[str, dict] = {}
    if REGISTRY_FILE.exists():
        try:
            registry = json.loads(REGISTRY_FILE.read_text())
        except Exception:
            registry = {}

    # Find every *_token.json (skip the registry file itself)
    token_files = sorted(
        f for f in TOKENS_DIR.glob("*_token.json")
        if f.name != "accounts_registry.json"
    )

    if not token_files:
        return []

    accounts      = []
    registry_dirty = False

    for i, token_path in enumerate(token_files, 1):
        fname = token_path.name

        if fname in registry:
            meta = registry[fname]
        else:
            # First time seeing this token — resolve via Gmail profile API
            meta = _resolve_account_meta(token_path, i)
            registry[fname] = meta
            registry_dirty  = True

        accounts.append({
            "index":      i,
            "name":       meta.get("name", f"Account {i}"),
            "email":      meta.get("email", ""),
            "token_path": token_path,
        })

    if registry_dirty:
        REGISTRY_FILE.write_text(json.dumps(registry, indent=2))

    return accounts


def _resolve_account_meta(token_path: Path, fallback_index: int) -> dict:
    """
    Call Gmail profile API with this token to get the real email address.
    Returns {email, name}. Falls back gracefully on any error.
    """
    try:
        stub = {
            "index":      fallback_index,
            "name":       f"Account {fallback_index}",
            "email":      "",
            "token_path": token_path,
        }
        svc     = get_service_for_account(stub)
        profile = svc.users().getProfile(userId="me").execute()
        email   = profile.get("emailAddress", "")

        # Derive a readable name from the email
        local = email.split("@")[0] if email else ""
        domain = email.split("@")[1] if "@" in email else ""
        if "fordham" in domain:
            name = f"Fordham ({local})"
        elif local:
            name = local.split(".")[0].capitalize()  # e.g. "nickdagod3" → "Nickdagod3"
        else:
            name = f"Account {fallback_index}"

        return {"email": email, "name": name}
    except Exception as e:
        return {"email": "", "name": f"Account {fallback_index}", "error": str(e)}


# ── Per-account service ───────────────────────────────────────────────────────

def get_service_for_account(account: dict):
    """
    Return an authenticated Gmail API service for one account.
    Refreshes the token file if expired.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_path = account["token_path"]
    if not token_path.exists():
        raise FileNotFoundError(
            f"Token not found for {account['name']} ({account['email']}).\n"
            f"Run: python scripts/setup_gmail_oauth.py --account {account['index']}"
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ── Single-account fetch (used internally + by setup verification) ─────────────

def fetch_unread_emails_for_account(
    account: dict,
    max_results: int = 50,
    hours_back: int = 24,
) -> list[dict]:
    """
    Fetch unread emails for one account.
    Each returned dict includes account_name, account_email, account_index.
    """
    service     = get_service_for_account(account)
    cutoff      = datetime.now(ET) - timedelta(hours=hours_back)
    after_epoch = int(cutoff.timestamp())
    query       = f"is:unread after:{after_epoch}"

    result   = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    messages = result.get("messages", [])

    emails = []
    for msg in messages:
        try:
            detail = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()

            headers    = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            sender_raw = headers.get("From", "Unknown")
            sender_name, sender_email = _parse_sender(sender_raw)

            emails.append({
                "id":            msg["id"],
                "thread_id":     detail.get("threadId", ""),
                "sender":        sender_name,
                "sender_email":  sender_email,
                "subject":       headers.get("Subject", "(no subject)"),
                "snippet":       detail.get("snippet", ""),
                "date":          headers.get("Date", ""),
                "label_ids":     detail.get("labelIds", []),
                # Account metadata
                "account_index": account["index"],
                "account_name":  account["name"],
                "account_email": account["email"],
                # Keep a reference so label-applying code can get the service
                "_account":      account,
            })
        except Exception:
            continue

    return emails


# ── Multi-account fetch ───────────────────────────────────────────────────────

def fetch_all_accounts(
    max_per_account: int = 50,
    hours_back: int = 24,
) -> tuple[list[dict], list[dict]]:
    """
    Fetch unread emails from all configured accounts.

    Returns:
        (all_emails, errors)
        all_emails — flat list of email dicts across all accounts
        errors     — list of {account, error} for any account that failed
    """
    accounts  = load_accounts()
    all_emails: list[dict] = []
    errors:     list[dict] = []

    for account in accounts:
        try:
            emails = fetch_unread_emails_for_account(account, max_per_account, hours_back)
            all_emails.extend(emails)
        except FileNotFoundError as e:
            errors.append({"account": account, "error": str(e), "type": "not_configured"})
        except Exception as e:
            errors.append({"account": account, "error": str(e), "type": "fetch_error"})

    return all_emails, errors


# ── Legacy single-account shim (keeps old code working) ──────────────────────

def get_service():
    """Backward-compat: get service for account 1."""
    accounts = load_accounts()
    if not accounts:
        raise FileNotFoundError("No Gmail accounts configured. Add GMAIL_ACCOUNT_1_* to .env")
    return get_service_for_account(accounts[0])


def fetch_unread_emails(max_results: int = 50, hours_back: int = 24) -> list[dict]:
    """Backward-compat: fetch from account 1 only."""
    accounts = load_accounts()
    if not accounts:
        return []
    return fetch_unread_emails_for_account(accounts[0], max_results, hours_back)


# ── Helpers ───────────────────────────────────────────────────────────────────

def mark_as_read(service, message_id: str):
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


def _parse_sender(raw: str) -> tuple[str, str]:
    if "<" in raw and ">" in raw:
        name  = raw[:raw.index("<")].strip().strip('"')
        email = raw[raw.index("<") + 1:raw.index(">")].strip()
        return name or email, email
    return raw.strip(), raw.strip()
