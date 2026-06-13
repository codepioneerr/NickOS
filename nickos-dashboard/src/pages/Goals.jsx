import React, { useState, useEffect } from 'react'
import Card, { CardHeader } from '../components/Card.jsx'
import { api } from '../hooks/useApi.js'

const DEADLINE_COLORS = {
  critical: '#ef4444',
  soon:     '#f59e0b',
  ok:       '#7c3aed',
}

function daysUntil(dateStr) {
  if (!dateStr) return null
  const diff = Math.ceil((new Date(dateStr) - new Date()) / 86400000)
  return diff
}

function GoalCard({ goal }) {
  const [expanded, setExpanded] = useState(false)
  const days = daysUntil(goal.target)
  const urgency = days !== null && days <= 7 ? 'critical' : days !== null && days <= 21 ? 'soon' : 'ok'
  const urgencyColor = DEADLINE_COLORS[urgency]

  return (
    <div className="rounded-2xl p-4 transition-all" style={{ background: '#1a1a1a', border: '1px solid #333' }}>
      <div className="flex items-start gap-3">
        <span className="text-2xl mt-0.5">{goal.emoji}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-bold text-white">{goal.name}</h3>
            {days !== null && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    style={{ background: `${urgencyColor}22`, color: urgencyColor }}>
                {days > 0 ? `${days}d left` : days === 0 ? 'Today' : 'Overdue'}
              </span>
            )}
          </div>
          {goal.target && (
            <p className="text-xs text-gray-500 mt-0.5">📅 Target: {goal.target}</p>
          )}
        </div>
        <button onClick={() => setExpanded(e => !e)}
                className="text-gray-600 text-lg leading-none flex-shrink-0 transition-transform"
                style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>›</button>
      </div>

      {/* Progress bar — shows 5% minimum so bar is visible */}
      <div className="mt-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-gray-500">Progress</span>
          <span className="text-xs font-bold" style={{ color: '#a78bfa' }}>
            {goal.progress || 0}%
          </span>
        </div>
        <div className="h-2 rounded-full" style={{ background: '#2a2a2a' }}>
          <div className="h-full rounded-full transition-all duration-700"
               style={{
                 width: `${Math.max(5, goal.progress || 0)}%`,
                 background: 'linear-gradient(90deg,#7c3aed,#a78bfa)',
               }} />
        </div>
      </div>

      {/* Next action placeholder */}
      <div className="mt-3 px-3 py-2 rounded-xl" style={{ background: 'rgba(124,58,237,0.1)', border: '1px solid rgba(124,58,237,0.2)' }}>
        <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-0.5">Next action</p>
        <p className="text-xs text-white">{goal.nextAction || 'Log progress via /goal command in Telegram'}</p>
      </div>

      {expanded && goal.wins && goal.wins.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-2">Wins so far</p>
          {goal.wins.map((win, i) => (
            <div key={i} className="flex items-center gap-2 py-1">
              <span className="text-green-500 text-xs">✓</span>
              <span className="text-xs text-gray-300">{win}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Goals() {
  const [goals,  setGoals]  = useState([])
  const [wins,   setWins]   = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [winText, setWinText] = useState('')
  const [localWins, setLocalWins] = useState([])

  useEffect(() => {
    api.goals()
      .then(data => {
        setGoals(data.goals || [])
        setWins(data.wins || [])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const overallProgress = goals.length
    ? Math.round(goals.reduce((s, g) => s + (g.progress || 0), 0) / goals.length)
    : 0

  function addWin() {
    if (!winText.trim()) return
    setLocalWins(p => [{ id: Date.now(), text: winText, time: 'Just now' }, ...p])
    setWinText('')
    setShowAdd(false)
  }

  return (
    <div className="flex flex-col gap-4 pb-2">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white tracking-tight">Goals 🎯</h1>
        <div className="text-right">
          <p className="text-2xl font-bold" style={{ color: '#7c3aed' }}>{overallProgress}%</p>
          <p className="text-[10px] text-gray-500">avg progress</p>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col gap-3">
          {[1,2,3].map(i => <div key={i} className="shimmer rounded-2xl" style={{ height: 120 }} />)}
        </div>
      ) : goals.length === 0 ? (
        <Card>
          <p className="text-sm text-gray-500 text-center py-6">
            No active goals. Add goals in MEMORY.md or via Telegram /goal command.
          </p>
        </Card>
      ) : (
        <>
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-500">
            Active ({goals.length})
          </p>
          <div className="flex flex-col gap-3">
            {goals.map(goal => <GoalCard key={goal.id} goal={goal} />)}
          </div>
        </>
      )}

      {/* Daily wins log */}
      <Card>
        <CardHeader
          title="🏆 Daily Wins"
          subtitle="Small wins compound"
          right={
            <button onClick={() => setShowAdd(v => !v)}
                    className="text-xs px-3 py-1.5 rounded-full font-semibold transition-all active:scale-95"
                    style={{ background: 'rgba(124,58,237,0.2)', color: '#a78bfa', border: '1px solid rgba(124,58,237,0.3)' }}>
              + Add
            </button>
          }
        />

        {showAdd && (
          <div className="flex gap-2 mb-3">
            <input
              autoFocus
              value={winText}
              onChange={e => setWinText(e.target.value)}
              placeholder="What did you accomplish?"
              className="flex-1 rounded-xl px-3 py-2.5 text-sm text-white outline-none"
              style={{ background: '#2a2a2a', border: '1px solid #3a3a3a' }}
              onKeyDown={e => e.key === 'Enter' && addWin()}
            />
            <button onClick={addWin}
                    className="px-4 py-2.5 rounded-xl text-sm font-bold active:scale-95"
                    style={{ background: '#7c3aed', color: 'white' }}>Log</button>
          </div>
        )}

        <div className="flex flex-col gap-2">
          {[...localWins, ...wins].slice(0, 10).map((win, i) => (
            <div key={win.id || i} className="flex items-start gap-2.5 py-1.5 border-b border-[#2a2a2a] last:border-0">
              <span className="text-sm mt-0.5">🏅</span>
              <div className="flex-1">
                <p className="text-sm text-white">{win.text}</p>
                {win.time && <p className="text-[10px] text-gray-600 mt-0.5">{win.time}</p>}
              </div>
            </div>
          ))}
          {localWins.length === 0 && wins.length === 0 && (
            <p className="text-xs text-gray-600 text-center py-3">
              No wins logged yet. Use /done in Telegram or tap + Add.
            </p>
          )}
        </div>
      </Card>
    </div>
  )
}
