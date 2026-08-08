/**
 * Analytics — chatbot precision and user satisfaction metrics
 *
 * Displays:
 *  - Overall satisfaction score (avg star rating)
 *  - Response accuracy (% of messages rated "helpful")
 *  - Escalation rate (% of sessions routed to human agent)
 *  - Intent distribution (NLP classification breakdown)
 *  - Satisfaction distribution (1–5 star histogram)
 *  - Recent user comments
 *
 * Uses adminFetch (Bearer token) for all API calls.
 */
import React, { useState, useEffect } from 'react'
import { adminFetch, API } from '../config.js'

function StatCard({ icon, label, value, sub, color = 'blue' }) {
  const colors = {
    blue:   'bg-yellow-50 border-yellow-300 text-blue-900',
    green:  'bg-green-50 border-green-200 text-green-700',
    orange: 'bg-orange-50 border-orange-200 text-orange-700',
    red:    'bg-red-50 border-red-200 text-red-700',
    purple: 'bg-purple-50 border-purple-200 text-purple-700',
  }
  return (
    <div className={`rounded-2xl border p-4 ${colors[color]}`}>
      <div className="text-2xl mb-1">{icon}</div>
      <div className="text-2xl font-bold">{value ?? '—'}</div>
      <div className="text-sm font-medium">{label}</div>
      {sub && <div className="text-xs mt-0.5 opacity-70">{sub}</div>}
    </div>
  )
}

function Stars({ value }) {
  return (
    <span className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <span key={s} className={s <= Math.round(value) ? 'text-yellow-400' : 'text-gray-300'}>★</span>
      ))}
    </span>
  )
}

