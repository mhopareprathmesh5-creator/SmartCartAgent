"""Cart tools: create_cart(), update_cart(), compute_bill(), checkout().

cart_items stores only (product, quantity). Prices are joined in from
inventory every time the bill is computed, so the bill is always live and
no number can come from anywhere but the database.
"""
import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import text

from smartcart.db import DEFAULT_STORE_ID, get_engine
from smartcart.tools.models import (Bill, BillLine, CartLine, CartNotActive, CartNotFound,
                                    CartUpdate, CheckoutResult, Order, ProductNotFound, TaxLine, money)
from smartcart.tools.offers import choose_best_offers, load_conflicts, load_coupons
from smartcart.tools.tax import allocate_discounts, line_taxes, tax_slabs

ZERO = Decimal("0.00")


def ensure_cart_exists(conn, cart_id: int, require_active: bool = False, lock: bool = False) -> None:
    sql = "SELECT status FROM carts WHERE cart_id = :cid" + (" FOR UPDATE" if lock else "")
    status = conn.execute(text(sql), {"cid": cart_id}).scalar()
    if status is None:
        raise CartNotFound(f"No cart with id {cart_id}")
    if require_active and status != "ACTIVE":
        raise CartNotActive(f"Cart {cart_id} is {status}")


def create_cart(session_id: str, store_id: int = DEFAULT_STORE_ID) -> int:
    """Open a new ACTIVE cart for a conversation session; returns its cart_id."""
    with get_engine().begin() as conn:
        return conn.execute(
            text("INSERT INTO carts (store_id, session_id) VALUES (:sid, :sess) RETURNING cart_id"),
            {"sid": store_id, "sess": session_id},
        ).scalar_one()


def update_cart(cart_id: int, product_id: int, quantity: int, mode: str = "set",
                store_id: int = DEFAULT_STORE_ID) -> CartUpdate:
    """Change the quantity of one product in a cart.

    mode="set": make the cart hold exactly `quantity` units (0 removes the item).
    mode="add": add `quantity` more units (must be > 0).

    The change is refused (ok=False, cart untouched) if it would exceed live
    stock; the result then carries available_stock so the agent can offer the
    remaining units or a substitute.
    """
    if mode not in ("set", "add"):
        raise ValueError("mode must be 'set' or 'add'")
    if mode == "set" and quantity < 0:
        raise ValueError("quantity cannot be negative")
    if mode == "add" and quantity <= 0:
        raise ValueError("quantity to add must be positive")

    with get_engine().begin() as conn:
        ensure_cart_exists(conn, cart_id, require_active=True, lock=True)
        prod = conn.execute(text("""
            SELECT p.name, i.stock_qty FROM products p
            JOIN inventory i ON i.product_id = p.product_id AND i.store_id = :store_id
            WHERE p.product_id = :pid
        """), {"pid": product_id, "store_id": store_id}).first()
        if prod is None:
            raise ProductNotFound(f"No product with id {product_id}")
        name, stock = prod

        current = conn.execute(
            text("SELECT quantity FROM cart_items WHERE cart_id = :cid AND product_id = :pid"),
            {"cid": cart_id, "pid": product_id},
        ).scalar() or 0
        new_qty = quantity if mode == "set" else current + quantity

        if new_qty > stock:
            msg = (f"{name} is out of stock" if stock == 0
                   else f"Only {stock} unit(s) of {name} in stock; requested {new_qty}")
            return CartUpdate(False, cart_id, product_id, current, stock, msg)

        if new_qty == 0:
            conn.execute(text("DELETE FROM cart_items WHERE cart_id = :cid AND product_id = :pid"),
                         {"cid": cart_id, "pid": product_id})
            msg = f"Removed {name} from the cart" if current else f"{name} was not in the cart"
        else:
            conn.execute(text("""
                INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (:cid, :pid, :qty)
                ON CONFLICT (cart_id, product_id) DO UPDATE SET quantity = EXCLUDED.quantity
            """), {"cid": cart_id, "pid": product_id, "qty": new_qty})
            msg = f"Cart now has {new_qty} × {name}"
        conn.execute(text("UPDATE carts SET updated_at = now() WHERE cart_id = :cid"), {"cid": cart_id})

    return CartUpdate(True, cart_id, product_id, new_qty, stock, msg)


def compute_bill(cart_id: int, today: Optional[date] = None,
                 store_id: int = DEFAULT_STORE_ID) -> Bill:
    """Itemised running bill with live prices and the optimal coupon combination applied."""
    with get_engine().connect() as conn:
        ensure_cart_exists(conn, cart_id)
        return _build_bill(conn, cart_id, today or date.today(), store_id)


