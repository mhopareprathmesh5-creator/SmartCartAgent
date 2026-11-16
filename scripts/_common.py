"""Shared paths and DB connection helper for the pipeline scripts."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
SEED_DIR = ROOT / "data" / "seed"
SCHEMA_FILE = ROOT / "db" / "schema.sql"

RAW_CSV = RAW_DIR / "BigBasket Products.csv"
CATALOG_CSV = PROCESSED_DIR / "catalog_clean.csv"
COUPONS_CSV = SEED_DIR / "coupons_seed.csv"
CONFLICTS_CSV = SEED_DIR / "coupon_conflicts_seed.csv"
GST_CSV = SEED_DIR / "gst_rates_seed.csv"

KAGGLE_DATASET = "surajjha101/bigbasket-entire-product-list-28k-datapoints"

RANDOM_SEED = 42  # every synthetic value is reproducible from this

load_dotenv(ROOT / ".env")

# Windows consoles default to cp1252, which cannot print the ₹ sign.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def get_engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL not set — copy .env.example to .env")
    return create_engine(url)
