import React, { useState } from 'react'
import { api } from '../hooks/useApi.js'

const LOGS = [
  { key: 'sleep',   emoji: '😴', label: 'Sleep',   type: 'number', placeholder: '7.5', hint: 'hrs' },
  { key: 'meal',    emoji: '🍳', label: 'Meal',    type: 'text',   placeholder: 'Chicken + rice', hint: '' },
  { key: 'water',   emoji: '💧', label: 'Water',   type: 'number', placeholder: '1', hint: 'glasses' },
  { key: 'workout', emoji: '💪', label: 'Workout', type: 'text',   placeholder: 'Push Day A', hint: '' },
]

export default function QuickLog({ onLogged }) {
  const [active,  setActive]  = useState(null)
  const [value,   setValue]   = useState('')
  const [toast,   setToast]   = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleLog(key) {
    if (!value.trim()) return
    setLoading(true)
    try {
      switch (key) {
        case 'sleep':   await api.logSleep(parseFloat(value));      break
        case 'meal':    await api.logMeal(value);                   break
        case 'water':   await api.logWater(parseInt(value) || 1);   break
        case 'workout': await api.logWorkout(value);                break
      }
      const item = LOGS.find(l => l.key === key)
      setToast(`${item.emoji} ${item.label} logged!`)
      setTimeout(() => setToast(null), 2500)
      onLogged?.(key)
    } catch (err) {
      setToast(`❌ ${err.message}`)
      setTimeout(() => setToast(null), 3000)
    } finally {
      setLoading(false)
      setActive(null)
      setValue('')
    }
  }

  return (
    <>
      {toast && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 rounded-full text-sm font-medium"
             style={{ background: toast.startsWith('❌') ? '#ef4444' : '#7c3aed', color: 'white',
                      boxShadow: '0 4px 20px rgba(124,58,237,0.5)' }}>
          {toast}
        </div>
      )}

      <div className="grid grid-cols-4 gap-2">
        {LOGS.map(item => (
          <button
            key={item.key}
            onClick={() => { setActive(active === item.key ? null : item.key); setValue('') }}
            className="flex flex-col items-center gap-1.5 py-3 rounded-xl transition-all active:scale-95"
            style={{
              background: active === item.key ? 'rgba(124,58,237,0.2)' : '#242424',
              border: active === item.key ? '1px solid rgba(124,58,237,0.6)' : '1px solid #333',
            }}
          >
            <span className="text-2xl">{item.emoji}</span>
            <span className="text-[10px] text-gray-400">{item.label}</span>
          </button>
        ))}
      </div>

      {active && (() => {
        const item = LOGS.find(l => l.key === active)
        return (
          <div className="mt-3 flex gap-2">
            <input
              autoFocus
              type={item.type}
              value={value}
              onChange={e => setValue(e.target.value)}
              placeholder={item.hint ? `${item.placeholder} ${item.hint}` : item.placeholder}
              className="flex-1 rounded-xl px-4 py-2.5 text-sm text-white outline-none"
              style={{ background: '#2a2a2a', border: '1px solid #3a3a3a' }}
              onKeyDown={e => e.key === 'Enter' && handleLog(active)}
              step={item.type === 'number' ? '0.5' : undefined}
              min={item.type === 'number' ? '0' : undefined}
            />
            <button
              onClick={() => handleLog(active)}
              disabled={loading || !value.trim()}
              className="px-4 py-2.5 rounded-xl text-sm font-semibold transition-all active:scale-95 disabled:opacity-50"
              style={{ background: '#7c3aed', color: 'white' }}
            >
              {loading ? '…' : 'Log'}
            </button>
          </div>
        )
      })()}
    </>
  )
}
