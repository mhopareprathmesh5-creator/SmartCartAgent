"""Verify the seeded database and print a short demo of what it contains.

Exits with code 1 if any integrity check fails.
"""
import sys

from sqlalchemy import text
from tabulate import tabulate

from _common import get_engine

TABLES = ["products", "stores", "store_map", "inventory",
          "coupons", "coupon_conflicts", "carts", "cart_items", "orders"]

# (description, SQL returning a single number, predicate on that number)
CHECKS = [
    ("Every product has exactly one store location",
     "SELECT count(*) FROM products p LEFT JOIN store_map m USING (product_id) WHERE m.product_id IS NULL",
     lambda v: v == 0),
    ("Every product has an inventory row",
     "SELECT count(*) FROM products p LEFT JOIN inventory i USING (product_id) WHERE i.product_id IS NULL",
     lambda v: v == 0),
    ("Out-of-stock share is between 5% and 8%",
     "SELECT round(100.0 * avg((stock_qty = 0)::int), 2) FROM inventory",
     lambda v: 5 <= v <= 8),
    ("Every out-of-stock product has an in-stock same-type substitute",
     """SELECT count(*) FROM v_store_catalog o
        WHERE o.stock_qty = 0 AND NOT EXISTS (
            SELECT 1 FROM v_store_catalog s
            WHERE s.product_type = o.product_type AND s.product_id <> o.product_id AND s.stock_qty > 0)""",
     lambda v: v == 0),
    ("Selling price never exceeds MRP",
     "SELECT count(*) FROM v_store_catalog WHERE current_price > mrp",
     lambda v: v == 0),
    ("Each aisle holds exactly one category",
     "SELECT count(*) FROM (SELECT aisle_no FROM store_map GROUP BY aisle_no HAVING count(DISTINCT aisle_name) > 1) x",
     lambda v: v == 0),
    ("Every scoped coupon matches at least one product",
     """SELECT count(*) FROM coupons c WHERE c.scope <> 'CART' AND NOT EXISTS (
            SELECT 1 FROM products p WHERE
                (c.scope = 'CATEGORY'     AND p.category     = c.scope_value) OR
                (c.scope = 'SUB_CATEGORY' AND p.sub_category = c.scope_value) OR
                (c.scope = 'BRAND'        AND p.brand        = c.scope_value))""",
     lambda v: v == 0),
    ("15-20 coupons authored",
     "SELECT count(*) FROM coupons", lambda v: 15 <= v <= 20),
    ("At least 3 mutual-exclusion pairs",
     "SELECT count(*) FROM coupon_conflicts", lambda v: v >= 3),
    ("At least one expired and one disabled coupon (optimizer must skip them)",
     "SELECT LEAST(count(*) FILTER (WHERE valid_to < CURRENT_DATE), count(*) FILTER (WHERE NOT is_active)) FROM coupons",
     lambda v: v >= 1),
]

DEMOS = [
    ("locate('milk') — where is it, is it in stock, what does it cost?",
     """SELECT name, brand, current_price AS price, stock_qty AS stock,
               'Aisle ' || aisle_no || ' (' || aisle_name || ')' AS aisle, shelf_code, shelf_level AS level
        FROM v_store_catalog WHERE product_type = 'Milk' ORDER BY current_price LIMIT 6"""),
    ("Out-of-stock items and their in-stock substitutes (sample)",
     """SELECT o.name AS out_of_stock, o.product_type,
               (SELECT s.name || ' (' || s.brand || ', ₹' || s.current_price || ')' FROM v_store_catalog s
                WHERE s.product_type = o.product_type AND s.stock_qty > 0
                ORDER BY abs(s.current_price - o.current_price) LIMIT 1) AS closest_substitute
        FROM v_store_catalog o WHERE o.stock_qty = 0 ORDER BY o.category LIMIT 6"""),
    ("Store layout — aisles",
     """SELECT aisle_no, aisle_name, count(DISTINCT shelf_code) AS shelves, count(*) AS products,
               sum((stock_qty = 0)::int) AS out_of_stock
        FROM v_store_catalog GROUP BY aisle_no, aisle_name ORDER BY aisle_no"""),
    ("Coupons",
     """SELECT code, discount_type AS type, discount_value AS value, max_discount AS cap,
               min_cart_value AS min_value, scope, coalesce(scope_value, '-') AS applies_to,
               CASE WHEN NOT is_active THEN 'DISABLED' WHEN valid_to < CURRENT_DATE THEN 'EXPIRED' ELSE 'valid' END AS status
        FROM coupons ORDER BY coupon_id"""),
    ("Mutually exclusive coupon pairs",
     """SELECT a.code AS coupon_a, b.code AS coupon_b, cc.reason
        FROM coupon_conflicts cc JOIN coupons a ON a.coupon_id = cc.coupon_a
                                 JOIN coupons b ON b.coupon_id = cc.coupon_b"""),
]


def main():
    engine = get_engine()
    with engine.connect() as conn:
        counts = [(t, conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()) for t in TABLES]
        print(tabulate(counts, headers=["table", "rows"], tablefmt="github"))

        print("\nIntegrity checks")
        failed = 0
        for desc, sql, ok in CHECKS:
            value = conn.execute(text(sql)).scalar_one()
            passed = ok(float(value))
            failed += not passed
            print(f"  [{'PASS' if passed else 'FAIL'}] {desc}  (value: {value})")

        for title, sql in DEMOS:
            result = conn.execute(text(sql))
            print(f"\n== {title} ==")
            print(tabulate(result.all(), headers=list(result.keys()), tablefmt="github", maxcolwidths=50))

    print(f"\n{'ALL CHECKS PASSED' if not failed else f'{failed} CHECK(S) FAILED'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
