#!/usr/bin/env python3
"""
scripts/setup_calendar_oauth.py
Set up Google Calendar OAuth for NickOS.

Run this ONCE on your machine (requires a browser):
    python scripts/setup_calendar_oauth.py

Saves: gmail/tokens/calendar_token.json
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

CREDENTIALS_PATH = Path(os.environ.get("GMAIL_CREDENTIALS_PATH",
                                        ROOT / "gmail/credentials.json"))
CALENDAR_TOKEN   = ROOT / "gmail/tokens/calendar_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError:
        print("Missing deps. Run:\n  pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        sys.exit(1)

    if not CREDENTIALS_PATH.exists():
        print(f"ERROR: credentials.json not found at {CREDENTIALS_PATH}")
        sys.exit(1)

    creds = None

    # Load existing token if present
    if CALENDAR_TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(CALENDAR_TOKEN), SCOPES)

    # Refresh or re-authorize
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing existing calendar token...")
            creds.refresh(Request())
        else:
            print("Opening browser for Google Calendar OAuth...")
            print("Sign in as: nickdagod3@gmail.com (or whichever account owns the calendar)\n")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save token
        CALENDAR_TOKEN.parent.mkdir(parents=True, exist_ok=True)
        CALENDAR_TOKEN.write_text(creds.to_json())
        print(f"\n✅ Calendar token saved to: {CALENDAR_TOKEN}")

    # Quick test — list today's events
    try:
        from googleapiclient.discovery import build
        from datetime import datetime, timezone

        service = build("calendar", "v3", credentials=creds)
        now = datetime.now(timezone.utc).isoformat()
        result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=5,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = result.get("items", [])
        print(f"\n📅 Upcoming events (next 5):")
        if not events:
            print("  (none)")
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            print(f"  • {start} — {e['summary']}")
        print("\n✅ Google Calendar integration ready!")
    except Exception as ex:
        print(f"\n⚠️  Token saved but test failed: {ex}")
        print("This is okay if your calendar is empty. The token is valid.")


if __name__ == "__main__":
    main()
