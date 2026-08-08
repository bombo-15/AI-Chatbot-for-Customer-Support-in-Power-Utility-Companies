import React, { useState } from 'react'
import ChatWindow  from './components/ChatWindow.jsx'
import OutageBoard from './components/OutageBoard.jsx'
import FaultForm   from './components/FaultForm.jsx'

const TABS = [
  { id: 'chat',    label: 'Chat Support',   icon: '💬' },
  { id: 'outages', label: 'Outage Status',  icon: '⚡' },
  { id: 'fault',   label: 'Report a Fault', icon: '🔧' },
]

export default function App() {
  const [tab, setTab] = useState('chat')

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-yellow-50 font-sans">
      {/* Top contact bar (mirrors ecg.com.gh's thin contact strip above the main nav) */}
      <div className="bg-ecg-navyDark text-xs">
        <div className="max-w-5xl mx-auto px-4 py-1.5 flex items-center justify-between text-blue-100">
          <span className="hidden sm:inline">The Name Behind Electricity in Ghana</span>
          <div className="flex items-center gap-4 ml-auto">
            <span>📞 +233 (0302) 611 611</span>
            <span className="hidden sm:inline">✉️ help@ecggh.com</span>
          </div>
        </div>
      </div>

      {/* Header */}
      <header className="bg-ecg-navy shadow-lg">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-ecg-yellow rounded-full flex items-center justify-center text-2xl shadow ring-2 ring-white/30">
              💡
            </div>
            <div>
              <h1 className="text-white font-bold text-lg leading-tight">Kanea</h1>
              <p className="text-ecg-yellow text-xs">AI Customer Support System</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="tel:+233302611611"
              className="hidden sm:flex items-center gap-2 bg-transparent hover:bg-white/10 text-white font-medium text-sm rounded-full px-4 py-1.5 border border-ecg-red transition-colors"
            >
              <span>📞</span> Emergency Line <span aria-hidden>→</span>
            </a>
          </div>
        </div>
      </header>

      {/* Tab Navigation */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4">
          <nav className="flex overflow-x-auto">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 px-4 sm:px-6 py-3.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  tab === t.id
                    ? 'border-ecg-red text-ecg-navy'
                    : 'border-transparent text-gray-500 hover:text-ecg-red hover:border-gray-300'
                }`}
              >
                <span>{t.icon}</span>
                <span className="hidden sm:inline">{t.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Tab Content */}
      <main className="max-w-5xl mx-auto px-4 py-6">
        {tab === 'chat' && (
          <div className="max-w-2xl mx-auto">
            <div className="mb-4">
              <h2 className="text-xl font-bold text-ecg-navy">AI Chat Support</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                </p>
            </div>
            <ChatWindow />
          </div>
        )}

        {tab === 'outages' && (
          <div>
            <div className="mb-4">
              <h2 className="text-xl font-bold text-ecg-navy">Outage Status Board</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Live outage and planned maintenance updates across all service areas
              </p>
            </div>
            <OutageBoard />
          </div>
        )}

        {tab === 'fault' && (
          <div className="max-w-xl mx-auto">
            <div className="mb-4">
              <h2 className="text-xl font-bold text-ecg-navy">Report a Fault</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Submit an electrical fault report — our field team will respond based on urgency
              </p>
            </div>
            <FaultForm />
            <p className="text-xs text-center text-gray-400 mt-3">
              For life-threatening emergencies call <strong>0302 611 611</strong> immediately
            </p>
          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="mt-12 border-t border-gray-200 bg-ecg-navy py-4">
        <div className="max-w-5xl mx-auto px-4 flex flex-wrap items-center justify-between gap-2 text-xs text-blue-200">
          <span>© 2026 Kanea Chatbot</span>
          <span>Emergency: <a href="tel:+233302611611" className="text-ecg-yellow hover:underline">0302 611 611</a></span>
        </div>
      </footer>
    </div>
  )
}
