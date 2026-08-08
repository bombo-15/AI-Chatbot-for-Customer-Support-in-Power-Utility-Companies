/**
 * OutageBoard — Objective 3: live outage & fault data display
 */
import React, { useState, useEffect } from 'react'
import { API } from '../config.js'

const STATUS_STYLES = {
  active:    'bg-red-100 text-red-700 border-red-200',
  scheduled: 'bg-amber-100 text-amber-700 border-amber-200',
  resolved:  'bg-green-100 text-green-700 border-green-200',
}

const STATUS_DOT = {
  active:    'bg-red-500',
  scheduled: 'bg-amber-500',
  resolved:  'bg-green-500',
}

const TYPE_ICON = {
  unplanned: '⚠️',
  scheduled: '🔧',
}

function fmt(iso) {
  if (!iso) return { date: 'TBD', time: '' }
  try {
    const d = new Date(iso)
    return {
      date: d.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }),
      time: d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
    }
  } catch {
    return { date: iso, time: '' }
  }
}

export default function OutageBoard() {
  const [outages, setOutages]   = useState([])
  const [filter, setFilter]     = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [loading, setLoading]   = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)

  async function load() {
    try {
      const res = await fetch(`${API}/outages`)
      const data = await res.json()
      setOutages(data)
      setLastRefresh(new Date())
    } catch {
      // backend not reachable
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 60_000)   // refresh every minute
    return () => clearInterval(id)
  }, [])

  const filtered = outages.filter((o) => {
    const matchArea   = o.area.toLowerCase().includes(filter.toLowerCase())
    const matchStatus = statusFilter === 'all' || o.status === statusFilter
    return matchArea && matchStatus
  })

  const counts = {
    active:    outages.filter(o => o.status === 'active').length,
    scheduled: outages.filter(o => o.status === 'scheduled').length,
    resolved:  outages.filter(o => o.status === 'resolved').length,
  }

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Active Outages',    count: counts.active,    color: 'red',   icon: '🔴' },
          { label: 'Scheduled Works',   count: counts.scheduled, color: 'amber', icon: '🟡' },
          { label: 'Resolved Today',    count: counts.resolved,  color: 'green', icon: '🟢' },
        ].map(({ label, count, color, icon }) => (
          <div key={label} className={`bg-${color}-50 border border-${color}-200 rounded-xl p-3 text-center`}>
            <div className="text-2xl">{icon}</div>
            <div className={`text-2xl font-bold text-${color}-700`}>{count}</div>
            <div className={`text-xs text-${color}-600`}>{label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search area…"
          className="flex-1 min-w-[140px] border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-yellow-300"
        />
        {['all', 'active', 'scheduled', 'resolved'].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              statusFilter === s
                ? 'bg-ecg-navy text-ecg-yellow border-ecg-navy'
                : 'bg-white text-gray-600 border-gray-200 hover:border-ecg-red hover:text-ecg-red'
            }`}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
        <button
          onClick={load}
          className="px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
          title="Refresh"
        >
          ↻ Refresh
        </button>
      </div>

      {lastRefresh && (
        <p className="text-xs text-gray-400">
          Last updated: {lastRefresh.toLocaleTimeString()}
        </p>
      )}

      {/* Outage list */}
      {loading ? (
        <div className="py-12 text-center text-gray-400">Loading outage data…</div>
      ) : filtered.length === 0 ? (
        <div className="py-12 text-center">
          <div className="text-4xl mb-2">✅</div>
          <p className="text-gray-500 text-sm">No outages match your search.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((o) => (
            <div
              key={o.id}
              className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{TYPE_ICON[o.type] || '⚡'}</span>
                  <div>
                    <p className="font-semibold text-gray-800">{o.area}</p>
                    <p className="text-xs text-gray-500 capitalize">{o.type} outage</p>
                  </div>
                </div>
                <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium ${STATUS_STYLES[o.status] || ''}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[o.status] || 'bg-gray-400'}`} />
                  {o.status.charAt(0).toUpperCase() + o.status.slice(1)}
                </span>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-600">
                <div>
                  <span className="text-gray-400">Started:</span>{' '}
                  <span>{fmt(o.start_time).date} {fmt(o.start_time).time}</span>
                </div>
                <div className="col-span-2 bg-blue-50 border border-ecg-navy/20 rounded-lg px-3 py-2 flex items-center gap-2">
                  <span className="text-base">🕐</span>
                  <div>
                    <p className="text-gray-400 text-xs leading-none mb-0.5">Est. Restoration</p>
                    <p className="font-bold text-ecg-navy text-sm">{fmt(o.estimated_restoration).date}</p>
                    <p className="text-ecg-navy/80 text-xs font-medium">{fmt(o.estimated_restoration).time}</p>
                  </div>
                </div>
                <div>
                  <span className="text-gray-400">Cause:</span>{' '}
                  <span>{o.cause || 'Under investigation'}</span>
                </div>
                <div>
                  <span className="text-gray-400">Affected:</span>{' '}
                  <span className="font-medium">{o.affected_customers?.toLocaleString() || '?'} customers</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
