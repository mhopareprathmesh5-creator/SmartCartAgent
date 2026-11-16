"""update_cart(), compute_bill(), optimize_offers() against the seeded database."""
from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from smartcart.db import get_engine
from smartcart.tools import (CartNotActive, CartNotFound, ProductNotFound, checkout,
                             compute_bill, optimize_offers, update_cart)
from tests.conftest import pick

pytestmark = pytest.mark.db
TODAY = date(2026, 10, 12)


def cart_qty(db, cart_id, pid):
    return db.execute(text("SELECT quantity FROM cart_items WHERE cart_id=:c AND product_id=:p"),
                      {"c": cart_id, "p": pid}).scalar()


# ---------------------------------------------------------------- update_cart
def test_set_add_and_remove(db, cart_id):
    pid = pick(db, "stock_qty >= 10")
    assert update_cart(cart_id, pid, 2).quantity == 2
    assert update_cart(cart_id, pid, 3, mode="add").quantity == 5
    assert update_cart(cart_id, pid, 1).quantity == 1           # set overrides
    r = update_cart(cart_id, pid, 0)
    assert r.ok and r.quantity == 0
    assert cart_qty(db, cart_id, pid) is None


def test_cannot_add_out_of_stock_product(db, cart_id):
    pid = pick(db, "stock_qty = 0")
    r = update_cart(cart_id, pid, 1)
    assert not r.ok and r.available_stock == 0 and "out of stock" in r.message
    assert cart_qty(db, cart_id, pid) is None


def test_cannot_exceed_stock_and_cart_is_unchanged(db, cart_id):
    pid = pick(db, "stock_qty BETWEEN 2 AND 9")
    stock = db.execute(text("SELECT stock_qty FROM inventory WHERE product_id=:p"), {"p": pid}).scalar()
    update_cart(cart_id, pid, 1)
    r = update_cart(cart_id, pid, stock, mode="add")              # 1 + stock > stock
    assert not r.ok and r.quantity == 1 and r.available_stock == stock
    assert cart_qty(db, cart_id, pid) == 1


def test_invalid_arguments(db, cart_id):
    pid = pick(db, "stock_qty >= 10")
    with pytest.raises(ValueError):
        update_cart(cart_id, pid, -1)
    with pytest.raises(ValueError):
        update_cart(cart_id, pid, 0, mode="add")
    with pytest.raises(ValueError):
        update_cart(cart_id, pid, 1, mode="replace")
    with pytest.raises(ProductNotFound):
        update_cart(cart_id, 999_999, 1)
    with pytest.raises(CartNotFound):
        update_cart(999_999, pid, 1)


def test_checked_out_cart_cannot_change(db, cart_id):
    pid = pick(db, "stock_qty >= 10")
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE carts SET status='CHECKED_OUT' WHERE cart_id=:c"), {"c": cart_id})
    with pytest.raises(CartNotActive):
        update_cart(cart_id, pid, 1)


# ---------------------------------------------------------------- compute_bill
def test_empty_cart_bill(cart_id):
    b = compute_bill(cart_id, today=TODAY)
    assert b.lines == [] and b.subtotal == b.final_total == D("0.00") and b.applied_coupons == []


def test_bill_is_grounded_in_inventory_prices(db, cart_id):
    pids = [pick(db, "category = :c AND stock_qty >= 10", {"c": c})
            for c in ("Beverages", "Snacks & Branded Foods", "Fruits & Vegetables")]
    for i, pid in enumerate(pids, start=1):
        update_cart(cart_id, pid, i)
    b = compute_bill(cart_id, today=TODAY)

    expected = db.execute(text("""
        SELECT sum(ci.quantity * i.current_price) FROM cart_items ci
        JOIN inventory i USING (product_id) WHERE ci.cart_id = :c"""), {"c": cart_id}).scalar()
    assert b.subtotal == expected
    assert b.item_count == 6
    assert b.final_total == b.subtotal - b.discount_total
    assert b.discount_total == sum((a.discount for a in b.applied_coupons), D("0"))
    assert b.savings_vs_mrp >= 0


def test_bill_follows_live_price_change(db, cart_id):
    """If the store changes a price, the next bill reflects it — nothing is cached in the cart."""
    pid = pick(db, "stock_qty >= 10")
    update_cart(cart_id, pid, 2)
    before = compute_bill(cart_id, today=TODAY).subtotal
    with get_engine().begin() as conn:
        old = conn.execute(text("SELECT current_price FROM inventory WHERE product_id=:p"), {"p": pid}).scalar()
        conn.execute(text("UPDATE inventory SET current_price = current_price + 10 WHERE product_id=:p"), {"p": pid})
    try:
        assert compute_bill(cart_id, today=TODAY).subtotal == before + D("20.00")
    finally:
        with get_engine().begin() as conn:
            conn.execute(text("UPDATE inventory SET current_price=:o WHERE product_id=:p"), {"o": old, "p": pid})


