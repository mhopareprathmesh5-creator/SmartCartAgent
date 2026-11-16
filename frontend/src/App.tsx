import { CircleAlert, Database, RotateCcw, ShoppingBasket, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Bill, BudgetPlan, Health, Order, SessionView, StoreComparison } from './api'
import { ApiError, api, rupees } from './api'
import { Admin } from './components/Admin'
import { EvaluationPanel } from './components/EvaluationPanel'
import { StudyPage } from './components/StudyPage'
import { CartPanel } from './components/CartPanel'
import { Chat, type ChatMessage } from './components/Chat'
import { Receipt } from './components/Receipt'

const SESSION_KEY = 'smartcart.session'
const msgsKey = (sid: string) => `smartcart.messages.${sid}`
const POLL_MS = 4000

// Browser storage is only a convenience (chat history across reloads); wrap every access.
function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    return v ? (JSON.parse(v) as T) : fallback
  } catch {
    return fallback
  }
}
function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch { /* storage unavailable: history just won't survive a reload */ }
}
function forget(key: string) {
  try {
    localStorage.removeItem(key)
  } catch { /* ignore */ }
}

const newSessionId = () => `web-${crypto.randomUUID().slice(0, 8)}`
const uid = () => crypto.randomUUID()
type Page = 'shop' | 'admin' | 'eval' | 'study'
const PAGES: Record<string, Page> = { '#/admin': 'admin', '#/eval': 'eval', '#/study': 'study' }
const pageFromHash = (): Page => PAGES[window.location.hash] ?? 'shop'

/** Compact signature of what a shopper sees, to notice store-side changes between polls. */
const billSig = (b: Bill | null) =>
  b ? `${b.final_total}|${b.items.map((i) => `${i.product_id}:${i.qty}:${i.unit_price}`).join(',')}|${b.warnings.join()}` : ''

