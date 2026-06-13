import React, { useState, Suspense } from 'react'
import BottomNav from './components/BottomNav.jsx'
import SideNav   from './components/SideNav.jsx'
import Today     from './pages/Today.jsx'
import Health    from './pages/Health.jsx'
import Inbox     from './pages/Inbox.jsx'
import Goals     from './pages/Goals.jsx'
import Weekly    from './pages/Weekly.jsx'

const PAGES = { today: Today, health: Health, inbox: Inbox, goals: Goals, weekly: Weekly }

function LoadingShim() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 p-4">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="shimmer rounded-2xl" style={{ height: 160 }} />
      ))}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('today')
  const Page = PAGES[tab]

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: '#0a0a0a' }}>
      {/* ── Desktop left sidebar ── */}
      <SideNav active={tab} onChange={setTab} />

      {/* ── Main content area — offset by sidebar width on desktop ── */}
      <main
        className="flex-1 h-full overflow-y-auto no-scrollbar page-scroll safe-top
                   lg:ml-[72px] xl:ml-[200px]"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 80px)' }}
      >
        {/* Desktop: shrink bottom padding since no bottom nav */}
        <style>{`@media (min-width: 1024px) { main { padding-bottom: 32px !important; } }`}</style>

        <div
          className="mx-auto px-4 pt-5
                     max-w-sm
                     md:max-w-2xl md:px-6
                     lg:max-w-none lg:px-8
                     xl:px-10"
        >
          <div className="page-enter" key={tab}>
            <Suspense fallback={<LoadingShim />}>
              <Page />
            </Suspense>
          </div>
        </div>
      </main>

      {/* ── Mobile bottom nav ── */}
      <BottomNav active={tab} onChange={setTab} />
    </div>
  )
}