def _build_bill(conn, cart_id: int, today: date, store_id: int) -> Bill:
    """Bill from inside an open connection/transaction (shared by compute_bill and checkout)."""
    rows = conn.execute(text("""
        SELECT p.product_id, p.name, p.brand, p.category, p.sub_category, p.base_price AS mrp,
               p.gst_rate, ci.quantity, i.current_price, i.stock_qty, m.aisle_no, m.aisle_name, m.shelf_code
        FROM cart_items ci
        JOIN products  p ON p.product_id = ci.product_id
        JOIN inventory i ON i.product_id = ci.product_id AND i.store_id = :store_id
        LEFT JOIN store_map m ON m.product_id = ci.product_id AND m.store_id = :store_id
        WHERE ci.cart_id = :cid
        ORDER BY ci.added_at, p.product_id
    """), {"cid": cart_id, "store_id": store_id}).mappings().all()
    coupons = load_coupons(conn)
    conflicts = load_conflicts(conn)

    lines, offer_lines, warnings = [], [], []
    mrp_total = ZERO
    for r in rows:
        line_total = money(r["quantity"] * r["current_price"])
        lines.append(BillLine(r["product_id"], r["name"], r["brand"], r["quantity"],
                              r["current_price"], line_total, r["stock_qty"],
                              r["aisle_no"], r["aisle_name"], r["shelf_code"]))
        offer_lines.append(CartLine(r["product_id"], r["category"], r["sub_category"],
                                    r["brand"], line_total))
        mrp_total += r["quantity"] * r["mrp"]
        if r["stock_qty"] == 0:
            warnings.append(f"{r['name']} is now out of stock")
        elif r["quantity"] > r["stock_qty"]:
            warnings.append(f"Only {r['stock_qty']} unit(s) of {r['name']} left; cart has {r['quantity']}")

    subtotal = money(sum((l.line_total for l in lines), ZERO))
    offers = choose_best_offers(offer_lines, coupons, conflicts, today)

    # GST included in the price, computed on each line's post-discount amount (see tax.py)
    shares = allocate_discounts(offer_lines, offers.applied, {c.code: c for c in coupons}, offers.total_discount)
    taxes = {t.product_id: t for t in line_taxes(offer_lines, {r["product_id"]: r["gst_rate"] for r in rows}, shares)}
    lines = [replace(l, gst_rate=taxes[l.product_id].gst_rate, discount_share=taxes[l.product_id].discount_share,
                     gst=taxes[l.product_id].gst) for l in lines]
    slabs = tax_slabs(list(taxes.values()))

    return Bill(
        cart_id=cart_id,
        lines=lines,
        item_count=sum(l.quantity for l in lines),
        subtotal=subtotal,
        mrp_total=money(mrp_total),
        savings_vs_mrp=money(mrp_total - subtotal),
        applied_coupons=offers.applied,
        discount_total=offers.total_discount,
        final_total=money(subtotal - offers.total_discount),
        rejected_coupons=offers.rejected,
        warnings=warnings,
        gst_total=money(sum((t.gst for t in taxes.values()), ZERO)),
        tax_breakup=[TaxLine(s.rate, s.taxable_value, s.cgst, s.sgst) for s in slabs],
    )


def checkout(cart_id: int, today: Optional[date] = None,
             store_id: int = DEFAULT_STORE_ID) -> CheckoutResult:
    """Place the order: final bill + stock decrement + order snapshot, all in ONE transaction.

    Inventory rows are locked (SELECT ... FOR UPDATE, in product_id order to avoid
    deadlocks) before the bill is computed, so price and stock cannot change between
    pricing and saving. If any item is short of stock, nothing is written and the
    problems are returned (ok=False) so the agent can offer substitutes.
    """
    today = today or date.today()
    with get_engine().begin() as conn:
        ensure_cart_exists(conn, cart_id, require_active=True, lock=True)
        conn.execute(text("""
            SELECT i.product_id FROM inventory i
            JOIN cart_items ci ON ci.product_id = i.product_id
            WHERE ci.cart_id = :cid AND i.store_id = :store_id
            ORDER BY i.product_id FOR UPDATE OF i
        """), {"cid": cart_id, "store_id": store_id})

        bill = _build_bill(conn, cart_id, today, store_id)
        if not bill.lines:
            return CheckoutResult(False, None, ["Cart is empty"])
        short = [f"{l.name}: cart has {l.quantity}, only {l.stock_qty} in stock"
                 for l in bill.lines if l.quantity > l.stock_qty]
        if short:
            return CheckoutResult(False, None, short)

        for l in bill.lines:
            conn.execute(text("""
                UPDATE inventory SET stock_qty = stock_qty - :q, updated_at = now()
                WHERE product_id = :pid AND store_id = :store_id
            """), {"q": l.quantity, "pid": l.product_id, "store_id": store_id})

        applied = [a.code for a in bill.applied_coupons]
        line_items = [{"product_id": l.product_id, "name": l.name, "qty": l.quantity,
                       "unit_price": str(l.unit_price), "line_total": str(l.line_total),
                       "gst_rate": str(l.gst_rate), "discount_share": str(l.discount_share), "gst": str(l.gst)}
                      for l in bill.lines]
        order_id, placed_at = conn.execute(text("""
            INSERT INTO orders (cart_id, subtotal, discount_total, final_total, applied_coupons, gst_total, line_items)
            VALUES (:cid, :sub, :disc, :final, :coupons, :gst, CAST(:lines AS JSONB))
            RETURNING order_id, placed_at
        """), {"cid": cart_id, "sub": bill.subtotal, "disc": bill.discount_total,
               "final": bill.final_total, "coupons": applied, "gst": bill.gst_total,
               "lines": json.dumps(line_items)}).one()
        conn.execute(text("UPDATE carts SET status = 'CHECKED_OUT', updated_at = now() WHERE cart_id = :cid"),
                     {"cid": cart_id})

    return CheckoutResult(True, Order(order_id, cart_id, bill.subtotal, bill.discount_total,
                                      bill.final_total, applied, bill.lines, placed_at,
                                      bill.gst_total, bill.tax_breakup), [])
