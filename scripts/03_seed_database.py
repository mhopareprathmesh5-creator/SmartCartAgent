"""Create the schema and load all seed data into PostgreSQL.

Re-runnable: db/schema.sql drops and recreates every table first.

What is real vs. synthesized
  REAL (BigBasket dataset): product names, brands, categories, MRP, selling price, rating.
  SYNTHESIZED (no public dataset has these):
    - store_map  : aisle per category, shelf per sub-category, random shelf level
    - inventory  : stock levels, incl. ~6% forced out-of-stock for substitution tests
    - coupons    : hand-authored rules in data/seed/*.csv
All randomness uses RANDOM_SEED, so every run produces identical data.
"""
import sys

import numpy as np
import pandas as pd
from sqlalchemy import text

from _common import (CATALOG_CSV, CONFLICTS_CSV, COUPONS_CSV, GST_CSV, RANDOM_SEED, ROOT,
                     SCHEMA_FILE, get_engine)

sys.path.insert(0, str(ROOT))        # for smartcart.auth (password hashing of the demo staff accounts)

STORE = {
    "name": "SmartMart Kolhapur",
    "city": "Kolhapur",
    "address": "Simulated store — Rajarampuri, Kolhapur, Maharashtra",
}

# Physical layout: one aisle per category, fresh food near the entrance.
AISLE_ORDER = [
    "Fruits & Vegetables",
    "Bakery, Cakes & Dairy",
    "Eggs, Meat & Fish",
    "Foodgrains, Oil & Masala",
    "Snacks & Branded Foods",
    "Beverages",
    "Cleaning & Household",
    "Beauty & Hygiene",
    "Baby Care",
]

# Multi-store comparison (Phase II): two more stores that publish only prices + stock.
# Synthetic: home price × a random factor per product (with a category bias), capped
# at MRP; ~8% of products not carried, ~5% of carried ones out of stock. A separate
# random generator per store keeps the home store's data identical to before.
OTHER_STORES = [
    {"name": "SmartMart Ichalkaranji", "city": "Ichalkaranji", "num_aisles": 9, "accepts_coupons": True,
     "address": "Simulated branch — Main Road, Ichalkaranji (same chain: coupons valid)",
     "bias": {"Foodgrains, Oil & Masala": 0.94, "Cleaning & Household": 0.95, "Beverages": 1.04}},
    {"name": "FreshBasket Sangli", "city": "Sangli", "num_aisles": 8, "accepts_coupons": False,
     "address": "Simulated competitor — Vishrambag, Sangli (SmartMart coupons not valid)",
     "bias": {"Fruits & Vegetables": 0.90, "Beverages": 0.93, "Bakery, Cakes & Dairy": 0.96,
              "Beauty & Hygiene": 1.06}},
]
NOT_CARRIED_FRACTION = 0.08
OTHER_OOS_FRACTION = 0.05

OUT_OF_STOCK_FRACTION = 0.06
LOW_STOCK_FRACTION = 0.10      # 1-9 units left: "only a few left" cases
NORMAL_STOCK_RANGE = (10, 150)
REORDER_LEVEL = 10


def run_schema(engine):
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            cur.execute(sql)
        raw.commit()
    finally:
        raw.close()
    print("Schema created (14 tables + v_store_catalog view)")


def load_products(conn, catalog: pd.DataFrame) -> pd.DataFrame:
    rows = catalog.rename(columns={"market_price": "base_price"})[[
        "source_id", "name", "brand", "category", "sub_category", "product_type",
        "pack_size", "base_price", "rating", "description",
    ]]
    rows = rows.astype(object).where(rows.notna(), None)
    conn.execute(
        text("""INSERT INTO products (source_id, name, brand, category, sub_category,
                                      product_type, pack_size, base_price, rating, description)
                VALUES (:source_id, :name, :brand, :category, :sub_category,
                        :product_type, :pack_size, :base_price, :rating, :description)"""),
        rows.to_dict("records"),
    )
    ids = pd.read_sql(text("SELECT product_id, source_id FROM products"), conn)
    print(f"products: {len(ids)} rows")
    return catalog.merge(ids, on="source_id")


