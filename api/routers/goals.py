"""
api/routers/goals.py
GET /api/goals — active goals from MEMORY.md
"""

from fastapi import APIRouter
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from api.db import get_goals, get_recent_wins

router = APIRouter(prefix="/api", tags=["goals"])

# Map goal text to emoji/category heuristic
_EMOJI_MAP = [
    (["intern", "job", "career", "upwork", "quant", "swe"],    "💼"),
    (["workout", "gym", "sleep", "health", "water", "habit"],  "💪"),
    (["study", "school", "abroad", "gpa", "grade", "class"],   "📚"),
    (["build", "nickos", "code", "project", "launch", "bot"],  "🚀"),
    (["trade", "algo", "stock", "market", "earn", "money"],    "📈"),
    (["read", "book", "learn", "skill", "course"],             "🧠"),
]

def _pick_emoji(text: str) -> str:
    lower = text.lower()
    for keywords, emoji in _EMOJI_MAP:
        if any(k in lower for k in keywords):
            return emoji
    return "🎯"


@router.get("/goals")
def goals_list():
    raw  = get_goals()
    wins = get_recent_wins()

    goals = []
    for g in raw:
        if g["done"]:
            continue  # skip completed goals
        emoji = _pick_emoji(g["name"])
        goals.append({
            "id":         g["id"],
            "name":       g["name"],
            "emoji":      emoji,
            "added":      g["added"],
            "target":     g["target"],
            "progress":   g["progress"],
            "nextAction": "",
            "wins":       [],
        })

    return {
        "goals": goals,
        "wins":  wins,
    }