function IntentBar({ intent, count, max }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0
  const labels = {
    outage_status: { label: 'Outage Status',   color: 'bg-red-400' },
    fault_report:  { label: 'Fault Reports',   color: 'bg-orange-400' },
    billing:       { label: 'Billing',          color: 'bg-yellow-400' },
    escalation:    { label: 'Escalation',       color: 'bg-purple-400' },
    complaint:     { label: 'Complaints',       color: 'bg-pink-400' },
    general:       { label: 'General Queries',  color: 'bg-blue-400' },
  }
  const meta = labels[intent] || { label: intent, color: 'bg-gray-400' }
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-600 mb-1">
        <span>{meta.label}</span>
        <span className="font-medium">{count} ({pct}%)</span>
      </div>
      <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${meta.color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function SatisfactionHistogram({ dist }) {
  const max = Math.max(...Object.values(dist).map(Number), 1)
  return (
    <div className="flex items-end gap-2 h-24">
      {[5, 4, 3, 2, 1].map((s) => {
        const count = dist[String(s)] || 0
        const pct   = Math.round((count / max) * 100)
        const colors = {
          5: 'bg-green-500', 4: 'bg-lime-400', 3: 'bg-yellow-400',
          2: 'bg-orange-400', 1: 'bg-red-500'
        }
        return (
          <div key={s} className="flex-1 flex flex-col items-center gap-1">
            <span className="text-xs text-gray-500">{count}</span>
            <div
              className={`w-full rounded-t-md ${colors[s]} transition-all`}
              style={{ height: `${Math.max(pct, 4)}%` }}
            />
            <span className="text-xs text-gray-500">{s}★</span>
          </div>
        )
      })}
    </div>
  )
}

export default function Analytics() {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(false)

  async function load() {
    setLoading(true)
    setError(false)
    try {
      const res = await adminFetch(`${API}/admin/analytics`)
      if (!res.ok) throw new Error()
      setData(await res.json())
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="py-16 text-center text-gray-400">Loading analytics…</div>

  if (error) return (
    <div className="py-16 text-center">
      <div className="text-4xl mb-2">⚠️</div>
      <p className="text-gray-500 text-sm">Could not load analytics. Is the backend running?</p>
      <button onClick={load} className="mt-4 text-yellow-600 text-sm underline">Retry</button>
    </div>
  )

  const {
    total_sessions, total_messages, avg_satisfaction, total_ratings,
    accuracy_percent, helpful_count, unhelpful_count,
    escalation_rate, total_escalations,
    intent_distribution, satisfaction_distribution, recent_ratings
  } = data

  const maxIntentCount = Math.max(...(intent_distribution.map(i => i.count)), 1)

  return (
    <div className="space-y-6">
      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard
          icon="⭐"
          label="Avg Satisfaction"
          value={avg_satisfaction ? `${avg_satisfaction}/5` : 'No data'}
          sub={total_ratings ? `from ${total_ratings} ratings` : undefined}
          color="blue"
        />
        <StatCard
          icon="🎯"
          label="Response Accuracy"
          value={accuracy_percent != null ? `${accuracy_percent}%` : 'No data'}
          sub={`${helpful_count} helpful / ${unhelpful_count} not`}
          color="green"
        />
        <StatCard
          icon="🧑‍💼"
          label="Escalation Rate"
          value={`${escalation_rate}%`}
          sub={`${total_escalations} session${total_escalations !== 1 ? 's' : ''} escalated`}
          color={escalation_rate > 20 ? 'red' : 'orange'}
        />
        <StatCard
          icon="💬"
          label="Total Conversations"
          value={total_sessions}
          sub={`${total_messages} messages total`}
          color="purple"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Satisfaction distribution */}
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-800">Satisfaction Distribution</h3>
            {avg_satisfaction > 0 && (
              <div className="flex items-center gap-1">
                <Stars value={avg_satisfaction} />
                <span className="text-sm font-bold text-gray-700 ml-1">{avg_satisfaction}</span>
              </div>
            )}
          </div>
          {Object.keys(satisfaction_distribution).length === 0 ? (
            <p className="text-sm text-gray-400 py-8 text-center">No ratings yet — ask users to rate the chat!</p>
          ) : (
            <SatisfactionHistogram dist={satisfaction_distribution} />
          )}
        </div>

        {/* Intent distribution */}
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <h3 className="font-semibold text-gray-800 mb-3">NLP Intent Distribution</h3>
          {intent_distribution.length === 0 ? (
            <p className="text-sm text-gray-400 py-8 text-center">No chat data yet.</p>
          ) : (
            <div className="space-y-3">
              {intent_distribution.map(({ intent, count }) => (
                <IntentBar key={intent} intent={intent} count={count} max={maxIntentCount} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Message feedback detail */}
      <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
        <h3 className="font-semibold text-gray-800 mb-4">Response Precision Breakdown</h3>
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="text-green-600 font-medium">👍 Helpful responses</span>
              <span className="font-bold">{helpful_count}</span>
            </div>
            <div className="h-3 bg-gray-100 rounded-full">
              <div
                className="h-full bg-green-500 rounded-full transition-all"
                style={{ width: `${helpful_count + unhelpful_count > 0 ? (helpful_count / (helpful_count + unhelpful_count)) * 100 : 0}%` }}
              />
            </div>
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="text-red-500 font-medium">👎 Unhelpful responses</span>
              <span className="font-bold">{unhelpful_count}</span>
            </div>
            <div className="h-3 bg-gray-100 rounded-full">
              <div
                className="h-full bg-red-400 rounded-full transition-all"
                style={{ width: `${helpful_count + unhelpful_count > 0 ? (unhelpful_count / (helpful_count + unhelpful_count)) * 100 : 0}%` }}
              />
            </div>
          </div>
        </div>
        <p className="text-xs text-gray-400 mt-3">
          Precision is calculated from user thumbs up/down votes on individual bot messages.
        </p>
      </div>

      {/* Recent comments */}
      {recent_ratings.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <h3 className="font-semibold text-gray-800 mb-3">Recent User Feedback</h3>
          <div className="space-y-3">
            {recent_ratings.map((r, i) => (
              <div key={i} className="flex items-start gap-3 border-b border-gray-50 pb-3 last:border-0 last:pb-0">
                <div className="flex shrink-0">
                  {[1,2,3,4,5].map(s => (
                    <span key={s} className={`text-sm ${s <= r.stars ? 'text-yellow-400' : 'text-gray-200'}`}>★</span>
                  ))}
                </div>
                <div className="flex-1">
                  {r.comment
                    ? <p className="text-sm text-gray-700">"{r.comment}"</p>
                    : <p className="text-sm text-gray-400 italic">No comment</p>
                  }
                  <p className="text-xs text-gray-400 mt-0.5">{new Date(r.timestamp).toLocaleString()}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="text-right">
        <button onClick={load} className="text-xs text-yellow-600 hover:text-yellow-800 underline">
          ↻ Refresh analytics
        </button>
      </div>
    </div>
  )
}