def test_bill_warns_when_item_goes_out_of_stock(db, cart_id):
    pid = pick(db, "stock_qty >= 10")
    update_cart(cart_id, pid, 1)
    with get_engine().begin() as conn:
        old = conn.execute(text("SELECT stock_qty FROM inventory WHERE product_id=:p"), {"p": pid}).scalar()
        conn.execute(text("UPDATE inventory SET stock_qty = 0 WHERE product_id=:p"), {"p": pid})
    try:
        assert any("out of stock" in w for w in compute_bill(cart_id, today=TODAY).warnings)
    finally:
        with get_engine().begin() as conn:
            conn.execute(text("UPDATE inventory SET stock_qty=:o WHERE product_id=:p"), {"o": old, "p": pid})


def test_bill_applies_coupons_and_respects_conflicts(db, cart_id):
    """₹300+ of Beverages unlocks BEV75; SAVE10 conflicts with it — never both."""
    pid = pick(db, "category = 'Beverages' AND stock_qty >= 20 AND current_price BETWEEN 100 AND 400")
    price = db.execute(text("SELECT current_price FROM inventory WHERE product_id=:p"), {"p": pid}).scalar()
    qty = int(D(300) // price) + 1
    update_cart(cart_id, pid, qty)
    b = compute_bill(cart_id, today=TODAY)
    applied = {a.code for a in b.applied_coupons}
    assert not {"SAVE10", "BEV75"} <= applied
    assert applied & {"SAVE10", "BEV75"}
    assert b.discount_total > 0


def test_optimize_offers_matches_bill(db, cart_id):
    pid = pick(db, "category = 'Fruits & Vegetables' AND stock_qty >= 20")
    update_cart(cart_id, pid, 15)
    assert optimize_offers(cart_id, today=TODAY).total_discount == compute_bill(cart_id, today=TODAY).discount_total


def test_unknown_cart():
    with pytest.raises(CartNotFound):
        compute_bill(999_999)
    with pytest.raises(CartNotFound):
        optimize_offers(999_999)
    with pytest.raises(CartNotFound):
        checkout(999_999)


# ---------------------------------------------------------------- checkout
def stock_of(db, pid):
    return db.execute(text("SELECT stock_qty FROM inventory WHERE product_id=:p"), {"p": pid}).scalar()


def test_checkout_places_order_and_decrements_stock(db, cart_id, restore_inventory):
    a = pick(db, "category = 'Beverages' AND stock_qty >= 20")
    b = pick(db, "category = 'Baby Care' AND stock_qty >= 20")
    update_cart(cart_id, a, 3)
    update_cart(cart_id, b, 1)
    bill = compute_bill(cart_id)
    stock_a, stock_b = stock_of(db, a), stock_of(db, b)

    r = checkout(cart_id)
    assert r.ok and r.problems == []
    o = r.order
    assert (o.subtotal, o.discount_total, o.final_total) == (bill.subtotal, bill.discount_total, bill.final_total)
    assert o.applied_coupons == [c.code for c in bill.applied_coupons]

    with get_engine().connect() as conn:
        assert stock_of(conn, a) == stock_a - 3 and stock_of(conn, b) == stock_b - 1
        status = conn.execute(text("SELECT status FROM carts WHERE cart_id=:c"), {"c": cart_id}).scalar()
        row = conn.execute(text("SELECT final_total, line_items FROM orders WHERE order_id=:o"),
                           {"o": o.order_id}).one()
    assert status == "CHECKED_OUT"
    assert row[0] == o.final_total and len(row[1]) == 2

    with pytest.raises(CartNotActive):          # cannot check out (or edit) twice
        checkout(cart_id)


def test_checkout_empty_cart_is_refused(cart_id):
    r = checkout(cart_id)
    assert not r.ok and r.order is None and r.problems == ["Cart is empty"]


def test_checkout_short_of_stock_writes_nothing(db, cart_id, restore_inventory):
    pid = pick(db, "stock_qty >= 10")
    update_cart(cart_id, pid, 5)
    with get_engine().begin() as conn:     # stock drops after the item was added
        conn.execute(text("UPDATE inventory SET stock_qty = 2 WHERE product_id=:p"), {"p": pid})

    r = checkout(cart_id)
    assert not r.ok and "only 2 in stock" in r.problems[0]
    with get_engine().connect() as conn:
        assert stock_of(conn, pid) == 2
        assert conn.execute(text("SELECT status FROM carts WHERE cart_id=:c"), {"c": cart_id}).scalar() == "ACTIVE"
        assert conn.execute(text("SELECT count(*) FROM orders WHERE cart_id=:c"), {"c": cart_id}).scalar() == 0
