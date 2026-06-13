"""
gmail/calendar_client.py
Google Calendar API wrapper for NickOS.

Requires: gmail/tokens/calendar_token.json
Run scripts/setup_calendar_oauth.py once to create it.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=False)

from config import CALENDAR_TOKEN_PATH, CREDENTIALS_PATH  # noqa: E402

CALENDAR_TOKEN = CALENDAR_TOKEN_PATH
CALENDAR_ID    = os.environ.get("GOOGLE_CALENDAR_ID", "primary")
ET             = ZoneInfo("America/New_York")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def _get_service():
    """Build and return an authorized Google Calendar service."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not CALENDAR_TOKEN.exists():
        raise FileNotFoundError(
            f"Calendar token not found at {CALENDAR_TOKEN}. "
            "Run: python scripts/setup_calendar_oauth.py"
        )

    creds = Credentials.from_authorized_user_file(str(CALENDAR_TOKEN), SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            CALENDAR_TOKEN.write_text(creds.to_json())
        else:
            raise RuntimeError("Calendar token expired. Re-run setup_calendar_oauth.py.")

    return build("calendar", "v3", credentials=creds)


def get_today_events(calendar_id: str = CALENDAR_ID) -> list[dict]:
    """
    Fetch today's calendar events (midnight → midnight ET).
    Returns list of dicts: {id, title, time, duration, color, all_day, raw}
    """
    try:
        service = _get_service()
    except FileNotFoundError:
        return []  # Calendar not configured yet — return empty gracefully

    now   = datetime.now(ET)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = start + timedelta(days=1)

    result = service.events().list(
        calendarId=calendar_id,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=20,
    ).execute()

    events = []
    for e in result.get("items", []):
        start_raw = e["start"].get("dateTime") or e["start"].get("date")
        end_raw   = e["end"].get("dateTime")   or e["end"].get("date")
        all_day   = "date" in e["start"] and "dateTime" not in e["start"]

        if not all_day:
            dt_start  = datetime.fromisoformat(start_raw)
            dt_end    = datetime.fromisoformat(end_raw)
            duration  = int((dt_end - dt_start).total_seconds() // 60)
            time_fmt  = dt_start.astimezone(ET).strftime("%-I:%M %p")
        else:
            duration  = 0
            time_fmt  = "All day"

        # Color map: GCal color IDs → hex
        COLOR_MAP = {
            "1": "#7986CB",  # lavender
            "2": "#33B679",  # sage
            "3": "#8E24AA",  # grape
            "4": "#E67C73",  # flamingo
            "5": "#F6BF26",  # banana
            "6": "#F4511E",  # tangerine
            "7": "#039BE5",  # peacock
            "8": "#616161",  # graphite
            "9": "#3F51B5",  # blueberry
            "10": "#0B8043", # basil
            "11": "#D50000", # tomato
        }
        color_id = e.get("colorId", "")
        color    = COLOR_MAP.get(color_id, "#7c3aed")  # default: NickOS purple

        events.append({
            "id":       e.get("id", ""),
            "title":    e.get("summary", "(no title)"),
            "time":     time_fmt,
            "duration": duration,
            "color":    color,
            "all_day":  all_day,
        })

    return events


def create_event(
    title: str,
    date: str,           # YYYY-MM-DD
    time: str,           # HH:MM (24h, ET)
    duration: int = 60,  # minutes
    description: str = "",
    calendar_id: str = CALENDAR_ID,
) -> dict:
    """
    Create a Google Calendar event.
    Returns the created event's id and htmlLink.
    """
    service = _get_service()

    tz_str  = "America/New_York"
    start_dt = datetime.fromisoformat(f"{date}T{time}:00").replace(tzinfo=ET)
    end_dt   = start_dt + timedelta(minutes=duration)

    body = {
        "summary": title,
        "description": description,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": tz_str,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": tz_str,
        },
    }

    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    return {
        "id":       created.get("id"),
        "title":    created.get("summary"),
        "htmlLink": created.get("htmlLink"),
        "start":    created["start"]["dateTime"],
    }


def calendar_ready() -> bool:
    """Return True if calendar token exists and is valid."""
    return CALENDAR_TOKEN.exists()
