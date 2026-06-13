import React, { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import Card, { CardHeader } from '../components/Card.jsx'
import { api } from '../hooks/useApi.js'

function StatPill({ label, value, sub, color }) {
  return (
    <div className="flex-1 rounded-xl p-3 flex flex-col gap-1" style={{ background: '#242424', border: '1px solid #333' }}>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-xl font-bold" style={{ color }}>{value}</p>
      {sub && <p className="text-[10px] text-gray-600">{sub}</p>}
    </div>
  )
}

function StreakBadge({ icon, label, value }) {
  return (
    <div className="flex-1 rounded-xl p-3 flex flex-col items-center gap-1.5" style={{ background: '#242424', border: '1px solid #333' }}>
      <span className="text-2xl">{icon}</span>
      <p className="text-xl font-bold text-white">{value}</p>
      <p className="text-[10px] text-gray-500 text-center">{label}</p>
    </div>
  )
}

function ScoreArc({ score }) {
  const circ = 2 * Math.PI * 54
  let color = '#ef4444'
  if (score >= 80) color = '#10b981'
  else if (score >= 60) color = '#f59e0b'
  else if (score >= 40) color = '#7c3aed'
  return (
    <div className="flex flex-col items-center">
      <svg width="140" height="80" viewBox="0 0 140 80">
        <path d="M 14 70 A 56 56 0 0 1 126 70" fill="none" stroke="#2a2a2a" strokeWidth="10" strokeLinecap="round" />
        <path d="M 14 70 A 56 56 0 0 1 126 70" fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
              strokeDasharray={circ / 2} strokeDashoffset={circ / 2 * (1 - score / 100)}
              style={{ transition: 'stroke-dashoffset 1s ease-out' }} />
        <text x="70" y="65" textAnchor="middle" fill="white" fontSize="28" fontWeight="800" fontFamily="-apple-system">{score}</text>
      </svg>
      <p className="text-xs text-gray-400 -mt-2">Health Score</p>
    </div>
  )
}

const CustomBar = ({ x, y, width, height, value }) => {
  const color = value >= 8 ? '#10b981' : value >= 7 ? '#7c3aed' : value >= 6 ? '#f59e0b' : '#ef4444'
  return <rect x={x} y={y} width={width} height={height} fill={color} rx="4" />
}

const MEAL_EMOJI = { Breakfast: '🌅', Lunch: '☀️', Dinner: '🌙' }

export default function Health() {
  const [data,    setData]    = useState(null)
  const [error,   setError]   = useState(null)
  const [doneEx,  setDoneEx]  = useState([])

  useEffect(() => {
    api.healthStats()
      .then(setData)
      .catch(e => setError(e.message))
  }, [])

  const toggleEx = i => setDoneEx(p => p.includes(i) ? p.filter(x => x !== i) : [...p, i])

  if (error) return (
    <div className="flex flex-col items-center justify-center min-h-64 gap-3">
      <p className="text-red-400 text-sm">⚠️ {error}</p>
    </div>
  )

  if (!data) return (
    <div className="flex flex-col gap-4">
      {[120, 80, 150, 100].map((h, i) => (
        <div key={i} className="shimmer rounded-2xl" style={{ height: h }} />
      ))}
    </div>
  )

  const { weekStats, today, streaks, sleepChart, healthScore, isWorkoutDay, workoutPlan, mealSuggestions } = data

  // Sleep chart: API returns [{day, hours}, ...]
  const chartData = (sleepChart || []).map(d => ({ day: d.day, hrs: d.hours }))

  return (
    <div className="flex flex-col gap-4 pb-2">
      <h1 className="text-2xl font-bold text-white tracking-tight">Health 💪</h1>

      {/* Health Score */}
      <Card>
        <div className="flex items-center gap-4">
          <ScoreArc score={healthScore} />
          <div className="flex flex-col gap-2 flex-1">
            {[
              { label: 'Sleep',   pct: Math.min(100, Math.round(weekStats.sleepAvg / 8 * 100)), weight: 0.4 },
              { label: 'Meals',   pct: Math.min(100, Math.round(weekStats.mealsTotal / 21 * 100)), weight: 0.3 },
              { label: 'Workout', pct: Math.min(100, Math.round(weekStats.workouts / 5 * 100)), weight: 0.2 },
              { label: 'Water',   pct: Math.min(100, Math.round(weekStats.waterAvg / 8 * 100)), weight: 0.1 },
            ].map(({ label, pct, weight }) => (
              <div key={label} className="flex items-center gap-2">
                <span className="text-xs text-gray-400 w-14">{label}</span>
                <div className="flex-1 h-1.5 rounded-full" style={{ background: '#2a2a2a' }}>
                  <div className="h-full rounded-full" style={{ width: `${pct}%`, background: '#7c3aed', opacity: 0.4 + weight }} />
                </div>
                <span className="text-xs text-white w-8 text-right">{pct}</span>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* Week Stats */}
      <div className="flex gap-2">
        <StatPill label="Sleep avg"  value={`${weekStats.sleepAvg}h`}  sub="goal: 8h"    color="#7c3aed" />
        <StatPill label="Meals"      value={weekStats.mealsTotal}       sub="this week"   color="#10b981" />
        <StatPill label="Water avg"  value={weekStats.waterAvg}         sub="glasses/day" color="#3b82f6" />
        <StatPill label="Workouts"   value={`${weekStats.workouts}/5`}  sub="this week"   color="#f59e0b" />
      </div>

      {/* Today's rings */}
      <Card>
        <CardHeader title="Today's Progress" subtitle="Real-time" />
        <div className="grid grid-cols-4 gap-2 mt-1">
          {[
            { label: 'Sleep',   emoji: '😴', ...today.sleep },
            { label: 'Meals',   emoji: '🍽', ...today.meals },
            { label: 'Water',   emoji: '💧', ...today.water },
            { label: 'Workout', emoji: '💪', ...today.workout },
          ].map(({ label, emoji, value, goal, pct, unit }) => (
            <div key={label} className="flex flex-col items-center gap-1 p-2 rounded-xl" style={{ background: '#242424' }}>
              <span className="text-xl">{emoji}</span>
              <p className="text-sm font-bold text-white">{value}/{goal}</p>
              <p className="text-[10px] text-gray-600">{unit}</p>
              <div className="w-full h-1 rounded-full" style={{ background: '#333' }}>
                <div className="h-full rounded-full" style={{
                  width: `${pct}%`,
                  background: pct >= 100 ? '#10b981' : '#7c3aed',
                }} />
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Sleep Chart */}
      <Card>
        <CardHeader title="😴 Sleep — Last 7 Days" subtitle="Goal: 8 hrs" />
        <ResponsiveContainer width="100%" height={130}>
          <BarChart data={chartData} barSize={28}>
            <XAxis dataKey="day" tick={{ fill: '#666', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 10]} hide />
            <Tooltip
              contentStyle={{ background: '#1a1a1a', border: '1px solid #333', borderRadius: 10, color: 'white', fontSize: 12 }}
              formatter={v => [`${v} hrs`, 'Sleep']}
              cursor={{ fill: 'rgba(255,255,255,0.04)' }}
            />
            <ReferenceLine y={8} stroke="#7c3aed" strokeDasharray="3 3" strokeOpacity={0.5} />
            <Bar dataKey="hrs" shape={<CustomBar />} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* Streaks */}
      <Card>
        <CardHeader title="🔥 Streaks" subtitle="From MEMORY.md" />
        <div className="flex gap-2">
          <StreakBadge icon="😴" label="Sleep streak"   value={streaks.sleep} />
          <StreakBadge icon="💪" label="Workouts/week"  value={streaks.workouts} />
        </div>
      </Card>

      {/* Workout plan if today */}
      {isWorkoutDay && workoutPlan && (
        <Card>
          <CardHeader title="💪 Today's Workout" subtitle="Tap exercises to mark done" />
          <p className="text-sm text-gray-300 leading-relaxed">{workoutPlan}</p>
        </Card>
      )}

      {/* Budget Meals */}
      {mealSuggestions && (
        <Card>
          <CardHeader title="🛒 Budget Meal Ideas" subtitle="High protein · Walmart-friendly" />
          <div className="flex flex-col gap-2">
            {Object.entries(mealSuggestions).map(([meal, options]) => (
              <div key={meal}>
                <p className="text-xs text-gray-500 font-semibold mb-1">
                  {MEAL_EMOJI[meal] || '🍽'} {meal}
                </p>
                {options.map((opt, i) => (
                  <p key={i} className="text-xs text-gray-300 ml-4 py-0.5">{opt}</p>
                ))}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
