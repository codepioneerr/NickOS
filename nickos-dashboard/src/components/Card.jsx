import React from 'react'

export default function Card({ children, className = '', onClick, accent = false }) {
  return (
    <div
      onClick={onClick}
      className={`rounded-2xl p-4 lg:p-5 xl:p-6 ${onClick ? 'cursor-pointer active:scale-[0.98] transition-transform' : ''} ${className}`}
      style={{
        background: '#1a1a1a',
        border: accent ? '1px solid rgba(124,58,237,0.4)' : '1px solid #2a2a2a',
        boxShadow: accent ? '0 0 24px rgba(124,58,237,0.1)' : 'none',
      }}
    >
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, right }) {
  return (
    <div className="flex items-start justify-between mb-3 lg:mb-4">
      <div>
        <h3 className="text-sm lg:text-base font-semibold text-white">{title}</h3>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      {right && <div>{right}</div>}
    </div>
  )
}
