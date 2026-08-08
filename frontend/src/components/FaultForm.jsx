/**
 * FaultForm — Objective 3: Fault reporting
 * 3-step guided form to submit electrical fault reports
 */
import React, { useState } from 'react'
import { API } from '../config.js'

const FAULT_TYPES = [
  { value: 'fallen_line',   label: 'Fallen Power Line',       icon: '⚡', danger: true  },
  { value: 'no_supply',     label: 'No Power Supply',          icon: '🔌', danger: false },
  { value: 'flickering',    label: 'Flickering Lights',        icon: '💡', danger: false },
  { value: 'damaged_pole',  label: 'Damaged Pole / Equipment', icon: '🪵', danger: true  },
  { value: 'streetlight',   label: 'Streetlight Fault',        icon: '🔦', danger: false },
  { value: 'transformer',   label: 'Transformer Issue',        icon: '🏭', danger: true  },
  { value: 'other',         label: 'Other',                    icon: '📋', danger: false },
]

const URGENCY = [
  { value: 'critical', label: 'Critical — Immediate danger', color: 'red',    dot: '🔴' },
  { value: 'high',     label: 'High — Major disruption',    color: 'orange',  dot: '🟠' },
  { value: 'medium',   label: 'Medium — Partial issue',     color: 'yellow',  dot: '🟡' },
  { value: 'low',      label: 'Low — Minor / cosmetic',     color: 'green',   dot: '🟢' },
]

const STEPS = ['Customer Details', 'Fault Type & Urgency', 'Review & Submit']

