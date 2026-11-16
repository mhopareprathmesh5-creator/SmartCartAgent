"""LLM-facing tools: thin wrappers around smartcart.tools that return compact JSON.

The cart_id, session_id and budget are injected from the graph state, so the LLM
can never pick, invent or mistype a cart id.
"""
import json
from dataclasses import asdict
from decimal import Decimal
from typing import Annotated, Literal, Optional

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from smartcart import tools as T
from smartcart.tools.models import Bill, money


def to_json(obj) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)


def bill_summary(bill: Bill, budget: Optional[str]) -> dict:
    """Compact bill for the LLM. Budget status is computed here, by code, never by the LLM."""
    s = {
        "items": [{"product_id": l.product_id, "name": l.name, "brand": l.brand, "qty": l.quantity,
                   "unit_price": l.unit_price, "line_total": l.line_total, "stock_qty": l.stock_qty,
                   "aisle_no": l.aisle_no, "aisle_name": l.aisle_name, "shelf_code": l.shelf_code,
                   "gst_rate": l.gst_rate}
                  for l in bill.lines],
        "item_count": bill.item_count,
        "subtotal": bill.subtotal,
        "mrp_total": bill.mrp_total,
        "savings_vs_mrp": bill.savings_vs_mrp,
        "coupons_applied": [{"code": a.code, "description": a.description, "discount": a.discount}
                            for a in bill.applied_coupons],
        "discount_total": bill.discount_total,
        "final_total": bill.final_total,
        "coupons_skipped_due_to_conflict": [{"code": r.code, "why": r.detail}
                                            for r in bill.rejected_coupons if r.reason == "conflict"],
        "almost_unlocked": [{"code": r.code, "add_amount": r.shortfall, "detail": r.detail}
                            for r in sorted((r for r in bill.rejected_coupons if r.reason == "below_minimum"),
                                            key=lambda r: r.shortfall)[:3]],
        "warnings": bill.warnings,
        "gst_included": bill.gst_total,
        "gst_breakup": [{"rate": t.rate, "taxable_value": t.taxable_value, "cgst": t.cgst, "sgst": t.sgst}
                        for t in bill.tax_breakup],
    }
    if budget is not None:
        b = Decimal(budget)
        s["budget"] = b
        if bill.final_total > b:
            s["over_budget_by"] = money(bill.final_total - b)
        else:
            s["budget_remaining"] = money(b - bill.final_total)
    return s


@tool
def search_products(query: str, limit: int = 5) -> str:
    """Search the store catalogue. `query` is a short product phrase, e.g. "toned milk",
    "basmati rice", "amul butter". Returns matching products with product_id, price (live),
    MRP, stock, and location (aisle, shelf, shelf level 1=bottom). Typos are tolerated."""
    hits = T.locate(query, limit=limit)
    keep = ("product_id", "name", "brand", "product_type", "pack_size", "price", "mrp",
            "stock_qty", "in_stock", "aisle_no", "aisle_name", "shelf_code", "shelf_level")
    return to_json([{k: getattr(h, k) for k in keep} for h in hits] or {"result": "no matching products"})


@tool
def check_stock(product_id: int, quantity: int = 1) -> str:
    """Check live stock and price of one product and whether `quantity` units are available."""
    return to_json(asdict(T.check_inventory(product_id, quantity)))


@tool
def find_substitutes(product_id: int, quantity: int = 1) -> str:
    """Ranked in-stock alternatives for a product (same type first, then closest price).
    Use it for out-of-stock items or to find a cheaper option when over budget."""
    return to_json([asdict(s) for s in T.find_substitutes(product_id, quantity=quantity, limit=5)])


@tool
def update_cart(product_id: int, quantity: int, mode: Literal["add", "set"] = "add",
                cart_id: Annotated[int, InjectedState("cart_id")] = 0) -> str:
    """Change the cart. mode="add": add `quantity` more units. mode="set": make the cart hold
    exactly `quantity` units (0 removes the item). Refused (ok=false) if stock is insufficient."""
    return to_json(asdict(T.update_cart(cart_id, product_id, quantity, mode=mode)))


@tool
def view_bill(cart_id: Annotated[int, InjectedState("cart_id")] = 0,
              budget: Annotated[Optional[str], InjectedState("budget")] = None) -> str:
    """Current itemised bill: subtotal, best coupon combination, final total, budget status,
    coupons that are almost unlocked."""
    return to_json(bill_summary(T.compute_bill(cart_id), budget))


@tool
def fit_budget(cart_id: Annotated[int, InjectedState("cart_id")] = 0,
               budget: Annotated[Optional[str], InjectedState("budget")] = None) -> str:
    """When the cart is over budget: the fewest swaps to cheaper same-type products that bring
    the payable total (coupons re-optimized) within budget. Only SUGGESTS — apply the swaps with
    update_cart only after the shopper agrees."""
    if budget is None:
        return to_json({"error": "No budget set. Ask the shopper for a budget and call set_budget first."})
    return to_json(asdict(T.fit_budget(cart_id, Decimal(budget))))


@tool
def compare_stores(cart_id: Annotated[int, InjectedState("cart_id")] = 0) -> str:
    """Price the current cart at the other stores (SmartMart Ichalkaranji, FreshBasket Sangli) and
    this store: per store the total after valid coupons, which items it cannot supply, and the
    cheapest store that can supply the whole cart (`best_store_id`, `saving_vs_home`). Use it when
    the shopper asks where the cart is cheaper or about other stores."""
    return to_json(asdict(T.compare_stores(cart_id)))


@tool
def set_budget(amount: float, tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """Record the shopper's budget in rupees (e.g. "under ₹600" -> 600)."""
    b = str(money(Decimal(str(amount))))
    return Command(update={
        "budget": b,
        "messages": [ToolMessage(to_json({"ok": True, "budget": b}), tool_call_id=tool_call_id)],
    })


@tool
def checkout(tool_call_id: Annotated[str, InjectedToolCallId],
             cart_id: Annotated[int, InjectedState("cart_id")] = 0,
             session_id: Annotated[str, InjectedState("session_id")] = "") -> Command:
    """Place the order for the current cart. Only when the shopper explicitly asks to pay/check out."""
    r = T.checkout(cart_id)
    update = {"messages": [ToolMessage(to_json(asdict(r)), tool_call_id=tool_call_id)]}
    if r.ok:   # start a fresh cart so the conversation can continue
        update["cart_id"] = T.create_cart(session_id)
    return Command(update=update)


AGENT_TOOLS = [search_products, check_stock, find_substitutes, update_cart, view_bill,
               set_budget, fit_budget, compare_stores, checkout]
