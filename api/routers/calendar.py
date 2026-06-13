"""
api/routers/calendar.py
GET  /api/calendar      — today's Google Calendar events
POST /api/calendar/add  — create a new Google Calendar event
"""

from fastapi import APIRouter, HTTPException
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from api.models import CalendarEventCreate
from security import validate_calendar_event, ValidationError

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("")
def get_calendar():
    """Return today's events from Google Calendar. Returns [] if not configured."""
    try:
        from gmail.calendar_client import get_today_events, calendar_ready
        if not calendar_ready():
            return {"events": [], "configured": False,
                    "message": "Run scripts/setup_calendar_oauth.py to connect Google Calendar"}
        events = get_today_events()
        return {"events": events, "configured": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
def add_calendar_event(body: CalendarEventCreate):
    """Create a new event in Google Calendar."""
    try:
        # Validate
        validated = validate_calendar_event({
            "title":    body.title,
            "date":     body.date,
            "time":     body.time,
            "duration": body.duration,
        })
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        from gmail.calendar_client import create_event, calendar_ready
        if not calendar_ready():
            raise HTTPException(
                status_code=503,
                detail="Calendar not configured. Run scripts/setup_calendar_oauth.py"
            )
        created = create_event(
            title=validated["title"],
            date=validated["date"],
            time=validated["time"],
            duration=validated["duration"],
            description=body.description or "",
        )
        return {"ok": True, "event": created}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
