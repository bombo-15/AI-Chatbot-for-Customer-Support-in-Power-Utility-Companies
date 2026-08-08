import React, { useState, useEffect, useRef, useCallback } from 'react'
import DOMPurify from 'dompurify'
import { WS_URL, API } from '../config.js'

function formatISODates(text) {
  return text.replace(
    /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?/g,
    (match) => {
      const d = new Date(match)
      if (isNaN(d)) return match
      return (
        d.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }) +
        ' at ' +
        d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
      )
    }
  )
}

function sanitize(text) {
  const html = formatISODates(text).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  return DOMPurify.sanitize(html, { ALLOWED_TAGS: ['strong', 'em', 'br', 'ul', 'li', 'p'] })
}

const SESSION_STORAGE_KEY = 'kanea_session_id'

// Quick-reply labels that should jump straight to a real app tab instead of
// round-tripping through the LLM — e.g. "Submit fault form" opens the actual
// working Report a Fault form rather than the bot talking about it.
const NAV_QUICK_REPLIES = {
  'Submit fault form': { tab: 'fault', note: 'Opening the fault report form for you →' },
  'Report a fault':    { tab: 'fault', note: 'Opening the fault report form for you →' },
}

function genSessionId() {
  const existing = localStorage.getItem(SESSION_STORAGE_KEY)
  if (existing) return existing
  const id = 'sess-' + Math.random().toString(36).slice(2, 10)
  localStorage.setItem(SESSION_STORAGE_KEY, id)
  return id
}

// ── Star Rating ───────────────────────────────────────────────────────────────
function StarRating({ sessionId, onDone }) {
  const [selected, setSelected] = useState(0)
  const [hovered, setHovered]   = useState(0)
  const [comment, setComment]   = useState('')
  const [submitted, setSubmitted] = useState(false)

  async function submit() {
    if (!selected) return
    await fetch(`${API}/chat-rating`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, stars: selected, comment }),
    })
    setSubmitted(true)
    setTimeout(onDone, 1500)
  }

  if (submitted) {
    return (
      <div className="text-center py-2 text-sm text-green-600 font-medium">
        ✅ Thanks for your feedback!
      </div>
    )
  }

  return (
    <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-4 py-3 space-y-2">
      <p className="text-xs font-medium text-ecg-navy">How was your experience?</p>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onClick={() => setSelected(star)}
            onMouseEnter={() => setHovered(star)}
            onMouseLeave={() => setHovered(0)}
            className="text-2xl transition-transform hover:scale-110"
          >
            {star <= (hovered || selected) ? '⭐' : '☆'}
          </button>
        ))}
      </div>
      {selected > 0 && (
        <>
          <input
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Any comments? (optional)"
            className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-yellow-300"
          />
          <button
            onClick={submit}
            className="bg-ecg-navy text-ecg-yellow text-xs font-semibold rounded-full px-4 py-1.5 hover:bg-ecg-navyDark transition-colors"
          >
            Submit
          </button>
        </>
      )}
    </div>
  )
}

