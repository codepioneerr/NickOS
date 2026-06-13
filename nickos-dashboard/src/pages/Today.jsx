import React, { useState, useEffect, useCallback } from 'react'
import Card, { CardHeader } from '../components/Card.jsx'
import HealthRing from '../components/HealthRing.jsx'
import NudgeTimer from '../components/NudgeTimer.jsx'
import QuickLog from '../components/QuickLog.jsx'
import HabitsWidget from '../components/HabitsWidget.jsx'
import FocusTimer from '../components/FocusTimer.jsx'
import InsightsPanel from '../components/InsightsPanel.jsx'
import ObsidianSearch from '../components/ObsidianSearch.jsx'
import { api, SSE_URL } from '../hooks/useApi.js'

const TAG_CONFIG = {
  act_now:     { label: '🔴 Act Now',    bg: 'rgba(239,68,68,0.15)',   border: 'rgba(239,68,68,0.4)',   text: '#ef4444' },
  opportunity: { label: '🟠 Opportunity', bg: 'rgba(245,158,11,0.15)', border: 'rgba(245,158,11,0.4)', text: '#f59e0b' },
  fyi:         { label: '🔵 FYI',         bg: 'rgba(59,130,246,0.15)', border: 'rgba(59,130,246,0.4)', text: '#3b82f6' },
}

// ── Sub-sections ─────────────────────────────────────────────────────────────

function HealthSection({ health }) {
  const avgPct = Math.round(
    [health.sleep, health.meals, health.water, health.workout]
      .reduce((s, x) => s + x.pct, 0) / 4
  )
  return (
    <Card>
      <CardHeader
        title="Health Rings"
        subtitle="Today's progress"
        right={
          <span className="text-xs px-2.5 py-1 rounded-full font-semibold"
                style={{ background: 'rgba(124,58,237,0.2)', color: '#a78bfa' }}>
            {avgPct}%
          </span>
        }
      />
      <div className="health-ring-wrap">
        <HealthRing health={health} />
      </div>
    </Card>
  )
}

function FocusSection({ focus }) {
  return (
    <Card accent>
      <div className="flex items-start gap-3">
        <span className="text-2xl mt-0.5">🎯</span>
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest mb-1.5" style={{ color: '#a78bfa' }}>
            Today's Focus
          </p>
          <p className="text-sm lg:text-base text-white leading-relaxed">{focus}</p>
        </div>
      </div>
    </Card>
  )
}

function AffirmSection({ text, onRefresh, refreshing }) {
  return (
    <Card>
      <div className="flex items-start gap-3">
        <span className="text-2xl mt-0.5">✨</span>
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: '#a78bfa' }}>
              Affirmation
            </p>
            <button onClick={onRefresh} disabled={refreshing}
                    className="text-xs text-gray-500 hover:text-gray-300 transition-colors disabled:opacity-40">
              {refreshing ? '…' : '↻ refresh'}
            </button>
          </div>
          <p className="text-sm lg:text-base text-gray-200 leading-relaxed italic">"{text}"</p>
        </div>
      </div>
    </Card>
  )
}

function WorkoutSection({ plan }) {
  return (
    <Card>
      <CardHeader title="💪 Today's Workout" subtitle="Tap when done" />
      <p className="text-sm text-gray-300 leading-relaxed">{plan}</p>
    </Card>
  )
}

