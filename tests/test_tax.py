"""GST breakdown: discount allocation + per-line tax (pure) and on real bills (DB)."""
import random
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from smartcart.tools import checkout, compute_bill, update_cart
from smartcart.tools.models import AppliedCoupon, CartLine
from smartcart.tools.tax import allocate_discounts, line_taxes, tax_slabs
from tests.conftest import pick
from tests.test_offers import C, TODAY

ZERO = D("0.00")


def L(pid, total, category="Beverages", brand="X"):
    return CartLine(pid, category, category, brand, D(str(total)))


def test_discount_split_in_proportion_and_adds_up_exactly():
    lines = [L(1, "100.00"), L(2, "200.00"), L(3, "50.00", category="Snacks")]
    bev = C("BEV", "FLAT", 10, scope="CATEGORY", scope_value="Beverages")
    shares = allocate_discounts(lines, [AppliedCoupon("BEV", "", D("300.00"), D("10.00"))], {"BEV": bev}, D("10.00"))
    assert shares == {1: D("3.33"), 2: D("6.67"), 3: ZERO}      # remainder to the largest line


def test_overlapping_coupons_never_push_a_line_below_zero():
    lines = [L(1, "100.00", brand="Amul"), L(2, "900.00", category="Snacks")]
    coupons = {"A": C("A", "FLAT", 100, scope="BRAND", scope_value="Amul"), "B": C("B", "FLAT", 80, scope="BRAND",
                                                                                  scope_value="Amul")}
    applied = [AppliedCoupon("A", "", D("100.00"), D("100.00")), AppliedCoupon("B", "", D("100.00"), D("80.00"))]
    shares = allocate_discounts(lines, applied, coupons, D("180.00"))
    assert shares[1] == D("100.00") and shares[2] == D("80.00") and sum(shares.values()) == D("180.00")


def test_gst_is_extracted_from_inclusive_price():
    lines = [L(1, "105.00"), L(2, "118.00"), L(3, "50.00")]
    taxes = line_taxes(lines, {1: D("5"), 2: D("18"), 3: D("0")}, {})
    by = {t.product_id: t for t in taxes}
    assert (by[1].taxable, by[1].gst) == (D("100.00"), D("5.00"))
    assert (by[2].taxable, by[2].gst) == (D("100.00"), D("18.00"))
    assert (by[3].taxable, by[3].gst) == (D("50.00"), ZERO)
    slabs = {s.rate: s for s in tax_slabs(taxes)}
    assert slabs[D("18")].cgst + slabs[D("18")].sgst == D("18.00") and slabs[D("18")].cgst == D("9.00")


def test_invariants_on_random_carts():
    rng = random.Random(11)
    for _ in range(300):
        lines = [L(i, f"{rng.randint(1, 900)}.{rng.randint(0, 99):02d}", rng.choice(["Beverages", "Snacks"]),
                   rng.choice(["Amul", "Tata"])) for i in range(rng.randint(1, 8))]
        coupons = {"P": C("P", "PERCENT", 10, cap=150), "F": C("F", "FLAT", 75, scope="CATEGORY", scope_value="Beverages"),
                   "B": C("B", "FLAT", 40, scope="BRAND", scope_value="Amul")}
        from smartcart.tools.offers import choose_best_offers
        offers = choose_best_offers(lines, list(coupons.values()), set(), TODAY)
        shares = allocate_discounts(lines, offers.applied, coupons, offers.total_discount)
        rates = {l.product_id: D(rng.choice(["0", "5", "18", "40"])) for l in lines}
        taxes = line_taxes(lines, rates, shares)
        subtotal = sum((l.line_total for l in lines), ZERO)
        assert sum(shares.values(), ZERO) == offers.total_discount
        assert all(ZERO <= shares[l.product_id] <= l.line_total for l in lines)
        assert sum((t.taxable + t.gst for t in taxes), ZERO) == subtotal - offers.total_discount
        assert all(t.gst >= 0 for t in taxes)


# ---------------------------------------------------------------- real bills
@pytest.mark.db
def test_real_bill_gst_adds_up_and_fresh_milk_is_exempt(db, cart_id):
    milk = pick(db, "product_type = 'Milk' AND stock_qty >= 5")
    soap = pick(db, "gst_rate = 18 AND stock_qty >= 5")
    tea = pick(db, "category = 'Beverages' AND gst_rate = 5 AND stock_qty >= 10 AND current_price BETWEEN 100 AND 400")
    for pid, q in ((milk, 2), (soap, 1), (tea, 3)):
        assert update_cart(cart_id, pid, q).ok
    b = compute_bill(cart_id, today=TODAY)
    by = {l.product_id: l for l in b.lines}
    assert by[milk].gst_rate == 0 and by[milk].gst == ZERO
    assert by[soap].gst > 0
    assert sum((l.discount_share for l in b.lines), ZERO) == b.discount_total
    taxable = sum((t.taxable_value for t in b.tax_breakup), ZERO)
    assert taxable + b.gst_total == b.final_total
    assert b.gst_total == sum((t.cgst + t.sgst for t in b.tax_breakup), ZERO)


@pytest.mark.db
def test_checkout_stores_gst(db, cart_id, restore_inventory):
    pid = pick(db, "gst_rate = 18 AND stock_qty >= 5")
    update_cart(cart_id, pid, 2)
    r = checkout(cart_id, today=TODAY)
    stored = db.execute(text("SELECT gst_total, line_items FROM orders WHERE order_id = :o"),
                        {"o": r.order.order_id}).one()
    assert stored[0] == r.order.gst_total > 0
    assert stored[1][0]["gst_rate"] == "18.00"


@pytest.mark.db
def test_every_product_has_a_valid_gst_slab(db):
    rates = {r[0] for r in db.execute(text("SELECT DISTINCT gst_rate FROM products")).all()}
    assert rates <= {D(0), D(5), D(18), D(40)} and len(rates) == 4