def apply_gst_rates(conn):
    """GST % per product from hand-authored rules (simplified: real rates depend on HSN codes).

    Rules are applied from general to specific — category, then sub-category, then
    product type — so a more specific rule overrides a general one.
    """
    rules = pd.read_csv(GST_CSV, keep_default_na=False)
    rules["specificity"] = (rules["sub_category"] != "").astype(int) + (rules["product_type"] != "").astype(int)
    for r in rules.sort_values("specificity").itertuples():
        sql = "UPDATE products SET gst_rate = :rate WHERE category = :c"
        if r.sub_category:
            sql += " AND sub_category = :s"
        if r.product_type:
            sql += " AND product_type = :t"
        n = conn.execute(text(sql), {"rate": r.gst_rate, "c": r.category, "s": r.sub_category,
                                      "t": r.product_type}).rowcount
        if n == 0:
            raise SystemExit(f"GST rule matched no products: {r.category} / {r.sub_category} / {r.product_type}")
    slabs = dict(conn.execute(text("SELECT gst_rate, count(*) FROM products GROUP BY 1 ORDER BY 1")).all())
    print("gst rates: " + ", ".join(f"{float(k):g}% × {v}" for k, v in slabs.items()))


def build_store_map(products: pd.DataFrame, store_id: int, rng) -> pd.DataFrame:
    aisle_no = {cat: i + 1 for i, cat in enumerate(AISLE_ORDER)}
    shelf_no = {}
    for cat, g in products.groupby("category"):
        for i, sub in enumerate(sorted(g["sub_category"].unique())):
            shelf_no[(cat, sub)] = i + 1

    m = pd.DataFrame({
        "store_id": store_id,
        "product_id": products["product_id"],
        "aisle_no": products["category"].map(aisle_no),
        "aisle_name": products["category"],
        "shelf_label": products["sub_category"],
        "shelf_level": rng.integers(1, 6, size=len(products)),
    })
    shelf = [shelf_no[(c, s)] for c, s in zip(products["category"], products["sub_category"])]
    m["shelf_code"] = [f"A{a}-S{s}" for a, s in zip(m["aisle_no"], shelf)]
    return m


def build_inventory(products: pd.DataFrame, store_id: int, rng) -> pd.DataFrame:
    n = len(products)
    stock = rng.integers(NORMAL_STOCK_RANGE[0], NORMAL_STOCK_RANGE[1] + 1, size=n)

    # Out-of-stock: at most one product per product_type, and only in types with
    # >= 2 products, so every out-of-stock item keeps an in-stock substitute.
    type_sizes = products["product_type"].map(products["product_type"].value_counts())
    eligible = products[type_sizes >= 2]
    one_per_type = eligible.groupby("product_type").sample(n=1, random_state=RANDOM_SEED)
    n_oos = round(n * OUT_OF_STOCK_FRACTION)
    oos_ids = set(one_per_type.sample(n=n_oos, random_state=RANDOM_SEED)["product_id"])
    oos_mask = products["product_id"].isin(oos_ids).to_numpy()
    stock[oos_mask] = 0

    in_stock_idx = np.flatnonzero(~oos_mask)
    low_idx = rng.choice(in_stock_idx, size=round(n * LOW_STOCK_FRACTION), replace=False)
    stock[low_idx] = rng.integers(1, 10, size=len(low_idx))

    return pd.DataFrame({
        "store_id": store_id,
        "product_id": products["product_id"],
        "stock_qty": stock,
        "current_price": products["sale_price"],   # live selling price (MRP stays in products)
        "reorder_level": REORDER_LEVEL,
    })