function CalendarSection({ events }) {
  if (!events || events.length === 0) {
    return (
      <Card>
        <CardHeader title="📅 Today's Schedule" subtitle="No events today" />
        <p className="text-xs text-gray-600 text-center py-4">
          Connect Google Calendar to see events here
        </p>
      </Card>
    )
  }
  return (
    <Card>
      <CardHeader title="📅 Today's Schedule" subtitle={`${events.length} events`} />
      <div className="flex flex-col gap-1">
        {events.map(ev => (
          <div key={ev.id} className="flex items-center gap-3 py-2.5 border-b border-[#2a2a2a] last:border-0">
            <div className="w-1 self-stretch rounded-full flex-shrink-0" style={{ background: ev.color || '#7c3aed' }} />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-white font-medium truncate">{ev.title}</p>
              <p className="text-xs text-gray-500">
                {ev.time}{ev.duration ? ` · ${ev.duration} min` : ''}
              </p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

function EmailSection({ emails }) {
  const urgent = (emails || []).filter(e => e.tag === 'act_now' || e.tag === 'opportunity').slice(0, 3)
  if (!urgent.length) {
    return (
      <Card>
        <CardHeader title="📬 Email Alerts" subtitle="All clear" />
        <p className="text-xs text-gray-600 text-center py-4">✅ Nothing urgent right now</p>
      </Card>
    )
  }
  return (
    <Card>
      <CardHeader
        title="📬 Email Alerts"
        subtitle="Act Now + Opportunities"
        right={<span className="text-xs text-gray-500">{urgent.length} urgent</span>}
      />
      <div className="flex flex-col gap-2">
        {urgent.map(email => {
          const cfg = TAG_CONFIG[email.tag] || TAG_CONFIG.fyi
          return (
            <div key={email.id} className="rounded-xl p-3"
                 style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold" style={{ color: cfg.text }}>{cfg.label}</span>
                <span className="text-xs text-gray-500">{email.account}</span>
              </div>
              <p className="text-sm text-white font-medium leading-snug">{email.subject}</p>
              <p className="text-xs text-gray-400 mt-1 line-clamp-2">{email.preview}</p>
            </div>
          )
        })}
      </div>
    </Card>
  )
}

function GoalsSummarySection({ goals }) {
  const active = (goals || []).slice(0, 3)
  return (
    <Card>
      <CardHeader title="🎯 Active Goals" subtitle={`${active.length} in progress`} />
      <div className="flex flex-col gap-3">
        {active.map(g => (
          <div key={g.id}>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm text-white font-medium">{g.emoji} {g.name}</span>
              {g.target && <span className="text-xs text-gray-600">📅 {g.target}</span>}
            </div>
            <div className="h-1.5 rounded-full" style={{ background: '#2a2a2a' }}>
              <div className="h-full rounded-full" style={{
                width: `${g.progress || 5}%`,
                background: 'linear-gradient(90deg,#7c3aed,#a78bfa)',
              }} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

function Shimmer() {
  return (
    <div className="flex flex-col gap-4">
      {[160, 100, 80, 120].map((h, i) => (
        <div key={i} className="shimmer rounded-2xl" style={{ height: h }} />
      ))}
    </div>
  )
}

// ── Main ─────────────────────────────────────────────────────────────────────
export default function Today() {
  const [data,      setData]      = useState(null)
  const [emails,    setEmails]    = useState([])
  const [affText,   setAffText]   = useState('Discipline is just doing the thing when you don\'t feel like it.')
  const [affRefreshing, setAffRefreshing] = useState(false)
  const [error,     setError]     = useState(null)

  const loadToday = useCallback(async () => {
    try {
      const d = await api.today()
      setData(d)
      if (d.affirmation?.text) setAffText(d.affirmation.text)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  const loadEmails = useCallback(async () => {
    try {
      const e = await api.emails()
      setEmails(e || [])
    } catch (_) {}
  }, [])

  useEffect(() => {
    loadToday()
    loadEmails()

    // ── SSE: live reload when Telegram bot logs health data ──────────────────
    let es
    try {
      es = new EventSource(SSE_URL)
      es.addEventListener('health_updated', () => loadToday())
      es.onerror = () => {
        // silently close — will reconnect on next page focus
        es.close()
      }
    } catch (_) {}

    return () => es?.close()
  }, [])

  async function refreshAffirmation() {
    setAffRefreshing(true)
    try {
      const r = await api.affirmation(true)
      if (r.text) setAffText(r.text)
    } catch (_) {}
    setAffRefreshing(false)
  }

  if (error) return (
    <div className="flex flex-col items-center justify-center min-h-64 gap-3">
      <p className="text-red-400 text-sm">⚠️ {error}</p>
      <button onClick={loadToday} className="text-xs text-gray-400 underline">Retry</button>
    </div>
  )

  if (!data) return <Shimmer />

  const { health, focus, nextNudge, isWorkoutDay, workout, calendar, goals, date, greeting } = data

  const healthScore = Math.round(
    [health.sleep, health.meals, health.water, health.workout]
      .reduce((s, x) => s + x.pct, 0) / 4
  )

  return (
    <div className="flex flex-col gap-5 lg:gap-6 pb-2">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-500 font-medium tracking-widest uppercase">{date}</p>
          <h1 className="text-2xl lg:text-3xl xl:text-4xl font-bold text-white mt-0.5 tracking-tight">
            {greeting} 👋
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="hidden lg:flex flex-col items-center">
            <span className="text-3xl font-black" style={{ color: healthScore >= 80 ? '#10b981' : '#7c3aed' }}>
              {healthScore}
            </span>
            <span className="text-[10px] text-gray-500 uppercase tracking-widest">Health</span>
          </div>
          <div className="w-11 h-11 rounded-full flex items-center justify-center text-lg font-bold"
               style={{ background: 'linear-gradient(135deg, #7c3aed, #a78bfa)' }}>N</div>
        </div>
      </div>

      {/* Mobile */}
      <div className="flex flex-col gap-4 lg:hidden">
        <HealthSection health={health} />
        <InsightsPanel />
        <FocusTimer />
        <HabitsWidget />
        <FocusSection focus={focus} />
        <Card>
          <NudgeTimer label={nextNudge.label} minutesAway={Math.ceil(nextNudge.seconds_left / 60)} />
        </Card>
        {isWorkoutDay && <WorkoutSection plan={workout} />}
        <AffirmSection text={affText} onRefresh={refreshAffirmation} refreshing={affRefreshing} />
        <Card>
          <CardHeader title="Quick Log" subtitle="Tap to log your day" />
          <QuickLog onLogged={loadToday} />
        </Card>
        <CalendarSection events={calendar} />
        <EmailSection emails={emails} />
        <GoalsSummarySection goals={goals} />
        <ObsidianSearch />
      </div>

      {/* Desktop 3-col */}
      <div className="hidden lg:grid grid-cols-3 gap-5 xl:gap-6 items-start">
        <div className="flex flex-col gap-5">
          <HealthSection health={health} />
          <HabitsWidget />
          <FocusSection focus={focus} />
          <AffirmSection text={affText} onRefresh={refreshAffirmation} refreshing={affRefreshing} />
          <Card>
            <CardHeader title="Quick Log" subtitle="Tap to log your day" />
            <QuickLog onLogged={loadToday} />
          </Card>
        </div>
        <div className="flex flex-col gap-5">
          <FocusTimer />
          <Card>
            <NudgeTimer label={nextNudge.label} minutesAway={Math.ceil(nextNudge.seconds_left / 60)} />
          </Card>
          {isWorkoutDay && <WorkoutSection plan={workout} />}
          <CalendarSection events={calendar} />
        </div>
        <div className="flex flex-col gap-5">
          <InsightsPanel />
          <EmailSection emails={emails} />
          <GoalsSummarySection goals={goals} />
          <ObsidianSearch />
        </div>
      </div>
    </div>
  )
}
