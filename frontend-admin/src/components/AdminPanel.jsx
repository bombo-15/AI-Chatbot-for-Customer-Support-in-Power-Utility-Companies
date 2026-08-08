/**
 * AdminPanel — Internal operations dashboard
 * Runs standalone on port 5174.
 *
 * Tabs:
 *  - Analytics     : chatbot performance metrics (from Analytics.jsx)
 *  - Fault Reports : submitted fault reports queue
 *  - Escalations   : sessions routed to human agents
 *  - RAG Sources   : knowledge retrieval references
 */
import React, { useState, useEffect } from 'react'
import Analytics from './Analytics.jsx'
import { API, adminFetch } from '../config.js'

const TOKEN_KEY = 'kanea_admin_token'

// ─── Password Gate ─────────────────────────────────────────────────────────

function LoginGate({ onAuth }) {
  const [pw, setPw]         = useState('')
  const [error, setError]   = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await fetch(`${API}/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pw }),
      })
      if (!res.ok) throw new Error()
      const { token } = await res.json()
      sessionStorage.setItem(TOKEN_KEY, token)
      onAuth()
    } catch {
      setError(true)
      setPw('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-yellow-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl shadow-lg border border-gray-200 w-full max-w-sm p-8">
        <div className="text-center mb-6">
          <div className="w-14 h-14 bg-blue-900 rounded-full flex items-center justify-center text-3xl mx-auto mb-3">
            🔐
          </div>
          <h1 className="text-xl font-bold text-blue-900">Kanea Admin Panel</h1>
          <p className="text-sm text-gray-500 mt-1">Internal use only</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Admin Password
            </label>
            <input
              type="password"
              value={pw}
              onChange={e => { setPw(e.target.value); setError(false) }}
              placeholder="Enter password"
              autoFocus
              className={`w-full border rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-yellow-400 ${
                error ? 'border-red-400 bg-red-50' : 'border-gray-300'
              }`}
            />
            {error && (
              <p className="text-xs text-red-500 mt-1">Incorrect password. Try again.</p>
            )}
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-900 hover:bg-blue-800 disabled:opacity-50 text-white font-semibold rounded-xl py-2.5 text-sm transition-colors"
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}

// ─── Fault Reports Tab ──────────────────────────────────────────────────────

const URGENCY_COLORS = {
  critical: 'bg-red-100 text-red-700 border-red-200',
  high:     'bg-orange-100 text-orange-700 border-orange-200',
  medium:   'bg-yellow-100 text-yellow-700 border-yellow-200',
  low:      'bg-green-100 text-green-700 border-green-200',
}

function FaultReportsTab() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(false)

  async function load() {
    setLoading(true); setError(false)
    try {
      const res = await adminFetch(`${API}/admin/fault-reports`)
      if (!res.ok) throw new Error()
      setReports(await res.json())
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="py-16 text-center text-gray-400">Loading fault reports…</div>
  if (error)   return (
    <div className="py-16 text-center">
      <p className="text-gray-500 text-sm">Could not load fault reports.</p>
      <button onClick={load} className="mt-3 text-yellow-600 text-sm underline">Retry</button>
    </div>
  )

  if (reports.length === 0) return (
    <div className="py-16 text-center text-gray-400 text-sm">No fault reports submitted yet.</div>
  )

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center mb-2">
        <p className="text-sm text-gray-500">{reports.length} report{reports.length !== 1 ? 's' : ''}</p>
        <button onClick={load} className="text-xs text-yellow-600 hover:text-yellow-800 underline">↻ Refresh</button>
      </div>
      {reports.map((r) => (
        <div key={r.id} className="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
            <div>
              <span className="font-mono text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded px-2 py-0.5">
                {r.reference}
              </span>
              <span className={`ml-2 text-xs border rounded px-2 py-0.5 capitalize ${URGENCY_COLORS[r.urgency] || 'bg-gray-100 text-gray-600'}`}>
                {r.urgency}
              </span>
              <span className="ml-2 text-xs bg-gray-100 text-gray-600 border border-gray-200 rounded px-2 py-0.5 capitalize">
                {r.status}
              </span>
            </div>
            <span className="text-xs text-gray-400">{new Date(r.timestamp).toLocaleString()}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm mt-1">
            <div><span className="text-gray-400">Name:</span> <span className="font-medium text-gray-700">{r.customer_name}</span></div>
            <div><span className="text-gray-400">Phone:</span> <span className="font-medium text-gray-700">{r.phone}</span></div>
            <div><span className="text-gray-400">Location:</span> <span className="font-medium text-gray-700">{r.location}</span></div>
            <div><span className="text-gray-400">Fault type:</span> <span className="font-medium text-gray-700">{r.fault_type}</span></div>
          </div>
          {r.description && (
            <p className="mt-2 text-xs text-gray-500 italic border-t border-gray-50 pt-2">"{r.description}"</p>
          )}
        </div>
      ))}
    </div>
  )
}

// ─── Escalations Tab ────────────────────────────────────────────────────────

function EscalationsTab() {
  const [escalations, setEscalations] = useState([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(false)

  async function load() {
    setLoading(true); setError(false)
    try {
      const res = await adminFetch(`${API}/admin/escalations`)
      if (!res.ok) throw new Error()
      setEscalations(await res.json())
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="py-16 text-center text-gray-400">Loading escalations…</div>
  if (error)   return (
    <div className="py-16 text-center">
      <p className="text-gray-500 text-sm">Could not load escalations.</p>
      <button onClick={load} className="mt-3 text-yellow-600 text-sm underline">Retry</button>
    </div>
  )

  if (escalations.length === 0) return (
    <div className="py-16 text-center text-gray-400 text-sm">No escalations yet.</div>
  )

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center mb-2">
        <p className="text-sm text-gray-500">{escalations.length} escalation{escalations.length !== 1 ? 's' : ''}</p>
        <button onClick={load} className="text-xs text-yellow-600 hover:text-yellow-800 underline">↻ Refresh</button>
      </div>
      {escalations.map((e) => (
        <div key={e.id} className="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <span className="text-lg">🧑‍💼</span>
              <span className="font-medium text-gray-800 text-sm">{e.customer_name || 'Anonymous'}</span>
              <span className={`text-xs border rounded px-2 py-0.5 capitalize ${
                e.status === 'pending'
                  ? 'bg-orange-50 text-orange-600 border-orange-200'
                  : 'bg-green-50 text-green-600 border-green-200'
              }`}>{e.status}</span>
            </div>
            <span className="text-xs text-gray-400">{new Date(e.timestamp).toLocaleString()}</span>
          </div>
          <div className="text-sm space-y-1">
            <div><span className="text-gray-400">Session:</span> <span className="font-mono text-xs text-gray-500">{e.session_id}</span></div>
            <div><span className="text-gray-400">Intent:</span> <span className="text-gray-700 capitalize">{e.intent?.replace('_', ' ')}</span></div>
            <div><span className="text-gray-400">Last message:</span> <span className="text-gray-700 italic">"{e.last_message}"</span></div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── RAG Sources Tab ────────────────────────────────────────────────────────

function RagSourcesTab() {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  async function load() {
    setLoading(true); setError(false)
    try {
      const res = await adminFetch(`${API}/admin/rag-sources`)
      if (!res.ok) throw new Error()
      setSources(await res.json())
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="py-16 text-center text-gray-400">Loading RAG sources…</div>
  if (error) return (
    <div className="py-16 text-center">
      <p className="text-gray-500 text-sm">Could not load RAG references.</p>
      <button onClick={load} className="mt-3 text-yellow-600 text-sm underline">Retry</button>
    </div>
  )

  if (sources.length === 0) return (
    <div className="py-16 text-center text-gray-400 text-sm">No RAG references recorded yet.</div>
  )

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center mb-2">
        <p className="text-sm text-gray-500">{sources.length} reference{sources.length !== 1 ? 's' : ''}</p>
        <button onClick={load} className="text-xs text-yellow-600 hover:text-yellow-800 underline">↻ Refresh</button>
      </div>
      {sources.map((item) => (
        <div key={item.id} className="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between gap-2 mb-3">
            <div>
              <p className="text-sm font-semibold text-slate-800">Message #{item.message_id}</p>
              <p className="text-xs text-slate-500">Session: {item.session_id}</p>
            </div>
            <span className="text-xs text-slate-400">{new Date(item.timestamp).toLocaleString()}</span>
          </div>
          <div className="space-y-2 text-sm text-slate-700">
            {item.sources.map((source, index) => (
              <div key={index} className="rounded-xl bg-slate-50 border border-slate-100 p-3">
                <div className="text-slate-900 font-medium">Slide {source.id}</div>
                <div className="text-slate-600 mt-1 leading-snug">{source.text}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Admin Shell ────────────────────────────────────────────────────────────

const TABS = [
  { id: 'analytics',    label: 'Analytics',     icon: '📊' },
  { id: 'faults',       label: 'Fault Reports', icon: '🔧' },
  { id: 'escalations',  label: 'Escalations',   icon: '🧑‍💼' },
  { id: 'sources',      label: 'RAG Sources',   icon: '📚' },
]

function AdminShell({ onLogout }) {
  const [tab, setTab] = useState('analytics')

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-yellow-50">
      {/* Header */}
      <header className="bg-blue-900 shadow-lg">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-yellow-400 rounded-full flex items-center justify-center text-2xl shadow">
              📊
            </div>
            <div>
              <h1 className="text-white font-bold text-lg leading-tight">Kanea Admin</h1>
              <p className="text-yellow-300 text-xs">Operations Dashboard</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <a
              href="http://127.0.0.1:5173"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:flex items-center gap-1.5 text-blue-300 hover:text-white text-xs transition-colors"
            >
              ← Customer App
            </a>
            <button
              onClick={onLogout}
              className="text-xs bg-blue-800 hover:bg-blue-700 text-blue-200 hover:text-white px-3 py-1.5 rounded-full transition-colors"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Tab Navigation */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4">
          <nav className="flex overflow-x-auto">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 px-5 py-3.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  tab === t.id
                    ? 'border-yellow-400 text-blue-900'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span>{t.icon}</span>
                <span>{t.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Tab Content */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        <div className="mb-5">
          <h2 className="text-xl font-bold text-blue-900">{TABS.find(t => t.id === tab)?.label}</h2>
        </div>
        {tab === 'analytics'   && <Analytics />}
        {tab === 'faults'      && <FaultReportsTab />}
        {tab === 'escalations' && <EscalationsTab />}
        {tab === 'sources'     && <RagSourcesTab />}
      </main>
    </div>
  )
}

// ─── Entry Point ─────────────────────────────────────────────────────────────

export default function AdminPanel() {
  const [authed, setAuthed] = useState(
    () => Boolean(sessionStorage.getItem(TOKEN_KEY))
  )

  async function handleLogout() {
    await adminFetch(`${API}/admin/logout`, { method: 'POST' }).catch(() => {})
    sessionStorage.removeItem(TOKEN_KEY)
    setAuthed(false)
  }

  if (!authed) return <LoginGate onAuth={() => setAuthed(true)} />
  return <AdminShell onLogout={handleLogout} />
}