export default function FaultForm() {
  const [step, setStep]           = useState(0)
  const [submitted, setSubmitted] = useState(false)
  const [reference, setReference] = useState('')
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')

  const [form, setForm] = useState({
    customer_name: '',
    phone: '',
    location: '',
    fault_type: '',
    urgency: '',
    description: '',
  })

  function update(k, v) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  const canNext = [
    () => form.customer_name && form.phone && form.location,
    () => form.fault_type && form.urgency,
    () => true,
  ]

  async function submit() {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API}/fault-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error('Server error')
      const data = await res.json()
      setReference(data.reference)
      setSubmitted(true)
    } catch {
      setError('Failed to submit. Please try again or call 0800-POWER.')
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setForm({ customer_name: '', phone: '', location: '', fault_type: '', urgency: '', description: '' })
    setStep(0)
    setSubmitted(false)
    setReference('')
    setError('')
  }

  // ── Success screen ──────────────────────────────────────────────────────────
  if (submitted) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center shadow-sm">
        <div className="text-5xl mb-3">✅</div>
        <h3 className="text-xl font-bold text-gray-800 mb-1">Fault Report Submitted</h3>
        <p className="text-gray-500 text-sm mb-4">Your reference number is:</p>
        <div className="bg-blue-50 border border-ecg-navy/20 rounded-xl px-6 py-3 inline-block mb-6">
          <span className="text-2xl font-mono font-bold text-ecg-navy">{reference}</span>
        </div>
        <p className="text-sm text-gray-500 mb-6">
          Our team has been notified. You will receive updates on <strong>{form.phone}</strong>.
          {['critical', 'high'].includes(form.urgency) && (
            <span className="block mt-1 text-red-600 font-medium">
              ⚠️ For immediate danger, call <strong>0800-POWER</strong> now.
            </span>
          )}
        </p>
        <button
          onClick={reset}
          className="bg-ecg-navy hover:bg-ecg-navyDark text-white rounded-lg px-6 py-2 text-sm font-medium"
        >
          Submit Another Report
        </button>
      </div>
    )
  }

  // ── Step indicator ──────────────────────────────────────────────────────────
  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Progress bar */}
      <div className="bg-gray-50 px-6 pt-5 pb-3 border-b border-gray-100">
        <div className="flex items-center justify-between mb-3">
          {STEPS.map((s, i) => (
            <React.Fragment key={s}>
              <div className="flex items-center gap-1.5">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                  i < step ? 'bg-green-500 text-white'
                  : i === step ? 'bg-ecg-navy text-white'
                  : 'bg-gray-200 text-gray-500'
                }`}>
                  {i < step ? '✓' : i + 1}
                </div>
                <span className={`text-xs hidden sm:inline ${i === step ? 'text-ecg-navy font-medium' : 'text-gray-400'}`}>
                  {s}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-2 ${i < step ? 'bg-green-400' : 'bg-gray-200'}`} />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      <div className="p-6">
        {/* Step 0: Customer Details */}
        {step === 0 && (
          <div className="space-y-4">
            <h3 className="font-semibold text-gray-800">Your Details</h3>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Full Name *</label>
              <input
                value={form.customer_name}
                onChange={(e) => update('customer_name', e.target.value)}
                placeholder="e.g. Kwame Mensah"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ecg-navy/30"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Phone Number *</label>
              <input
                value={form.phone}
                onChange={(e) => update('phone', e.target.value)}
                placeholder="e.g. 0244 123 456"
                type="tel"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ecg-navy/30"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Location / Address *</label>
              <input
                value={form.location}
                onChange={(e) => update('location', e.target.value)}
                placeholder="e.g. 14 Ring Road, Accra Central"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ecg-navy/30"
              />
            </div>
          </div>
        )}

        {/* Step 1: Fault Type & Urgency */}
        {step === 1 && (
          <div className="space-y-5">
            <div>
              <h3 className="font-semibold text-gray-800 mb-2">Fault Type *</h3>
              <div className="grid grid-cols-2 gap-2">
                {FAULT_TYPES.map((ft) => (
                  <button
                    key={ft.value}
                    onClick={() => update('fault_type', ft.value)}
                    className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border text-sm text-left transition-colors ${
                      form.fault_type === ft.value
                        ? 'bg-blue-50 border-ecg-navy text-ecg-navy'
                        : 'bg-white border-gray-200 text-gray-700 hover:border-ecg-navy/40'
                    }`}
                  >
                    <span>{ft.icon}</span>
                    <span className="leading-tight">{ft.label}</span>
                    {ft.danger && <span className="ml-auto text-red-500 text-xs">⚠️</span>}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <h3 className="font-semibold text-gray-800 mb-2">Urgency Level *</h3>
              <div className="space-y-2">
                {URGENCY.map((u) => (
                  <button
                    key={u.value}
                    onClick={() => update('urgency', u.value)}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl border text-sm transition-colors ${
                      form.urgency === u.value
                        ? 'bg-blue-50 border-ecg-navy text-ecg-navy'
                        : 'bg-white border-gray-200 text-gray-700 hover:border-ecg-navy/40'
                    }`}
                  >
                    <span>{u.dot}</span>
                    <span>{u.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Additional Description</label>
              <textarea
                rows={3}
                value={form.description}
                onChange={(e) => update('description', e.target.value)}
                placeholder="Describe the fault in more detail (optional)…"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ecg-navy/30"
              />
            </div>
          </div>
        )}

        {/* Step 2: Review */}
        {step === 2 && (
          <div className="space-y-4">
            <h3 className="font-semibold text-gray-800">Review & Confirm</h3>
            <div className="bg-gray-50 rounded-xl p-4 space-y-2 text-sm">
              {[
                ['Name',     form.customer_name],
                ['Phone',    form.phone],
                ['Location', form.location],
                ['Fault',    FAULT_TYPES.find(f => f.value === form.fault_type)?.label || form.fault_type],
                ['Urgency',  URGENCY.find(u => u.value === form.urgency)?.label || form.urgency],
                ['Notes',    form.description || '—'],
              ].map(([k, v]) => (
                <div key={k} className="flex gap-2">
                  <span className="text-gray-500 w-20 shrink-0">{k}:</span>
                  <span className="text-gray-800 font-medium">{v}</span>
                </div>
              ))}
            </div>

            {['critical', 'high'].includes(form.urgency) && (
              <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
                <strong>⚠️ Danger notice:</strong> If there is immediate risk to life or property,
                call <strong>0800-POWER</strong> immediately — do not wait for a field team.
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-600">
                {error}
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between mt-6">
          <button
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 0}
            className="px-5 py-2 rounded-lg border border-gray-200 text-gray-600 text-sm disabled:opacity-30 hover:bg-gray-50"
          >
            Back
          </button>
          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              disabled={!canNext[step]()}
              className="px-5 py-2 rounded-lg bg-ecg-navy text-white text-sm font-medium disabled:opacity-40 hover:bg-ecg-navyDark"
            >
              Next →
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={loading}
              className="px-6 py-2 rounded-lg bg-green-600 text-white text-sm font-medium disabled:opacity-60 hover:bg-green-700"
            >
              {loading ? 'Submitting…' : 'Submit Report'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
