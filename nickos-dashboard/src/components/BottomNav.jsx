import React from 'react'

const tabs = [
  { id: 'today',  label: 'Today',  icon: '⚡' },
  { id: 'health', label: 'Health', icon: '💪' },
  { id: 'inbox',  label: 'Inbox',  icon: '📬' },
  { id: 'goals',  label: 'Goals',  icon: '🎯' },
  { id: 'weekly', label: 'Weekly', icon: '📊' },
]

export default function BottomNav({ active, onChange }) {
  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-50 safe-bottom"
         style={{ background: 'rgba(10,10,10,0.95)', backdropFilter: 'blur(20px)', borderTop: '1px solid #2a2a2a' }}>
      <div className="flex items-center justify-around" style={{ height: '56px' }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className="flex flex-col items-center justify-center gap-0.5 flex-1 py-1 transition-all duration-200"
            style={{ color: active === tab.id ? '#7c3aed' : '#666' }}
          >
            <span className="text-xl leading-none">{tab.icon}</span>
            <span className="text-[10px] font-medium tracking-wide">
              {tab.label}
            </span>
            {active === tab.id && (
              <div className="absolute bottom-1 w-1 h-1 rounded-full bg-accent" style={{ background: '#7c3aed' }} />
            )}
          </button>
        ))}
      </div>
    </nav>
  )
}
