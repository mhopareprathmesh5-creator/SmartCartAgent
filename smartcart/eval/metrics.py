"""Evaluation metrics: pure functions, no LLM.

  discount_report()    discount the system applied vs the theoretical optimum (brute
                       force over every subset of valid coupons), plus two baselines a
                       simpler system might use: greedy (biggest coupon first) and the
                       single best coupon.
  check_goal()         did the final cart / replies satisfy the goal? (task success)
  substitution_report() for each unavailable product: was it replaced by an in-stock
                       product of the same type, and was that the top-ranked substitute?
  reply_values()       how many ₹ amounts / aisle numbers a reply contains (all of
                       them are audited by the grounding guard).
"""
import itertools
from datetime import date
from decimal import Decimal

from smartcart.agent.grounding import AISLE_RE, MONEY_RE, _money, _num
from smartcart.tools.models import CartLine, Coupon, money
from smartcart.tools.offers import choose_best_offers, evaluate

ZERO = Decimal("0.00")


# ---------------------------------------------------------------- discounts
def _candidates(lines: list[CartLine], coupons: list[Coupon], today: date):
    return [ok for c in coupons for ok, _ in [evaluate(c, lines, today)] if ok]


def brute_force_optimum(lines, coupons, conflicts, today) -> Decimal:
    """Largest total discount over EVERY conflict-free subset of the valid coupons."""
    cands = _candidates(lines, coupons, today)
    subtotal = money(sum((l.line_total for l in lines), ZERO))
    best = ZERO
    for r in range(1, len(cands) + 1):
        for combo in itertools.combinations(cands, r):
            if any(frozenset((a.code, b.code)) in conflicts for a, b in itertools.combinations(combo, 2)):
                continue
            best = max(best, min(sum((c.discount for c in combo), ZERO), subtotal))
    return money(best)


def greedy_discount(lines, coupons, conflicts, today) -> Decimal:
    """Baseline: keep taking the biggest coupon that does not conflict with those taken."""
    taken = []
    for c in sorted(_candidates(lines, coupons, today), key=lambda c: (-c.discount, c.code)):
        if all(frozenset((c.code, t.code)) not in conflicts for t in taken):
            taken.append(c)
    subtotal = money(sum((l.line_total for l in lines), ZERO))
    return money(min(sum((t.discount for t in taken), ZERO), subtotal))


def single_best_discount(lines, coupons, today) -> Decimal:
    """Baseline: one coupon per bill (how many real checkouts work)."""
    return max((c.discount for c in _candidates(lines, coupons, today)), default=ZERO)


def discount_report(lines, coupons, conflicts, today) -> dict:
    system = choose_best_offers(lines, coupons, conflicts, today)
    optimum = brute_force_optimum(lines, coupons, conflicts, today)
    return {
        "subtotal": money(sum((l.line_total for l in lines), ZERO)),
        "valid_coupons": len(_candidates(lines, coupons, today)),
        "system": system.total_discount,
        "system_codes": [a.code for a in system.applied],
        "optimum": optimum,
        "greedy": greedy_discount(lines, coupons, conflicts, today),
        "single_best": single_best_discount(lines, coupons, today),
        "is_optimal": system.total_discount == optimum,
    }


def pct(part: Decimal, whole: Decimal) -> float:
    """part / whole in %, 100 when there was nothing to capture."""
    return 100.0 if whole == 0 else round(float(part) / float(whole) * 100, 2)


# ---------------------------------------------------------------- task success
def reply_values(reply: str) -> int:
    return len(MONEY_RE.findall(reply)) + len(AISLE_RE.findall(reply))


def amounts_in(reply: str) -> set[Decimal]:
    return {_num(_money(m)) for m in MONEY_RE.finditer(reply)}


def aisles_in(reply: str) -> set[int]:
    return {int(_num(m.group(1))) for m in AISLE_RE.finditer(reply)}


def check_goal(goal, cart: list[dict], bill: dict, budget, replies: list[str], type_aisles: dict,
               offered_types: frozenset = frozenset(), tools_called: frozenset = frozenset()) -> list[dict]:
    """One {check, passed, detail, pending} per expectation of the goal. `cart` rows carry
    product_type + qty. `offered_types`: types of unavailable products for which substitute cards
    were shown. A shortfall there passes as `pending` (the shopper confirms the substitute,
    synopsis objective 4); strict scoring counts pending checks as failed."""
    qty_by_type: dict[str, int] = {}
    for row in cart:
        qty_by_type[row["product_type"]] = qty_by_type.get(row["product_type"], 0) + row["qty"]
    checks = []

    def add(name, passed, detail, pending=False):
        checks.append({"check": name, "passed": bool(passed), "detail": detail, "pending": pending})

    for w in goal.want:
        got = qty_by_type.get(w.product_type, 0)
        if got < w.qty and w.product_type in offered_types:
            add(f"{w.qty} × {w.product_type}", True,
                f"cart has {got}; substitutes offered for the rest, shopper to confirm", pending=True)
        else:
            add(f"{w.qty} × {w.product_type}", got == w.qty, f"cart has {got}")
    for t in goal.absent:
        add(f"no {t}", t not in qty_by_type, f"cart has {qty_by_type.get(t, 0)}")
    if goal.empty_cart:
        add("cart stays empty", not cart, f"{len(cart)} line(s)")
    for pid in goal.unavailable:
        short = next((r for r in cart if r["product_id"] == pid and r["qty"] > r["stock_qty"]), None)
        add(f"unavailable #{pid} not over-sold", short is None, "ok" if short is None else "over stock")
    if goal.budget is not None:
        recorded = None if budget is None else Decimal(str(budget))
        add(f"budget ₹{goal.budget} recorded", recorded == goal.budget, f"recorded {recorded}")
    last = replies[-1] if replies else ""
    for t in goal.aisle_for:
        aisle = type_aisles.get(t)
        add(f"names aisle of {t}", aisle in aisles_in(" ".join(replies)), f"expected Aisle {aisle}")
    for t in goal.tools:
        add(f"calls {t}", t in tools_called, "called" if t in tools_called else "not called")
    for key in goal.mention:
        value = Decimal(str(bill.get(key, "0"))).quantize(Decimal("0.01"))
        add(f"quotes bill {key} ₹{value}", value in amounts_in(last), "from compute_bill")
    return checks


# ---------------------------------------------------------------- substitution
def substitution_report(goal, cart: list[dict], catalog: dict, ranked: dict, offered: set[int]) -> list[dict]:
    """For each unavailable product: outcome 'added' (a same-type in-stock product is in the cart),
    'offered' (substitute cards shown, shopper still to choose) or 'missing'.
    `catalog[pid]` -> product_type; `ranked[pid]` -> find_substitutes ids, best first."""
    out = []
    for pid in goal.unavailable:
        want_type = catalog[pid]
        replacements = [r for r in cart if r["product_id"] != pid and r["product_type"] == want_type]
        if replacements:
            sub = replacements[0]
            ids = ranked.get(pid, [])
            out.append({"product_id": pid, "outcome": "added", "substitute": sub["product_id"],
                        "same_type": True, "in_stock": sub["stock_qty"] >= sub["qty"],
                        "rank": ids.index(sub["product_id"]) + 1 if sub["product_id"] in ids else None})
        elif pid in offered:
            out.append({"product_id": pid, "outcome": "offered", "substitute": None,
                        "same_type": True, "in_stock": True, "rank": None})
        else:
            out.append({"product_id": pid, "outcome": "missing", "substitute": None,
                        "same_type": False, "in_stock": False, "rank": None})
    return out
