"""Budget fitter: fit_budget() — suggest swaps that bring an over-budget cart under budget.

Problem
  Each cart line can keep its product or switch to a cheaper in-stock product of the
  SAME product type (same quantity). Pick a plan such that the payable total — with the
  coupons re-optimized for the new cart, because swaps can win or lose coupons — is
  within budget, and among those:
      1. as FEW swaps as possible           (least disruption to the shopper's choices)
      2. the HIGHEST total that still fits   (closest to what they picked, least downgrade)
      3. deterministic tie-break on product ids

Algorithm
  Exact search over the candidate set, in increasing number of swaps k = 0, 1, 2, …:
  try every choice of k lines and every alternative for each of them; stop at the first
  k with a feasible plan. Work = Σ_k C(n, k)·m^k payable-total evaluations (n lines, m
  alternatives each), each running the exact coupon optimizer. With m ≤ 3 and k ≤ 4
  this stays well under a second. Tests check the result against brute force over
  every plan.

Read-only: it only SUGGESTS swaps; the agent or the UI applies them after the shopper
agrees. All amounts are computed here from database prices, never by the LLM.
"""
import itertools
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import text

from smartcart.db import DEFAULT_STORE_ID, get_engine
from smartcart.tools.models import CartLine, Coupon, money
from smartcart.tools.offers import Conflicts, choose_best_offers, load_conflicts, load_coupons

ZERO = Decimal("0.00")
MAX_SWAPS = 4
ALTERNATIVES_PER_ITEM = 3


@dataclass(frozen=True)
class PlanItem:
    """A product that can occupy a cart line (the current one or an alternative)."""
    product_id: int
    name: str
    brand: str
    category: str
    sub_category: str
    unit_price: Decimal
    aisle_no: Optional[int] = None
    shelf_code: Optional[str] = None


@dataclass(frozen=True)
class PlanLine:
    current: PlanItem
    quantity: int
    alternatives: tuple[PlanItem, ...]       # cheaper, same product type, enough stock


@dataclass(frozen=True)
class Swap:
    from_product_id: int
    from_name: str
    to_product_id: int
    to_name: str
    to_brand: str
    quantity: int
    from_unit_price: Decimal
    to_unit_price: Decimal
    saving: Decimal                          # line saving before coupons
    aisle_no: Optional[int]
    shelf_code: Optional[str]


@dataclass(frozen=True)
class BudgetPlan:
    feasible: bool
    budget: Decimal
    current_total: Decimal
    new_total: Decimal                       # payable after swaps, coupons re-optimized
    total_saving: Decimal
    swaps: list[Swap]
    plans_evaluated: int
    message: str


def payable(lines: list[PlanLine], choice: dict[int, PlanItem], coupons: list[Coupon], conflicts: Conflicts,
            today: date) -> Decimal:
    """Payable total if line i uses product choice[i] (default: its current product)."""
    cart = []
    for i, l in enumerate(lines):
        p = choice.get(i, l.current)
        cart.append(CartLine(p.product_id, p.category, p.sub_category, p.brand, money(p.unit_price * l.quantity)))
    offers = choose_best_offers(cart, coupons, conflicts, today)
    return money(sum((c.line_total for c in cart), ZERO) - offers.total_discount)


