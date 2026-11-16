import { AlertTriangle, ChevronDown, Mic, MicOff, SendHorizontal, ShieldCheck, Sparkles, Wrench } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { SuggestionGroup, ToolCall } from '../api'
import { type CardActions, SuggestionGroups } from './ProductCards'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'notice'
  text: string
  grounded?: boolean
  ungrounded?: string[]
  toolCalls?: ToolCall[]
  suggestions?: SuggestionGroup[]
}

type Lang = 'en-IN' | 'hi-IN' | 'mr-IN'
const LANGS: { code: Lang; label: string }[] = [
  { code: 'en-IN', label: 'English' }, { code: 'hi-IN', label: 'हिंदी' }, { code: 'mr-IN', label: 'मराठी' },
]
const EXAMPLES: Record<Lang, string[]> = {
  'en-IN': [
    'I need 2 toned milk, oats, instant coffee and Britannia brown bread. Budget ₹600',
    'Where can I find basmati rice?',
    'Add 3 Tea Bags and show my coupons',
    'Is my cart cheaper at another store?',
  ],
  'hi-IN': [
    'मुझे 2 टोंड दूध, ओट्स, इंस्टेंट कॉफी और ब्रिटानिया ब्राउन ब्रेड चाहिए। बजट ₹600',
    'बासमती चावल कहाँ मिलेगा?',
    'मेरे बिल में कितना GST है?',
    'क्या दूसरी दुकान में यह सस्ता है?',
  ],
  'mr-IN': [
    'मला 2 टोन्ड दूध, ओट्स, इन्स्टंट कॉफी आणि ब्रिटानिया ब्राउन ब्रेड हवे आहे. बजेट ₹600',
    'बासमती तांदूळ कुठे मिळेल?',
    'माझ्या बिलात किती GST आहे?',
    'दुसऱ्या दुकानात हे स्वस्त आहे का?',
  ],
}
const PLACEHOLDER: Record<Lang, string> = {
  'en-IN': 'e.g. 2 litres milk, oats and coffee under ₹600',
  'hi-IN': 'जैसे: 2 लीटर दूध, ओट्स और कॉफी, ₹600 के अंदर',
  'mr-IN': 'उदा. 2 लिटर दूध, ओट्स आणि कॉफी, ₹600 च्या आत',
}
const LANG_KEY = 'smartcart.lang'

// Web Speech API (Chrome / Edge): speech -> text in the chosen language, entirely in the browser.
interface SpeechResultEvent { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }
interface Recognizer {
  lang: string; interimResults: boolean; continuous: boolean
  onresult: ((e: SpeechResultEvent) => void) | null; onend: (() => void) | null; onerror: (() => void) | null
  start: () => void; stop: () => void
}
type RecognizerCtor = new () => Recognizer
const SpeechRecognition: RecognizerCtor | undefined =
  (window as unknown as { SpeechRecognition?: RecognizerCtor; webkitSpeechRecognition?: RecognizerCtor })
    .SpeechRecognition ?? (window as unknown as { webkitSpeechRecognition?: RecognizerCtor }).webkitSpeechRecognition

/** Short, readable form of one tool call, e.g. search_products("toned milk"). */
function describeCall(c: ToolCall): string {
  const a = c.args
  switch (c.tool) {
    case 'search_products':
      return `search “${a.query}”`
    case 'update_cart':
      return Number(a.quantity) === 0 && a.mode === 'set'
        ? `remove #${a.product_id}`
        : `${a.mode === 'set' ? 'set' : 'add'} #${a.product_id} × ${a.quantity}`
    case 'check_stock':
      return `stock #${a.product_id}`
    case 'find_substitutes':
      return `substitutes for #${a.product_id}`
    case 'set_budget':
      return `budget ₹${a.amount}`
    case 'fit_budget':
      return 'find swaps to fit the budget'
    case 'view_bill':
      return 'view bill'
    case 'compare_stores':
      return 'compare prices at other stores'
    case 'checkout':
      return 'checkout'
    default:
      return c.tool
  }
}

function GroundingBadge({ grounded, ungrounded }: { grounded?: boolean; ungrounded?: string[] }) {
  if (grounded === undefined) return null
  return grounded ? (
    <span className="badge badge-ok" title="Every ₹ amount and aisle number in this reply came from the store database">
      <ShieldCheck size={13} aria-hidden /> Grounded in database
    </span>
  ) : (
    <span className="badge badge-warn" title="These values were not returned by any tool">
      <AlertTriangle size={13} aria-hidden /> Unverified: {ungrounded?.join(', ')}
    </span>
  )
}

