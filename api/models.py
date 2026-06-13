"""
api/models.py — Pydantic models for NickOS API request/response bodies.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Log endpoint bodies ───────────────────────────────────────────────────────

class SleepLog(BaseModel):
    hours: float = Field(..., ge=0, le=24, description="Hours slept")

class MealLog(BaseModel):
    meal: str = Field(..., min_length=1, max_length=200)

class WaterLog(BaseModel):
    glasses: int = Field(1, ge=1, le=10)

class WorkoutLog(BaseModel):
    notes: Optional[str] = Field("", max_length=500)

class FocusLog(BaseModel):
    minutes: int = Field(25, ge=1, le=240)
    label:   Optional[str] = Field("", max_length=200)

class HabitLog(BaseModel):
    habit_id: str  = Field(..., min_length=1, max_length=50)
    done:     bool = Field(True)


# ── Calendar ──────────────────────────────────────────────────────────────────

class CalendarEventCreate(BaseModel):
    title: str    = Field(..., min_length=1, max_length=100)
    date:  str    = Field(..., description="YYYY-MM-DD")
    time:  str    = Field("09:00", description="HH:MM (24h ET)")
    duration: int = Field(60, ge=5, le=480)
    description: Optional[str] = Field("", max_length=500)


# ── Email actions ─────────────────────────────────────────────────────────────

class DraftReplyRequest(BaseModel):
    email_id:    str
    account_idx: int = 1
    subject:     str = ""
    sender:      str = ""
    snippet:     str = ""
