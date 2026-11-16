import { ArrowLeftRight, Check, MapPin, Plus } from 'lucide-react'
import type { Card, SuggestionGroup } from '../api'
import { rupees } from '../api'

export interface CardActions {
  cartQty: Record<number, number>
  busy: boolean
  onAdd: (productId: number) => void
  onSwap: (fromProductId: number, toProductId: number, quantity: number) => void
}

/** For a substitutes group: the product of this group currently in the cart (the original or an alternative). */
function occupant(group: SuggestionGroup, cartQty: Record<number, number>): number | null {
  if (group.kind !== 'substitutes') return null
  const ids = [group.for_product_id!, ...group.items.map((c) => c.product_id)]
  return ids.find((id) => (cartQty[id] ?? 0) > 0) ?? null
}

function Diff({ d }: { d?: string }) {
  if (d === undefined) return null
  const n = parseFloat(d)
  if (n === 0) return <span className="diff">same price</span>
  return <span className={`diff ${n < 0 ? 'cheaper' : 'dearer'}`}>{n < 0 ? `−₹${d.replace('-', '')}` : `+₹${d}`}</span>
}

function ProductCard({ c, group, a }: { c: Card; group: SuggestionGroup; a: CardActions }) {
  const inCart = a.cartQty[c.product_id] ?? 0
  const occ = occupant(group, a.cartQty)
  let action
  if (inCart > 0) {
    action = <button className="card-btn done" disabled><Check size={13} aria-hidden /> In cart · {inCart}</button>
  } else if (!c.in_stock) {
    action = <button className="card-btn" disabled>Out of stock</button>
  } else if (occ !== null) {
    action = (
      <button className="card-btn swap" disabled={a.busy} onClick={() => a.onSwap(occ, c.product_id, a.cartQty[occ])}>
        <ArrowLeftRight size={13} aria-hidden /> Swap in
      </button>
    )
  } else {
    action = (
      <button className="card-btn add" disabled={a.busy} onClick={() => a.onAdd(c.product_id)}>
        <Plus size={13} aria-hidden /> Add
      </button>
    )
  }
  return (
    <div className="pcard">
      <div className="pcard-name" title={c.name}>{c.name}</div>
      <div className="pcard-brand">{c.brand}</div>
      <div className="pcard-price">
        <strong>{rupees(c.price)}</strong>
        {c.mrp && c.mrp !== c.price && <span className="strike">{rupees(c.mrp)}</span>}
        <Diff d={c.price_difference} />
      </div>
      <div className="pcard-loc"><MapPin size={11} aria-hidden /> Aisle {c.aisle_no} · {c.shelf_code}</div>
      {action}
    </div>
  )
}

export function SuggestionGroups({ groups, actions }: { groups: SuggestionGroup[]; actions: CardActions }) {
  if (!groups.length) return null
  return (
    <div className="suggestions">
      {groups.map((g) => (
        <div key={g.title} className="sgroup">
          <div className="sgroup-title">{g.title}</div>
          <div className="pcards">
            {g.items.map((c) => <ProductCard key={c.product_id} c={c} group={g} a={actions} />)}
          </div>
        </div>
      ))}
    </div>
  )
}
