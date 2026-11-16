"""Offer optimizer: optimize_offers().

Problem
  Given the cart lines, every coupon and the mutually-exclusive coupon pairs,
  choose the set of coupons that gives the LARGEST total discount such that
    - every chosen coupon is active and valid today,
    - every chosen coupon's eligible subtotal reaches its min_cart_value,
    - no two chosen coupons are a conflict pair,
    - the total discount never exceeds the cart subtotal.

Stacking rule (decided with the team): coupons are INDEPENDENT. Each coupon's
discount is computed on the original, pre-discount subtotal of its eligible
items, and the chosen discounts are added. Order of application never matters.

Algorithm
  Step 1 (filter): each coupon's discount is fixed once the cart is known, so
  compute it per coupon and drop the ones that cannot apply (with a reason).
  Step 2 (select): picking the best non-conflicting subset is a maximum-weight
  independent set on the conflict graph — NP-hard in general, but a store has
  tens of coupons, so an exact branch-and-bound search is instant. It explores
  include/exclude for each coupon (largest first) and prunes any branch whose
  optimistic bound (current + all remaining discounts) cannot beat the best
  found. The result is provably optimal (tests check it against brute force).
"""
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import text

from smartcart.db import DEFAULT_STORE_ID, get_engine
from smartcart.tools.models import (AppliedCoupon, CartLine, Coupon, OfferResult,
                                    RejectedCoupon, money)

ZERO = Decimal("0.00")
Conflicts = set[frozenset[str]]


# ------------------------------------------------------------------ step 1
def line_matches(coupon: Coupon, line: CartLine) -> bool:
    """Does the coupon apply to this cart line?"""
    if coupon.scope == "CART":
        return True
    if coupon.scope == "CATEGORY":
        return line.category == coupon.scope_value
    if coupon.scope == "SUB_CATEGORY":
        return line.sub_category == coupon.scope_value
    if coupon.scope == "BRAND":
        return line.brand == coupon.scope_value
    raise ValueError(f"Unknown coupon scope {coupon.scope!r}")


def eligible_subtotal(coupon: Coupon, lines: Iterable[CartLine]) -> Decimal:
    """Sum of line totals the coupon applies to."""
    return money(sum((l.line_total for l in lines if line_matches(coupon, l)), ZERO))


def coupon_discount(coupon: Coupon, eligible: Decimal) -> Decimal:
    """Discount the coupon gives on `eligible` (assumes it qualifies)."""
    if coupon.discount_type == "PERCENT":
        d = money(eligible * coupon.discount_value / 100)
        if coupon.max_discount is not None:
            d = min(d, coupon.max_discount)
    elif coupon.discount_type == "FLAT":
        d = coupon.discount_value
    else:
        raise ValueError(f"Unknown discount type {coupon.discount_type!r}")
    return money(min(d, eligible))     # a coupon can never discount more than it covers


def evaluate(coupon: Coupon, lines: list[CartLine], today: date):
    """Return (AppliedCoupon candidate, None) or (None, RejectedCoupon)."""
    if not coupon.is_active:
        return None, RejectedCoupon(coupon.code, "inactive", "Coupon is disabled")
    if today < coupon.valid_from:
        return None, RejectedCoupon(coupon.code, "not_started", f"Valid from {coupon.valid_from}")
    if today > coupon.valid_to:
        return None, RejectedCoupon(coupon.code, "expired", f"Expired on {coupon.valid_to}")

    eligible = eligible_subtotal(coupon, lines)
    if eligible == ZERO:
        return None, RejectedCoupon(coupon.code, "no_eligible_items",
                                    f"No items in the cart match {coupon.scope_value}")
    if eligible < coupon.min_cart_value:
        shortfall = money(coupon.min_cart_value - eligible)
        where = "" if coupon.scope == "CART" else f" of {coupon.scope_value}"
        return None, RejectedCoupon(
            coupon.code, "below_minimum",
            f"Needs ₹{coupon.min_cart_value}{where}; cart has ₹{eligible}", shortfall)
    return AppliedCoupon(coupon.code, coupon.description, eligible,
                         coupon_discount(coupon, eligible)), None


