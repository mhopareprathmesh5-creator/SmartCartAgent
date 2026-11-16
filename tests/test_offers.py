"""Offer optimizer tests.

Part 1 — hand-built cases, each proving one rule.
Part 2 — optimality: compare against brute force over every subset of coupons,
         on 500 random problems and on random carts priced from the real DB.
"""
import itertools
import random
from datetime import date
from decimal import Decimal as D

import pytest

from smartcart.tools.models import CartLine, Coupon
from smartcart.tools.offers import choose_best_offers, evaluate, load_conflicts, load_coupons

TODAY = date(2026, 10, 12)


def C(code, dtype, value, min_value=0, scope="CART", scope_value=None, cap=None,
      active=True, valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31)):
    return Coupon(0, code, code, dtype, D(str(value)), D(str(cap)) if cap is not None else None,
                  D(str(min_value)), scope, scope_value, valid_from, valid_to, active)


def L(total, category="Beverages", sub="Tea", brand="X", pid=1):
    return CartLine(pid, category, sub, brand, D(str(total)))


def conflicts(*pairs):
    return {frozenset(p) for p in pairs}


def codes(result):
    return sorted(a.code for a in result.applied)


# ---------------------------------------------------------------- part 1: rules
def test_empty_cart_gets_no_discount():
    r = choose_best_offers([], [C("SAVE10", "PERCENT", 10)], set(), TODAY)
    assert r.applied == [] and r.total_discount == D("0.00")


def test_percent_discount_and_cap():
    lines = [L(1000)]
    assert choose_best_offers(lines, [C("P", "PERCENT", 10)], set(), TODAY).total_discount == D("100.00")
    assert choose_best_offers(lines, [C("P", "PERCENT", 10, cap=60)], set(), TODAY).total_discount == D("60.00")


def test_flat_discount_never_exceeds_eligible_items():
    lines = [L(40, category="Beverages"), L(500, category="Snacks")]
    r = choose_best_offers(lines, [C("BEV75", "FLAT", 75, scope="CATEGORY", scope_value="Beverages")],
                           set(), TODAY)
    assert r.total_discount == D("40.00")


def test_minimum_is_checked_on_eligible_items_not_whole_cart():
    # ₹900 cart but only ₹200 of Beverages: BEV75 (needs ₹300 of Beverages) must NOT apply
    lines = [L(200, category="Beverages"), L(700, category="Snacks")]
    bev = C("BEV75", "FLAT", 75, min_value=300, scope="CATEGORY", scope_value="Beverages")
    r = choose_best_offers(lines, [bev], set(), TODAY)
    assert r.applied == []
    rej = r.rejected[0]
    assert rej.reason == "below_minimum" and rej.shortfall == D("100.00")


def test_scopes_match_the_right_lines():
    lines = [L(300, category="Bakery, Cakes & Dairy", sub="Dairy", brand="Amul", pid=1),
             L(200, category="Bakery, Cakes & Dairy", sub="Breads & Buns", brand="Britannia", pid=2)]
    cs = [C("CAT", "PERCENT", 10, scope="CATEGORY", scope_value="Bakery, Cakes & Dairy"),
          C("SUB", "PERCENT", 10, scope="SUB_CATEGORY", scope_value="Dairy"),
          C("BRAND", "PERCENT", 10, scope="BRAND", scope_value="Britannia")]
    applied = {a.code: a for a in choose_best_offers(lines, cs, set(), TODAY).applied}
    assert applied["CAT"].eligible_subtotal == D("500.00")
    assert applied["SUB"].eligible_subtotal == D("300.00")
    assert applied["BRAND"].eligible_subtotal == D("200.00")


@pytest.mark.parametrize("coupon,reason", [
    (C("OLD", "PERCENT", 50, valid_to=date(2026, 8, 31)), "expired"),
    (C("SOON", "PERCENT", 50, valid_from=date(2026, 11, 1)), "not_started"),
    (C("OFF", "PERCENT", 50, active=False), "inactive"),
])
def test_invalid_coupons_never_apply_even_if_they_are_the_biggest(coupon, reason):
    r = choose_best_offers([L(1000)], [coupon, C("SMALL", "FLAT", 10)], set(), TODAY)
    assert codes(r) == ["SMALL"]
    assert {x.code: x.reason for x in r.rejected}[coupon.code] == reason


def test_conflicting_pair_is_never_chosen_together():
    # the synopsis example: store-wide 10% vs ₹75 off Beverages, mutually exclusive
    lines = [L(400, category="Beverages"), L(300, category="Snacks")]
    cs = [C("SAVE10", "PERCENT", 10, min_value=500, cap=150),
          C("BEV75", "FLAT", 75, min_value=300, scope="CATEGORY", scope_value="Beverages")]
    r = choose_best_offers(lines, cs, conflicts(("SAVE10", "BEV75")), TODAY)
    assert codes(r) == ["BEV75"]                      # 75 > 10% of 700 = 70
    assert r.total_discount == D("75.00")
    rej = {x.code: x for x in r.rejected}["SAVE10"]
    assert rej.reason == "conflict" and "BEV75" in rej.detail

    lines.append(L(200, category="Snacks"))           # cart 900 -> SAVE10 = 90 > 75
    assert codes(choose_best_offers(lines, cs, conflicts(("SAVE10", "BEV75")), TODAY)) == ["SAVE10"]


