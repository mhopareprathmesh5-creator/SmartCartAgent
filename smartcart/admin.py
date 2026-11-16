"""Store-staff operations: inventory (price / stock), coupons on/off, sales summary.

Deliberately NOT exposed as agent tools: the LLM can read prices but has no way to
change them. Staff changes take effect immediately everywhere, because carts store no
prices — every bill is recomputed from `inventory` (the core design rule).
"""
import json
from decimal import Decimal
from typing import Optional

from sqlalchemy import text

from smartcart.auth import StaffUser, require
from smartcart.db import DEFAULT_STORE_ID, get_engine
from smartcart.tools.models import ProductNotFound, ToolError, money


class CouponNotFound(ToolError):
    pass


FILTERS = {
    "all": "TRUE",
    "out": "c.stock_qty = 0",
    "low": "c.stock_qty BETWEEN 1 AND 9",
}


def list_inventory(q: str = "", filter: str = "all", limit: int = 50, offset: int = 0,
                   store_id: int = DEFAULT_STORE_ID) -> dict:
    if filter not in FILTERS:
        raise ValueError(f"filter must be one of {sorted(FILTERS)}")
    where = [FILTERS[filter], "c.store_id = :store_id"]
    params = {"store_id": store_id, "limit": limit, "offset": offset}
    if q.strip():
        where.append("(lower(c.name) LIKE :q OR lower(c.brand) LIKE :q OR lower(c.product_type) LIKE :q)")
        params["q"] = f"%{q.strip().lower()}%"
    cond = " AND ".join(where)
    with get_engine().connect() as conn:
        total = conn.execute(text(f"SELECT count(*) FROM v_store_catalog c WHERE {cond}"), params).scalar_one()
        rows = conn.execute(text(f"""
            SELECT c.product_id, c.name, c.brand, c.category, c.product_type, c.mrp, c.current_price AS price,
                   c.stock_qty, c.gst_rate, c.aisle_no, c.shelf_code, i.updated_at
            FROM v_store_catalog c JOIN inventory i ON i.product_id = c.product_id AND i.store_id = c.store_id
            WHERE {cond}
            ORDER BY c.stock_qty = 0 DESC, c.aisle_no, c.name
            LIMIT :limit OFFSET :offset"""), params).mappings().all()
    return {"total": total, "items": [dict(r) for r in rows]}


def _audit(conn, by: Optional[StaffUser], action: str, target, detail: dict):
    if by is not None:
        conn.execute(text("""INSERT INTO admin_audit (username, role, action, target, detail)
                             VALUES (:u, :r, :a, :t, CAST(:d AS jsonb))"""),
                     {"u": by.username, "r": by.role, "a": action, "t": str(target),
                      "d": json.dumps(detail, default=str, ensure_ascii=False)})


def update_inventory(product_id: int, price: Optional[Decimal] = None, stock_qty: Optional[int] = None,
                     store_id: int = DEFAULT_STORE_ID, by: Optional[StaffUser] = None) -> dict:
    """Change the live selling price and/or stock of one product.

    Rules: price > 0 and never above MRP (selling above MRP is illegal in India);
    stock ≥ 0. Raises ValueError (→ HTTP 422) on violation. `by` = the logged-in staff
    member: only a manager may change a price, and every change is audited."""
    if price is None and stock_qty is None:
        raise ValueError("Nothing to update: give price and/or stock_qty")
    if by is not None and price is not None:
        require(by, "manager")
    with get_engine().begin() as conn:
        row = conn.execute(text("""
            SELECT p.base_price AS mrp, p.name, i.current_price, i.stock_qty
            FROM products p JOIN inventory i ON i.product_id = p.product_id
            WHERE p.product_id = :pid AND i.store_id = :store_id FOR UPDATE OF i
        """), {"pid": product_id, "store_id": store_id}).first()
        if row is None:
            raise ProductNotFound(f"No product with id {product_id}")
        sets, params = [], {"pid": product_id, "store_id": store_id}
        if price is not None:
            price = money(price)
            if price <= 0:
                raise ValueError("Price must be greater than 0")
            if price > row.mrp:
                raise ValueError(f"Price ₹{price} is above the MRP ₹{row.mrp}")
            sets.append("current_price = :price")
            params["price"] = price
        if stock_qty is not None:
            if stock_qty < 0:
                raise ValueError("Stock cannot be negative")
            sets.append("stock_qty = :stock")
            params["stock"] = stock_qty
        conn.execute(text(f"UPDATE inventory SET {', '.join(sets)}, updated_at = now() "
                          "WHERE product_id = :pid AND store_id = :store_id"), params)
        if price is not None and price != row.current_price:
            _audit(conn, by, "price", product_id, {"name": row.name, "from": row.current_price, "to": price})
        if stock_qty is not None and stock_qty != row.stock_qty:
            _audit(conn, by, "stock", product_id, {"name": row.name, "from": row.stock_qty, "to": stock_qty})
    return list_inventory_row(product_id, store_id)