// ── Single message bubble ─────────────────────────────────────────────────────
function Message({ msg, sessionId, onFeedback }) {
  const isBot = msg.type === 'bot'
  const time  = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const [feedback, setFeedback] = useState(null)

  async function sendFeedback(rating) {
    if (!msg.message_id) return
    setFeedback(rating)
    await fetch(`${API}/message-feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message_id: msg.message_id, session_id: sessionId, rating }),
    })
    onFeedback?.()
  }

  return (
    <div className={`flex ${isBot ? 'justify-start' : 'justify-end'} mb-3`}>
      {isBot && (
        <div className="w-8 h-8 rounded-full bg-ecg-yellow flex items-center justify-center text-lg mr-2 mt-1 shrink-0 shadow">
          💡
        </div>
      )}
      <div className="max-w-[78%]">
        <div
          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
            isBot
              ? 'bg-white border border-yellow-200 text-gray-800 rounded-tl-sm shadow-sm'
              : 'bg-ecg-navy text-white rounded-tr-sm'
          }`}
          dangerouslySetInnerHTML={{ __html: sanitize(msg.text) }}
        />

        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-gray-400">{time}</span>

          {/* Helpful / Unhelpful feedback buttons */}
          {isBot && msg.message_id && !feedback && (
            <div className="flex gap-1">
              <button
                onClick={() => sendFeedback('helpful')}
                title="Helpful"
                className="text-xs text-gray-400 hover:text-green-500 transition-colors"
              >👍</button>
              <button
                onClick={() => sendFeedback('unhelpful')}
                title="Not helpful"
                className="text-xs text-gray-400 hover:text-red-400 transition-colors"
              >👎</button>
            </div>
          )}
          {feedback && (
            <span className="text-xs text-gray-400">
              {feedback === 'helpful' ? '👍 Marked helpful' : '👎 Noted'}
            </span>
          )}
        </div>

        {isBot && msg.escalate && (
          <div className="mt-2 flex items-center gap-2 bg-yellow-50 border border-yellow-300 rounded-lg px-3 py-2">
            <span className="text-yellow-600 text-sm">🧑‍💼</span>
            <span className="text-xs text-ecg-navy font-medium">
              Connecting you to a human agent — or call <strong>0302 611 611</strong> now
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main ChatWindow ───────────────────────────────────────────────────────────
export default function ChatWindow({ onNavigate }) {
  const [messages, setMessages]         = useState([])
  const [input, setInput]               = useState('')
  const [connected, setConnected]       = useState(false)
  const [sessionId]                     = useState(genSessionId)
  const [quickReplies, setQuickReplies] = useState([])
  const [isTyping, setIsTyping]         = useState(false)
  const [showRating, setShowRating]     = useState(false)
  const [botMsgCount, setBotMsgCount]   = useState(0)

  const wsRef        = useRef(null)
  const bottomRef    = useRef(null)
  const retryCount   = useRef(0)
  const retryTimeout = useRef(null)

  const addMessage = useCallback((msg) => {
    setMessages((prev) => [...prev, msg])
    if (msg.quick_replies?.length) setQuickReplies(msg.quick_replies)
    if (msg.type === 'bot') {
      setBotMsgCount((n) => {
        const next = n + 1
        // Show rating prompt after the 5th bot response
        if (next === 5) setShowRating(true)
        return next
      })
    }
  }, [])

  // Re-hydrate chat history if this session already has messages (e.g. after a page refresh)
  useEffect(() => {
    fetch(`${API}/session/${sessionId}/messages`)
      .then((res) => res.json())
      .then((history) => {
        if (Array.isArray(history) && history.length) {
          setMessages(history)
          setBotMsgCount(history.filter((m) => m.type === 'bot').length)
        }
      })
      .catch(() => {})
  }, [sessionId])

  // WebSocket connection with exponential-backoff reconnect
  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL(sessionId))
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        retryCount.current = 0
      }

      ws.onclose = () => {
        setConnected(false)
        // Backoff: 1s → 2s → 4s → 8s … max 30s
        const delay = Math.min(1000 * Math.pow(2, retryCount.current), 30_000)
        retryCount.current += 1
        retryTimeout.current = setTimeout(connect, delay)
      }

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data)
        if (data.type === 'user') return
        setIsTyping(false)
        addMessage(data)
      }
    }

    connect()

    return () => {
      clearTimeout(retryTimeout.current)
      wsRef.current?.close()
    }
  }, [sessionId, addMessage])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function send(text) {
    const msg = text || input.trim()
    if (!msg || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    addMessage({ type: 'user', text: msg })
    wsRef.current.send(JSON.stringify({ message: msg }))
    setInput('')
    setQuickReplies([])
    setIsTyping(true)
  }

  function handleQuickReply(qr) {
    const nav = NAV_QUICK_REPLIES[qr]
    if (nav && onNavigate) {
      addMessage({ type: 'user', text: qr })
      addMessage({ type: 'bot', text: nav.note })
      setQuickReplies([])
      onNavigate(nav.tab)
      return
    }
    send(qr)
  }

  return (
    <div className="flex flex-col h-[620px] bg-white rounded-2xl shadow-md border border-yellow-200 overflow-hidden">
      {/* Header */}
      <div className="bg-ecg-navy px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-full bg-ecg-yellow flex items-center justify-center text-xl shadow ring-2 ring-white/30">
            💡
          </div>
          <div>
            <p className="text-white font-semibold text-sm">Kanea</p>
            <p className="text-ecg-yellow text-xs">AI Customer Support</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-ecg-red animate-pulse'}`} />
          <span className="text-blue-200 text-xs">
            {connected ? 'Online' : retryCount.current > 0 ? 'Reconnecting…' : 'Connecting…'}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 bg-ecg-navy/[0.03]">
        {messages.map((msg, i) => (
          <Message key={i} msg={msg} sessionId={sessionId} />
        ))}

        {isTyping && (
          <div className="flex justify-start mb-3">
            <div className="w-8 h-8 rounded-full bg-ecg-yellow flex items-center justify-center text-lg mr-2 mt-1 shrink-0 shadow">
              💡
            </div>
            <div className="bg-white border border-yellow-200 rounded-2xl rounded-tl-sm shadow-sm px-4 py-3 flex items-center gap-1">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}

        {/* Star rating prompt */}
        {showRating && (
          <div className="mb-3">
            <StarRating sessionId={sessionId} onDone={() => setShowRating(false)} />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Quick replies */}
      {quickReplies.length > 0 && (
        <div className="px-4 py-2 flex gap-2 flex-wrap bg-white border-t border-yellow-100">
          {quickReplies.map((qr) => (
            <button
              key={qr}
              onClick={() => handleQuickReply(qr)}
              className="text-xs bg-yellow-50 text-ecg-navy border border-yellow-300 rounded-full px-3 py-1 hover:bg-yellow-100 hover:text-ecg-red hover:border-ecg-red transition-colors font-medium"
            >
              {qr}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="border-t border-yellow-100 bg-white px-3 py-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Type your message…"
          className="flex-1 border border-gray-200 rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-yellow-300"
        />
        <button
          onClick={() => send()}
          disabled={!input.trim() || !connected}
          className="bg-ecg-yellow hover:opacity-90 disabled:opacity-40 text-ecg-navy font-semibold rounded-full px-4 py-2 text-sm transition-colors shadow-sm"
        >
          Send
        </button>
      </div>
    </div>
  )
}
