import React from 'react'

// Ring specs — all relative to viewBox 200x200 center (100,100)
const RINGS = [
  { key: 'sleep',   label: '😴', color: '#7c3aed', r: 75 },
  { key: 'meals',   label: '🍳', color: '#10b981', r: 59 },
  { key: 'water',   label: '💧', color: '#3b82f6', r: 43 },
  { key: 'workout', label: '💪', color: '#f59e0b', r: 27 },
]

function Ring({ pct, color, r }) {
  const circ   = 2 * Math.PI * r
  const offset = circ * (1 - Math.min(pct, 100) / 100)
  return (
    <>
      <circle cx="100" cy="100" r={r} fill="none" stroke="#222" strokeWidth="9" />
      <circle
        cx="100" cy="100" r={r}
        fill="none"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        style={{
          transform: 'rotate(-90deg)',
          transformOrigin: '100px 100px',
          transition: 'stroke-dashoffset 0.9s ease-out',
          filter: `drop-shadow(0 0 6px ${color}66)`,
        }}
      />
    </>
  )
}

export default function HealthRing({ health }) {
  const avgPct = Math.round(
    RINGS.reduce((s, r) => s + (health[r.key]?.pct ?? 0), 0) / RINGS.length
  )

  return (
    <div className="flex items-center gap-4 lg:gap-6">
      {/* Rings — small on mobile, large on desktop */}
      <div
        className="relative flex-shrink-0"
        style={{ width: 112, height: 112 }}          /* mobile */
      >
        {/* Desktop override via CSS class */}
        <svg
          viewBox="0 0 200 200"
          className="health-ring-svg"
          style={{ width: '100%', height: '100%' }}
        >
          {RINGS.map(ring => (
            <Ring key={ring.key} pct={health[ring.key]?.pct ?? 0} color={ring.color} r={ring.r} />
          ))}
          {/* Center score */}
          <text x="100" y="94" textAnchor="middle" fill="white" fontSize="28" fontWeight="800"
                fontFamily="-apple-system, BlinkMacSystemFont, sans-serif">
            {avgPct}
          </text>
          <text x="100" y="114" textAnchor="middle" fill="#555" fontSize="14" fontWeight="600"
                fontFamily="-apple-system, BlinkMacSystemFont, sans-serif">
            TODAY
          </text>
        </svg>
      </div>

      {/* Legend */}
      <div className="flex flex-col gap-2.5 flex-1">
        {RINGS.map(ring => {
          const item = health[ring.key]
          if (!item) return null
          return (
            <div key={ring.key} className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: ring.color }} />
              <span className="text-xs text-gray-400 capitalize w-14">{ring.key}</span>
              <div className="flex-1 h-1.5 rounded-full" style={{ background: '#2a2a2a' }}>
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${item.pct}%`,
                    background: ring.color,
                    transition: 'width 0.8s ease-out',
                  }}
                />
              </div>
              <span className="text-xs text-white font-medium w-20 text-right">
                {item.value}/{item.goal} {item.unit}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
