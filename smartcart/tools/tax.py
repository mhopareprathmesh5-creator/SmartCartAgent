"""GST breakdown of a bill (pure functions, no database).

Indian shelf prices are GST-inclusive, so GST is not added on top — the bill
shows how much of what the shopper pays is tax. A discount given at the time of
sale reduces the taxable value, so tax is computed on each line's amount AFTER
its share of the coupon discounts:

    1. allocate_discounts: each applied coupon's discount is split across the lines
       it applies to, in proportion to their line totals (rounding remainder goes to
       the largest line, so the shares add up exactly).
    2. per line:  net = line_total − discount_share
                  taxable = net × 100 / (100 + rate)      (rounded to the paisa)
                  gst = net − taxable,  CGST = gst / 2,  SGST = gst − CGST
    3. lines are grouped into rate slabs (0 / 5 / 18 / 40 %).

Invariants (tested): shares add up to the bill's discount; no share exceeds its line;
Σ taxable + Σ gst = final_total exactly.
"""
from dataclasses import dataclass
from decimal import Decimal

from smartcart.tools.models import AppliedCoupon, CartLine, Coupon, money
from smartcart.tools.offers import line_matches

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class LineTax:
    product_id: int
    gst_rate: Decimal
    discount_share: Decimal
    net: Decimal          # line_total − discount_share (what the shopper pays for this line)
    taxable: Decimal
    gst: Decimal


@dataclass(frozen=True)
class TaxSlab:
    rate: Decimal
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal

    @property
    def gst(self) -> Decimal:
        return self.cgst + self.sgst


def allocate_discounts(lines: list[CartLine], applied: list[AppliedCoupon],
                       coupons: dict[str, Coupon], total_discount: Decimal) -> dict[int, Decimal]:
    """Share of the total discount carried by each line (product_id -> ₹)."""
    share = {l.product_id: ZERO for l in lines}
    for a in applied:
        eligible = [l for l in lines if line_matches(coupons[a.code], l) and l.line_total > 0]
        base = sum((l.line_total for l in eligible), ZERO)
        if base == 0:
            continue
        parts = {l.product_id: money(a.discount * l.line_total / base) for l in eligible}
        largest = max(eligible, key=lambda l: (l.line_total, -l.product_id)).product_id
        parts[largest] += a.discount - sum(parts.values(), ZERO)       # exact rounding remainder
        for pid, v in parts.items():
            share[pid] += v

    # Overlapping coupons can push one line past its own total; move the excess to lines
    # that still have room. The total discount never exceeds the subtotal, so it always fits.
    totals = {l.product_id: l.line_total for l in lines}
    excess = ZERO
    for pid in share:
        if share[pid] > totals[pid]:
            excess += share[pid] - totals[pid]
            share[pid] = totals[pid]
    for pid in sorted(share, key=lambda p: totals[p] - share[p], reverse=True):
        if excess == 0:
            break
        move = min(excess, totals[pid] - share[pid])
        share[pid] += move
        excess -= move

    drift = total_discount - sum(share.values(), ZERO)      # total discount may be capped at subtotal
    if drift < 0:
        for pid in sorted(share, key=lambda p: share[p], reverse=True):
            take = min(-drift, share[pid])
            share[pid] -= take
            drift += take
            if drift == 0:
                break
    return share


def line_taxes(lines: list[CartLine], rates: dict[int, Decimal], shares: dict[int, Decimal]) -> list[LineTax]:
    out = []
    for l in lines:
        rate = Decimal(rates[l.product_id])
        net = l.line_total - shares.get(l.product_id, ZERO)
        taxable = money(net * 100 / (100 + rate))
        out.append(LineTax(l.product_id, rate, shares.get(l.product_id, ZERO), net, taxable, net - taxable))
    return out


def tax_slabs(taxes: list[LineTax]) -> list[TaxSlab]:
    slabs = {}
    for t in taxes:
        taxable, gst = slabs.get(t.gst_rate, (ZERO, ZERO))
        slabs[t.gst_rate] = (taxable + t.taxable, gst + t.gst)
    out = []
    for rate in sorted(slabs):
        taxable, gst = slabs[rate]
        cgst = money(gst / 2)
        out.append(TaxSlab(rate, taxable, cgst, gst - cgst))
    return out
