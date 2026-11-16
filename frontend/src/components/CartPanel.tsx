import { AlertTriangle, ArrowRight, ChevronDown, MapPin, Minus, Plus, Receipt as ReceiptIcon, ShoppingCart,
  Store, Tag, Trash2, Wallet, Wand2, X } from 'lucide-react'
import { useState } from 'react'
import type { Bill, BillItem, BudgetPlan, StoreComparison } from '../api'
import { pct, rupees } from '../api'

interface CartPanelProps {
  bill: Bill | null
  busy: boolean
  hasSession: boolean
  onSetQty: (productId: number, qty: number) => void
  onCheckout: () => void
  onSetBudget: (amount: string | null) => void
  onFetchPlan: () => Promise<BudgetPlan | null>
  onApplyPlan: (plan: BudgetPlan) => void
  onCompareStores: () => Promise<StoreComparison | null>
}

function Item({ it, busy, onSetQty }: { it: BillItem; busy: boolean; onSetQty: CartPanelProps['onSetQty'] }) {
  return (
    <li className="item">
      <div className="aisle-chip" title={it.aisle_name ?? ''}>A{it.aisle_no}</div>
      <div className="item-main">
        <div className="item-name" title={it.name}>{it.name}</div>
        <div className="item-sub">
          {it.brand} · <MapPin size={11} aria-hidden /> Aisle {it.aisle_no}, shelf {it.shelf_code}
        </div>
        <div className="item-row">
          <div className="stepper" role="group" aria-label={`Quantity of ${it.name}`}>
            <button onClick={() => onSetQty(it.product_id, it.qty - 1)} disabled={busy} aria-label="Decrease">
              {it.qty === 1 ? <Trash2 size={13} /> : <Minus size={13} />}
            </button>
            <span>{it.qty}</span>
            <button onClick={() => onSetQty(it.product_id, it.qty + 1)} disabled={busy} aria-label="Increase">
              <Plus size={13} />
            </button>
          </div>
          <span className="item-unit">× {rupees(it.unit_price)}</span>
          <span className="item-total">{rupees(it.line_total)}</span>
        </div>
      </div>
    </li>
  )
}

