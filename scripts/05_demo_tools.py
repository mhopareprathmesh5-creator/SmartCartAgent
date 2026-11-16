"""End-to-end demo of the six tool functions — no LLM involved.

Simulates: "2 toned milk, oats, instant coffee, Britannia brown bread and 3 tea, budget ₹600".
In the finished system the LLM turns that sentence into the SHOPPING_LIST below
and decides which tool to call next; here the sequence is scripted so you can
see that every number comes from the database.

    python scripts/05_demo_tools.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from tabulate import tabulate  # noqa: E402

import _common  # noqa: E402,F401  (UTF-8 console for ₹)
from smartcart.db import get_engine  # noqa: E402
from smartcart.tools import (check_inventory, compute_bill, create_cart,  # noqa: E402
                             find_substitutes, locate, update_cart)

# "britannia brown bread" is out of stock in the seed data -> triggers find_substitutes()
SHOPPING_LIST = [("toned milk", 2), ("oats", 1), ("instant coffee", 1),
                 ("britannia brown bread", 1), ("tea", 3)]
BUDGET = 600


def step(title):
    print(f"\n── {title} " + "─" * max(0, 70 - len(title)))


def main():
    session = f"demo-{uuid.uuid4().hex[:6]}"
    cart_id = create_cart(session)
    print(f"Opened cart #{cart_id} for session {session}")

    for query, qty in SHOPPING_LIST:
        step(f'locate("{query}")')
        hits = locate(query, limit=3)
        print(tabulate([(h.name, h.brand, f"₹{h.price}", h.stock_qty,
                         f"Aisle {h.aisle_no} {h.shelf_code} L{h.shelf_level}") for h in hits],
                       headers=["product", "brand", "price", "stock", "location"], tablefmt="simple"))
        product = hits[0]

        status = check_inventory(product.product_id, qty)
        print(f"check_inventory -> stock {status.stock_qty}, need {qty}: "
              f"{'OK' if status.can_fulfil else 'CANNOT FULFIL'}")

        if not status.can_fulfil:
            subs = find_substitutes(product.product_id, quantity=qty)
            print("find_substitutes ->")
            print(tabulate([(s.name, s.brand, f"₹{s.price}", f"{s.price_difference:+}", s.match,
                             f"Aisle {s.aisle_no} {s.shelf_code}") for s in subs],
                           headers=["substitute", "brand", "price", "diff", "match", "location"],
                           tablefmt="simple"))
            product = subs[0]

        print(f"update_cart -> {update_cart(cart_id, product.product_id, qty).message}")

    step("compute_bill (optimal coupons applied)")
    bill = compute_bill(cart_id)
    print(tabulate([(l.name, l.quantity, f"₹{l.unit_price}", f"₹{l.line_total}") for l in bill.lines],
                   headers=["item", "qty", "unit", "total"], tablefmt="simple"))
    print(f"\nSubtotal          ₹{bill.subtotal}   (MRP ₹{bill.mrp_total}, you save ₹{bill.savings_vs_mrp})")
    for a in bill.applied_coupons:
        print(f"  {a.code:<12} -₹{a.discount}   {a.description}")
    print(f"Final total       ₹{bill.final_total}   (budget ₹{BUDGET}: "
          f"{'within' if bill.final_total <= BUDGET else 'OVER'})")

    for r in bill.rejected_coupons:
        if r.reason == "conflict":
            print(f"  {r.code:<12} skipped — {r.detail}")

    nearly = sorted((r for r in bill.rejected_coupons if r.reason == "below_minimum"),
                    key=lambda r: r.shortfall)[:3]
    if nearly:
        print("\nAlmost unlocked:")
        for r in nearly:
            print(f"  {r.code:<12} add ₹{r.shortfall} more — {r.detail}")
    for w in bill.warnings:
        print(f"WARNING: {w}")

    with get_engine().begin() as conn:   # demo carts are not kept
        conn.execute(text("DELETE FROM carts WHERE session_id = :s"), {"s": session})


if __name__ == "__main__":
    main()
