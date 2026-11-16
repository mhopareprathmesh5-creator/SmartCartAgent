"""HTTP API tests (FastAPI TestClient — no server needs to be running)."""
import uuid
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from smartcart.api.main import app
from tests.conftest import delete_session, pick

pytestmark = pytest.mark.db
client = TestClient(app)


@pytest.fixture
def session():
    s = f"pytest-api-{uuid.uuid4().hex[:8]}"
    yield s
    delete_session(s)


def test_health():
    r = client.get("/health")
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok" and body["products"] == 849
    assert isinstance(body["llm_configured"], bool)


def test_search_returns_location_and_money_as_strings():
    r = client.get("/products/search", params={"q": "toned milk", "limit": 2})
    assert r.status_code == 200
    top = r.json()[0]
    assert top["product_type"] == "Milk"
    assert top["shelf_code"].startswith("A2-")
    assert isinstance(top["price"], str) and D(top["price"]) > 0     # exact decimal, not float


def test_search_validation():
    assert client.get("/products/search", params={"q": ""}).status_code == 422
    assert client.get("/products/search", params={"q": "milk", "limit": 0}).status_code == 422


def test_stock_and_substitutes(db):
    oos = pick(db, "stock_qty = 0")
    s = client.get(f"/products/{oos}/stock").json()
    assert s["in_stock"] is False
    subs = client.get(f"/products/{oos}/substitutes").json()
    assert subs and all(x["stock_qty"] > 0 for x in subs)


def test_unknown_product_is_404():
    assert client.get("/products/999999/stock").status_code == 404
    assert client.get("/products/999999/substitutes").status_code == 404


def test_coupons_listed():
    codes = {c["code"] for c in client.get("/coupons").json()}
    assert len(codes) == 19 and {"SAVE10", "BEV75", "MONSOON20"} <= codes


def test_full_shopping_flow(db, session, restore_inventory):
    cart_id = client.post("/carts", json={"session_id": session}).json()["cart_id"]

    pid = pick(db, "category = 'Beverages' AND stock_qty >= 20 AND current_price BETWEEN 100 AND 400")
    r = client.put(f"/carts/{cart_id}/items/{pid}", json={"quantity": 4})
    assert r.status_code == 200 and r.json()["ok"] and r.json()["quantity"] == 4

    oos = pick(db, "stock_qty = 0")
    refused = client.put(f"/carts/{cart_id}/items/{oos}", json={"quantity": 1}).json()
    assert refused["ok"] is False and refused["available_stock"] == 0

    bill = client.get(f"/carts/{cart_id}/bill").json()
    assert D(bill["final_total"]) == D(bill["subtotal"]) - D(bill["discount_total"])
    offers = client.get(f"/carts/{cart_id}/offers").json()
    assert offers["total_discount"] == bill["discount_total"]

    done = client.post(f"/carts/{cart_id}/checkout").json()
    assert done["ok"] and done["order"]["final_total"] == bill["final_total"]

    order = client.get(f"/orders/{done['order']['order_id']}").json()
    assert order["final_total"] == bill["final_total"] and order["cart_id"] == cart_id

    # cart is closed now
    assert client.put(f"/carts/{cart_id}/items/{pid}", json={"quantity": 1}).status_code == 409


def test_chat_without_llm_key_is_503(monkeypatch):
    import smartcart.api.main as api
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(api, "_assistant", None)
    r = client.post("/chat", json={"session_id": "x", "message": "hi"})
    assert r.status_code == 503 and "GOOGLE_API_KEY" in r.json()["detail"]


def test_chat_endpoint_with_scripted_llm(monkeypatch, session):
    import smartcart.api.main as api
    from langchain_core.messages import AIMessage
    from smartcart.agent import ShoppingAssistant
    from tests.test_agent import ScriptedLLM

    monkeypatch.setattr(api, "_assistant", ShoppingAssistant(llm=ScriptedLLM(script=[AIMessage("Hello!")])))
    r = client.post("/chat", json={"session_id": session, "message": "hi"})
    body = r.json()
    assert r.status_code == 200 and body["reply"] == "Hello!" and body["grounded"] is True
    assert body["bill"]["final_total"] == "0.00"


