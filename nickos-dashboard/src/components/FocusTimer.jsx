import React, { useState, useEffect, useRef, useCallback } from 'react'
import Card, { CardHeader } from './Card.jsx'
import { api } from '../hooks/useApi.js'

const WORK_MIN  = 25
const BREAK_MIN = 5

function fmt(s) {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${String(sec).padStart(2, '0')}`
}

export default function FocusTimer() {
  const [mode, setMode]         = useState('idle')   // idle | work | break
  const [secondsLeft, setSecs]  = useState(WORK_MIN * 60)
  const [label, setLabel]       = useState('')
  const [sessions, setSessions] = useState(0)
  const [justDone, setJustDone] = useState(false)
  const intervalRef = useRef(null)

  const stopTick = () => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
  }

  const notify = useCallback((title, body) => {
    try {
      if ('Notification' in window) {
        if (Notification.permission === 'granted') new Notification(title, { body })
        else if (Notification.permission !== 'denied') Notification.requestPermission()
      }
    } catch { /* no-op */ }
  }, [])

  useEffect(() => () => stopTick(), [])

  useEffect(() => {
    if (mode === 'idle') return
    if (secondsLeft > 0) return

    stopTick()
    if (mode === 'work') {
      // Work block complete → log it (backend also pings Telegram)
      api.logFocus(WORK_MIN, label).catch(() => {})
      setSessions(n => n + 1)
      setJustDone(true)
      notify('🎯 Focus session done!', `${WORK_MIN}min in the books — 5min break.`)
      setMode('break')
      setSecs(BREAK_MIN * 60)
      startTick()
    } else {
      notify('⚡ Break over', 'Back to work — start the next session.')
      setMode('idle')
      setSecs(WORK_MIN * 60)
    }
  }, [secondsLeft, mode]) // eslint-disable-line react-hooks/exhaustive-deps

  function startTick() {
    stopTick()
    intervalRef.current = setInterval(() => setSecs(s => Math.max(0, s - 1)), 1000)
  }

  function start() {
    setJustDone(false)
    setMode('work')
    setSecs(WORK_MIN * 60)
    if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission()
    startTick()
  }

  function cancel() {
    stopTick()
    setMode('idle')
    setSecs(WORK_MIN * 60)
  }

  const isRunning = mode !== 'idle'
  const total     = (mode === 'break' ? BREAK_MIN : WORK_MIN) * 60
  const pct       = isRunning ? Math.round((1 - secondsLeft / total) * 100) : 0
  const accent    = mode === 'break' ? '#10b981' : '#a78bfa'

  return (
    <Card accent={isRunning}>
      <CardHeader
        title="🎯 Focus Session"
        subtitle={mode === 'work' ? 'Deep work — no distractions' : mode === 'break' ? 'Break — step away' : '25min work + 5min break'}
        right={sessions > 0 && (
          <span className="text-xs px-2.5 py-1 rounded-full font-semibold"
                style={{ background: 'rgba(124,58,237,0.2)', color: '#a78bfa' }}>
            🔥 {sessions} today
          </span>
        )}
      />

      {isRunning ? (
        <div className="flex flex-col items-center gap-3">
          <p className="text-5xl font-black tabular-nums" style={{ color: accent }}>
            {fmt(secondsLeft)}
          </p>
          <div className="w-full h-1.5 rounded-full" style={{ background: '#2a2a2a' }}>
            <div className="h-full rounded-full transition-all duration-1000"
                 style={{ width: `${pct}%`, background: accent }} />
          </div>
          {label && mode === 'work' && (
            <p className="text-xs text-gray-400 truncate max-w-full">📌 {label}</p>
          )}
          <button
            onClick={cancel}
            className="text-xs px-4 py-2 rounded-xl font-semibold active:scale-95 transition-transform"
            style={{ background: '#242424', border: '1px solid #333', color: '#999' }}
          >
            ✕ End early
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {justDone && (
            <p className="text-xs text-center" style={{ color: '#10b981' }}>
              ✅ Session logged — nice work.
            </p>
          )}
          <input
            value={label}
            onChange={e => setLabel(e.target.value)}
            placeholder="What are you focusing on? (optional)"
            maxLength={100}
            className="w-full px-3 py-2.5 rounded-xl text-sm text-white placeholder-gray-600 outline-none"
            style={{ background: '#242424', border: '1px solid #333' }}
          />
          <button
            onClick={start}
            className="w-full py-3 rounded-xl font-bold text-sm active:scale-[0.98] transition-transform"
            style={{ background: 'linear-gradient(90deg,#7c3aed,#a78bfa)', color: '#fff' }}
          >
            ▶ Start 25min Focus
          </button>
        </div>
      )}
    </Card>
  )
}
