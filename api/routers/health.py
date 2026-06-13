"""
api/routers/health.py
GET /api/health/stats — weekly health data for the Health page
"""

from fastapi import APIRouter
from datetime import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from bot.utils import (
    ET, get_weekly_stats, get_sleep_streak, get_workout_this_week,
    WORKOUT_DAYS, WORKOUT_PLAN
)
from api.db import get_today_health, get_sleep_chart

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/stats")
def health_stats():
    """
    Returns all data needed by the Health page:
    - weekStats: 7-day aggregates (sleep avg, meals, workouts, water avg)
    - today: real-time today's health rings data
    - streaks: sleep/meals/workout streaks from MEMORY.md
    - weeklyWorkouts: workouts done this week vs target (5)
    - workoutPlan: today's workout if applicable
    - healthScore: 0-100 weekly score
    """
    now   = datetime.now(ET)
    today = get_today_health()
    week  = get_weekly_stats()

    # Compute health score (0–100)
    sleep_score   = min(100, round(week["sleep_avg"] / 8 * 40))   # 40 pts
    meal_score    = min(100, round(week["meals_total"] / 21 * 30)) # 30 pts (3/day * 7)
    workout_score = min(100, round(week["workouts"] / 5 * 20))     # 20 pts
    water_score   = min(100, round(week["water_avg"] / 8 * 10))    # 10 pts
    health_score  = sleep_score + meal_score + workout_score + water_score

    # Sleep chart — last 7 days (from SQLite)
    sleep_chart = get_sleep_chart(7)

    # Streaks
    sleep_streak   = get_sleep_streak()
    workouts_week  = get_workout_this_week()

    weekday = now.strftime("%A")
    is_workout_day = weekday in WORKOUT_DAYS

    # Meal suggestions (budget ~$10–15/meal)
    MEAL_SUGGESTIONS = {
        "Breakfast": ["Oatmeal + eggs ($3)", "Greek yogurt + fruit ($4)", "Protein shake + banana ($2)"],
        "Lunch":     ["Rice + chicken + salad ($8)", "Turkey wrap ($6)", "Meal prep bowl ($7)"],
        "Dinner":    ["Ground beef + rice + veggies ($9)", "Pasta + protein ($8)", "Chicken stir fry ($10)"],
    }

    return {
        "weekStats": {
            "sleepAvg":     week["sleep_avg"],
            "sleepDays":    week["sleep_days"],
            "mealsTotal":   week["meals_total"],
            "workouts":     week["workouts"],
            "waterAvg":     week["water_avg"],
            "daysCounted":  week["days_counted"],
        },
        "today": today,
        "streaks": {
            "sleep":   sleep_streak,
            "workouts": workouts_week,
        },
        "sleepChart":       sleep_chart,
        "healthScore":      health_score,
        "isWorkoutDay":     is_workout_day,
        "workoutPlan":      WORKOUT_PLAN.get(weekday, "") if is_workout_day else "",
        "mealSuggestions":  MEAL_SUGGESTIONS,
    }
