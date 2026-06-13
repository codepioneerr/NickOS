#!/usr/bin/env python3
"""
scripts/fetch_study_abroad_emails.py

Searches nblack10@fordham.edu for all study abroad / London / appeal emails
and writes a chronological timeline to memory/study_abroad_timeline.md.

Run from the NickOS root:
    python3 scripts/fetch_study_abroad_emails.py
"""

import sys
import os
import re
import json
import base64
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

TOKEN_PATH = ROOT / "gmail/tokens/account2_token.json"
OUTPUT_PATH = ROOT / "memory/study_abroad_timeline.md"

# ── Setup ─────────────────────────────────────────────────────────────────────

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except ImportError:
    print("ERROR: Missing Google API libraries.")
    print("Run: python3 -m pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)

if not TOKEN_PATH.exists():
    print(f"ERROR: Token not found at {TOKEN_PATH}")
    print("This script needs the Fordham Gmail OAuth token (account2_token.json).")
    sys.exit(1)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
if creds.expired and creds.refresh_token:
    print("Refreshing expired token...")
    creds.refresh(Request())
    TOKEN_PATH.write_text(creds.to_json())

svc = build("gmail", "v1", credentials=creds)
profile = svc.users().getProfile(userId="me").execute()
email_addr = profile["emailAddress"]
print(f"✓ Authenticated as: {email_addr}\n")

# ── Search queries ─────────────────────────────────────────────────────────────

QUERIES = [
    'subject:"study abroad"',
    'subject:London',
    'subject:ISAP',
    'subject:appeal',
    'subject:"GPA requirement"',
    'subject:withdrawal',
    '"study abroad"',
    '"London program"',
    '"fall 2026"',
    '"Finley Peay"',
    'Finley',
    '"Dean Campbell"',
    '"Provost Jacobs"',
    'Edson study',
    'from:studyabroad',
    'from:international',
    'from:fordham.edu subject:(abroad OR London OR appeal OR GPA)',
    '"case by case"',
    '"case-by-case"',
    '"academic standing"',
    '"minimum GPA"',
    '"academic appeal"',
    '"study abroad office"',
    '"International Study Abroad Programs"',
    '"ISAP"',
]

print("Searching for study abroad emails...")
seen_ids = set()
all_threads = []  # list of thread dicts with messages

for query in QUERIES:
    try:
        resp = svc.users().threads().list(userId="me", q=query, maxResults=50).execute()
        threads = resp.get("threads", [])
        for t in threads:
            if t["id"] not in seen_ids:
                seen_ids.add(t["id"])
                all_threads.append(t["id"])
        if threads:
            print(f"  [{len(threads):2d}] {query}")
    except Exception as e:
        print(f"  [ERR] {query}: {e}")

print(f"\nTotal unique threads: {len(all_threads)}")
print("Fetching full thread content...\n")

# ── Fetch thread content ───────────────────────────────────────────────────────

def decode_body(payload):
    """Extract plain text from a Gmail message payload."""
    text = ""

    def walk(part):
        nonlocal text
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data", "")

        if mime == "text/plain" and data:
            decoded = base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="replace")
            text += decoded
        elif mime.startswith("multipart/"):
            for sub in part.get("parts", []):
                walk(sub)

    walk(payload)

    # Truncate very long bodies
    if len(text) > 3000:
        text = text[:3000] + "\n... [truncated]"
    return text.strip()


def get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


emails = []

for thread_id in all_threads:
    try:
        thread = svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
        messages = thread.get("messages", [])

        for msg in messages:
            headers = msg["payload"].get("headers", [])
            subject = get_header(headers, "Subject")
            sender  = get_header(headers, "From")
            to      = get_header(headers, "To")
            date_str = get_header(headers, "Date")
            body    = decode_body(msg["payload"])

            # Parse date for sorting
            try:
                # Strip timezone name in parens if present, e.g., "(EDT)"
                clean_date = re.sub(r"\s*\([^)]+\)$", "", date_str).strip()
                dt = datetime.strptime(clean_date, "%a, %d %b %Y %H:%M:%S %z")
            except Exception:
                try:
                    dt = datetime.strptime(clean_date[:25], "%a, %d %b %Y %H:%M:%S")
                except Exception:
                    dt = datetime.min.replace(tzinfo=None)

            emails.append({
                "dt":      dt,
                "date":    date_str,
                "subject": subject,
                "from":    sender,
                "to":      to,
                "body":    body,
                "thread_id": thread_id,
                "msg_id":   msg["id"],
            })

    except Exception as e:
        print(f"  WARNING: Could not fetch thread {thread_id}: {e}")

# Sort chronologically
emails.sort(key=lambda e: e["dt"] if e["dt"] != datetime.min else datetime.min.replace(tzinfo=None))

print(f"Total individual emails: {len(emails)}")

# ── Write timeline ─────────────────────────────────────────────────────────────

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

lines = [
    f"# Study Abroad Appeal — Email Timeline",
    f"",
    f"> Generated: {now_str}  ",
    f"> Account searched: {email_addr}  ",
    f"> Total threads found: {len(all_threads)} | Total emails: {len(emails)}  ",
    f"> **Purpose:** Context for June 15 meeting with Finley Peay (Study Abroad Office) re: London Fall 2026 appeal.",
    f"",
    f"---",
    f"",
]

if not emails:
    lines.append("*No emails found matching study abroad search terms.*\n")
    lines.append("\n**Searches tried:**\n")
    for q in QUERIES:
        lines.append(f"- `{q}`")
else:
    # Group by month for readability
    current_month = None
    for e in emails:
        month = e["dt"].strftime("%B %Y") if e["dt"] != datetime.min else "Unknown Date"
        if month != current_month:
            current_month = month
            lines.append(f"\n## {month}\n")

        # Format date
        try:
            d = e["dt"].strftime("%Y-%m-%d %H:%M")
        except Exception:
            d = e["date"]

        lines.append(f"### {d} — {e['subject']}")
        lines.append(f"**From:** {e['from']}  ")
        lines.append(f"**To:** {e['to']}  ")
        lines.append(f"**Thread:** `{e['thread_id']}`")
        lines.append(f"")

        if e["body"]:
            lines.append("```")
            lines.append(e["body"])
            lines.append("```")
        else:
            lines.append("*(no plain-text body)*")

        lines.append("")
        lines.append("---")
        lines.append("")

OUTPUT_PATH.write_text("\n".join(lines))
print(f"\n✓ Timeline saved to: {OUTPUT_PATH}")
print(f"  {len(emails)} emails across {len(all_threads)} threads")

# Quick summary of key emails
print("\n── Key emails (subjects) ───────────────────────────────────")
for e in emails:
    try:
        d = e["dt"].strftime("%Y-%m-%d")
    except Exception:
        d = "????"
    print(f"  {d}  {e['from'][:35]:<35}  {e['subject'][:60]}")

print("\nDone. Open memory/study_abroad_timeline.md for the full timeline.")
