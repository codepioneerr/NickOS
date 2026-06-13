import React, { useState, useEffect, useCallback } from 'react'
import Card, { CardHeader } from './Card.jsx'
import { api } from '../hooks/useApi.js'

export default function InsightsPanel() {
  const [insights, setInsights] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(false)

  const load = useCallback(async (force = false) => {
    setLoading(true)
    setError(false)
    try {
      const res = await api.insights(force)
      setInsights(res.insights || [])
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <Card>
      <CardHeader
        title="🧠 AI Insights"
        subtitle="What matters right now"
        right={
          <button
            onClick={() => load(true)}
            disabled={loading}
            className="text-xs px-2.5 py-1 rounded-full font-semibold active:scale-95 transition-transform"
            style={{ background: 'rgba(124,58,237,0.2)', color: '#a78bfa', opacity: loading ? 0.5 : 1 }}
          >
            {loading ? '…' : '↻ Refresh'}
          </button>
        }
      />

      {loading && !insights && (
        <div className="flex flex-col gap-2">
          {[0, 1, 2].map(i => (
            <div key={i} className="h-12 rounded-xl animate-pulse" style={{ background: '#242424' }} />
          ))}
        </div>
      )}

      {error && (
        <div className="flex items-center justify-between px-3 py-2.5 rounded-xl"
             style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)' }}>
          <p className="text-xs" style={{ color: '#ef4444' }}>Couldn't load insights</p>
          <button onClick={() => load(true)} className="text-xs font-semibold" style={{ color: '#a78bfa' }}>
            Retry
          </button>
        </div>
      )}

      {insights && !error && (
        <div className="flex flex-col gap-2">
          {insights.map((ins, i) => (
            <div key={i} className="flex items-start gap-3 px-3 py-2.5 rounded-xl"
                 style={{ background: '#242424', border: '1px solid #333' }}>
              <span className="text-lg mt-0.5">{ins.icon}</span>
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-widest mb-0.5" style={{ color: '#a78bfa' }}>
                  {ins.title}
                </p>
                <p className="text-xs text-gray-300 leading-relaxed">{ins.text}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