function Message({ m, actions }: { m: ChatMessage; actions: CardActions }) {
  const [traceOpen, setTraceOpen] = useState(false)
  if (m.role === 'notice') return <div className="notice">{m.text}</div>
  if (m.role === 'user') return <div className="msg msg-user">{m.text}</div>
  const calls = m.toolCalls ?? []
  return (
    <div className="msg msg-bot">
      <div className="md">
        <ReactMarkdown>{m.text}</ReactMarkdown>
      </div>
      <div className="msg-meta">
        <GroundingBadge grounded={m.grounded} ungrounded={m.ungrounded} />
        {calls.length > 0 && (
          <button className="trace-toggle" onClick={() => setTraceOpen(!traceOpen)} aria-expanded={traceOpen}>
            <Wrench size={13} aria-hidden /> {calls.length} tool call{calls.length > 1 ? 's' : ''}
            <ChevronDown size={14} className={traceOpen ? 'rot' : ''} aria-hidden />
          </button>
        )}
      </div>
      {traceOpen && (
        <ol className="trace-list">
          {calls.map((c, i) => (
            <li key={i}>
              <code>{c.tool}</code> <span>{describeCall(c)}</span>
            </li>
          ))}
        </ol>
      )}
      <SuggestionGroups groups={m.suggestions ?? []} actions={actions} />
    </div>
  )
}

interface ChatProps {
  messages: ChatMessage[]
  busy: boolean
  disabled: boolean
  onSend: (text: string) => void
  actions: CardActions
}

export function Chat({ messages, busy, disabled, onSend, actions }: ChatProps) {
  const [draft, setDraft] = useState('')
  const [lang, setLangState] = useState<Lang>(() => {
    try { return (localStorage.getItem(LANG_KEY) as Lang) || 'en-IN' } catch { return 'en-IN' }
  })
  const [listening, setListening] = useState(false)
  const recRef = useRef<Recognizer | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  const setLang = (l: Lang) => {
    setLangState(l)
    try { localStorage.setItem(LANG_KEY, l) } catch { /* private mode */ }
  }

  const toggleMic = () => {
    if (!SpeechRecognition) return
    if (listening) { recRef.current?.stop(); return }
    const rec = new SpeechRecognition()
    rec.lang = lang
    rec.interimResults = true
    rec.continuous = false
    rec.onresult = (e) => setDraft(Array.from(e.results).map((r) => r[0].transcript).join(' '))
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    recRef.current = rec
    setListening(true)
    rec.start()
  }

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, busy])

  const send = (text: string) => {
    const t = text.trim()
    if (!t || busy || disabled) return
    onSend(t)
    setDraft('')
  }

  return (
    <section className="chat" aria-label="Chat with the shopping assistant">
      <div className="chat-scroll">
        {messages.length === 0 ? (
          <div className="welcome">
            <div className="welcome-icon"><Sparkles size={22} aria-hidden /></div>
            <h1>What do you need today?</h1>
            <p>
              Tell me your shopping list in your own words. I’ll find each item’s aisle, check live
              stock, swap anything that’s out of stock and apply the best coupons. Every price comes
              from the store database.
            </p>
            <div className="lang-pick" role="group" aria-label="Language">
              {LANGS.map((l) => (
                <button key={l.code} className={`chip ${lang === l.code ? 'on' : ''}`} onClick={() => setLang(l.code)}>
                  {l.label}
                </button>
              ))}
            </div>
            <div className="examples">
              {EXAMPLES[lang].map((e) => (
                <button key={e} className="example" onClick={() => send(e)} disabled={busy || disabled}>
                  {e}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="messages">
            {messages.map((m) => <Message key={m.id} m={m} actions={actions} />)}
            {busy && (
              <div className="msg msg-bot typing" aria-live="polite">
                <span className="dots" aria-hidden><i /><i /><i /></span>
                Checking aisles, stock and offers…
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); recRef.current?.stop(); send(draft) }}>
        <select className="lang-select" value={lang} onChange={(e) => setLang(e.target.value as Lang)}
          aria-label="Language for voice input">
          {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
        </select>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={disabled ? 'AI assistant unavailable — see the status above'
            : listening ? '🎙 Listening… speak your shopping list' : PLACEHOLDER[lang]}
          disabled={disabled}
          aria-label="Message"
        />
        {SpeechRecognition && (
          <button type="button" className={`mic ${listening ? 'on' : ''}`} onClick={toggleMic} disabled={disabled || busy}
            aria-label={listening ? 'Stop voice input' : 'Speak your request'} title="Voice input">
            {listening ? <MicOff size={18} aria-hidden /> : <Mic size={18} aria-hidden />}
          </button>
        )}
        <button type="submit" className="send" disabled={!draft.trim() || busy || disabled} aria-label="Send">
          <SendHorizontal size={18} aria-hidden />
        </button>
      </form>
    </section>
  )
}
