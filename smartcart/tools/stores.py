"""Multi-store comparison: what would this exact cart cost at the other stores?

The home store (where the shopper is, with the aisle map) prices the cart from
`inventory` via compute_bill(). The other stores publish a price/stock feed
(`store_prices`). For each store the cart is re-priced line by line:
  - a line counts only if the store carries the product AND has enough stock;
    otherwise it is listed as missing (not_carried / out_of_stock / not_enough_stock),
  - if the store accepts SmartMart's chain-wide coupons, the same exact coupon
    optimizer picks the best valid combination for the lines it can supply.
The recommendation is the cheapest store that can supply the WHOLE cart, so a
cheaper-but-incomplete store is never presented as a saving. Every number is
computed here from the database — the agent only reports it.
"""
from datetime import date
from typing import Optional

from sqlalchemy import text

from smartcart.db import DEFAULT_STORE_ID, get_engine
from smartcart.tools.cart import compute_bill, ensure_cart_exists
from smartcart.tools.models import CartLine, MissingItem, StoreComparison, StoreQuote, money
from smartcart.tools.offers import choose_best_offers, load_conflicts, load_coupons

ZERO = money(0)


def compare_stores(cart_id: int, today: Optional[date] = None,
                   home_store_id: int = DEFAULT_STORE_ID) -> StoreComparison:
    today = today or date.today()
    home_bill = compute_bill(cart_id, today, home_store_id)
    with get_engine().connect() as conn:
        ensure_cart_exists(conn, cart_id)
        stores = conn.execute(text("SELECT store_id, name, city, is_home, accepts_coupons FROM stores "
                                   "ORDER BY store_id")).mappings().all()
        items = conn.execute(text("""
            SELECT ci.product_id, ci.quantity, p.name, p.category, p.sub_category, p.brand
            FROM cart_items ci JOIN products p USING (product_id)
            WHERE ci.cart_id = :c ORDER BY ci.product_id"""), {"c": cart_id}).mappings().all()
        feed = {(r["store_id"], r["product_id"]): r for r in conn.execute(text("""
            SELECT store_id, product_id, price, stock_qty FROM store_prices
            WHERE product_id IN (SELECT product_id FROM cart_items WHERE cart_id = :c)"""),
            {"c": cart_id}).mappings().all()}
        coupons, conflicts = load_coupons(conn), load_conflicts(conn)

    quotes = []
    for s in stores:
        if s["store_id"] == home_store_id:
            missing = [MissingItem(l.product_id, l.name, l.quantity,
                                   "out_of_stock" if l.stock_qty == 0 else "not_enough_stock")
                       for l in home_bill.lines if l.quantity > l.stock_qty]
            quotes.append(StoreQuote(s["store_id"], s["name"], s["city"], True, s["accepts_coupons"],
                                     len(home_bill.lines) - len(missing), len(home_bill.lines), not missing,
                                     home_bill.subtotal, home_bill.discount_total,
                                     [a.code for a in home_bill.applied_coupons], home_bill.final_total, missing))
            continue
        lines, missing = [], []
        for it in items:
            row = feed.get((s["store_id"], it["product_id"]))
            if row is None:
                missing.append(MissingItem(it["product_id"], it["name"], it["quantity"], "not_carried"))
            elif row["stock_qty"] < it["quantity"]:
                missing.append(MissingItem(it["product_id"], it["name"], it["quantity"],
                                           "out_of_stock" if row["stock_qty"] == 0 else "not_enough_stock"))
            else:
                lines.append(CartLine(it["product_id"], it["category"], it["sub_category"], it["brand"],
                                      money(row["price"] * it["quantity"])))
        subtotal = money(sum((l.line_total for l in lines), ZERO))
        offers = choose_best_offers(lines, coupons, conflicts, today) if s["accepts_coupons"] else None
        discount = offers.total_discount if offers else ZERO
        quotes.append(StoreQuote(s["store_id"], s["name"], s["city"], False, s["accepts_coupons"],
                                 len(lines), len(items), not missing, subtotal, discount,
                                 [a.code for a in offers.applied] if offers else [],
                                 money(subtotal - discount), missing))

    home = next(q for q in quotes if q.is_home)
    complete = sorted((q for q in quotes if q.complete and q.items_total), key=lambda q: (q.final_total, not q.is_home))
    best = complete[0] if complete else None
    saving = money(home.final_total - best.final_total) if best and home.complete and not best.is_home else ZERO
    if not items:
        message = "The cart is empty."
    elif best is None:
        message = "No single store can supply the whole cart."
    elif best.is_home:
        message = f"{home.name} (this store) is the cheapest for this cart."
    elif not home.complete:
        message = f"{best.name} can supply the whole cart; this store cannot."
    else:
        message = f"{best.name} is cheaper for this cart."
    quotes = [home] + sorted((q for q in quotes if not q.is_home), key=lambda q: (not q.complete, q.final_total))
    return StoreComparison(cart_id, quotes, best.store_id if best else None, saving, message)