def load_coupons(conn):
    coupons = pd.read_csv(COUPONS_CSV, keep_default_na=False, dtype={"is_active": str})
    coupons["is_active"] = coupons["is_active"].str.lower() == "true"
    for col in ["max_discount", "scope_value"]:
        coupons[col] = coupons[col].replace("", None)
    conn.execute(
        text("""INSERT INTO coupons (code, description, discount_type, discount_value, max_discount,
                                     min_cart_value, scope, scope_value, valid_from, valid_to, is_active)
                VALUES (:code, :description, :discount_type, :discount_value, :max_discount,
                        :min_cart_value, :scope, :scope_value, :valid_from, :valid_to, :is_active)"""),
        coupons.to_dict("records"),
    )
    ids = dict(conn.execute(text("SELECT code, coupon_id FROM coupons")).all())

    conflicts = pd.read_csv(CONFLICTS_CSV)
    rows = []
    for r in conflicts.itertuples():
        a, b = sorted((ids[r.code_a], ids[r.code_b]))   # schema requires coupon_a < coupon_b
        rows.append({"a": a, "b": b, "reason": r.reason})
    conn.execute(
        text("INSERT INTO coupon_conflicts (coupon_a, coupon_b, reason) VALUES (:a, :b, :reason)"),
        rows,
    )
    print(f"coupons: {len(coupons)} rows, coupon_conflicts: {len(rows)} pairs")


def load_other_stores(conn, products: pd.DataFrame, home: pd.DataFrame):
    """Price/stock feeds of the comparison stores (store_prices)."""
    home_price = dict(zip(home["product_id"], home["current_price"]))
    for k, s in enumerate(OTHER_STORES, start=1):
        rng = np.random.default_rng(RANDOM_SEED + 100 * k)
        sid = conn.execute(text("""INSERT INTO stores (name, city, address, num_aisles, is_home, accepts_coupons)
                                   VALUES (:name, :city, :address, :num_aisles, FALSE, :accepts_coupons)
                                   RETURNING store_id"""), s).scalar_one()
        n = len(products)
        carried = rng.random(n) >= NOT_CARRIED_FRACTION
        factor = rng.uniform(0.88, 1.08, size=n) * products["category"].map(s["bias"]).fillna(1.0).to_numpy()
        price = np.round(products["product_id"].map(home_price).to_numpy() * factor * 2) / 2   # to ₹0.50
        price = np.clip(np.minimum(price, products["market_price"].to_numpy()), 1, None)       # never above MRP
        stock = rng.integers(5, 151, size=n)
        stock[rng.random(n) < OTHER_OOS_FRACTION] = 0
        feed = pd.DataFrame({"store_id": sid, "product_id": products["product_id"], "price": price,
                             "stock_qty": stock})[carried]
        feed.to_sql("store_prices", conn, if_exists="append", index=False)
        print(f"store_prices: {s['name']}: {len(feed)} products ({(feed['stock_qty'] == 0).sum()} out of stock)")


def create_staff(conn):
    from smartcart.auth import DEMO_USERS, create_user
    for username, full_name, role, password in DEMO_USERS:
        create_user(conn, username, full_name, role, password)
    print("staff_users: " + ", ".join(f"{u} ({r})" for u, _, r, _ in DEMO_USERS))


def main():
    rng = np.random.default_rng(RANDOM_SEED)
    engine = get_engine()
    catalog = pd.read_csv(CATALOG_CSV)

    run_schema(engine)
    with engine.begin() as conn:
        store_id = conn.execute(
            text("""INSERT INTO stores (name, city, address, num_aisles, is_home)
                    VALUES (:name, :city, :address, :n, TRUE) RETURNING store_id"""),
            {**STORE, "n": len(AISLE_ORDER)},
        ).scalar_one()
        print(f"stores: 1 row ({STORE['name']})")

        products = load_products(conn, catalog)
        apply_gst_rates(conn)

        store_map = build_store_map(products, store_id, rng)
        store_map.to_sql("store_map", conn, if_exists="append", index=False)
        print(f"store_map: {len(store_map)} rows across {store_map['aisle_no'].nunique()} aisles, "
              f"{store_map['shelf_code'].nunique()} shelves")

        inventory = build_inventory(products, store_id, rng)
        inventory.to_sql("inventory", conn, if_exists="append", index=False)
        print(f"inventory: {len(inventory)} rows "
              f"({(inventory['stock_qty'] == 0).sum()} out of stock, "
              f"{inventory['stock_qty'].between(1, 9).sum()} low stock)")

        load_coupons(conn)
        load_other_stores(conn, products, inventory)
        create_staff(conn)

    print("\nSeed complete. Run scripts/04_verify_seed.py to check it.")


if __name__ == "__main__":
    main()
