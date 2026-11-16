"""Database connection shared by all tool functions."""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# The home store (aisle map, carts, checkout); seeding always creates it as store 1.
# Comparison stores only publish prices (store_prices), see tools/stores.py.
DEFAULT_STORE_ID = 1


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set — copy .env.example to .env")
    if url.startswith("postgres://"):        # cloud hosts (Render, Heroku) use the old scheme name
        url = "postgresql://" + url[len("postgres://"):]
    return create_engine(url, pool_pre_ping=True)
