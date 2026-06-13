import React, { useState, useEffect } from 'react'

export default function NudgeTimer({ label, minutesAway }) {
  const [secs, setSecs] = useState(minutesAway * 60)

  useEffect(() => {
    const t = setInterval(() => setSecs(s => Math.max(0, s - 1)), 1000)
    return () => clearInterval(t)
  }, [])

  const h   = Math.floor(secs / 3600)
  const m   = Math.floor((secs % 3600) / 60)
  const s   = secs % 60
  const pct = 1 - secs / (minutesAway * 60)

  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="text-xs text-gray-400">Next nudge</p>
        <p className="text-sm font-medium text-white mt-0.5">{label}</p>
      </div>
      <div className="text-right">
        <p className="text-2xl font-bold tabular-nums" style={{ color: '#7c3aed', letterSpacing: '-0.02em' }}>
          {h > 0 ? `${h}:` : ''}{String(m).padStart(2,'0')}:{String(s).padStart(2,'0')}
        </p>
        <div className="w-24 h-1 rounded-full mt-1" style={{ background: '#2a2a2a' }}>
          <div className="h-full rounded-full transition-all" style={{ width: `${pct * 100}%`, background: '#7c3aed' }} />
        </div>
      </div>
    </div>
  )
}
