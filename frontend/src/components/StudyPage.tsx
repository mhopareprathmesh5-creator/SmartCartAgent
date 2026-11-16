import { CheckCircle2, ClipboardList, Minus, Plus, Search, SendHorizontal, Timer, Users, XCircle } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { RawBill, SearchHit, StudyResult, StudyRun, StudySummary, StudyTask } from '../api'
import { api, rupees } from '../api'

type Line = { product_id: number; name: string; quantity: number; line_total: string }

/** Manual condition: the classic way — search, read the aisle, press Add. No AI. */
function ManualShop({ cartId, onError }: { cartId: number; onError: (m: string) => void }) {
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])
  const [bill, setBill] = useState<RawBill | null>(null)

  const refresh = useCallback(() => { api.cartBill(cartId).then(setBill).catch((e: Error) => onError(e.message)) }, [cartId, onError])
  useEffect(refresh, [refresh])

  const search = async (e: { preventDefault: () => void }) => {
    e.preventDefault()
    if (q.trim()) setHits(await api.search(q.trim()).catch(() => []))
  }
  const qty = (pid: number) => bill?.lines.find((l) => l.product_id === pid)?.quantity ?? 0
  const set = async (pid: number, n: number) => {
    const r = await api.cartSet(cartId, pid, n).catch((e: Error) => { onError(e.message); return null })
    if (r && !r.ok) onError(r.message)
    refresh()
  }

  return (
    <div className="study-work">
      <div className="study-col">
        <form className="study-search" onSubmit={search}>
          <Search size={15} aria-hidden />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search products…" aria-label="Search products" />
          <button className="mini primary" type="submit">Search</button>
        </form>
        <ul className="study-hits">
          {hits.map((h) => (
            <li key={h.product_id}>
              <div>
                <div className="a-name">{h.name}</div>
                <div className="a-sub">{h.brand} · Aisle {h.aisle_no}, {h.shelf_code} · {h.in_stock ? `${h.stock_qty} in stock` : 'out of stock'}</div>
              </div>
              <div className="study-hit-right">
                <strong>{rupees(h.price)}</strong>
                <button className="mini primary" disabled={!h.in_stock} onClick={() => set(h.product_id, qty(h.product_id) + 1)}>Add</button>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <MiniCart lines={bill?.lines ?? []} total={bill?.final_total} onSet={set} />
    </div>
  )
}

function MiniCart({ lines, total, onSet }: { lines: Line[]; total?: string; onSet?: (pid: number, n: number) => void }) {
  return (
    <div className="study-col study-cart">
      <div className="section-title">Cart</div>
      {lines.length === 0 ? <p className="a-sub">Empty</p> : (
        <ul>
          {lines.map((l) => (
            <li key={l.product_id}>
              <span>{l.name}</span>
              <span className="study-qty">
                {onSet && <button className="mini" onClick={() => onSet(l.product_id, l.quantity - 1)} aria-label="Less"><Minus size={12} /></button>}
                × {l.quantity}
                {onSet && <button className="mini" onClick={() => onSet(l.product_id, l.quantity + 1)} aria-label="More"><Plus size={12} /></button>}
              </span>
              <span>{rupees(l.line_total)}</span>
            </li>
          ))}
        </ul>
      )}
      {total && <div className="row total"><span>To pay</span><span>{rupees(total)}</span></div>}
    </div>
  )
}

/** Assistant condition: the same agent as the Shop page, in a compact chat. */
function AssistantShop({ sessionId, onSent, onError }: { sessionId: string; onSent: () => void; onError: (m: string) => void }) {
  const [draft, setDraft] = useState('')
  const [log, setLog] = useState<{ who: 'you' | 'bot'; text: string }[]>([])
  const [lines, setLines] = useState<Line[]>([])
  const [total, setTotal] = useState<string>()
  const [busy, setBusy] = useState(false)

  const send = async (e: { preventDefault: () => void }) => {
    e.preventDefault()
    const t = draft.trim()
    if (!t || busy) return
    setDraft('')
    setLog((l) => [...l, { who: 'you', text: t }])
    setBusy(true)
    onSent()
    try {
      const r = await api.chat(sessionId, t)
      setLog((l) => [...l, { who: 'bot', text: r.reply }])
      setLines(r.bill.items.map((i) => ({ product_id: i.product_id, name: i.name, quantity: i.qty, line_total: i.line_total })))
      setTotal(r.bill.final_total)
    } catch (err) {
      onError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="study-work">
      <div className="study-col">
        <div className="study-chat">
          {log.map((m, i) => (
            <div key={i} className={`msg ${m.who === 'you' ? 'msg-user' : 'msg-bot'}`}>
              {m.who === 'bot' ? <div className="md"><ReactMarkdown>{m.text}</ReactMarkdown></div> : m.text}
            </div>
          ))}
          {busy && <div className="msg msg-bot typing">Working…</div>}
        </div>
        <form className="composer" onSubmit={send}>
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Type the shopping list…" aria-label="Message" />
          <button className="send" type="submit" disabled={!draft.trim() || busy} aria-label="Send"><SendHorizontal size={18} /></button>
        </form>
      </div>
      <MiniCart lines={lines} total={total} />
    </div>
  )
}

/** User study: assistant vs manual shopping, timed and scored by the server. */
export function StudyPage({ onToast }: { onToast: (m: string) => void }) {
  const [tasks, setTasks] = useState<StudyTask[]>([])
  const [participant, setParticipant] = useState('')
  const [taskId, setTaskId] = useState('A')
  const [mode, setMode] = useState<'assistant' | 'manual'>('assistant')
  const [run, setRun] = useState<StudyRun | null>(null)
  const [startedAt, setStartedAt] = useState(0)
  const [now, setNow] = useState(0)
  const [messages, setMessages] = useState(0)
  const [result, setResult] = useState<StudyResult | null>(null)
  const [summary, setSummary] = useState<StudySummary | null>(null)

  useEffect(() => {
    api.study.tasks().then(setTasks).catch(() => {})
    api.study.summary().then(setSummary).catch(() => {})
  }, [])
  useEffect(() => {
    if (!run) return
    const t = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(t)
  }, [run])

  const start = async () => {
    try {
      const r = await api.study.start(participant, mode, taskId)
      setResult(null)
      setMessages(0)
      setStartedAt(Date.now())
      setNow(Date.now())
      setRun(r)
    } catch (e) {
      onToast((e as Error).message)
    }
  }
  const finish = async () => {
    if (!run) return
    try {
      setResult(await api.study.finish(run.run_id, run.mode === 'assistant' ? messages : undefined))
      setRun(null)
      api.study.summary().then(setSummary).catch(() => {})
    } catch (e) {
      onToast((e as Error).message)
    }
  }

  const m = summary?.modes
  return (
    <div className="admin study">
      {!run && (
        <section className="panel pad-panel">
          <h2 className="study-h"><ClipboardList size={18} aria-hidden /> User study: assistant vs. manual shopping</h2>
          <p className="a-sub">Each participant does task A with one method and task B with the other (swap the order for
            every second participant). The clock runs from Start to Finish; the cart is scored automatically.</p>
          <div className="study-form">
            <label>Participant code<input value={participant} onChange={(e) => setParticipant(e.target.value)} placeholder="P01" /></label>
            <label>Task
              <select value={taskId} onChange={(e) => setTaskId(e.target.value)}>
                {tasks.map((t) => <option key={t.task_id} value={t.task_id}>{t.task_id} · {t.title}</option>)}
              </select>
            </label>
            <div className="chips" role="group" aria-label="Method">
              <button className={`chip ${mode === 'assistant' ? 'on' : ''}`} onClick={() => setMode('assistant')}>With assistant</button>
              <button className={`chip ${mode === 'manual' ? 'on' : ''}`} onClick={() => setMode('manual')}>Manual (search)</button>
            </div>
            <button className="card-btn add" onClick={start} disabled={!participant.trim()}>Start task</button>
          </div>
          {result && (
            <div className={`study-result ${result.success ? 'ok' : 'bad'}`}>
              {result.success ? <CheckCircle2 size={18} aria-hidden /> : <XCircle size={18} aria-hidden />}
              <strong>{result.success ? 'Task completed correctly' : 'Task not completed'}</strong> in {result.seconds} s ·
              total {rupees(result.final_total)}
              <ul>{result.checks.map((c) => <li key={c.check}>{c.passed ? '✓' : '✗'} {c.check} ({c.detail})</li>)}</ul>
            </div>
          )}
        </section>
      )}

      {run && (
        <section className="panel pad-panel">
          <div className="study-bar">
            <span className="study-timer"><Timer size={16} aria-hidden /> {Math.floor((now - startedAt) / 1000)} s</span>
            <span><strong>Task {run.task_id}</strong> ({run.mode}): {run.instructions}</span>
            <button className="card-btn add" onClick={finish}>Finish</button>
          </div>
          {run.mode === 'manual'
            ? <ManualShop cartId={run.cart_id} onError={onToast} />
            : <AssistantShop sessionId={run.session_id} onSent={() => setMessages((n) => n + 1)} onError={onToast} />}
        </section>
      )}

      <section className="panel pad-panel">
        <h2 className="study-h"><Users size={18} aria-hidden /> Results so far</h2>
        {!summary || summary.runs === 0 ? <p className="a-sub">No completed runs yet.</p> : (
          <>
            <table className="atable">
              <thead><tr><th>Method</th><th className="num">Runs</th><th className="num">Correct</th>
                <th className="num">Mean time</th><th className="num">Median time</th></tr></thead>
              <tbody>
                {(['assistant', 'manual'] as const).map((k) => (
                  <tr key={k}><td>{k}</td><td className="num">{m?.[k].runs}</td>
                    <td className="num">{m?.[k].success_pct ?? '–'}{m?.[k].success_pct != null && '%'}</td>
                    <td className="num">{m?.[k].mean_seconds ?? '–'} s</td><td className="num">{m?.[k].median_seconds ?? '–'} s</td></tr>
                ))}
              </tbody>
            </table>
            {summary.paired_participants > 0 && (
              <p className="study-paired">{summary.paired_participants} participant(s) did both: on average
                {' '}<strong>{summary.mean_seconds_saved} s ({summary.mean_time_saved_pct}%)</strong> saved with the assistant.</p>
            )}
          </>
        )}
      </section>
    </div>
  )
}