def list_inventory_row(product_id: int, store_id: int = DEFAULT_STORE_ID) -> dict:
    with get_engine().connect() as conn:
        r = conn.execute(text("""
            SELECT c.product_id, c.name, c.brand, c.category, c.product_type, c.mrp, c.current_price AS price,
                   c.stock_qty, c.gst_rate, c.aisle_no, c.shelf_code, i.updated_at
            FROM v_store_catalog c JOIN inventory i ON i.product_id = c.product_id AND i.store_id = c.store_id
            WHERE c.product_id = :pid AND c.store_id = :store_id"""), {"pid": product_id, "store_id": store_id}
        ).mappings().first()
    if r is None:
        raise ProductNotFound(f"No product with id {product_id}")
    return dict(r)


def list_coupons() -> list[dict]:
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT code, description, discount_type, discount_value, max_discount, min_cart_value, scope,
                   scope_value, valid_from, valid_to, is_active,
                   CASE WHEN NOT is_active THEN 'disabled'
                        WHEN CURRENT_DATE < valid_from THEN 'not started'
                        WHEN CURRENT_DATE > valid_to THEN 'expired' ELSE 'live' END AS status,
                   (SELECT array_agg(o.code ORDER BY o.code) FROM coupon_conflicts cc
                      JOIN coupons o ON o.coupon_id = CASE WHEN cc.coupon_a = c.coupon_id THEN cc.coupon_b
                                                           ELSE cc.coupon_a END
                    WHERE c.coupon_id IN (cc.coupon_a, cc.coupon_b)) AS conflicts_with
            FROM coupons c ORDER BY coupon_id""")).mappings().all()
    return [{**r, "conflicts_with": r["conflicts_with"] or []} for r in rows]


def set_coupon_active(code: str, active: bool, by: Optional[StaffUser] = None) -> dict:
    if by is not None:
        require(by, "manager")
    with get_engine().begin() as conn:
        n = conn.execute(text("UPDATE coupons SET is_active = :a WHERE code = :c"), {"a": active, "c": code}).rowcount
        if n:
            _audit(conn, by, "coupon", code, {"to": "enabled" if active else "disabled"})
    if n == 0:
        raise CouponNotFound(f"No coupon {code!r}")
    return next(c for c in list_coupons() if c["code"] == code)


def recent_audit(limit: int = 15) -> list[dict]:
    """Who changed what, newest first (shown on the admin page)."""
    with get_engine().connect() as conn:
        rows = conn.execute(text("SELECT audit_id, username, role, action, target, detail, at FROM admin_audit "
                                 "ORDER BY audit_id DESC LIMIT :n"), {"n": limit}).mappings().all()
    return [dict(r) for r in rows]


def summary(store_id: int = DEFAULT_STORE_ID) -> dict:
    with get_engine().connect() as conn:
        inv = conn.execute(text("""
            SELECT count(*) AS products,
                   count(*) FILTER (WHERE stock_qty = 0) AS out_of_stock,
                   count(*) FILTER (WHERE stock_qty BETWEEN 1 AND 9) AS low_stock
            FROM inventory WHERE store_id = :s"""), {"s": store_id}).mappings().one()
        coupons = conn.execute(text("""SELECT count(*) FROM coupons
                                      WHERE is_active AND CURRENT_DATE BETWEEN valid_from AND valid_to""")).scalar_one()
        orders = conn.execute(text("""
            SELECT count(*) AS orders, coalesce(sum(final_total), 0) AS revenue,
                   coalesce(sum(discount_total), 0) AS discounts, coalesce(sum(gst_total), 0) AS gst
            FROM orders""")).mappings().one()
    return {**inv, "live_coupons": coupons, **orders}


def recent_orders(limit: int = 10) -> list[dict]:
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT order_id, placed_at, final_total, discount_total, gst_total, applied_coupons,
                   jsonb_array_length(line_items) AS lines,
                   (SELECT sum((li->>'qty')::int) FROM jsonb_array_elements(line_items) li) AS items
            FROM orders ORDER BY placed_at DESC LIMIT :n"""), {"n": limit}).mappings().all()
    return [dict(r) for r in rows]
