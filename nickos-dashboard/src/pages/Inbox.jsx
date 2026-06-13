import React, { useState, useEffect, useCallback } from 'react'
import Card, { CardHeader } from '../components/Card.jsx'
import { api } from '../hooks/useApi.js'

const TAG_CONFIG = {
  act_now:     { label: '🔴 Act Now',     bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.35)',   text: '#ef4444', badgeBg: 'rgba(239,68,68,0.2)' },
  opportunity: { label: '🟠 Opportunity',  bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.35)', text: '#f59e0b', badgeBg: 'rgba(245,158,11,0.2)' },
  fyi:         { label: '🔵 FYI',          bg: 'rgba(59,130,246,0.12)', border: 'rgba(59,130,246,0.35)', text: '#3b82f6', badgeBg: 'rgba(59,130,246,0.2)' },
}
const FILTERS = ['all', 'act_now', 'opportunity', 'fyi']

// ── Add-to-Calendar mini modal ────────────────────────────────────────────────
function CalendarModal({ email, onClose }) {
  const today = new Date().toISOString().split('T')[0]
  const [title,    setTitle]    = useState(email.subject.slice(0, 80))
  const [date,     setDate]     = useState(today)
  const [time,     setTime]     = useState('09:00')
  const [duration, setDuration] = useState(60)
  const [saving,   setSaving]   = useState(false)
  const [done,     setDone]     = useState(false)

  async function save() {
    setSaving(true)
    try {
      await api.addCalEvent({ title, date, time, duration })
      setDone(true)
      setTimeout(onClose, 1000)
    } catch (e) {
      alert(`Calendar error: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  if (done) return (
    <div className="mt-3 p-3 rounded-xl text-center" style={{ background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)' }}>
      <p className="text-sm text-green-400 font-semibold">✅ Added to Google Calendar!</p>
    </div>
  )

  return (
    <div className="mt-3 p-3 rounded-xl flex flex-col gap-2" style={{ background: '#242424', border: '1px solid #3a3a3a' }}>
      <p className="text-xs text-gray-500 font-semibold uppercase tracking-widest">Add to Calendar</p>
      <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Event title"
             className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
             style={{ background: '#1a1a1a', border: '1px solid #333' }} />
      <div className="flex gap-2">
        <input type="date" value={date} onChange={e => setDate(e.target.value)}
               className="flex-1 px-3 py-2 rounded-lg text-sm text-white outline-none"
               style={{ background: '#1a1a1a', border: '1px solid #333', colorScheme: 'dark' }} />
        <input type="time" value={time} onChange={e => setTime(e.target.value)}
               className="flex-1 px-3 py-2 rounded-lg text-sm text-white outline-none"
               style={{ background: '#1a1a1a', border: '1px solid #333', colorScheme: 'dark' }} />
      </div>
      <div className="flex gap-2">
        <select value={duration} onChange={e => setDuration(Number(e.target.value))}
                className="flex-1 px-3 py-2 rounded-lg text-sm text-white outline-none"
                style={{ background: '#1a1a1a', border: '1px solid #333' }}>
          {[15,30,45,60,90,120].map(d => <option key={d} value={d}>{d} min</option>)}
        </select>
        <button onClick={save} disabled={saving}
                className="px-4 py-2 rounded-lg text-sm font-bold transition-all active:scale-95 disabled:opacity-50"
                style={{ background: '#7c3aed', color: 'white' }}>
          {saving ? '…' : '📅 Save'}
        </button>
        <button onClick={onClose} className="px-3 py-2 rounded-lg text-sm text-gray-500 transition-all"
                style={{ background: '#1a1a1a' }}>✕</button>
      </div>
    </div>
  )
}

// ── Draft Reply modal ─────────────────────────────────────────────────────────
function DraftModal({ email, onClose }) {
  const [draft,   setDraft]   = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.draftReply(email.id, email.account_idx, email.subject, email.from, email.preview)
      .then(r => setDraft(r.draft || ''))
      .catch(e => setDraft(`Error: ${e.message}`))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="mt-3 p-3 rounded-xl flex flex-col gap-2" style={{ background: '#242424', border: '1px solid #3a3a3a' }}>
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500 font-semibold uppercase tracking-widest">Draft Reply</p>
        <button onClick={onClose} className="text-gray-600 text-sm">✕</button>
      </div>
      {loading ? (
        <div className="shimmer rounded-lg" style={{ height: 80 }} />
      ) : (
        <textarea
          value={draft}
          onChange={e => setDraft(e.target.value)}
          rows={5}
          className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none resize-none"
          style={{ background: '#1a1a1a', border: '1px solid #333' }}
        />
      )}
      <p className="text-[10px] text-gray-600">Generated by Claude Haiku · Edit before sending</p>
    </div>
  )
}

// ── Email card ────────────────────────────────────────────────────────────────
function EmailCard({ email, onDismiss }) {
  const cfg = TAG_CONFIG[email.tag] || TAG_CONFIG.fyi
  const [dismissed,  setDismissed]  = useState(false)
  const [showCal,    setShowCal]    = useState(false)
  const [showDraft,  setShowDraft]  = useState(false)
  const [dismissing, setDismissing] = useState(false)

  if (dismissed) return null

  async function dismiss() {
    setDismissing(true)
    try {
      await api.dismissEmail(email.id, email.account_idx)
    } catch (_) {}
    setDismissed(true)
    onDismiss?.(email.id)
  }

  return (
    <div className="rounded-2xl p-4 transition-all" style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ background: cfg.badgeBg, color: cfg.text }}>
              {cfg.label}
            </span>
            <span className="text-xs text-gray-500 flex-shrink-0">{email.time}</span>
          </div>
          <p className="text-xs text-gray-500 truncate">{email.from}</p>
        </div>
        <span className="text-xs px-1.5 py-0.5 rounded text-gray-600" style={{ background: '#2a2a2a' }}>
          {email.account}
        </span>
      </div>

      <p className="text-sm font-semibold text-white mb-1 leading-snug">{email.subject}</p>
      <p className="text-xs text-gray-400 leading-relaxed line-clamp-3">{email.preview}</p>
      {email.reason && (
        <p className="text-[10px] text-gray-600 mt-1 italic">{email.reason}</p>
      )}

      <div className="flex gap-2 mt-3">
        <button
          onClick={() => { setShowCal(v => !v); setShowDraft(false) }}
          className="flex-1 py-2 rounded-xl text-xs font-medium transition-all active:scale-95"
          style={{
            background: showCal ? 'rgba(124,58,237,0.25)' : '#2a2a2a',
            color: showCal ? '#a78bfa' : '#aaa',
            border: '1px solid #3a3a3a',
          }}
        >📅 Calendar</button>
        <button
          onClick={() => { setShowDraft(v => !v); setShowCal(false) }}
          className="flex-1 py-2 rounded-xl text-xs font-medium transition-all active:scale-95"
          style={{
            background: showDraft ? 'rgba(59,130,246,0.2)' : '#2a2a2a',
            color: showDraft ? '#3b82f6' : '#aaa',
            border: '1px solid #3a3a3a',
          }}
        >✏️ Draft Reply</button>
        <button
          onClick={dismiss}
          disabled={dismissing}
          className="py-2 px-3 rounded-xl text-xs font-medium transition-all active:scale-95 disabled:opacity-40"
          style={{ background: '#2a2a2a', color: '#666', border: '1px solid #3a3a3a' }}
        >{dismissing ? '…' : '✕'}</button>
      </div>

      {showCal   && <CalendarModal email={email} onClose={() => setShowCal(false)} />}
      {showDraft && <DraftModal   email={email} onClose={() => setShowDraft(false)} />}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Inbox() {
  const [emails,  setEmails]  = useState([])
  const [filter,  setFilter]  = useState('all')
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const loadEmails = useCallback(async (force = false) => {
    setLoading(true)
    try {
      const data = await api.emails(force)
      setEmails(data || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadEmails() }, [])

  const visible = emails.filter(e => filter === 'all' || e.tag === filter)
  const counts  = {
    all:         emails.length,
    act_now:     emails.filter(e => e.tag === 'act_now').length,
    opportunity: emails.filter(e => e.tag === 'opportunity').length,
    fyi:         emails.filter(e => e.tag === 'fyi').length,
  }

  const tagLabels = { all: 'All', act_now: '🔴 Act Now', opportunity: '🟠 Opps', fyi: '🔵 FYI' }
  const tagColors = {
    all:         { active: '#7c3aed', bg: 'rgba(124,58,237,0.2)' },
    act_now:     { active: '#ef4444', bg: 'rgba(239,68,68,0.2)' },
    opportunity: { active: '#f59e0b', bg: 'rgba(245,158,11,0.2)' },
    fyi:         { active: '#3b82f6', bg: 'rgba(59,130,246,0.2)' },
  }

  return (
    <div className="flex flex-col gap-4 pb-2">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white tracking-tight">Inbox 📬</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{counts.all} emails</span>
          <button onClick={() => loadEmails(true)}
                  className="text-xs px-2.5 py-1 rounded-full text-gray-500 transition-all"
                  style={{ background: '#1a1a1a', border: '1px solid #2a2a2a' }}>
            ↻ refresh
          </button>
        </div>
      </div>

      {/* Filter chips */}
      <div className="flex gap-2 no-scrollbar overflow-x-auto pb-1">
        {FILTERS.map(f => {
          const tc = tagColors[f]
          const isActive = filter === f
          return (
            <button key={f} onClick={() => setFilter(f)}
                    className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-semibold transition-all"
                    style={{
                      background: isActive ? tc.bg : '#1a1a1a',
                      color: isActive ? tc.active : '#666',
                      border: `1px solid ${isActive ? tc.active : '#2a2a2a'}`,
                    }}>
              {tagLabels[f]}
              <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold"
                    style={{ background: isActive ? 'rgba(255,255,255,0.15)' : '#2a2a2a' }}>
                {counts[f]}
              </span>
            </button>
          )
        })}
      </div>

      {loading ? (
        <div className="flex flex-col gap-3">
          {[120, 100, 110].map((h, i) => (
            <div key={i} className="shimmer rounded-2xl" style={{ height: h }} />
          ))}
          <p className="text-xs text-gray-600 text-center">Fetching all inboxes + classifying with Claude Haiku…</p>
        </div>
      ) : error ? (
        <div className="text-center py-12">
          <p className="text-red-400 text-sm">⚠️ {error}</p>
          <button onClick={() => loadEmails(true)} className="text-xs text-gray-400 underline mt-2">Retry</button>
        </div>
      ) : visible.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <p className="text-4xl mb-3">📭</p>
          <p className="text-sm">No emails in this category</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {visible.map(email => (
            <EmailCard
              key={email.id}
              email={email}
              onDismiss={id => setEmails(prev => prev.filter(e => e.id !== id))}
            />
          ))}
        </div>
      )}
    </div>
  )
}
