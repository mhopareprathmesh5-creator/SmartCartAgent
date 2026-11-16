"""Clean the raw BigBasket CSV and sample a store-sized catalogue.

Output: data/processed/catalog_clean.csv  (~900 products, 9 categories)

Steps
  1. Drop rows with missing name/brand or non-positive prices; strip whitespace.
  2. MRP (market_price) must be >= selling price (sale_price); fix rows where it isn't.
  3. Remove duplicate (name, brand) pairs.
  4. Keep 9 everyday supermarket categories.
  5. Parse pack size from the product name where present (e.g. "500 g", "1 L").
  6. Sample ~100 products per category, grouped by product type so every
     sampled type has several products — this guarantees out-of-stock items
     have real same-type substitutes later. Staple types (milk, rice, coffee...)
     are always included so natural demo requests work.
"""
import re

import pandas as pd

from _common import CATALOG_CSV, PROCESSED_DIR, RANDOM_SEED, RAW_CSV

CATEGORIES = [
    "Fruits & Vegetables",
    "Bakery, Cakes & Dairy",
    "Beverages",
    "Snacks & Branded Foods",
    "Foodgrains, Oil & Masala",
    "Eggs, Meat & Fish",
    "Cleaning & Household",
    "Beauty & Hygiene",
    "Baby Care",
]

# Everyday product types that must be stocked so typical shopping requests resolve.
STAPLE_TYPES = {
    "Milk", "Curd", "Butter & Margarine", "Paneer, Tofu & Cream", "Milk, White & Sandwich",
    "Instant Coffee", "Ground Coffee", "Leaf & Dust Tea", "Tea Bags", "Juices",
    "Oats & Porridge", "Instant Noodles", "Chips & Corn Snacks", "Cream Biscuits & Wafers",
    "Glucose & Milk Biscuits", "Tomato Ketchup & Sauces",
    "Basmati Rice", "Atta Whole Wheat", "Sugar & Jaggery", "Salts", "Sunflower, Rice Bran Oil",
    "Toor, Channa & Moong Dal", "Ghee & Vanaspati",
    "Farm Eggs", "Potato, Onion & Tomato", "Banana, Sapota & Papaya", "Apples & Pomegranate",
    "Detergent Powder, Liquid", "Toilet Cleaners", "Bathing Bars & Soaps", "Toothpaste",
    "Shampoo & Conditioner", "Diapers",
}

PER_CATEGORY = 100
PER_STAPLE_TYPE = 8
PER_OTHER_TYPE = 4
MIN_TYPE_SIZE = 3  # ignore product types too small to offer a substitute

PACK_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(kg|gm|g|ml|ltr|litre|l|pcs|pc|units?)\b", re.IGNORECASE
)
UNIT_NORMALISE = {"gm": "g", "ltr": "L", "litre": "L", "l": "L", "pc": "pcs", "unit": "pcs", "units": "pcs"}


def parse_pack_size(name: str):
    m = PACK_RE.search(name)
    if not m:
        return None
    unit = m.group(2).lower()
    return f"{m.group(1)} {UNIT_NORMALISE.get(unit, unit)}"


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"index": "source_id", "product": "name", "type": "product_type"})
    df = df.dropna(subset=["name", "brand", "category", "sub_category", "product_type"])

    for col in ["name", "brand", "category", "sub_category", "product_type", "description"]:
        df[col] = df[col].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    df.loc[df["description"] == "nan", "description"] = None

    df = df[(df["sale_price"] > 0) & (df["market_price"] > 0)].copy()
    df["market_price"] = df[["market_price", "sale_price"]].max(axis=1)

    df["_key"] = df["name"].str.lower() + "|" + df["brand"].str.lower()
    df = df.drop_duplicates("_key").drop(columns="_key")

    df = df[df["category"].isin(CATEGORIES)].copy()
    df["pack_size"] = df["name"].map(parse_pack_size)
    return df


def sample_category(cat_df: pd.DataFrame) -> pd.DataFrame:
    shuffled = cat_df.sample(frac=1, random_state=RANDOM_SEED)
    sizes = shuffled["product_type"].value_counts()
    sizes = sizes[sizes >= MIN_TYPE_SIZE]

    staples = [t for t in sizes.index if t in STAPLE_TYPES]
    others = [t for t in sizes.index if t not in STAPLE_TYPES]  # already largest-first

    picked, total = [], 0
    for ptype in staples + others:
        if total >= PER_CATEGORY:
            break
        n = PER_STAPLE_TYPE if ptype in STAPLE_TYPES else PER_OTHER_TYPE
        n = min(n, PER_CATEGORY - total)
        if n < 2:  # a lone product of a type has no substitute — skip
            break
        rows = shuffled[shuffled["product_type"] == ptype].head(n)
        picked.append(rows)
        total += len(rows)
    return pd.concat(picked)


def main():
    raw = pd.read_csv(RAW_CSV)
    print(f"Raw rows: {len(raw):,}")

    df = clean(raw)
    print(f"After cleaning + category filter: {len(df):,}")

    catalog = pd.concat(sample_category(g) for _, g in df.groupby("category"))
    catalog = catalog.sort_values(["category", "sub_category", "product_type", "name"])
    catalog = catalog[[
        "source_id", "name", "brand", "category", "sub_category", "product_type",
        "pack_size", "market_price", "sale_price", "rating", "description",
    ]]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(CATALOG_CSV, index=False)

    print(f"\nSampled catalogue: {len(catalog)} products -> {CATALOG_CSV}")
    summary = catalog.groupby("category").agg(
        products=("name", "size"),
        sub_categories=("sub_category", "nunique"),
        product_types=("product_type", "nunique"),
    )
    print(summary.to_string())
    missing = STAPLE_TYPES - set(catalog["product_type"])
    if missing:
        print(f"\nWARNING: staple types not in catalogue: {sorted(missing)}")


if __name__ == "__main__":
    main()
