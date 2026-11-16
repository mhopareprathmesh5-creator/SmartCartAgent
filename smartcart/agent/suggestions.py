"""Product cards for the UI, built from the tool results of one agent turn.

Two kinds of group:
  - "substitutes": alternatives for a product (from find_substitutes, or attached
    automatically by the graph after a stock-out), so the shopper can pick or swap.
  - "search": results of a search whose products were NOT added this turn
    (e.g. "where is basmati rice?"), so the shopper can add one with a click.

Every field is copied from a tool result, i.e. from the database — the LLM's text is
not parsed, so a card can never show an invented price.
"""
import json

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from smartcart import tools as T
from smartcart.agent.grounding import message_text

MAX_GROUPS, MAX_CARDS = 3, 4
CARD_FIELDS = ("product_id", "name", "brand", "price", "mrp", "stock_qty", "aisle_no", "shelf_code",
               "price_difference")


def _card(p: dict) -> dict:
    c = {k: p[k] for k in CARD_FIELDS if k in p}
    c["in_stock"] = p.get("stock_qty", 0) > 0
    return c


def _payload(m: ToolMessage):
    try:
        return json.loads(message_text(m))
    except json.JSONDecodeError:
        return None


def build_suggestions(new_messages: list[BaseMessage]) -> list[dict]:
    args = {c["id"]: c["args"] for m in new_messages if isinstance(m, AIMessage) for c in m.tool_calls}
    added = set()
    substitutes: dict[int, list[dict]] = {}
    searches: list[tuple[str, list[dict]]] = []

    for m in new_messages:
        if not isinstance(m, ToolMessage):
            continue
        p = _payload(m)
        a = args.get(m.tool_call_id, {})
        if m.name == "update_cart" and isinstance(p, dict) and p.get("ok") and p.get("quantity", 0) > 0:
            added.add(p["product_id"])
        if m.name == "search_products" and isinstance(p, list):
            searches.append((str(a.get("query", "")), p))
        elif m.name == "find_substitutes" and isinstance(p, list) and "product_id" in a:
            substitutes.setdefault(int(a["product_id"]), []).extend(p)
        if isinstance(p, dict) and p.get("auto_substitutes"):
            substitutes.setdefault(int(p["product_id"]), []).extend(p["auto_substitutes"])

    groups = []
    for original, items in substitutes.items():
        unique = list({i["product_id"]: i for i in items}.values())[:MAX_CARDS]
        name = T.check_inventory(original).name
        groups.append({"kind": "substitutes", "title": f"Alternatives for {name}", "for_product_id": original,
                       "items": [_card(i) for i in unique]})
    covered = set(substitutes) | {c["product_id"] for g in groups for c in g["items"]}
    for query, hits in searches:
        ids = {h["product_id"] for h in hits}
        # skip searches that led to an add, or whose products are already shown as substitutes
        if not hits or ids & added or ids & covered:
            continue
        groups.append({"kind": "search", "title": f"Results for “{query}”", "for_product_id": None,
                       "items": [_card(h) for h in hits[:MAX_CARDS]]})
    return groups[:MAX_GROUPS]
