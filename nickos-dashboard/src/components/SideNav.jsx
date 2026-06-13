import React from 'react'

const tabs = [
  { id: 'today',  label: 'Today',  icon: '⚡' },
  { id: 'health', label: 'Health', icon: '💪' },
  { id: 'inbox',  label: 'Inbox',  icon: '📬' },
  { id: 'goals',  label: 'Goals',  icon: '🎯' },
  { id: 'weekly', label: 'Weekly', icon: '📊' },
]

export default function SideNav({ active, onChange }) {
  return (
    <aside
      className="hidden lg:flex flex-col fixed left-0 top-0 h-full z-40 w-[72px] xl:w-[200px]"
      style={{
        background: 'rgba(10,10,10,0.98)',
        borderRight: '1px solid #1e1e1e',
        backdropFilter: 'blur(20px)',
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-[#1e1e1e]">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center text-base font-black flex-shrink-0"
          style={{ background: 'linear-gradient(135deg, #7c3aed, #a78bfa)' }}
        >
          N
        </div>
        <span className="hidden xl:block text-sm font-bold text-white tracking-tight">NickOS</span>
      </div>

      {/* Nav items */}
      <nav className="flex flex-col gap-1 px-2 pt-4 flex-1">
        {tabs.map(tab => {
          const isActive = active === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              className="flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-150 w-full"
              style={{
                background: isActive ? 'rgba(124,58,237,0.18)' : 'transparent',
                color: isActive ? '#a78bfa' : '#555',
                border: isActive ? '1px solid rgba(124,58,237,0.3)' : '1px solid transparent',
              }}
            >
              <span className="text-xl leading-none flex-shrink-0">{tab.icon}</span>
              <span className="hidden xl:block text-sm font-semibold">{tab.label}</span>
            </button>
          )
        })}
      </nav>

      {/* Bottom: version */}
      <div className="px-4 py-4 border-t border-[#1e1e1e]">
        <p className="hidden xl:block text-[10px] text-gray-700 font-medium">Phase 5 · Live data</p>
      </div>
    </aside>
  )
}
