"""locate(), check_inventory(), find_substitutes() against the seeded database."""
import pytest
from sqlalchemy import text

from smartcart.tools import ProductNotFound, check_inventory, find_substitutes, locate
from tests.conftest import pick

pytestmark = pytest.mark.db


# ---------------------------------------------------------------- locate
@pytest.mark.parametrize("query,expected_type", [
    ("milk", "Milk"),
    ("toned milk", "Milk"),
    ("oats", "Oats & Porridge"),
    ("basmati rice", "Basmati Rice"),
    ("cofee", "Ground Coffee"),          # typo tolerated
])
def test_locate_finds_the_right_kind_of_product(query, expected_type):
    results = locate(query)
    assert results, f"nothing found for {query!r}"
    assert results[0].product_type == expected_type


def test_locate_matches_brand_and_name_together():
    top = locate("amul butter")[0]
    assert top.brand == "Amul" and "butter" in top.name.lower()


def test_locate_returns_nothing_for_nonsense_or_empty():
    assert locate("xqzv plmk") == []
    assert locate("   ") == []


def test_locate_values_match_database(db):
    """Grounding: every number locate() returns is exactly what the DB holds."""
    for r in locate("coffee", limit=10):
        row = db.execute(text("""
            SELECT i.current_price, i.stock_qty, m.aisle_no, m.shelf_code, p.base_price
            FROM inventory i JOIN store_map m USING (product_id) JOIN products p USING (product_id)
            WHERE product_id = :pid"""), {"pid": r.product_id}).one()
        assert (r.price, r.stock_qty, r.aisle_no, r.shelf_code, r.mrp) == tuple(row)


def test_locate_respects_limit():
    assert len(locate("milk", limit=3)) == 3


# ---------------------------------------------------------------- check_inventory
def test_check_inventory_in_stock(db):
    pid = pick(db, "stock_qty >= 10")
    s = check_inventory(pid, quantity=2)
    assert s.in_stock and s.can_fulfil and not s.low_stock


def test_check_inventory_out_of_stock(db):
    s = check_inventory(pick(db, "stock_qty = 0"))
    assert not s.in_stock and not s.can_fulfil and not s.low_stock


def test_check_inventory_more_than_available(db):
    pid = pick(db, "stock_qty BETWEEN 1 AND 9")
    stock = check_inventory(pid).stock_qty
    s = check_inventory(pid, quantity=stock + 1)
    assert s.in_stock and not s.can_fulfil and s.low_stock


def test_check_inventory_unknown_product():
    with pytest.raises(ProductNotFound):
        check_inventory(999_999)


# ---------------------------------------------------------------- find_substitutes
def test_every_out_of_stock_product_has_an_in_stock_same_type_substitute(db):
    oos = db.execute(text("SELECT product_id, product_type FROM v_store_catalog WHERE stock_qty = 0")).all()
    assert len(oos) > 0
    for pid, ptype in oos:
        subs = find_substitutes(pid)
        assert subs, f"no substitute for product {pid}"
        assert subs[0].match == "same_type" and subs[0].product_type == ptype
        assert all(s.stock_qty > 0 and s.product_id != pid for s in subs)


def test_substitutes_rank_same_type_first_then_closest_price(db):
    pid = pick(db, "stock_qty = 0")
    subs = find_substitutes(pid, limit=10)
    tiers = [0 if s.match == "same_type" else 1 for s in subs]
    assert tiers == sorted(tiers)
    same_type = [abs(s.price_difference) for s in subs if s.match == "same_type"]
    original = check_inventory(pid).price
    rel = [d / original for d in same_type]
    assert rel == sorted(rel)


def test_substitutes_respect_requested_quantity(db):
    pid = pick(db, "stock_qty = 0")
    for s in find_substitutes(pid, quantity=50, limit=10):
        assert s.stock_qty >= 50


def test_substitutes_unknown_product():
    with pytest.raises(ProductNotFound):
        find_substitutes(999_999)