# ------------------------------------------------------------------ step 2
def best_combination(candidates: list[AppliedCoupon], conflicts: Conflicts,
                     cap: Decimal) -> list[AppliedCoupon]:
    """Exact maximum-discount subset of `candidates` with no conflicting pair.

    Total counted is min(sum of discounts, cap). Ties are broken by fewer
    coupons, then alphabetical codes, so the answer is deterministic.
    """
    items = sorted(candidates, key=lambda c: (-c.discount, c.code))
    n = len(items)
    remaining = [ZERO] * (n + 1)          # remaining[i] = sum of discounts of items[i:]
    for i in range(n - 1, -1, -1):
        remaining[i] = remaining[i + 1] + items[i].discount

    def key(chosen):
        value = min(sum((c.discount for c in chosen), ZERO), cap)
        return value, -len(chosen), tuple(sorted(c.code for c in chosen))

    best: list = []
    best_key = key(best)

    def better(k, than):
        # higher value, then fewer coupons, then alphabetically smaller codes
        return (k[0], k[1]) > (than[0], than[1]) or ((k[0], k[1]) == (than[0], than[1]) and k[2] < than[2])

    def search(i, chosen, total):
        nonlocal best, best_key
        k = key(chosen)
        if better(k, best_key):
            best, best_key = list(chosen), k
        if i == n:
            return
        if min(total + remaining[i], cap) < best_key[0]:
            return                         # bound: this branch cannot beat the best
        c = items[i]
        if all(frozenset((c.code, x.code)) not in conflicts for x in chosen):
            chosen.append(c)
            search(i + 1, chosen, total + c.discount)
            chosen.pop()
        search(i + 1, chosen, total)

    search(0, [], ZERO)
    return sorted(best, key=lambda c: (-c.discount, c.code))


def choose_best_offers(lines: list[CartLine], coupons: list[Coupon], conflicts: Conflicts,
                       today: date) -> OfferResult:
    """Pure optimizer: no database access. Used by optimize_offers() and compute_bill()."""
    subtotal = money(sum((l.line_total for l in lines), ZERO))
    candidates, rejected = [], []
    for c in sorted(coupons, key=lambda c: c.code):
        ok, why = evaluate(c, lines, today)
        if ok:
            candidates.append(ok)
        else:
            rejected.append(why)

    chosen = best_combination(candidates, conflicts, subtotal)
    chosen_codes = {c.code for c in chosen}

    for c in candidates:
        if c.code in chosen_codes:
            continue
        blockers = sorted(x for x in chosen_codes if frozenset((c.code, x)) in conflicts)
        if blockers:
            rejected.append(RejectedCoupon(
                c.code, "conflict",
                f"Cannot be combined with {', '.join(blockers)}, which saves more"))
        else:
            rejected.append(RejectedCoupon(c.code, "not_needed",
                                           "Discount already covers the full cart"))

    total = min(sum((c.discount for c in chosen), ZERO), subtotal)
    return OfferResult(applied=chosen, total_discount=money(total), rejected=rejected)


# ------------------------------------------------------------------ DB access
def load_coupons(conn) -> list[Coupon]:
    rows = conn.execute(text("SELECT * FROM coupons ORDER BY coupon_id")).mappings().all()
    return [Coupon(**r) for r in rows]


def load_conflicts(conn) -> Conflicts:
    rows = conn.execute(text("""
        SELECT a.code, b.code FROM coupon_conflicts cc
        JOIN coupons a ON a.coupon_id = cc.coupon_a
        JOIN coupons b ON b.coupon_id = cc.coupon_b
    """)).all()
    return {frozenset(r) for r in rows}


def load_cart_lines(conn, cart_id: int, store_id: int = DEFAULT_STORE_ID) -> list[CartLine]:
    rows = conn.execute(text("""
        SELECT p.product_id, p.category, p.sub_category, p.brand,
               ci.quantity * i.current_price AS line_total
        FROM cart_items ci
        JOIN products  p ON p.product_id = ci.product_id
        JOIN inventory i ON i.product_id = ci.product_id AND i.store_id = :store_id
        WHERE ci.cart_id = :cart_id
    """), {"cart_id": cart_id, "store_id": store_id}).mappings().all()
    return [CartLine(r["product_id"], r["category"], r["sub_category"], r["brand"],
                     money(r["line_total"])) for r in rows]


def optimize_offers(cart_id: int, today: Optional[date] = None,
                    store_id: int = DEFAULT_STORE_ID) -> OfferResult:
    """Best valid coupon combination for a cart, plus why every other coupon was not used."""
    from smartcart.tools.cart import ensure_cart_exists   # avoid import cycle

    today = today or date.today()
    with get_engine().connect() as conn:
        ensure_cart_exists(conn, cart_id)
        lines = load_cart_lines(conn, cart_id, store_id)
        coupons = load_coupons(conn)
        conflicts = load_conflicts(conn)
    return choose_best_offers(lines, coupons, conflicts, today)
