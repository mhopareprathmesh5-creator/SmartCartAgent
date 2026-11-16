import { CheckCircle2, X } from 'lucide-react'
import { useEffect } from 'react'
import type { Order } from '../api'
import { pct, rupees } from '../api'

export function Receipt({ order, onClose }: { order: Order; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="overlay" onClick={onClose}>
      <div className="receipt" role="dialog" aria-modal="true" aria-label="Order receipt" onClick={(e) => e.stopPropagation()}>
        <button className="close" onClick={onClose} aria-label="Close"><X size={18} /></button>
        <CheckCircle2 size={38} className="receipt-ok" aria-hidden />
        <h2>Order #{order.order_id} placed</h2>
        <p className="receipt-time">{new Date(order.placed_at).toLocaleString()}</p>
        <table>
          <tbody>
            {order.lines.map((l) => (
              <tr key={l.product_id}>
                <td>{l.quantity} × {l.name}</td>
                <td>{rupees(l.line_total)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr><td>Subtotal</td><td>{rupees(order.subtotal)}</td></tr>
            {order.discount_total !== '0.00' && (
              <tr className="save"><td>Coupons ({order.applied_coupons.join(', ')})</td><td>−{rupees(order.discount_total)}</td></tr>
            )}
            <tr className="grand"><td>Paid</td><td>{rupees(order.final_total)}</td></tr>
          </tfoot>
        </table>
        {order.tax_breakup.length > 0 && (
          <table className="receipt-gst">
            <thead><tr><th>GST</th><th>Taxable</th><th>CGST</th><th>SGST</th></tr></thead>
            <tbody>
              {order.tax_breakup.map((t) => (
                <tr key={t.rate}>
                  <td>{pct(t.rate)}</td><td>{rupees(t.taxable_value)}</td><td>{rupees(t.cgst)}</td><td>{rupees(t.sgst)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot><tr><td colSpan={3}>Total GST included</td><td>{rupees(order.gst_total)}</td></tr></tfoot>
          </table>
        )}
        <p className="fine">Stock has been updated. Your next items go into a fresh cart.</p>
      </div>
    </div>
  )
}