export default function App() {
  const [page, setPage] = useState<Page>(pageFromHash)
  const [sessionId, setSessionId] = useState<string>(() => {
    const s = load<string | null>(SESSION_KEY, null) ?? newSessionId()
    save(SESSION_KEY, s)
    return s
  })
  const [messages, setMessages] = useState<ChatMessage[]>(() => load(msgsKey(sessionId), []))
  const [bill, setBill] = useState<Bill | null>(null)
  const [hasSession, setHasSession] = useState(false)
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [receipt, setReceipt] = useState<Order | null>(null)
  const billRef = useRef<Bill | null>(null)
  const busyRef = useRef(false)

  useEffect(() => save(msgsKey(sessionId), messages), [sessionId, messages])
  useEffect(() => { billRef.current = bill }, [bill])
  useEffect(() => { busyRef.current = busy }, [busy])

  useEffect(() => {
    const onHash = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 4500)
    return () => clearTimeout(t)
  }, [toast])

  const applyView = useCallback((v: SessionView) => {
    setBill(v.bill)
    setHasSession(true)
  }, [])

  // On load: server status, then restore this session's cart (if the server still knows it).
  useEffect(() => {
    api.health().then(setHealth).catch((e: Error) => setHealthError(e.message))
    if (load<ChatMessage[]>(msgsKey(sessionId), []).length === 0) return   // nothing to restore yet
    api.session(sessionId)
      .then(applyView)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) {
          // Server restarted (chat memory is in-process) — the old transcript no longer matches.
          setMessages((m) => (m.length ? [{ id: uid(), role: 'notice', text: 'Previous conversation expired (server restarted). Starting fresh.' }] : m))
          setBill(null)
          setHasSession(false)
        }
      })
  }, [sessionId, applyView])

  // Live refresh: store staff may change prices / stock / coupons at any time (admin page).
  useEffect(() => {
    if (!hasSession || page !== 'shop') return
    const t = setInterval(() => {
      if (busyRef.current || document.hidden) return
      api.session(sessionId).then((v) => {
        if (busyRef.current) return
        if (billRef.current && billSig(v.bill) !== billSig(billRef.current)) {
          setToast('Store prices or stock changed — your bill was updated.')
        }
        setBill(v.bill)
      }).catch(() => { /* transient; next poll retries */ })
    }, POLL_MS)
    return () => clearInterval(t)
  }, [hasSession, sessionId, page])

  const notice = (text: string) => setMessages((m) => [...m, { id: uid(), role: 'notice', text }])

  /** Run a cart action with the busy flag and error toast. */
  const run = useCallback(async (fn: () => Promise<void>) => {
    setBusy(true)
    try {
      await fn()
    } catch (e) {
      setToast((e as Error).message)
    } finally {
      setBusy(false)
    }
  }, [])

  const send = useCallback(async (text: string) => {
    setMessages((m) => [...m, { id: uid(), role: 'user', text }])
    setBusy(true)
    try {
      const r = await api.chat(sessionId, text)
      setMessages((m) => [...m, {
        id: uid(), role: 'assistant', text: r.reply,
        grounded: r.grounded, ungrounded: r.ungrounded, toolCalls: r.tool_calls, suggestions: r.suggestions,
      }])
      setBill(r.bill)
      setHasSession(true)
    } catch (e) {
      notice((e as Error).message)
    } finally {
      setBusy(false)
    }
  }, [sessionId])

  const setQty = useCallback((productId: number, qty: number) => run(async () => {
    const { update, session } = await api.setItem(sessionId, productId, Math.max(0, qty))
    applyView(session)
    if (!update.ok) setToast(update.message)
  }), [sessionId, run, applyView])

  const swap = useCallback((from: number, to: number, quantity: number) => run(async () => {
    const { results, session } = await api.swap(sessionId, [{ from_product_id: from, to_product_id: to, quantity }])
    applyView(session)
    if (!results[0].ok) setToast(results[0].message)
  }), [sessionId, run, applyView])

  const setBudget = useCallback((amount: string | null) => run(async () => {
    applyView(await api.setBudget(sessionId, amount))
  }), [sessionId, run, applyView])

  const compareStores = useCallback(async (): Promise<StoreComparison | null> => {
    try {
      return await api.compareStores(sessionId)
    } catch (e) {
      setToast((e as Error).message)
      return null
    }
  }, [sessionId])

  const fetchPlan = useCallback(async (): Promise<BudgetPlan | null> => {
    try {
      return await api.budgetPlan(sessionId)
    } catch (e) {
      setToast((e as Error).message)
      return null
    }
  }, [sessionId])

  const applyPlan = useCallback((plan: BudgetPlan) => run(async () => {
    const { results, session } = await api.swap(sessionId, plan.swaps.map((s) => ({
      from_product_id: s.from_product_id, to_product_id: s.to_product_id, quantity: s.quantity })))
    applyView(session)
    const refused = results.filter((r) => !r.ok)
    if (refused.length) setToast(refused.map((r) => r.message).join(' · '))
    else notice(`Applied ${plan.swaps.length} budget swap${plan.swaps.length > 1 ? 's' : ''} — you now pay ${rupees(session.bill.final_total)}.`)
  }), [sessionId, run, applyView])

  const checkout = useCallback(() => run(async () => {
    const { result, session } = await api.checkout(sessionId)
    applyView(session)
    if (result.ok && result.order) {
      setReceipt(result.order)
      notice(`Order #${result.order.order_id} placed — paid ${rupees(result.order.final_total)}. Your cart is empty again.`)
    } else {
      setToast(result.problems.join(' · '))
    }
  }), [sessionId, run, applyView])

  const newChat = () => {
    forget(msgsKey(sessionId))
    const s = newSessionId()
    save(SESSION_KEY, s)
    setSessionId(s)
    setMessages([])
    setBill(null)
    setHasSession(false)
  }

  const cartQty = useMemo(() => Object.fromEntries((bill?.items ?? []).map((i) => [i.product_id, i.qty])), [bill])
  const cardActions = useMemo(() => ({
    cartQty, busy,
    onAdd: (pid: number) => setQty(pid, (cartQty[pid] ?? 0) + 1),
    onSwap: swap,
  }), [cartQty, busy, setQty, swap])

  const aiReady = health?.llm_configured ?? true

  return (
    <div className={`app ${page !== 'shop' ? 'app-admin' : ''}`}>
      <header className="top">
        <div className="brand">
          <div className="logo"><ShoppingBasket size={20} aria-hidden /></div>
          <div>
            <div className="brand-name">SmartMart Assistant</div>
            <div className="brand-sub">Kolhapur store · AI shopping & billing</div>
          </div>
        </div>
        <nav className="tabs" aria-label="Pages">
          <a href="#/" className={page === 'shop' ? 'on' : ''}>Shop</a>
          <a href="#/admin" className={page === 'admin' ? 'on' : ''}>Store admin</a>
          <a href="#/eval" className={page === 'eval' ? 'on' : ''}>Evaluation</a>
          <a href="#/study" className={page === 'study' ? 'on' : ''}>User study</a>
        </nav>
        <div className="top-right">
          {healthError ? (
            <span className="status bad"><CircleAlert size={14} aria-hidden /> Server offline</span>
          ) : health && (
            <>
              <span className="status"><Database size={14} aria-hidden /> {health.products} products live</span>
              <span className={`status ${aiReady ? '' : 'bad'}`}>
                <Sparkles size={14} aria-hidden /> {aiReady ? 'Gemini agent ready' : 'GOOGLE_API_KEY missing'}
              </span>
            </>
          )}
          {page === 'shop' && (
            <button className="ghost" onClick={newChat} disabled={busy}>
              <RotateCcw size={15} aria-hidden /> New chat
            </button>
          )}
        </div>
      </header>

      {page === 'admin' ? (
        <Admin onToast={setToast} />
      ) : page === 'eval' ? (
        <div className="admin"><EvaluationPanel /></div>
      ) : page === 'study' ? (
        <StudyPage onToast={setToast} />
      ) : (
        <main className="layout">
          <Chat messages={messages} busy={busy} disabled={!aiReady || !!healthError} onSend={send} actions={cardActions} />
          <CartPanel bill={bill} busy={busy} hasSession={hasSession} onSetQty={setQty} onCheckout={checkout}
            onSetBudget={setBudget} onFetchPlan={fetchPlan} onApplyPlan={applyPlan} onCompareStores={compareStores} />
        </main>
      )}

      {toast && <div className="toast" role="status">{toast}</div>}
      {receipt && <Receipt order={receipt} onClose={() => setReceipt(null)} />}
    </div>
  )
}
