/**
 * NickOS API hooks
 * Set VITE_API_URL and VITE_API_KEY in .env.local
 */

const BASE    = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_KEY = import.meta.env.VITE_API_KEY || ''

async function fetchApi(path, opts = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
    ...opts.headers,
  }
  const res = await fetch(`${BASE}${path}`, { ...opts, headers })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

/** Base URL + API key for EventSource (SSE can't set custom headers, so we pass the key as a query param) */
export const SSE_URL = API_KEY
  ? `${BASE}/api/stream?key=${encodeURIComponent(API_KEY)}`
  : `${BASE}/api/stream`

// ── GET endpoints ──────────────────────────────────────────────────────────
export const api = {
  /** Aggregated today data */
  today: () => fetchApi('/api/today'),

  /** Health stats for health page */
  healthStats: () => fetchApi('/api/health/stats'),

  /** Email triage digest — pass force=true to bypass 15-min cache */
  emails: (force = false) => fetchApi(`/api/emails${force ? '?force=true' : ''}`),

  /** Goals from MEMORY.md */
  goals: () => fetchApi('/api/goals'),

  /** Fresh affirmation from Claude Haiku — pass force=true to bypass cache */
  affirmation: (force = false) => fetchApi(`/api/affirmation${force ? '?force=true' : ''}`),

  /** Today's Google Calendar events */
  calendar: () => fetchApi('/api/calendar'),

  // ── Log endpoints ──────────────────────────────────────────────────────
  logSleep:   (hours)   => fetchApi('/api/log/sleep',   { method: 'POST', body: JSON.stringify({ hours }) }),
  logMeal:    (meal)    => fetchApi('/api/log/meal',    { method: 'POST', body: JSON.stringify({ meal }) }),
  logWater:   (glasses) => fetchApi('/api/log/water',   { method: 'POST', body: JSON.stringify({ glasses }) }),
  logWorkout: (notes)   => fetchApi('/api/log/workout', { method: 'POST', body: JSON.stringify({ notes }) }),

  // ── Calendar ───────────────────────────────────────────────────────────
  /** Create Google Calendar event */
  addCalEvent: (event) => fetchApi('/api/calendar/add', { method: 'POST', body: JSON.stringify(event) }),

  // ── Email actions ──────────────────────────────────────────────────────
  /** Mark email as read in Gmail (dismiss) */
  dismissEmail: (emailId, accountIdx = 1) =>
    fetchApi(`/api/emails/${emailId}/dismiss?account_idx=${accountIdx}`, { method: 'POST', body: JSON.stringify({}) }),

  /** Generate Claude Haiku draft reply */
  draftReply: (emailId, accountIdx, subject, sender, snippet) =>
    fetchApi(`/api/emails/${emailId}/draft-reply`, {
      method: 'POST',
      body: JSON.stringify({ account_idx: accountIdx, subject, sender, snippet }),
    }),

  // ── Weekly review ──────────────────────────────────────────────────────
  /** Real weekly review data (report card, trends, charts) */
  weekly: () => fetchApi('/api/weekly'),

  // ── AI Insights ────────────────────────────────────────────────────────
  /** Claude Haiku insights for Today page — pass force=true to refresh */
  insights: (force = false) => fetchApi(`/api/insights${force ? '?force=true' : ''}`),

  // ── Obsidian ───────────────────────────────────────────────────────────
  /** Search the Obsidian vault by title + content */
  obsidianSearch: (q) => fetchApi(`/api/obsidian/search?q=${encodeURIComponent(q)}`),

  // ── Focus + habits ─────────────────────────────────────────────────────
  /** Log a completed focus (pomodoro) session */
  logFocus: (minutes = 25, label = '') =>
    fetchApi('/api/log/focus', { method: 'POST', body: JSON.stringify({ minutes, label }) }),

  /** Toggle a habit for today */
  logHabit: (habitId, done = true) =>
    fetchApi('/api/log/habit', { method: 'POST', body: JSON.stringify({ habit_id: habitId, done }) }),
}