def plan_budget_fit(lines: list[PlanLine], budget: Decimal, coupons: list[Coupon], conflicts: Conflicts,
                    today: date, max_swaps: int = MAX_SWAPS) -> BudgetPlan:
    """Pure planner (no database). See module docstring for the exact objective."""
    budget = money(budget)
    current = payable(lines, {}, coupons, conflicts, today)
    evaluated = 1
    if current <= budget:
        return BudgetPlan(True, budget, current, current, ZERO, [], evaluated, "The cart is already within budget.")

    swappable = [i for i, l in enumerate(lines) if l.alternatives]
    for k in range(1, min(max_swaps, len(swappable)) + 1):
        best = None                          # (total, tie-key, choice)
        for idxs in itertools.combinations(swappable, k):
            for picks in itertools.product(*(lines[i].alternatives for i in idxs)):
                choice = dict(zip(idxs, picks))
                total = payable(lines, choice, coupons, conflicts, today)
                evaluated += 1
                if total > budget:
                    continue
                key = (total, tuple(-p.product_id for p in picks))
                if best is None or key > best[:2]:
                    best = (total, key[1], choice)
        if best is not None:
            total, _, choice = best
            swaps = [_swap(lines[i], p) for i, p in sorted(choice.items())]
            return BudgetPlan(True, budget, current, total, money(current - total), swaps, evaluated,
                              f"{len(swaps)} swap{'s' if len(swaps) > 1 else ''} bring the cart within budget.")

    # Not possible with same-type swaps: report the cheapest the cart can get.
    cheapest = {i: min(lines[i].alternatives, key=lambda p: (p.unit_price, p.product_id)) for i in swappable}
    floor = payable(lines, cheapest, coupons, conflicts, today)
    evaluated += 1
    return BudgetPlan(False, budget, current, floor, money(current - floor), [], evaluated,
                      f"Even the cheapest same-type alternatives give ₹{floor}, above the ₹{budget} budget. "
                      "Removing an item or reducing a quantity is needed.")


def _swap(line: PlanLine, to: PlanItem) -> Swap:
    c = line.current
    return Swap(c.product_id, c.name, to.product_id, to.name, to.brand, line.quantity, c.unit_price, to.unit_price,
                money((c.unit_price - to.unit_price) * line.quantity), to.aisle_no, to.shelf_code)


# ------------------------------------------------------------------ DB wrapper
_LINES_SQL = text("""
    SELECT c.product_id, c.name, c.brand, c.category, c.sub_category, c.product_type, c.current_price,
           c.aisle_no, c.shelf_code, ci.quantity
    FROM cart_items ci JOIN v_store_catalog c ON c.product_id = ci.product_id AND c.store_id = :store_id
    WHERE ci.cart_id = :cid ORDER BY ci.added_at, c.product_id
""")

# Cheaper, same product type, enough stock, not already in the cart. Closest-cheaper first,
# plus the cheapest of all, so the search sees both small and deep savings.
_ALTS_SQL = text("""
    SELECT product_id, name, brand, category, sub_category, current_price, aisle_no, shelf_code
    FROM v_store_catalog
    WHERE store_id = :store_id AND product_type = :ptype AND current_price < :price AND stock_qty >= :qty
      AND product_id <> ALL(:in_cart)
    ORDER BY current_price DESC, product_id
""")


def fit_budget(cart_id: int, budget: Decimal, today: Optional[date] = None,
               store_id: int = DEFAULT_STORE_ID) -> BudgetPlan:
    """Suggest the fewest same-type swaps that bring the cart within `budget` (does not change the cart)."""
    from smartcart.tools.cart import ensure_cart_exists   # avoid import cycle

    today = today or date.today()
    with get_engine().connect() as conn:
        ensure_cart_exists(conn, cart_id)
        rows = conn.execute(_LINES_SQL, {"cid": cart_id, "store_id": store_id}).mappings().all()
        in_cart = [r["product_id"] for r in rows]
        lines = []
        for r in rows:
            alts = conn.execute(_ALTS_SQL, {"store_id": store_id, "ptype": r["product_type"],
                                            "price": r["current_price"], "qty": r["quantity"],
                                            "in_cart": in_cart}).mappings().all()
            picked = list(alts[:ALTERNATIVES_PER_ITEM - 1])
            if alts and alts[-1] not in picked:
                picked.append(alts[-1])     # the cheapest one
            lines.append(PlanLine(_item(r), r["quantity"], tuple(_item(a) for a in picked)))
        coupons, conflicts = load_coupons(conn), load_conflicts(conn)
    return plan_budget_fit(lines, Decimal(budget), coupons, conflicts, today)


def _item(r) -> PlanItem:
    return PlanItem(r["product_id"], r["name"], r["brand"], r["category"], r["sub_category"],
                    r["current_price"], r["aisle_no"], r["shelf_code"])