/** Aisles that hold cart items, in walking order (aisle 1 is at the entrance). */
function Route({ items }: { items: BillItem[] }) {
  const stops = new Map<number, { name: string; count: number }>()
  for (const it of items) {
    if (it.aisle_no == null) continue
    const s = stops.get(it.aisle_no) ?? { name: it.aisle_name ?? '', count: 0 }
    s.count += it.qty
    stops.set(it.aisle_no, s)
  }
  const ordered = [...stops.entries()].sort((a, b) => a[0] - b[0])
  if (!ordered.length) return null
  return (
    <div className="route">
      <div className="section-title"><MapPin size={14} aria-hidden /> Pick route</div>
      <ol className="route-steps">
        {ordered.map(([no, s]) => (
          <li key={no}>
            <span className="route-no">{no}</span>
            <span className="route-name">{s.name}</span>
            <span className="route-count">{s.count}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

function Gst({ bill }: { bill: Bill }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="gst">
      <button className="row gst-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span><ReceiptIcon size={13} aria-hidden /> GST included in prices</span>
        <span>{rupees(bill.gst_included)} <ChevronDown size={13} className={open ? 'rot' : ''} aria-hidden /></span>
      </button>
      {open && (
        <table className="gst-table">
          <thead><tr><th>Rate</th><th>Taxable</th><th>CGST</th><th>SGST</th></tr></thead>
          <tbody>
            {bill.gst_breakup.map((s) => (
              <tr key={s.rate}>
                <td>{pct(s.rate)}</td><td>{rupees(s.taxable_value)}</td><td>{rupees(s.cgst)}</td><td>{rupees(s.sgst)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function Budget({ bill, busy, hasSession, onSetBudget, onFetchPlan, onApplyPlan }: {
  bill: Bill; busy: boolean; hasSession: boolean
} & Pick<CartPanelProps, 'onSetBudget' | 'onFetchPlan' | 'onApplyPlan'>) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(bill.budget ?? '')
  const [stored, setStored] = useState<{ plan: BudgetPlan; total: string; budget?: string } | null>(null)
  const [loading, setLoading] = useState(false)
  // A plan is only valid for the cart and budget it was made for.
  const plan = stored && stored.total === bill.final_total && stored.budget === bill.budget ? stored.plan : null
  const setPlan = (p: BudgetPlan | null) => setStored(p && { plan: p, total: bill.final_total, budget: bill.budget })

  const save = () => {
    const v = draft.trim()
    onSetBudget(v === '' ? null : v)
    setEditing(false)
  }

  if (editing || !bill.budget) {
    return (
      <div className="budget">
        {editing ? (
          <form className="budget-form" onSubmit={(e) => { e.preventDefault(); save() }}>
            <span>Budget ₹</span>
            <input type="number" min="1" step="1" value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus
              aria-label="Budget in rupees" />
            <button type="submit" className="mini primary" disabled={busy}>Save</button>
            <button type="button" className="mini" onClick={() => setEditing(false)} aria-label="Cancel"><X size={13} /></button>
          </form>
        ) : (
          <button className="link-btn" onClick={() => { setDraft(''); setEditing(true) }} disabled={!hasSession || busy}>
            <Wallet size={14} aria-hidden /> Set a budget
          </button>
        )}
      </div>
    )
  }

  const over = bill.over_budget_by !== undefined
  // Bar width only — display values are the server's exact strings.
  const fill = Math.min(100, (parseFloat(bill.final_total) / parseFloat(bill.budget)) * 100)

  const fit = async () => {
    setLoading(true)
    setPlan(await onFetchPlan())
    setLoading(false)
  }

  return (
    <div className={`budget ${over ? 'over' : ''}`}>
      <div className="budget-head">
        <button className="link-btn" onClick={() => { setDraft(bill.budget ?? ''); setEditing(true) }}>
          Budget {rupees(bill.budget)}
        </button>
        <strong>{over ? `Over by ${rupees(bill.over_budget_by!)}` : `${rupees(bill.budget_remaining!)} left`}</strong>
      </div>
      <div className="bar" role="progressbar" aria-valuenow={Math.round(fill)} aria-valuemin={0} aria-valuemax={100}>
        <div style={{ width: `${fill}%` }} />
      </div>
      {over && !plan && (
        <button className="fit-btn" onClick={fit} disabled={busy || loading}>
          <Wand2 size={14} aria-hidden /> {loading ? 'Finding swaps…' : 'Fit my budget'}
        </button>
      )}
      {plan && (
        <div className="plan">
          {plan.feasible ? (
            <>
              <div className="plan-head">
                {plan.swaps.length} swap{plan.swaps.length > 1 ? 's' : ''} → pay <strong>{rupees(plan.new_total)}</strong>
                {' '}(save {rupees(plan.total_saving)})
              </div>
              <ul className="plan-swaps">
                {plan.swaps.map((s) => (
                  <li key={s.from_product_id}>
                    <span className="from">{s.from_name}</span>
                    <ArrowRight size={13} aria-hidden />
                    <span className="to">{s.to_name} <em>({s.to_brand}, {rupees(s.to_unit_price)}, {s.shelf_code})</em></span>
                  </li>
                ))}
              </ul>
              <div className="plan-actions">
                <button className="mini primary" onClick={() => onApplyPlan(plan)} disabled={busy}>Apply swaps</button>
                <button className="mini" onClick={() => setPlan(null)}>Dismiss</button>
              </div>
              <div className="plan-note">Fewest changes that fit, coupons re-optimized · {plan.plans_evaluated} plans checked</div>
            </>
          ) : (
            <>
              <div className="plan-head">{plan.message}</div>
              <div className="plan-actions"><button className="mini" onClick={() => setPlan(null)}>OK</button></div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

const MISSING: Record<string, string> = {
  not_carried: 'not sold', out_of_stock: 'out of stock', not_enough_stock: 'not enough stock',
}

/** Multi-store comparison: this cart priced at the other stores (all numbers from the server). */
function CompareStores({ bill, onCompare }: { bill: Bill; onCompare: CartPanelProps['onCompareStores'] }) {
  const [stored, setStored] = useState<{ cmp: StoreComparison; total: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const cmp = stored && stored.total === bill.final_total ? stored.cmp : null   // stale after a cart change

  const load = async () => {
    setLoading(true)
    const r = await onCompare()
    setLoading(false)
    if (r) setStored({ cmp: r, total: bill.final_total })
  }

  if (!cmp) {
    return (
      <button className="fit-btn compare-btn" onClick={load} disabled={loading}>
        <Store size={15} aria-hidden /> {loading ? 'Comparing stores…' : 'Compare with other stores'}
      </button>
    )
  }
  return (
    <div className="compare">
      <h3><Store size={15} aria-hidden /> Same cart at other stores
        <button className="link-x" onClick={() => setStored(null)} aria-label="Close comparison"><X size={14} /></button></h3>
      <p className="compare-msg">{cmp.message}
        {cmp.saving_vs_home !== '0.00' && <> Save {rupees(cmp.saving_vs_home)}.</>}</p>
      {cmp.quotes.map((q) => (
        <div key={q.store_id} className={`store-q ${q.store_id === cmp.best_store_id ? 'best' : ''}`}>
          <div>
            <strong>{q.name}</strong>{q.is_home && <span className="a-sub"> · you are here</span>}
            <div className="a-sub">
              {q.items_available}/{q.items_total} items
              {q.coupons.length > 0 ? ` · ${q.coupons.join(', ')} −${rupees(q.discount)}` : !q.accepts_coupons ? ' · no SmartMart coupons' : ''}
            </div>
            {q.missing.map((m) => (
              <div key={m.product_id} className="store-missing">{m.name}: {MISSING[m.reason] ?? m.reason}</div>
            ))}
          </div>
          <div className="store-total">{rupees(q.final_total)}{!q.complete && <div className="a-sub">partial</div>}</div>
        </div>
      ))}
    </div>
  )
}

export function CartPanel(props: CartPanelProps) {
  const { bill, busy, onSetQty, onCheckout } = props
  const empty = !bill || bill.items.length === 0
  return (
    <aside className="cart" aria-label="Cart and running bill">
      <div className="cart-head">
        <h2><ShoppingCart size={18} aria-hidden /> Your cart</h2>
        <span className="pill">{bill?.item_count ?? 0} item{bill?.item_count === 1 ? '' : 's'}</span>
      </div>

      {empty ? (
        <div className="cart-empty">
          <ShoppingCart size={34} aria-hidden />
          <p>Your cart is empty.</p>
          <span>Ask the assistant to add items. Prices, stock and aisles appear here live.</span>
        </div>
      ) : (
        <div className="cart-scroll">
          <ul className="items">
            {bill.items.map((it) => <Item key={it.product_id} it={it} busy={busy} onSetQty={onSetQty} />)}
          </ul>

          {bill.warnings.length > 0 && (
            <div className="warn">
              {bill.warnings.map((w) => <div key={w}><AlertTriangle size={13} aria-hidden /> {w}</div>)}
            </div>
          )}

          <Budget {...props} bill={bill} />
          <Route items={bill.items} />

          <CompareStores bill={bill} onCompare={props.onCompareStores} />

          <div className="bill">
            <div className="section-title"><Tag size={14} aria-hidden /> Bill</div>
            <div className="row"><span>Subtotal</span><span>{rupees(bill.subtotal)}</span></div>
            <div className="row muted"><span>MRP total</span><span className="strike">{rupees(bill.mrp_total)}</span></div>
            {bill.coupons_applied.map((c) => (
              <div className="row save" key={c.code}>
                <span><span className="code">{c.code}</span> {c.description}</span>
                <span>−{rupees(c.discount)}</span>
              </div>
            ))}
            {bill.coupons_skipped_due_to_conflict.map((c) => (
              <div className="row skipped" key={c.code}>
                <span><span className="code dim">{c.code}</span> skipped: {c.why}</span>
              </div>
            ))}
            <Gst bill={bill} />
          </div>

          {bill.almost_unlocked.length > 0 && (
            <div className="unlock">
              <div className="section-title">Almost unlocked</div>
              {bill.almost_unlocked.map((u) => (
                <div key={u.code} className="unlock-row">
                  <span className="code">{u.code}</span> add {rupees(u.add_amount)} more
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="cart-foot">
        {!empty && (
          <>
            <div className="row total"><span>To pay</span><span>{rupees(bill.final_total)}</span></div>
            <div className="saved">You save {rupees(bill.savings_vs_mrp)} on MRP
              {bill.discount_total !== '0.00' && <> + {rupees(bill.discount_total)} with coupons</>}
              <span className="incl"> · incl. {rupees(bill.gst_included)} GST</span>
            </div>
          </>
        )}
        <button className="checkout" onClick={onCheckout} disabled={empty || busy}>
          Checkout
        </button>
        <p className="fine">All amounts come from the store database. The AI never sets a price.</p>
      </div>
    </aside>
  )
}
