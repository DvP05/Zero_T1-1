import { useState } from 'react'
import { api } from '../lib/api'
import { useTidalis } from '../store'

const SUGGESTIONS = [
  'What is happening near the coast?',
  'Why was this event detected?',
  'What is the forecast for the next 12 hours?',
  'Which assets are potentially exposed?',
  'Which area should be investigated first and why?',
  'Generate an incident report.',
]

function renderRich(text) {
  const parts = text.split('**')
  return parts.map((part, i) =>
    i % 2 === 1 ? <strong key={i}>{part}</strong> : <span key={i}>{part}</span>,
  )
}

export default function CopilotPanel() {
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      text: 'Copilot online. Ask me anything about the current coastal situation — every answer is grounded in live TIDALIS data.',
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [sessionEventId, setSessionEventId] = useState(null)
  const selectedEventId = useTidalis((s) => s.selectedEventId)

  const push = (msg) => setMessages((m) => [...m, msg])

  const ask = async (text) => {
    const q = text.trim()
    if (!q || busy) return
    const eventId = selectedEventId
    push({ role: 'user', text: q })
    setInput('')
    setBusy(true)
    try {
      const res = await api.copilot(q, eventId)
      push({
        role: 'bot',
        text: res.reply,
        sources: res.sources_used,
        copyable: /report/i.test(q),
      })
      setSessionEventId(res.event_id ?? eventId)
    } catch {
      push({
        role: 'bot',
        text: '⚠️ Backend unreachable. Copilot requires the TIDALIS API (port 8000).',
      })
    } finally {
      setBusy(false)
    }
  }

  const copyReport = async (text) => {
    try {
      await navigator.clipboard.writeText(text.replace(/\*\*/g, ''))
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="copilot">
      <div className="thread">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {renderRich(m.text)}
            {m.sources?.length > 0 && (
              <div className="sources">SOURCES: {m.sources.join(' · ')}</div>
            )}
            {m.copyable && (
              <button type="button" className="copy-btn" onClick={() => copyReport(m.text)}>
                copy text
              </button>
            )}
          </div>
        ))}
        {busy && <div className="msg bot"><span className="typing">Analyzing coastal data</span></div>}
      </div>

      <div className="chip-grid">
        {SUGGESTIONS.map((s) => (
          <button key={s} type="button" className="chip" onClick={() => ask(s)}>
            {s}
          </button>
        ))}
      </div>

      <div className="copilot-input">
        <input
          type="text"
          placeholder="Ask TIDALIS Copilot… (e.g. Generate an incident report)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && ask(input)}
        />
        <button type="button" className="btn" disabled={busy} onClick={() => ask(input)}>
          Send
        </button>
      </div>
      {sessionEventId ? (
        <div style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: 1, color: 'var(--muted)' }}>
          Responding for event EVT {sessionEventId.replace('evt-', '')}
        </div>
      ) : null}
    </div>
  )
}