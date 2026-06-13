import React, { useState, useEffect, useRef } from 'react'
import Card, { CardHeader } from './Card.jsx'
import { api } from '../hooks/useApi.js'

export default function ObsidianSearch() {
  const [query, setQuery]     = useState('')
  const [results, setResults] = useState([])
  const [vaultFound, setVaultFound] = useState(true)
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const debounceRef = useRef(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const q = query.trim()
    if (!q) { setResults([]); setSearched(false); return }

    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await api.obsidianSearch(q)
        setVaultFound(res.vaultFound)
        setResults(res.results || [])
        setSearched(true)
      } catch {
        setResults([])
        setSearched(true)
      } finally {
        setLoading(false)
      }
    }, 350)

    return () => clearTimeout(debounceRef.current)
  }, [query])

  return (
    <Card>
      <CardHeader title="🗂️ Obsidian" subtitle="Search your vault" />

      <input
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search notes…"
        maxLength={100}
        className="w-full px-3 py-2.5 rounded-xl text-sm text-white placeholder-gray-600 outline-none mb-2"
        style={{ background: '#242424', border: '1px solid #333' }}
      />

      {loading && (
        <div className="h-10 rounded-xl animate-pulse" style={{ background: '#242424' }} />
      )}

      {!loading && searched && !vaultFound && (
        <p className="text-xs text-gray-500 px-1 py-2">
          📭 No vault found yet — set <span style={{ color: '#a78bfa' }}>OBSIDIAN_VAULT_PATH</span> when you create one.
        </p>
      )}

      {!loading && searched && vaultFound && results.length === 0 && (
        <p className="text-xs text-gray-500 px-1 py-2">No notes match "{query.trim()}"</p>
      )}

      {!loading && results.length > 0 && (
        <div className="flex flex-col gap-2 max-h-72 overflow-y-auto">
          {results.map((r, i) => (
            <a
              key={i}
              href={r.obsidianUrl}
              className="block px-3 py-2.5 rounded-xl transition-all active:scale-[0.98]"
              style={{ background: '#242424', border: '1px solid #333' }}
            >
              <p className="text-xs font-semibold text-white truncate">📝 {r.title}</p>
              <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{r.preview}</p>
              <p className="text-[10px] mt-1 truncate" style={{ color: '#7c3aed' }}>{r.path}</p>
            </a>
          ))}
        </div>
      )}
    </Card>
  )
}