def test_session_endpoints_share_the_agents_cart(monkeypatch, db, session, restore_inventory):
    """UI actions (GET/PUT/checkout on /sessions) work on the same cart the agent fills."""
    import smartcart.api.main as api
    from langchain_core.messages import AIMessage
    from smartcart.agent import ShoppingAssistant
    from tests.test_agent import ScriptedLLM, call

    pid = pick(db, "stock_qty >= 20 AND current_price < 200")
    other = pick(db, "stock_qty >= 20 AND product_id <> :p", {"p": pid})
    bot = ShoppingAssistant(llm=ScriptedLLM(script=[call("update_cart", product_id=pid, quantity=2),
                                                    AIMessage("Added.")]))
    monkeypatch.setattr(api, "_assistant", bot)

    assert client.get(f"/sessions/{session}").status_code == 404          # no chat yet
    first = client.post("/chat", json={"session_id": session, "message": "add 2"}).json()

    view = client.get(f"/sessions/{session}").json()
    assert view["cart_id"] == first["cart_id"] and view["bill"]["item_count"] == 2
    item = view["bill"]["items"][0]
    assert item["aisle_no"] >= 1 and item["shelf_code"].startswith(f"A{item['aisle_no']}-")

    r = client.put(f"/sessions/{session}/items/{other}", json={"quantity": 1}).json()
    assert r["update"]["ok"] and r["session"]["bill"]["item_count"] == 3
    r = client.put(f"/sessions/{session}/items/{pid}", json={"quantity": 0}).json()
    assert r["session"]["bill"]["item_count"] == 1
    assert client.put(f"/sessions/{session}/items/{pid}", json={"quantity": -1}).status_code == 422

    done = client.post(f"/sessions/{session}/checkout").json()
    assert done["result"]["ok"] and done["result"]["order"]["final_total"]
    assert done["session"]["cart_id"] != first["cart_id"] and done["session"]["bill"]["item_count"] == 0
    assert bot.session(session)["cart_id"] == done["session"]["cart_id"]   # agent continues on the new cart

    assert client.post("/sessions/unknown-session/checkout").status_code == 404


def test_budget_plan_and_swaps_through_the_session(monkeypatch, db, session):
    import smartcart.api.main as api
    from langchain_core.messages import AIMessage
    from smartcart.agent import ShoppingAssistant
    from tests.test_agent import ScriptedLLM, call

    tea = pick(db, "product_type = 'Leaf & Dust Tea' AND stock_qty >= 5 AND current_price > 200")
    bot = ShoppingAssistant(llm=ScriptedLLM(script=[call("update_cart", product_id=tea, quantity=2),
                                                    AIMessage("Added.")]))
    monkeypatch.setattr(api, "_assistant", bot)
    client.post("/chat", json={"session_id": session, "message": "add tea"})

    assert client.get(f"/sessions/{session}/budget-plan").status_code == 422          # no budget yet
    total = D(client.get(f"/sessions/{session}").json()["bill"]["final_total"])
    view = client.put(f"/sessions/{session}/budget", json={"amount": str(total - 20)}).json()
    assert view["budget"] == str(total - 20) and "over_budget_by" in view["bill"]
    assert bot.graph.get_state(bot._config(session)).values["budget"] == view["budget"]   # agent sees it

    plan = client.get(f"/sessions/{session}/budget-plan").json()
    assert plan["feasible"] and len(plan["swaps"]) == 1
    s = plan["swaps"][0]
    done = client.post(f"/sessions/{session}/swaps", json={"swaps": [
        {"from_product_id": s["from_product_id"], "to_product_id": s["to_product_id"], "quantity": s["quantity"]}]}).json()
    assert done["results"][0]["ok"]
    assert done["session"]["bill"]["final_total"] == plan["new_total"]
    assert "budget_remaining" in done["session"]["bill"]

    assert client.put(f"/sessions/{session}/budget", json={"amount": None}).json()["budget"] is None
    assert client.put(f"/sessions/{session}/budget", json={"amount": "-5"}).status_code == 422


def test_cart_errors(session):
    assert client.get("/carts/999999/bill").status_code == 404
    assert client.post("/carts", json={"session_id": ""}).status_code == 422
    cart_id = client.post("/carts", json={"session_id": session}).json()["cart_id"]
    assert client.put(f"/carts/{cart_id}/items/1", json={"quantity": -1}).status_code == 422
    assert client.put(f"/carts/{cart_id}/items/1", json={"quantity": 1, "mode": "x"}).status_code == 422
    assert client.delete(f"/carts/{cart_id}/items/999999").status_code == 404
    assert client.get("/orders/999999").status_code == 404
