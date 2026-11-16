import { History, Info, LogOut, PackageX, RefreshCw, Search, ShieldCheck, Store, TicketPercent, TrendingUp } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import type { AdminCoupon, AdminOrder, AdminProduct, AdminSummary, AuditEntry, StaffSession } from '../api'
import { adminToken, api, ApiError, pct, rupees } from '../api'
type Filter = 'all' | 'out' | 'low'
type Draft = { price: string; stock: string }

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: 'bad' | 'warn' | 'good' }) {
  return (
    <div className={`stat ${tone ? `tone-${tone}` : ''}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function ProductRow({ p, canEditPrice, onSaved, onError }: {
  p: AdminProduct; canEditPrice: boolean; onSaved: (p: AdminProduct) => void; onError: (msg: string) => void
}) {
  // The row is keyed by its saved values, so it remounts (resetting the draft) when they change.
  const [draft, setDraft] = useState<Draft>({ price: p.price, stock: String(p.stock_qty) })
  const [saving, setSaving] = useState(false)

  const priceChanged = draft.price !== p.price && draft.price.trim() !== ''
  const stockChanged = draft.stock !== String(p.stock_qty) && draft.stock.trim() !== ''
  const save = async () => {
    setSaving(true)
    try {
      const change: { price?: string; stock_qty?: number } = {}
      if (priceChanged) change.price = draft.price
      if (stockChanged) change.stock_qty = parseInt(draft.stock, 10)
      onSaved(await api.admin.updateProduct(p.product_id, change))
    } catch (e) {
      onError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr className={p.stock_qty === 0 ? 'row-out' : p.stock_qty < 10 ? 'row-low' : ''}>
      <td>
        <div className="a-name" title={p.name}>{p.name}</div>
        <div className="a-sub">{p.brand} · {p.product_type}</div>
      </td>
      <td><span className="aisle-chip sm">A{p.aisle_no}</span> <span className="a-sub">{p.shelf_code}</span></td>
      <td className="num a-sub">{rupees(p.mrp)}</td>
      <td className="num">
        <input className="cell-input" type="number" step="0.01" min="0.01" value={draft.price}
          disabled={!canEditPrice} title={canEditPrice ? undefined : 'Only a manager can change prices'}
          onChange={(e) => setDraft({ ...draft, price: e.target.value })} aria-label={`Price of ${p.name}`} />
      </td>
      <td className="num">
        <input className="cell-input narrow" type="number" step="1" min="0" value={draft.stock}
          onChange={(e) => setDraft({ ...draft, stock: e.target.value })} aria-label={`Stock of ${p.name}`} />
      </td>
      <td className="num a-sub">{pct(p.gst_rate)}</td>
      <td>
        <button className="mini primary" onClick={save} disabled={saving || (!priceChanged && !stockChanged)}>
          {saving ? '…' : 'Save'}
        </button>
      </td>
    </tr>
  )
}

function Login({ onLogin }: { onLogin: (u: StaffSession) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: { preventDefault: () => void }) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { token, ...user } = await api.admin.login(username, password)
      adminToken.set(token)
      onLogin(user)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin">
      <form className="panel login" onSubmit={submit}>
        <h2><ShieldCheck size={20} aria-hidden /> Store staff login</h2>
        <p className="a-sub">Managers can change prices, stock and coupons. Staff can update stock only.</p>
        <label>Username<input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password" required /></label>
        {error && <div className="login-error" role="alert">{error}</div>}
        <button className="card-btn add" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <p className="a-sub">Demo accounts: <code>manager</code> / <code>manager123</code> · <code>staff</code> / <code>staff123</code></p>
      </form>
    </div>
  )
}

const AUDIT_TEXT: Record<AuditEntry['action'], (e: AuditEntry) => string> = {
  price: (e) => `price of ${e.detail.name}: ₹${e.detail.from} → ₹${e.detail.to}`,
  stock: (e) => `stock of ${e.detail.name}: ${e.detail.from} → ${e.detail.to}`,
  coupon: (e) => `coupon ${e.target} ${e.detail.to}`,
}

/** Admin page: login first (store staff only), then the console for the signed-in role. */
export function Admin({ onToast }: { onToast: (msg: string) => void }) {
  const [user, setUser] = useState<StaffSession | null>(null)
  const [checked, setChecked] = useState(() => !adminToken.get())

  useEffect(() => {
    if (!adminToken.get()) return
    api.admin.me().then(setUser).catch(() => adminToken.set(null)).finally(() => setChecked(true))
  }, [])

  const logout = useCallback(() => { adminToken.set(null); setUser(null) }, [])

  if (!checked) return null
  if (!user) return <Login onLogin={setUser} />
  return <AdminConsole user={user} onLogout={logout} onToast={onToast} />
}

function AdminConsole({ user, onLogout, onToast }: {
  user: StaffSession; onLogout: () => void; onToast: (msg: string) => void
}) {
  const [summary, setSummary] = useState<AdminSummary | null>(null)
  const [items, setItems] = useState<AdminProduct[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [coupons, setCoupons] = useState<AdminCoupon[]>([])
  const [orders, setOrders] = useState<AdminOrder[]>([])
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const isManager = user.role === 'manager'

  const onApiError = useCallback((e: Error) => {
    if (e instanceof ApiError && e.status === 401) onLogout()    // token expired / server restarted
    else onToast(e.message)
  }, [onLogout, onToast])

  const loadStats = useCallback(() => {
    api.admin.summary().then(setSummary).catch(onApiError)
    api.admin.orders().then(setOrders).catch(() => {})
    api.admin.audit().then(setAudit).catch(() => {})
  }, [onApiError])

  const loadInventory = useCallback(() => {
    api.admin.inventory(q, filter).then((r) => { setItems(r.items); setTotal(r.total) })
      .catch(onApiError)
  }, [q, filter, onApiError])

  useEffect(() => {
    const t = setTimeout(loadInventory, 250)     // debounce typing
    return () => clearTimeout(t)
  }, [loadInventory])

  useEffect(() => {
    loadStats()
    api.admin.coupons().then(setCoupons).catch(() => {})
    const t = setInterval(loadStats, 8000)
    return () => clearInterval(t)
  }, [loadStats])

  const saved = (p: AdminProduct) => {
    setItems((list) => list.map((x) => (x.product_id === p.product_id ? p : x)))
    loadStats()
    onToast(`Saved ${p.name}: ${rupees(p.price)}, ${p.stock_qty} in stock. Open carts update automatically.`)
  }

  const toggleCoupon = async (c: AdminCoupon) => {
    try {
      const updated = await api.admin.setCoupon(c.code, !c.is_active)
      setCoupons((list) => list.map((x) => (x.code === c.code ? updated : x)))
      loadStats()
    } catch (e) {
      onApiError(e as Error)
    }
  }

  return (
    <div className="admin">
      <div className="admin-banner">
        <Info size={16} aria-hidden />
        <span>
          Changes here apply <strong>instantly</strong>: carts store no prices, so every shopper's bill is
          recomputed from these values. The AI can read prices but has no tool to change them.
        </span>
        <span className="whoami">
          <ShieldCheck size={15} aria-hidden /> {user.full_name} · <strong>{user.role}</strong>
          <button className="mini" onClick={onLogout}><LogOut size={13} aria-hidden /> Log out</button>
        </span>
      </div>
      {!isManager && (
        <div className="admin-banner role-note">
          Signed in as <strong>staff</strong>: you can update stock. Prices and coupons need a manager.
        </div>
      )}

      {summary && (
        <div className="stats">
          <Stat label="Products" value={summary.products} />
          <Stat label="Out of stock" value={summary.out_of_stock} tone={summary.out_of_stock ? 'bad' : undefined} />
          <Stat label="Low stock (1–9)" value={summary.low_stock} tone="warn" />
          <Stat label="Live coupons" value={summary.live_coupons} />
          <Stat label="Orders" value={summary.orders} />
          <Stat label="Revenue" value={rupees(summary.revenue)} tone="good" />
        </div>
      )}

      <div className="admin-grid">
        <section className="panel">
          <div className="panel-head">
            <h2><Store size={17} aria-hidden /> Inventory &amp; live prices</h2>
            <span className="a-sub">{total} products</span>
          </div>
          <div className="toolbar">
            <label className="search">
              <Search size={15} aria-hidden />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, brand or type…"
                aria-label="Search products" />
            </label>
            <div className="chips" role="group" aria-label="Filter">
              {(['all', 'out', 'low'] as Filter[]).map((f) => (
                <button key={f} className={`chip ${filter === f ? 'on' : ''}`} onClick={() => setFilter(f)}>
                  {f === 'all' ? 'All' : f === 'out' ? 'Out of stock' : 'Low stock'}
                </button>
              ))}
            </div>
            <button className="mini" onClick={loadInventory} aria-label="Refresh"><RefreshCw size={14} /></button>
          </div>
          <div className="table-wrap">
            <table className="atable">
              <thead>
                <tr><th>Product</th><th>Location</th><th className="num">MRP</th><th className="num">Price ₹</th>
                  <th className="num">Stock</th><th className="num">GST</th><th /></tr>
              </thead>
              <tbody>
                {items.map((p) => (
                  <ProductRow key={`${p.product_id}:${p.price}:${p.stock_qty}`} p={p} canEditPrice={isManager}
                    onSaved={saved} onError={(m) => onApiError(new Error(m))} />
                ))}
                {items.length === 0 && (
                  <tr><td colSpan={7} className="a-empty"><PackageX size={18} aria-hidden /> No products match.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          {total > items.length && <div className="a-sub more">Showing {items.length} of {total}. Search to narrow down.</div>}
        </section>

        <div className="admin-side">
          <section className="panel">
            <div className="panel-head"><h2><TrendingUp size={17} aria-hidden /> Recent orders</h2></div>
            {orders.length === 0 ? <p className="a-sub pad">No orders yet.</p> : (
              <ul className="order-list">
                {orders.map((o) => (
                  <li key={o.order_id}>
                    <div><strong>#{o.order_id}</strong> <span className="a-sub">{new Date(o.placed_at).toLocaleTimeString()} · {o.items} items</span></div>
                    <div className="order-amt">
                      {rupees(o.final_total)}
                      {o.applied_coupons.length > 0 && <span className="a-sub"> · {o.applied_coupons.join(', ')}</span>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel">
            <div className="panel-head"><h2><History size={17} aria-hidden /> Recent changes</h2></div>
            {audit.length === 0 ? <p className="a-sub pad">No changes yet.</p> : (
              <ul className="order-list audit-list">
                {audit.map((e) => (
                  <li key={e.audit_id}>
                    <div><strong>{e.username}</strong> <span className="a-sub">({e.role}) · {new Date(e.at).toLocaleTimeString()}</span></div>
                    <div className="a-sub">{AUDIT_TEXT[e.action](e)}</div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2><TicketPercent size={17} aria-hidden /> Coupons</h2>
              <span className="a-sub">{coupons.length} rules</span>
            </div>
            <ul className="coupon-list">
              {coupons.map((c) => (
                <li key={c.code}>
                  <div className="coupon-main">
                    <span className={`code ${c.status === 'live' ? '' : 'dim'}`}>{c.code}</span>
                    <span className="coupon-desc">{c.description}</span>
                    {c.conflicts_with.length > 0 && (
                      <span className="a-sub">Not with: {c.conflicts_with.join(', ')}</span>
                    )}
                  </div>
                  <div className="coupon-ctl">
                    <span className={`status-tag ${c.status.replace(' ', '-')}`}>{c.status}</span>
                    <button role="switch" aria-checked={c.is_active} aria-label={`Enable ${c.code}`}
                      disabled={!isManager} title={isManager ? undefined : 'Only a manager can switch coupons'}
                      className={`switch ${c.is_active ? 'on' : ''}`} onClick={() => toggleCoupon(c)}>
                      <span />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </div>
  )
}
