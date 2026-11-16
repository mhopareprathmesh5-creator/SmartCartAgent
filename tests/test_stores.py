"""Multi-store comparison + password/token helpers."""
import time
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from smartcart import auth
from smartcart.tools import compare_stores, compute_bill, update_cart
from tests.conftest import pick
from tests.test_offers import TODAY


def test_password_hash_and_tokens():
    h = auth.hash_password("secret")
    assert auth.verify_password("secret", h) and not auth.verify_password("Secret", h)
    user = auth.StaffUser("asha", "Asha", "staff")
    token = auth.issue_token(user)
    assert auth.read_token(token) == user
    payload, sig = token.split(".")
    with pytest.raises(auth.AuthError):                      # tampered payload (e.g. role changed)
        auth.read_token(payload[:-2] + "xx." + sig)
    with pytest.raises(auth.AuthError):                      # expired
        auth.read_token(auth.issue_token(user, now=time.time() - 13 * 3600))


@pytest.mark.db
def test_comparison_prices_every_store_from_the_database(db, cart_id):
    pids = [pick(db, "stock_qty >= 10 AND category = 'Beverages'"), pick(db, "stock_qty >= 10 AND category = 'Baby Care'")]
    for p in pids:
        assert update_cart(cart_id, p, 2).ok
    r = compare_stores(cart_id, today=TODAY)
    home = r.quotes[0]
    bill = compute_bill(cart_id, today=TODAY)
    assert home.is_home and home.final_total == bill.final_total and home.complete
    for q in r.quotes[1:]:
        rows = db.execute(text("SELECT product_id, price, stock_qty FROM store_prices WHERE store_id = :s "
                               "AND product_id = ANY(:p)"), {"s": q.store_id, "p": pids}).all()
        ok = [(p, price) for p, price, stock in rows if stock >= 2]
        assert q.items_available == len(ok) and q.complete == (len(ok) == 2)
        assert q.subtotal == sum((price * 2 for _, price in ok), D("0"))
        assert q.final_total == q.subtotal - q.discount
        if not q.accepts_coupons:
            assert q.discount == 0 and q.coupons == []


@pytest.mark.db
def test_incomplete_store_is_never_recommended(db, cart_id):
    # a product the Sangli competitor does not carry: Sangli can never be "best"
    pid = db.execute(text("""SELECT v.product_id FROM v_store_catalog v WHERE v.stock_qty >= 10 AND NOT EXISTS
        (SELECT 1 FROM store_prices sp JOIN stores s USING (store_id)
         WHERE sp.product_id = v.product_id AND s.name LIKE 'FreshBasket%') ORDER BY v.product_id LIMIT 1""")).scalar()
    update_cart(cart_id, pid, 1)
    r = compare_stores(cart_id, today=TODAY)
    sangli = next(q for q in r.quotes if q.name.startswith("FreshBasket"))
    assert not sangli.complete and sangli.missing[0].reason == "not_carried"
    assert r.best_store_id != sangli.store_id
    best = next(q for q in r.quotes if q.store_id == r.best_store_id)
    assert best.complete and all(best.final_total <= q.final_total for q in r.quotes if q.complete)
    assert r.saving_vs_home == r.quotes[0].final_total - best.final_total


@pytest.mark.db
def test_home_store_data_is_unaffected_by_other_stores(db):
    assert db.execute(text("SELECT count(*) FROM v_store_catalog")).scalar() == 849
    assert db.execute(text("SELECT count(*) FROM stores WHERE is_home")).scalar() == 1
    assert db.execute(text("SELECT count(*) FROM store_prices sp JOIN products p USING (product_id) "
                           "WHERE sp.price > p.base_price")).scalar() == 0      # never above MRP
