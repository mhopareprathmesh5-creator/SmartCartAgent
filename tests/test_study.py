"""User-study mode: timing + automatic scoring (a manual-mode run driven through the API)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from smartcart import study
from smartcart.api.main import app
from tests.conftest import delete_session

pytestmark = pytest.mark.db
client = TestClient(app)


@pytest.fixture
def cleanup():
    yield
    with study.get_engine().connect() as conn:
        sessions = [r[0] for r in conn.execute(text("SELECT session_id FROM study_runs WHERE participant LIKE 'pytest%'"))]
    for s in sessions:
        delete_session(s)
    study.delete_runs("pytest")


def test_manual_run_is_timed_and_scored_by_code(db, cleanup):
    run = client.post("/study/runs", json={"participant": "pytest-P1", "mode": "manual", "task_id": "B"}).json()
    cart = run["cart_id"]
    # do task B by hand: atta, toor dal, sunflower oil, 2 noodles (first in-stock hit of each search)
    for query, qty in [("atta", 1), ("toor dal", 1), ("sunflower oil", 1), ("maggi masala 2 minute", 2)]:
        hit = next(h for h in client.get("/products/search", params={"q": query}).json() if h["in_stock"])
        assert client.put(f"/carts/{cart}/items/{hit['product_id']}", json={"quantity": qty}).json()["ok"]
    done = client.post(f"/study/runs/{run['run_id']}/finish", json={}).json()
    assert done["success"] is True and float(done["seconds"]) >= 0, done["checks"]
    assert [c["check"] for c in done["checks"]][-1] == "total ≤ ₹600.00"
    assert client.post(f"/study/runs/{run['run_id']}/finish", json={}).status_code == 422   # only once
    s = client.get("/study/summary").json()
    assert s["modes"]["manual"]["runs"] >= 1


def test_wrong_cart_fails_the_task(db, cleanup):
    run = client.post("/study/runs", json={"participant": "pytest-P2", "mode": "manual", "task_id": "A"}).json()
    done = client.post(f"/study/runs/{run['run_id']}/finish", json={}).json()     # empty cart
    assert done["success"] is False and not any(c["passed"] for c in done["checks"])
