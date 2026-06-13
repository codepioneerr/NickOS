import React, { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts'
import Card, { CardHeader } from '../components/Card.jsx'
import { api } from '../hooks/useApi.js'

const GRADE_COLORS = {
  'A+': '#10b981', A: '#10b981', 'A-': '#34d399',
  'B+': '#7c3aed', B: '#7c3aed', 'B-': '#a78bfa',
  'C+': '#f59e0b', C: '#f59e0b', 'C-': '#fcd34d',
  D:    '#ef4444', F: '#ef4444',
}

const TOOLTIP_STYLE = {
  background: '#1a1a1a', border: '1px solid #333',
  borderRadius: 10, color: 'white', fontSize: 12,
}

// ── Sub-components ────────────────────────────────────────────────────────────

function GradeCard({ icon, label, grade, detail, trend }) {
  const color = GRADE_COLORS[grade] || '#666'
  return (
    <div className="flex-1 rounded-xl p-3 flex flex-col gap-1.5"
         style={{ background: '#242424', border: '1px solid #333' }}>
      <span className="text-xl">{icon}</span>
      <p className="text-2xl font-black" style={{ color }}>{grade}</p>
      <p className="text-xs text-white font-medium">{label}</p>
      <p className="text-[10px] text-gray-500">{detail}</p>
      <p className="text-[10px]"
         style={{ color: trend.includes('+') ? '#10b981' : trend.includes('-') ? '#ef4444' : '#666' }}>
        {trend}
      </p>
    </div>
  )
}

function Shimmer() {
  return (
    <div className="flex flex-col gap-4">
      {[180, 140, 100, 160, 120].map((h, i) => (
        <div key={i} className="shimmer rounded-2xl" style={{ height: h }} />
      ))}
    </div>
  )
}

function SleepTrendChart({ data }) {
  return (
    <Card>
      <CardHeader title="😴 Sleep Trend" subtitle="Last 30 days" />
      <ResponsiveContainer width="100%" height={140}>
        <BarChart data={data} margin={{ top: 4, right: 4, left: -32, bottom: 0 }}>
          <XAxis
            dataKey="day"
            tick={{ fill: '#666', fontSize: 10 }}
            axisLine={false} tickLine={false}
            interval={4}
          />
          <YAxis domain={[0, 10]} tick={{ fill: '#666', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(v) => [`${v}h`, 'Sleep']}
            labelFormatter={(_, payload) => payload?.[0]?.payload?.date || ''}
            cursor={{ fill: 'rgba(255,255,255,0.05)' }}
          />
          <ReferenceLine y={8} stroke="#10b981" strokeDasharray="3 3" strokeOpacity={0.5} />
          <Bar dataKey="hours" radius={[4, 4, 0, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.hours >= 7 ? '#7c3aed' : entry.hours >= 5 ? '#f59e0b' : '#ef4444'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex gap-3 mt-1">
        {[['#7c3aed', '≥7h (great)'], ['#f59e0b', '5–7h (ok)'], ['#ef4444', '<5h (low)']].map(([c, l]) => (
          <span key={l} className="flex items-center gap-1 text-[10px] text-gray-500">
            <span className="w-2 h-2 rounded-sm inline-block" style={{ background: c }} />{l}
          </span>
        ))}
      </div>
    </Card>
  )
}

function MealConsistencyChart({ data }) {
  const recent = (data.byDay || []).slice(-14)
  return (
    <Card>
      <CardHeader
        title="🍳 Meal Consistency"
        subtitle="Last 14 days"
        right={
          <span className="text-xs px-2.5 py-1 rounded-full font-semibold"
                style={{ background: 'rgba(124,58,237,0.2)', color: '#a78bfa' }}>
            {data.pct ?? 0}% ✓
          </span>
        }
      />
      <ResponsiveContainer width="100%" height={100}>
        <BarChart data={recent} margin={{ top: 4, right: 4, left: -32, bottom: 0 }}>
          <XAxis dataKey="day" tick={{ fill: '#666', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis domain={[0, 3]} ticks={[0, 1, 2, 3]} tick={{ fill: '#666', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(v) => [`${v}/3 meals`, '']}
            labelFormatter={(_, payload) => payload?.[0]?.payload?.date || ''}
            cursor={{ fill: 'rgba(255,255,255,0.05)' }}
          />
          <ReferenceLine y={3} stroke="#10b981" strokeDasharray="3 3" strokeOpacity={0.4} />
          <Bar dataKey="meals" radius={[3, 3, 0, 0]}>
            {recent.map((entry, i) => (
              <Cell key={i} fill={entry.meals >= 3 ? '#10b981' : entry.meals >= 2 ? '#f59e0b' : '#ef4444'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="text-[11px] text-gray-500 mt-1">
        {data.threeMealDays ?? 0}/{data.daysLogged ?? 0} days with all 3 meals (last 30d)
      </p>
    </Card>
  )
}

function WorkoutFreqCard({ thisWeek, lastWeek, goal }) {
  const bars = [
    { week: 'Last', count: lastWeek },
    { week: 'This', count: thisWeek },
  ]
  return (
    <Card>
      <CardHeader
        title="💪 Workouts"
        subtitle={`${thisWeek}/${goal} this week`}
        right={
          <span className="text-xs font-semibold"
                style={{ color: thisWeek >= lastWeek ? '#10b981' : '#ef4444' }}>
            {thisWeek >= lastWeek ? '↑' : '↓'} vs last week
          </span>
        }
      />
      <ResponsiveContainer width="100%" height={90}>
        <BarChart data={bars} layout="vertical" margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <XAxis type="number" domain={[0, goal]} tick={{ fill: '#666', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis dataKey="week" type="category" tick={{ fill: '#aaa', fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
          <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${v} sessions`, '']} cursor={false} />
          <ReferenceLine x={goal} stroke="#10b981" strokeDasharray="3 3" strokeOpacity={0.5} />
          <Bar dataKey="count" radius={[0, 4, 4, 0]}>
            <Cell fill="#444" />
            <Cell fill="#7c3aed" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  )
}

function GoalsBurndown({ goals }) {
  if (!goals?.active?.length && goals?.done === 0) return null
  return (
    <Card>
      <CardHeader
        title="🏁 Goals"
        subtitle={`${goals.done ?? 0}/${goals.total ?? 0} complete`}
      />
      {goals.active?.length > 0 ? (
        <div className="flex flex-col gap-2">
          {goals.active.map((g, i) => (
            <div key={g.id || i} className="flex items-center gap-3 py-2 border-b border-[#2a2a2a] last:border-0">
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0"
                    style={{ background: 'rgba(124,58,237,0.2)', color: '#a78bfa' }}>
                {g.target}
              </span>
              <p className="text-xs text-white flex-1 truncate">{g.name}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-gray-500">All goals complete 🏆</p>
      )}
    </Card>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function Weekly() {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const d = await api.weekly()
      setData(d)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <Shimmer />

  if (error) return (
    <div className="flex flex-col items-center justify-center min-h-64 gap-3">
      <p className="text-red-400 text-sm">⚠️ {error}</p>
      <button onClick={load} className="text-xs text-gray-400 underline">Retry</button>
    </div>
  )

  if (!data) return <Shimmer />

  const { reportCard: rc, weekLabel, oneThingToImprove, trendChart,
          sleepTrend, mealConsistency, workoutFreq, goals, focus } = data

  return (
    <div className="flex flex-col gap-4 pb-2">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Weekly 📊</h1>
          <p className="text-xs text-gray-500 mt-0.5">{weekLabel}</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={load}
                  className="text-xs px-2.5 py-1 rounded-full font-semibold active:scale-95 transition-transform"
                  style={{ background: 'rgba(124,58,237,0.2)', color: '#a78bfa' }}>
            ↻ Refresh
          </button>
          <div className="text-right">
            <p className="text-3xl font-black" style={{ color: GRADE_COLORS[rc.overall.grade] || '#7c3aed' }}>
              {rc.overall.grade}
            </p>
            <p className="text-[10px] text-gray-500">Overall</p>
          </div>
        </div>
      </div>

      {/* Report Card */}
      <Card>
        <CardHeader title="📋 Health Report Card" subtitle="This week's grades" />
        <div className="flex gap-2">
          <GradeCard icon="😴" label="Sleep"   grade={rc.sleep.grade}   detail={`${rc.sleep.avg}h avg`}                  trend={rc.sleep.trend} />
          <GradeCard icon="🍳" label="Meals"   grade={rc.meals.grade}   detail={`${rc.meals.avg} avg`}                   trend={rc.meals.trend} />
          <GradeCard icon="💧" label="Water"   grade={rc.water.grade}   detail={rc.water.avg}                             trend={rc.water.trend} />
          <GradeCard icon="💪" label="Workout" grade={rc.workout.grade} detail={`${rc.workout.done}/${rc.workout.goal}`}  trend={rc.workout.trend} />
        </div>

        <div className="mt-4 px-4 py-3 rounded-xl flex items-center justify-between"
             style={{ background: 'rgba(124,58,237,0.1)', border: '1px solid rgba(124,58,237,0.25)' }}>
          <div>
            <p className="text-xs text-gray-400">Overall Health Score</p>
            <p className="text-xs text-gray-600 mt-0.5">{rc.overall.trend}</p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-black" style={{ color: '#7c3aed' }}>{rc.overall.score}</p>
            <p className="text-[10px] text-gray-500">/ 100</p>
          </div>
        </div>
      </Card>

      {/* 5-week score trend */}
      {trendChart?.length > 0 && (
        <Card>
          <CardHeader title="📈 Score Trend" subtitle="Last 5 weeks" />
          <ResponsiveContainer width="100%" height={130}>
            <LineChart data={trendChart}>
              <XAxis dataKey="week" tick={{ fill: '#666', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} hide />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(v) => [`${v} pts`, 'Health Score']}
                cursor={{ stroke: 'rgba(255,255,255,0.1)' }}
              />
              <ReferenceLine y={80} stroke="#10b981" strokeDasharray="3 3" strokeOpacity={0.4} />
              <Line type="monotone" dataKey="score" stroke="#7c3aed" strokeWidth={2.5}
                    dot={{ fill: '#7c3aed', r: 4, strokeWidth: 0 }}
                    activeDot={{ fill: '#a78bfa', r: 6, strokeWidth: 0 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* One thing to improve */}
      {oneThingToImprove && (
        <Card accent>
          <div className="flex items-start gap-3">
            <span className="text-2xl mt-0.5">🔧</span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest mb-1.5" style={{ color: '#a78bfa' }}>
                One Thing to Improve
              </p>
              <p className="text-sm text-white leading-relaxed">{oneThingToImprove}</p>
            </div>
          </div>
        </Card>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {sleepTrend?.length > 0 && <SleepTrendChart data={sleepTrend} />}
        {mealConsistency && <MealConsistencyChart data={mealConsistency} />}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {workoutFreq && (
          <WorkoutFreqCard
            thisWeek={workoutFreq.thisWeek}
            lastWeek={workoutFreq.lastWeek}
            goal={workoutFreq.goal}
          />
        )}
        {goals && <GoalsBurndown goals={goals} />}
      </div>

      {/* Focus sessions */}
      {focus && (
        <Card>
          <div className="flex items-center gap-3">
            <span className="text-2xl">🎯</span>
            <div>
              <p className="text-sm font-semibold text-white">
                {focus.sessions} focus session{focus.sessions !== 1 ? 's' : ''} this week
              </p>
              <p className="text-xs text-gray-500">{focus.minutes} minutes of deep work</p>
            </div>
            <span className="ml-auto text-xs px-2.5 py-1 rounded-full font-semibold"
                  style={{ background: 'rgba(124,58,237,0.2)', color: '#a78bfa' }}>
              {focus.sessions > 0 ? '🔥 building habit' : '⚡ start today'}
            </span>
          </div>
        </Card>
      )}

    </div>
  )
}
