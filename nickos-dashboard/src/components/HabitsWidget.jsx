import React, { useState } from 'react'
import Card, { CardHeader } from './Card.jsx'
import { mockHabits } from '../data/mockData.js'
import { api } from '../hooks/useApi.js'

export default function HabitsWidget() {
  const [habits, setHabits] = useState(mockHabits)

  const hit   = habits.filter(h => h.hit).length
  const total = habits.length
  const pct   = Math.round(hit / total * 100)

  function toggle(id) {
    const wasHit = habits.find(h => h.id === id)?.hit
    setHabits(prev => prev.map(h =>
      h.id === id ? { ...h, hit: !h.hit, streak: !h.hit ? h.streak + 1 : Math.max(0, h.streak - 1) } : h
    ))
    // Persist — revert optimistic update on failure
    api.logHabit(id, !wasHit).catch(() => {
      setHabits(prev => prev.map(h =>
        h.id === id ? { ...h, hit: wasHit, streak: wasHit ? h.streak + 1 : Math.max(0, h.streak - 1) } : h
      ))
    })
  }

  return (
    <Card>
      <CardHeader
        title="📋 Today's Habits"
        subtitle={`${hit}/${total} complete`}
        right={
          <span
            className="text-xs px-2.5 py-1 rounded-full font-semibold"
            style={{
              background: pct === 100 ? 'rgba(16,185,129,0.2)' : 'rgba(124,58,237,0.2)',
              color:      pct === 100 ? '#10b981' : '#a78bfa',
            }}
          >
            {pct}%
          </span>
        }
      />

      {/* Progress bar */}
      <div className="h-1.5 rounded-full mb-4" style={{ background: '#2a2a2a' }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: pct === 100
              ? 'linear-gradient(90deg,#10b981,#34d399)'
              : 'linear-gradient(90deg,#7c3aed,#a78bfa)',
          }}
        />
      </div>

      {/* Habit grid — 2 columns on larger screens */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {habits.map(h => (
          <button
            key={h.id}
            onClick={() => toggle(h.id)}
            className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl transition-all active:scale-95 text-left"
            style={{
              background: h.hit ? 'rgba(16,185,129,0.1)' : '#242424',
              border:     `1px solid ${h.hit ? 'rgba(16,185,129,0.3)' : '#333'}`,
            }}
          >
            {/* Check or empty circle */}
            <span className="text-base flex-shrink-0">{h.hit ? '✅' : '⬜'}</span>

            {/* Emoji + label */}
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate" style={{ color: h.hit ? '#d1fae5' : '#ccc' }}>
                {h.emoji} {h.label}
              </p>
              {/* Streak */}
              {h.streak > 0 && (
                <p className="text-[10px]" style={{ color: h.streak >= 7 ? '#f59e0b' : '#666' }}>
                  {h.streak >= 7 ? '🔥' : '▸'} {h.streak}d streak
                  {h.streak === h.best && h.streak > 1 ? ' 🏆 best!' : ''}
                </p>
              )}
            </div>

            {/* Water progress special case */}
            {h.id === 'water' && h.goal && (
              <span className="text-xs font-bold flex-shrink-0"
                    style={{ color: h.value >= h.goal ? '#10b981' : '#3b82f6' }}>
                {h.value}/{h.goal}
              </span>
            )}
          </button>
        ))}
      </div>
    </Card>
  )
}
