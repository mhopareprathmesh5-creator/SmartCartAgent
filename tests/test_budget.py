"""Budget fitter: rules, optimality vs brute force, and on real carts."""
import itertools
import random
from decimal import Decimal as D

import pytest

from smartcart.tools import compute_bill, fit_budget, update_cart
from smartcart.tools.budget import PlanItem, PlanLine, payable, plan_budget_fit
from tests.conftest import pick
from tests.test_offers import C, TODAY


def item(pid, price, category="Snacks", brand="X"):
    return PlanItem(pid, f"P{pid}", brand, category, category, D(str(price)))


def line(current, qty, *alts):
    return PlanLine(current, qty, tuple(alts))


def test_already_within_budget_means_no_swaps():
    plan = plan_budget_fit([line(item(1, 100), 1, item(2, 50))], D(200), [], set(), TODAY)
    assert plan.feasible and plan.swaps == [] and plan.new_total == D("100.00")


def test_prefers_fewest_swaps_then_least_downgrade():
    lines = [line(item(1, 300), 1, item(11, 250), item(12, 100)),
             line(item(2, 200), 1, item(21, 150))]
    # budget 460: one swap is enough. Options: 11 -> 450, 12 -> 300, 21 -> 450. Keep the most: 450,
    # tie between 11 and 21 resolved deterministically.
    plan = plan_budget_fit(lines, D(460), [], set(), TODAY)
    assert plan.feasible and len(plan.swaps) == 1 and plan.new_total == D("450.00")
    # budget 360: one swap of item 1 to 12 (₹300 total) beats two swaps
    plan = plan_budget_fit(lines, D(360), [], set(), TODAY)
    assert [s.to_product_id for s in plan.swaps] == [12] and plan.new_total == D("300.00")


def test_coupons_are_reoptimized_for_each_plan():
    # FLAT 100 off a cart above ₹1000. Current 1050 → pays 950. Budget 940.
    # Swapping to a ₹990 item loses the coupon (pays 990, worse!); swapping to ₹900 pays 900.
    coupons = [C("BIG", "FLAT", 100, min_value=1000)]
    lines = [line(item(1, 1050), 1, item(2, 990), item(3, 900))]
    plan = plan_budget_fit(lines, D(940), coupons, set(), TODAY)
    assert plan.current_total == D("950.00")
    assert plan.feasible and plan.swaps[0].to_product_id == 3 and plan.new_total == D("900.00")


def test_infeasible_reports_the_cheapest_possible_total():
    lines = [line(item(1, 500), 1, item(2, 400)), line(item(3, 300), 2)]   # second line has no alternatives
    plan = plan_budget_fit(lines, D(500), [], set(), TODAY)
    assert not plan.feasible and plan.new_total == D("1000.00") and plan.swaps == []
    assert "cheapest" in plan.message


def brute_force(lines, budget, coupons, conflicts):
    best = None
    options = [[None] + list(l.alternatives) for l in lines]
    for combo in itertools.product(*options):
        choice = {i: p for i, p in enumerate(combo) if p is not None}
        total = payable(lines, choice, coupons, conflicts, TODAY)
        if total > budget:
            continue
        key = (-len(choice), total)
        if best is None or key > best:
            best = key
    return best


def test_matches_brute_force_on_random_carts():
    rng = random.Random(5)
    cats = ["Snacks", "Beverages", "Dairy"]
    for _ in range(150):
        pid = iter(range(1, 10_000))
        lines = []
        for _ in range(rng.randint(1, 5)):
            cat = rng.choice(cats)
            price = rng.randint(50, 600)
            alts = [item(next(pid), rng.randint(20, price - 1), cat) for _ in range(rng.randint(0, 3))]
            lines.append(line(item(next(pid), price, cat), rng.randint(1, 3), *alts))
        coupons = [C("CART", "PERCENT", 10, min_value=rng.choice([300, 800]), cap=150),
                   C("CAT", "FLAT", 75, min_value=300, scope="CATEGORY", scope_value=rng.choice(cats))]
        conflicts = {frozenset(("CART", "CAT"))} if rng.random() < 0.5 else set()
        current = payable(lines, {}, coupons, conflicts, TODAY)
        budget = D(rng.randint(int(current * D("0.5")), int(current) + 50))
        plan = plan_budget_fit(lines, budget, coupons, conflicts, TODAY, max_swaps=len(lines))
        expected = brute_force(lines, budget, coupons, conflicts)
        if expected is None:
            assert not plan.feasible
        else:
            assert plan.feasible and (-len(plan.swaps), plan.new_total) == expected


# ---------------------------------------------------------------- real carts
@pytest.mark.db
def test_real_cart_is_brought_within_budget_without_being_changed(db, cart_id):
    tea = pick(db, "product_type = 'Leaf & Dust Tea' AND stock_qty >= 5 AND current_price > 200")
    coffee = pick(db, "product_type = 'Instant Coffee' AND stock_qty >= 5 AND current_price > 200")
    update_cart(cart_id, tea, 2)
    update_cart(cart_id, coffee, 1)
    before = compute_bill(cart_id, today=TODAY)
    budget = before.final_total - D("50.00")

    plan = fit_budget(cart_id, budget, today=TODAY)
    assert plan.feasible and plan.new_total <= budget and plan.swaps
    for s in plan.swaps:
        assert s.to_unit_price < s.from_unit_price and s.shelf_code

    after = compute_bill(cart_id, today=TODAY)
    assert [(l.product_id, l.quantity) for l in after.lines] == [(l.product_id, l.quantity) for l in before.lines]

    for s in plan.swaps:                       # applying the plan gives exactly the promised total
        update_cart(cart_id, s.from_product_id, 0)
        update_cart(cart_id, s.to_product_id, s.quantity)
    assert compute_bill(cart_id, today=TODAY).final_total == plan.new_total
