"""Measure the numbers the documents quote, from the running system (no hand-typed figures).

    python docs/collect_facts.py      # -> docs/facts.json (read by docs/build_documents.js)

Needs the database up. Counts tests (pytest --collect-only), API endpoints, database rows,
and copies the latest evaluation summary (docs/evaluation/results.json).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from smartcart.api.main import app  # noqa: E402
from smartcart.db import get_engine  # noqa: E402


def count_tests(marker: str) -> int:
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", marker],
                         cwd=ROOT, capture_output=True, text=True).stdout
    m = re.search(r"(\d+)(?:/\d+)? tests? (?:collected|selected)", out)
    return int(m.group(1)) if m else 0


def tests_per_file() -> dict:
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "not live"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    counts: dict[str, int] = {}
    for line in out.splitlines():
        if "::" in line:
            f = line.split("::")[0].replace("tests/", "").replace("tests\\", "")
            counts[f] = counts.get(f, 0) + 1
    return counts


def main():
    endpoints = sorted({(m, r.path) for r in app.routes if hasattr(r, "methods") and r.path not in
                        ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc")
                        for m in r.methods if m != "HEAD"})
    with get_engine().connect() as conn:
        q = lambda sql: conn.execute(text(sql)).scalar()  # noqa: E731
        db = {
            "products": q("SELECT count(*) FROM products"),
            "categories": q("SELECT count(DISTINCT category) FROM products"),
            "product_types": q("SELECT count(DISTINCT product_type) FROM products"),
            "aisles": q("SELECT count(DISTINCT aisle_no) FROM store_map"),
            "shelves": q("SELECT count(DISTINCT shelf_code) FROM store_map"),
            "out_of_stock": q("SELECT count(*) FROM inventory WHERE stock_qty = 0"),
            "low_stock": q("SELECT count(*) FROM inventory WHERE stock_qty BETWEEN 1 AND 9"),
            "stock_units": q("SELECT sum(stock_qty) FROM inventory"),
            "coupons": q("SELECT count(*) FROM coupons"),
            "conflicts": q("SELECT count(*) FROM coupon_conflicts"),
            "stores": q("SELECT count(*) FROM stores"),
            "store_price_rows": q("SELECT count(*) FROM store_prices"),
            "tables": q("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' "
                        "AND table_type = 'BASE TABLE'"),
            "gst_slabs": {str(float(r[0])).rstrip("0").rstrip("."): r[1] for r in conn.execute(
                text("SELECT gst_rate, count(*) FROM products GROUP BY 1 ORDER BY 1"))},
            "study_runs": q("SELECT count(*) FROM study_runs WHERE finished_at IS NOT NULL")
            if q("SELECT to_regclass('study_runs') IS NOT NULL") else 0,
        }
    ev = json.loads((ROOT / "docs" / "evaluation" / "results.json").read_text(encoding="utf-8"))
    base = json.loads((ROOT / "docs" / "evaluation" / "run1_baseline" / "results.json").read_text(encoding="utf-8"))
    facts = {
        "tests_offline": count_tests("not live"), "tests_live": count_tests("live"),
        "tests_per_file": tests_per_file(),
        "endpoints": len(endpoints), "endpoint_list": [f"{m} {p}" for m, p in endpoints],
        "db": db,
        "eval": {"generated": ev["generated"], "summary": ev["summary"], "offline": ev["offline_offer_study"],
                 "goals": [{"id": g["id"], "title": g["title"], "features": g["features"],
                            "success": g.get("success", False), "infra_error": g["infra_error"],
                            "grounded": all(t["grounded"] for t in g["turns"]),
                            "latency_s": round(sum(t["latency_s"] for t in g["turns"]), 1),
                            "turns": len(g["turns"])} for g in ev["goals"]]},
        "baseline": base["summary"],
    }
    out = ROOT / "docs" / "facts.json"
    out.write_text(json.dumps(facts, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"tests {facts['tests_offline']} + {facts['tests_live']} live · endpoints {facts['endpoints']} · "
          f"tables {db['tables']} · eval {ev['summary']['goals_succeeded']}/{ev['summary']['goals_completed']} -> {out}")


if __name__ == "__main__":
    main()
