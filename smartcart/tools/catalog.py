"""Catalogue tools: locate(), check_inventory(), find_substitutes().

All read from the v_store_catalog view (products + store_map + inventory),
so prices are always the live inventory.current_price.
"""
from decimal import Decimal

from sqlalchemy import text

from smartcart.db import DEFAULT_STORE_ID, get_engine
from smartcart.tools.models import (ProductLocation, ProductNotFound, StockStatus,
                                    Substitute, money)

_LOCATE_SQL = text("""
    WITH scored AS (
        SELECT c.*,
               word_similarity(:q, lower(c.brand || ' ' || c.name))
             + 0.5 * word_similarity(:q, lower(c.product_type))
             + 0.5 * similarity(:q, lower(c.product_type))      AS score
        FROM v_store_catalog c
        WHERE c.store_id = :store_id
          AND (:q <% lower(c.brand || ' ' || c.name) OR :q <% lower(c.product_type))
    )
    SELECT * FROM scored
    ORDER BY score DESC, in_stock DESC, current_price ASC, product_id
    LIMIT :limit
""")


def locate(query: str, limit: int = 5, store_id: int = DEFAULT_STORE_ID) -> list[ProductLocation]:
    """Find products matching a free-text query and say where they are in the store.

    Fuzzy (trigram) match on brand + name and product type, so typos like
    "cofee" still work. Best matches first; among equal matches, in-stock and
    cheaper items come first. Returns [] when nothing matches.
    """
    q = " ".join(query.lower().split())
    if not q:
        return []
    with get_engine().connect() as conn:
        rows = conn.execute(_LOCATE_SQL, {"q": q, "limit": limit, "store_id": store_id}).mappings().all()
    return [
        ProductLocation(
            product_id=r["product_id"], name=r["name"], brand=r["brand"],
            category=r["category"], sub_category=r["sub_category"], product_type=r["product_type"],
            pack_size=r["pack_size"], price=r["current_price"], mrp=r["mrp"],
            stock_qty=r["stock_qty"], in_stock=r["in_stock"],
            aisle_no=r["aisle_no"], aisle_name=r["aisle_name"], shelf_code=r["shelf_code"],
            shelf_label=r["shelf_label"], shelf_level=r["shelf_level"],
            match_score=round(float(r["score"]), 3),
        )
        for r in rows
    ]


def check_inventory(product_id: int, quantity: int = 1,
                    store_id: int = DEFAULT_STORE_ID) -> StockStatus:
    """Live stock and price for one product, and whether `quantity` units can be supplied."""
    if quantity < 1:
        raise ValueError("quantity must be at least 1")
    with get_engine().connect() as conn:
        r = conn.execute(text("""
            SELECT p.product_id, p.name, p.brand, i.current_price, i.stock_qty, i.reorder_level
            FROM products p JOIN inventory i ON i.product_id = p.product_id
            WHERE p.product_id = :pid AND i.store_id = :store_id
        """), {"pid": product_id, "store_id": store_id}).mappings().first()
    if r is None:
        raise ProductNotFound(f"No product with id {product_id}")
    stock = r["stock_qty"]
    return StockStatus(
        product_id=r["product_id"], name=r["name"], brand=r["brand"], price=r["current_price"],
        stock_qty=stock, requested_qty=quantity, in_stock=stock > 0,
        can_fulfil=stock >= quantity, low_stock=0 < stock < r["reorder_level"],
    )


_SUBSTITUTES_SQL = text("""
    SELECT s.*, (s.current_price - o.current_price) AS price_difference,
           CASE WHEN s.product_type = o.product_type THEN 1 ELSE 2 END AS tier
    FROM v_store_catalog o
    JOIN v_store_catalog s
      ON s.store_id = o.store_id
     AND s.product_id <> o.product_id
     AND (s.product_type = o.product_type OR s.sub_category = o.sub_category)
    WHERE o.product_id = :pid AND o.store_id = :store_id
      AND s.stock_qty >= :qty
    ORDER BY tier,
             abs(s.current_price - o.current_price) / o.current_price,
             similarity(lower(s.name), lower(o.name)) DESC,
             s.rating DESC NULLS LAST,
             s.product_id
    LIMIT :limit
""")


def find_substitutes(product_id: int, quantity: int = 1, limit: int = 3,
                     store_id: int = DEFAULT_STORE_ID) -> list[Substitute]:
    """Ranked in-stock alternatives for a product (typically one that is out of stock).

    Ranking:
      1. same product_type (e.g. another 'Milk') before same sub_category (e.g. other 'Dairy')
      2. closest price (relative difference)
      3. most similar name (e.g. "Bath Book - Space" -> "Bath Book - Ocean")
      4. higher customer rating
    Only products with at least `quantity` units in stock are suggested.
    """
    with get_engine().connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM products WHERE product_id = :pid"),
                              {"pid": product_id}).first()
        if exists is None:
            raise ProductNotFound(f"No product with id {product_id}")
        rows = conn.execute(_SUBSTITUTES_SQL, {"pid": product_id, "qty": quantity, "limit": limit,
                                               "store_id": store_id}).mappings().all()
    return [
        Substitute(
            product_id=r["product_id"], name=r["name"], brand=r["brand"],
            product_type=r["product_type"], price=r["current_price"],
            price_difference=money(r["price_difference"]), stock_qty=r["stock_qty"],
            rating=Decimal(r["rating"]) if r["rating"] is not None else None,
            aisle_no=r["aisle_no"], shelf_code=r["shelf_code"],
            match="same_type" if r["tier"] == 1 else "same_sub_category",
        )
        for r in rows
    ]
