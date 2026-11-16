import uuid

import pytest
from sqlalchemy import text

from smartcart.agent.memory import delete_thread_memory, ensure_memory_tables
from smartcart.db import get_engine
from smartcart.tools import create_cart


def _db_available() -> bool:
    try:
        with get_engine().connect() as conn:
            return conn.execute(text("SELECT count(*) FROM products")).scalar() > 0
    except Exception:
        return False


DB_UP = _db_available()
if DB_UP:
    ensure_memory_tables()


def pytest_collection_modifyitems(config, items):
    if DB_UP:
        return
    skip = pytest.mark.skip(reason="seeded database not reachable (docker compose up -d, scripts 02-03)")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def db():
    with get_engine().begin() as conn:
        yield conn


@pytest.fixture
def cart_id():
    """A fresh ACTIVE cart, deleted (with its items and any order) after the test."""
    session = f"pytest-{uuid.uuid4().hex[:8]}"
    cid = create_cart(session)
    yield cid
    delete_session(session)


def delete_session(session: str):
    with get_engine().begin() as conn:
        delete_thread_memory(conn, session)
        conn.execute(text("DELETE FROM orders WHERE cart_id IN "
                          "(SELECT cart_id FROM carts WHERE session_id = :s)"), {"s": session})
        conn.execute(text("DELETE FROM carts WHERE session_id = :s"), {"s": session})


@pytest.fixture
def restore_inventory():
    """Snapshot inventory before the test and put back any stock/price it changed."""
    with get_engine().connect() as conn:
        before = conn.execute(text("SELECT product_id, stock_qty, current_price FROM inventory")).all()
    yield
    with get_engine().begin() as conn:
        conn.execute(text("""
            UPDATE inventory i SET stock_qty = s.stock_qty, current_price = s.current_price
            FROM (SELECT unnest(CAST(:ids AS int[])) AS product_id,
                         unnest(CAST(:stock AS int[])) AS stock_qty,
                         unnest(CAST(:price AS numeric[])) AS current_price) s
            WHERE i.product_id = s.product_id
              AND (i.stock_qty <> s.stock_qty OR i.current_price <> s.current_price)
        """), {"ids": [r[0] for r in before], "stock": [r[1] for r in before],
               "price": [r[2] for r in before]})


def pick(conn, where: str, params=None) -> int:
    """product_id of the first product in v_store_catalog matching `where`."""
    pid = conn.execute(text(f"SELECT product_id FROM v_store_catalog WHERE {where} "
                            "ORDER BY product_id LIMIT 1"), params or {}).scalar()
    assert pid is not None, f"no product matches {where}"
    return pid
