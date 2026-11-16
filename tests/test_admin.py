"""Store admin: price/stock edits, coupon switches, and their immediate effect on bills."""
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from smartcart import admin
from smartcart.api.main import app
from smartcart.db import get_engine
from smartcart.tools import ProductNotFound, compute_bill, update_cart
from tests.conftest import pick
from tests.test_offers import TODAY

pytestmark = pytest.mark.db
client = TestClient(app)


@pytest.fixture
def restore_coupons():
    with get_engine().connect() as conn:
        before = conn.execute(text("SELECT code, is_active FROM coupons")).all()
    yield
    with get_engine().begin() as conn:
        for code, active in before:
            conn.execute(text("UPDATE coupons SET is_active = :a WHERE code = :c"), {"a": active, "c": code})


def test_price_change_shows_up_in_an_existing_cart(db, cart_id, restore_inventory):
    pid = pick(db, "stock_qty >= 10 AND current_price > 20")
    update_cart(cart_id, pid, 2)
    before = compute_bill(cart_id, today=TODAY).subtotal
    row = admin.update_inventory(pid, price=admin.list_inventory_row(pid)["price"] - D("5.00"))
    assert compute_bill(cart_id, today=TODAY).subtotal == before - D("10.00")
    assert row["price"] == admin.list_inventory_row(pid)["price"]


def test_price_rules(db, restore_inventory):
    pid = pick(db, "stock_qty >= 1")
    mrp = admin.list_inventory_row(pid)["mrp"]
    with pytest.raises(ValueError, match="above the MRP"):
        admin.update_inventory(pid, price=mrp + 1)
    with pytest.raises(ValueError):
        admin.update_inventory(pid, price=D("0"))
    with pytest.raises(ValueError):
        admin.update_inventory(pid, stock_qty=-1)
    with pytest.raises(ValueError):
        admin.update_inventory(pid)
    with pytest.raises(ProductNotFound):
        admin.update_inventory(999_999, stock_qty=1)
    assert admin.update_inventory(pid, price=mrp)["price"] == mrp      # exactly MRP is allowed


def test_stock_to_zero_blocks_adding_and_warns_existing_carts(db, cart_id, restore_inventory):
    pid = pick(db, "stock_qty >= 10")
    update_cart(cart_id, pid, 1)
    admin.update_inventory(pid, stock_qty=0)
    assert any("out of stock" in w for w in compute_bill(cart_id, today=TODAY).warnings)
    assert not update_cart(cart_id, pid, 2).ok


def test_disabling_a_coupon_removes_it_from_the_bill(db, cart_id, restore_coupons):
    pid = pick(db, "category = 'Beverages' AND stock_qty >= 20 AND current_price BETWEEN 100 AND 400")
    price = admin.list_inventory_row(pid)["price"]
    update_cart(cart_id, pid, int(D(320) // price) + 1)
    with get_engine().begin() as conn:             # make BEV75 the only candidate
        conn.execute(text("UPDATE coupons SET is_active = false WHERE code <> 'BEV75'"))
    assert [a.code for a in compute_bill(cart_id).applied_coupons] == ["BEV75"]
    assert admin.set_coupon_active("BEV75", False)["status"] == "disabled"
    assert compute_bill(cart_id).applied_coupons == []


def test_inventory_listing_filters():
    out = admin.list_inventory(filter="out", limit=200)
    assert out["total"] == 51 and all(r["stock_qty"] == 0 for r in out["items"])
    low = admin.list_inventory(filter="low", limit=200)
    assert all(1 <= r["stock_qty"] <= 9 for r in low["items"])
    milk = admin.list_inventory(q="toned milk")
    assert milk["total"] >= 1 and all("milk" in r["name"].lower() for r in milk["items"])
    with pytest.raises(ValueError):
        admin.list_inventory(filter="weird")


def test_coupon_list_shows_status_and_conflicts():
    by = {c["code"]: c for c in admin.list_coupons()}
    assert by["TEA40"]["status"] == "disabled"
    assert "BEV75" in by["SAVE10"]["conflicts_with"]


# ---------------------------------------------------------------- HTTP (login + roles)
def login(username, password):
    r = client.post("/admin/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def clean_audit():
    with get_engine().connect() as conn:
        last = conn.execute(text("SELECT coalesce(max(audit_id), 0) FROM admin_audit")).scalar()
    yield
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM admin_audit WHERE audit_id > :a"), {"a": last})


def test_admin_endpoints(db, restore_inventory, restore_coupons, clean_audit):
    h = login("manager", "manager123")
    s = client.get("/admin/summary", headers=h).json()
    assert s["products"] == 849 and s["out_of_stock"] == 51
    inv = client.get("/admin/inventory", params={"filter": "low", "limit": 5}, headers=h).json()
    assert len(inv["items"]) == 5 and isinstance(inv["items"][0]["price"], str)
    pid = inv["items"][0]["product_id"]
    assert client.patch(f"/admin/inventory/{pid}", json={"stock_qty": 40}, headers=h).json()["stock_qty"] == 40
    assert client.patch(f"/admin/inventory/{pid}", json={"price": "999999"}, headers=h).status_code == 422
    assert client.patch("/admin/coupons/SAVE10", json={"is_active": False}, headers=h).json()["status"] == "disabled"
    assert client.patch("/admin/coupons/NOPE", json={"is_active": False}, headers=h).status_code == 404
    assert isinstance(client.get("/admin/orders", headers=h).json(), list)


def test_admin_requires_login(db):
    assert client.get("/admin/summary").status_code == 401
    assert client.get("/admin/inventory", headers={"Authorization": "Bearer forged.token"}).status_code == 401
    assert client.post("/admin/login", json={"username": "manager", "password": "wrong"}).status_code == 401
    assert client.get("/admin/me", headers=login("staff", "staff123")).json()["role"] == "staff"


def test_staff_can_restock_but_not_reprice_and_changes_are_audited(db, restore_inventory, restore_coupons,
                                                                     clean_audit):
    staff, manager = login("staff", "staff123"), login("manager", "manager123")
    pid = pick(db, "stock_qty >= 10 AND current_price > 20")
    price = admin.list_inventory_row(pid)["price"]
    assert client.patch(f"/admin/inventory/{pid}", json={"stock_qty": 77}, headers=staff).status_code == 200
    assert client.patch(f"/admin/inventory/{pid}", json={"price": str(price - 1)}, headers=staff).status_code == 403
    assert client.patch("/admin/coupons/SAVE10", json={"is_active": False}, headers=staff).status_code == 403
    assert admin.list_inventory_row(pid)["price"] == price           # the refused change did nothing
    assert client.patch(f"/admin/inventory/{pid}", json={"price": str(price - 1)}, headers=manager).status_code == 200
    log = client.get("/admin/audit", params={"limit": 2}, headers=manager).json()
    assert [(e["username"], e["action"]) for e in log] == [("manager", "price"), ("staff", "stock")]
    assert log[0]["detail"]["from"] == str(price) and log[0]["detail"]["to"] == str(price - 1)