def test_beats_greedy():
    """Taking the biggest coupon first (greedy) gives 100; the optimum is 60 + 60 = 120."""
    cs = [C("A", "FLAT", 100), C("B", "FLAT", 60), C("C", "FLAT", 60)]
    r = choose_best_offers([L(1000)], cs, conflicts(("A", "B"), ("A", "C")), TODAY)
    assert codes(r) == ["B", "C"] and r.total_discount == D("120.00")


def test_independent_stacking_is_order_free():
    # DAIRY10 and SAVE10 both cover the milk: each computed on the ORIGINAL amounts
    lines = [L(300, category="Bakery, Cakes & Dairy", sub="Dairy"), L(400, category="Snacks", sub="Chips")]
    cs = [C("DAIRY10", "PERCENT", 10, scope="SUB_CATEGORY", scope_value="Dairy"),
          C("SAVE10", "PERCENT", 10)]
    r = choose_best_offers(lines, cs, set(), TODAY)
    assert {a.code: a.discount for a in r.applied} == {"DAIRY10": D("30.00"), "SAVE10": D("70.00")}
    assert r.total_discount == D("100.00")


def test_total_discount_never_exceeds_subtotal():
    cs = [C("A", "FLAT", 80), C("B", "FLAT", 80)]
    r = choose_best_offers([L(100)], cs, set(), TODAY)
    assert r.total_discount == D("100.00")


def test_tie_prefers_fewer_coupons_then_alphabetical():
    cs = [C("B", "FLAT", 50), C("C", "FLAT", 50), C("A", "FLAT", 100)]
    r = choose_best_offers([L(1000)], cs, conflicts(("A", "B"), ("A", "C")), TODAY)
    assert codes(r) == ["A"]                          # 100 via 1 coupon beats 100 via 2
    cs = [C("Y", "FLAT", 50), C("X", "FLAT", 50)]
    assert codes(choose_best_offers([L(1000)], cs, conflicts(("X", "Y")), TODAY)) == ["X"]


def test_every_coupon_is_either_applied_or_explained():
    cs = [C("A", "FLAT", 100), C("B", "FLAT", 60), C("OLD", "FLAT", 5, valid_to=date(2025, 1, 1))]
    r = choose_best_offers([L(1000)], cs, conflicts(("A", "B")), TODAY)
    assert sorted(codes(r) + [x.code for x in r.rejected]) == ["A", "B", "OLD"]


# ---------------------------------------------------------------- part 2: optimality
def brute_force_best(lines, coupons, conflict_set, today):
    subtotal = sum((l.line_total for l in lines), D("0"))
    candidates = [a for a in (evaluate(c, lines, today)[0] for c in coupons) if a]
    best = D("0")
    for k in range(len(candidates) + 1):
        for combo in itertools.combinations(candidates, k):
            if any(frozenset((x.code, y.code)) in conflict_set
                   for x, y in itertools.combinations(combo, 2)):
                continue
            best = max(best, min(sum((c.discount for c in combo), D("0")), subtotal))
    return best


def random_problem(rng):
    cats = ["Beverages", "Snacks", "Dairy", "Baby Care"]
    brands = ["Amul", "Fresho", "Britannia", "Tata"]
    lines = [CartLine(i, rng.choice(cats), rng.choice(cats), rng.choice(brands),
                      D(rng.randint(10, 900)))
             for i in range(rng.randint(0, 8))]
    coupons = []
    for i in range(rng.randint(1, 12)):
        scope = rng.choice(["CART", "CATEGORY", "SUB_CATEGORY", "BRAND"])
        sv = None if scope == "CART" else rng.choice(brands if scope == "BRAND" else cats)
        if rng.random() < 0.5:
            coupons.append(C(f"P{i}", "PERCENT", rng.randint(5, 30), rng.choice([0, 100, 300, 800]),
                             scope, sv, cap=rng.choice([None, 50, 150])))
        else:
            coupons.append(C(f"F{i}", "FLAT", rng.randint(10, 200), rng.choice([0, 100, 300, 800]),
                             scope, sv))
    conflict_set = {frozenset((a.code, b.code))
                    for a, b in itertools.combinations(coupons, 2) if rng.random() < 0.3}
    return lines, coupons, conflict_set


def test_optimal_on_500_random_problems():
    rng = random.Random(2026)
    for _ in range(500):
        lines, coupons, conflict_set = random_problem(rng)
        r = choose_best_offers(lines, coupons, conflict_set, TODAY)
        assert r.total_discount == brute_force_best(lines, coupons, conflict_set, TODAY)
        chosen = [a.code for a in r.applied]
        assert not any(frozenset(p) in conflict_set for p in itertools.combinations(chosen, 2))


@pytest.mark.db
def test_optimal_with_real_seeded_coupons_on_random_carts(db):
    from sqlalchemy import text
    coupons, conflict_set = load_coupons(db), load_conflicts(db)
    products = db.execute(text(
        "SELECT product_id, category, sub_category, brand, current_price FROM v_store_catalog")).all()
    rng = random.Random(7)
    for _ in range(200):
        lines = [CartLine(p[0], p[1], p[2], p[3], p[4] * rng.randint(1, 4))
                 for p in rng.sample(products, rng.randint(1, 15))]
        r = choose_best_offers(lines, coupons, conflict_set, TODAY)
        assert r.total_discount == brute_force_best(lines, coupons, conflict_set, TODAY)
        assert "MONSOON20" not in codes(r) and "TEA40" not in codes(r)
