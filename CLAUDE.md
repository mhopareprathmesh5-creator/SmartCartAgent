# Conversational Smart-Cart & Billing Assistant Agent — Project Context

Group D8, KIT College of Engineering Kolhapur. B.Tech Mega Project, Phase I already reviewed
(synopsis + slide deck submitted, approved). This repo is the actual implementation, started
fresh — no code existed before this.

## The core idea

A shopper types a natural-language request ("2 litres milk, oats and coffee under ₹600") and an
agent autonomously: locates each product (aisle/shelf), checks live stock and price, finds the
best valid combination of coupons, suggests ranked substitutes for anything out of stock, and
keeps a running bill that recalculates on every cart change.

## The one non-negotiable architectural rule

**The LLM plans, understands and explains. It never generates a price, stock count, aisle
location, discount or total.** Every transactional value is fetched from backend tool functions
reading a PostgreSQL database. This is the whole point of the project — it's what makes the
system auditable and safe to reason about near real money. Any implementation choice that lets
a number originate from the model instead of the database violates the core design.

## Scope decisions already made (do not re-litigate without asking the user)

- **Single simulated supermarket**, not multi-platform price comparison. Multi-store/platform
  comparison is explicitly Future Scope in the synopsis, not core scope. This was a deliberate
  choice: aisle/shelf navigation only makes sense for one physical store, the literature survey
  (WebShop, ReAct, InteRecAgent, RecMind, LORE, etc.) is all single-environment, and there's no
  legal way to get live multi-platform pricing anyway.
- Product catalogue seeded from the **BigBasket** Kaggle dataset (real Indian grocery products +
  prices). Inventory levels, aisle/shelf map, and coupon rules do **not** exist in any public
  dataset — they are synthesized/hand-authored on top of the real catalogue.
- Novelty claim (from the panel-reviewed slide 9): integrating shelf-level location + live
  inventory + coupon optimization + substitution + billing into one tool-grounded agent over a
  shared cart state. Nobody in the literature survey does all five together. Don't drop the
  offer optimizer or the aisle map to save time — that's where the novelty lives.

## Tech stack (from the reviewed synopsis + confirmed with user)

- **LangGraph** — agent orchestration (state graph, persistent cart/conversation state, cycles
  for "more actions? → loop back")
- **PostgreSQL** (via Docker Compose) — single source of truth for all transactional data
- **FastAPI** — backend API wrapping the tool functions
- LLM provider: **Google Gemini** (user's choice, 2026-10-12) via `langchain-google-genai`.
  Key in `.env` as `GOOGLE_API_KEY` (free tier). **Main model `gemini-3.5-flash-lite`**
  (`GEMINI_MODEL`). **Fallback `gemini-3.1-flash-lite-preview`** (`GEMINI_FALLBACK_MODEL`, the
  user's original pick), used automatically if the main model errors. The user first chose
  3.1-flash-lite-preview, but measurements showed ~11 s per call (and a 503 "high demand") vs
  ~1 s for 3.5-flash-lite, so the user agreed to switch. Gemini 2.5 models return 404 for this
  key (retired). The provider can be swapped in one file (`smartcart/agent/llm.py`).
- **Frontend: React 19 + TypeScript + Vite** (`frontend/`), icons `lucide-react`, replies rendered
  with `react-markdown`. FastAPI serves the built site, so the demo is one server and one URL.

## Team

Mayur Khamamkar (2324000146), Prathmesh Mhopare (2324001087, mhopareprathmesh5@gmail.com),
Aniket Mane (2324000104), Harshvardhan Magdum (2324000418). Guide: Prof. Vrishali Prabhu.

## Build order / milestones

1. **Postgres schema + seed data** ✅ DONE (2026-10-12) — see "Milestone 1" below
2. **The six tool functions** ✅ DONE (2026-10-12) — plain Python, no LLM, 45 pytest tests.
   See "Milestone 2" below.
3. **Offer optimizer done properly** ✅ DONE together with milestone 2. Exact branch-and-bound
   over the conflict graph, proven optimal against brute force (500 random problems + 200 random
   real carts). This is the hardest and most technically defensible part of the project.
2b. **Wrap tools in FastAPI** ✅ DONE (2026-10-12): 12 endpoints + `checkout()`. See "Milestone 2b" below.
5. **LangGraph agent** ✅ DONE (2026-10-12): graph + tools + grounding guard + model fallback.
   13 offline tests + 3 live Gemini tests pass. See "Milestone 5" below.
6. **Frontend** ✅ DONE (2026-10-30): chat with a grounding badge + tool trace per reply, live
   cart with aisle/shelf + quantity buttons, pick route, bill with coupons, budget bar,
   checkout + receipt. Verified end to end in Chrome against live Gemini. See "Milestone 6" below.
6b. **Extra features** ✅ DONE (2026-10-30), chosen by the user before milestone 7:
   (1) store admin page, (2) clickable product cards in chat, (3) "fit my budget" optimizer,
   (4) GST breakdown. 93 tests pass. See "Milestone 6b" below.
7. **Evaluation harness** ✅ DONE (2026-11-12): 12 scripted shopping goals run live through the
   agent, scored by code. Final run: task success 12/12 (44/44 checks), grounding 100%, discount
   100% of the brute-force optimum, substitution 100% correct. See "Milestone 7" below.
   **All 7 milestones are complete.** Final deck for the POE: `docs/Group_No_D8_Final_POE.pptx`.
8. **Phase II enhancements** ✅ DONE (2026-11-12), chosen by the user from the deck's "next steps":
   persistent chat memory, staff login + roles + audit log, Hindi/Marathi chat + voice input,
   multi-store price comparison, user-study mode, cloud-ready Docker image (deployment itself
   postponed by the user), report + paper drafts. Evaluation re-run with 15 goals: 15/15, 53/53
   checks, grounding 100% over 147 values. See "Phase II enhancements" below.

## ALL COMMANDS (keep this section up to date every milestone)

Run everything from the repo root (`D:\SmartCartAgent`) in PowerShell. Docker Desktop must be
running first.

```powershell
# ---- one-time setup ----
python -m pip install -r requirements.txt
cd frontend; npm install; npm run build; cd ..   # builds the web UI into frontend/dist (re-run after UI changes)
python scripts/00_setup_kaggle_creds.py    # kaggle.json -> ~/.kaggle/ (skips if already there)
python scripts/01_fetch_dataset.py         # downloads BigBasket CSV (skips if already there)

# ---- start the database (every time after a reboot) ----
docker compose up -d                       # Postgres 16 on localhost:5432 (creds in .env)
docker compose ps                          # should say "healthy"

# ---- build / rebuild the data (re-runnable, always gives identical data) ----
python scripts/02_clean_catalog.py         # -> data/processed/catalog_clean.csv (849 products)
python scripts/03_seed_database.py         # drops + recreates schema, loads everything
python scripts/04_verify_seed.py           # 10 integrity checks + demo tables  (milestone 1 demo)

# ---- tests ----
python -m pytest -q                        # 108 tests, all must pass (~10 s). Leaves the data unchanged.
                                           # Uses a scripted fake LLM: no API key / no cost
python -m pytest -m live -v                # 3 LIVE tests against real Gemini (~15 s, uses ~10 of the
                                           # 15 requests/min free quota: wait 1 min before chatting)
python scripts/05_demo_tools.py            # scripted shopping trip through all 6 tools (milestone 2 demo)

# ---- the web app (API + UI on one server) ----
python -m uvicorn smartcart.api.main:app --reload    # web UI:  http://127.0.0.1:8000/       (milestone 6 demo)
                                           # store admin: http://127.0.0.1:8000/#/admin
                                           # API docs: http://127.0.0.1:8000/docs  (milestone 2b demo)
                                           # Ctrl+C to stop. The UI needs frontend/dist (npm run build)
cd frontend; npm run dev                   # optional: UI dev server with hot reload on http://localhost:5173
                                           # (forwards /api/* to uvicorn on :8000, so keep uvicorn running)

# ---- the AI agent (needs GOOGLE_API_KEY in .env) ----
python scripts/06_chat.py                  # chat in the terminal (milestone 5 demo)
python scripts/06_chat.py --trace          # same, but prints every tool call the agent makes

# ---- evaluation (milestone 7, needs GOOGLE_API_KEY; leaves the data unchanged) ----
python scripts/07_evaluate.py              # 15 goals live + offline coupon study, ~10 min (paced for the free tier)
python scripts/07_evaluate.py --goals G04 G07   # only some goals
python scripts/07_evaluate.py --goals G13 --out <folder>   # trial run without overwriting docs/evaluation
python scripts/07_evaluate.py --offline    # only the coupon study (no LLM, ~10 s)
                                           # -> docs/evaluation/EVALUATION_REPORT.md + results.json
                                           # web view: http://127.0.0.1:8000/#/eval

# ---- user study + staff accounts (Phase II) ----
# run the study in the browser: http://127.0.0.1:8000/#/study
python scripts/08_study_report.py          # assistant vs manual: times, success, time saved; -> docs/study/results.csv
python scripts/08_study_report.py --delete-prefix TEST    # remove rehearsal runs
python scripts/09_staff.py list            # staff accounts; also: add <user> "<name>" manager|staff, password <user>, disable <user>
# demo logins for http://127.0.0.1:8000/#/admin:  manager / manager123  ·  staff / staff123

# ---- documents + presentations (all numbers measured, nothing typed by hand) ----
python docs/collect_facts.py               # measures tests, endpoints, DB counts, latest evaluation -> docs/facts.json
cd docs; npm install; node build_documents.js; cd ..   # -> SmartCart_Project_Guide.docx, SmartCart_Project_Report.docx,
                                           #    SmartCart_Research_Paper.docx (open in Word, press F9 in the report to refresh the TOC)
python docs/build_final_deck.py            # rebuilds docs/Group_No_D8_Final_POE.pptx (LATEST, 38 slides, reads
                                           # docs/facts.json + docs/evaluation/results.json)
                                           # if the .pptx is open in PowerPoint: $env:DECK_OUT="Group_No_D8_Final_POE_v2.pptx" first

# ---- production image (cloud deployment postponed by the user; image tested locally) ----
docker build -t smartcart .                # UI + API in one image (Dockerfile, requirements-app.txt)
docker compose -f docker-compose.prod.yml up -d --build   # db + app on a server
python docs/build_review3_deck.py          # rebuilds the older Review III deck (33 slides)
python docs/build_review2_deck.py          # rebuilds the older Review II deck
                                           # (both read C:\Users\admin\Downloads\Group_No_D8_Review_I.pptx)
# docs/SmartCart_Project_Guide.docx        # project explanation + setup/run/test guide + demo script + viva Q&A
# docs/POE_Exam_Guide.md                   # exam-day checklist, 10-min demo script, numbers, 16 viva Q&As

# ---- handy extras ----
docker exec -it smartcart_db psql -U smartcart -d smartcart     # SQL shell (\dt lists tables, \q quits)
docker compose down                        # stop DB (data kept in volume)
docker compose down -v                     # stop DB AND delete all data (then re-run 03)
```

**For a guide demo:** start Docker Desktop, run `docker compose up -d`, then:
0. **Main demo:** `python -m uvicorn smartcart.api.main:app`, then open **http://127.0.0.1:8000/** and
   click the first example request. You'll see:
   - the agent fill the cart, with the out-of-stock Britannia bread swapped automatically
   - a "Grounded in database" badge, and the tool trace when you click "N tool calls"
   - each item's aisle/shelf and the pick route
   - the + / − buttons changing the bill live
   - Checkout opening the receipt

   **Best demo request** (shows everything at once): "I need 3 Instant Tea Premix Turmeric
   Ginger, 2 Homogenized Milk and Britannia Brown Bread. My budget is ₹440". This shows:
   - the bread is out of stock → auto-substituted, with **substitute cards** (Swap in / In cart)
   - the BEV75 coupon applied, "Over by ₹11.90", and the agent offering the budget swap
   - **Fit my budget** → 1 swap → "₹8.10 left" → **Apply swaps**
   - the **GST** row (click it for the CGST/SGST table)

   Then open **Store admin** in a second browser tab and change the tea's price. Within ~4 s
   the shopper tab's bill updates by itself ("Store prices or stock changed"). Checkout →
   the receipt includes the GST table, and the order appears in the admin's Recent orders.

   **Checkout and admin edits really change the data**: afterwards run
   `python scripts/03_seed_database.py` to restore it.
   Finally open the **Evaluation** tab (http://127.0.0.1:8000/#/eval): the 12-goal results.
1. `python scripts/04_verify_seed.py`: the data
2. `python -m pytest -q`: 98 passing tests
3. `python scripts/05_demo_tools.py`: the tools working end to end
4. `python -m uvicorn smartcart.api.main:app --reload` → open http://127.0.0.1:8000/docs. In Swagger, "Try
   it out": search "milk" → POST /carts → PUT an item → GET bill → POST checkout.
5. `python scripts/06_chat.py --trace`: type "I need 2 toned milk, oats, instant coffee and
   Britannia brown bread, budget ₹600". It shows the tool calls, the out-of-stock substitution,
   the coupons, the budget status and "grounding: OK". **Free-tier limit: 15 Gemini requests
   per minute, and one shopping turn uses ~2–5.** Pause ~15 s between messages in a live demo,
   and don't run the live tests right before it. If the limit is hit, the agent says so politely
   (no crash) and the fallback model, which has its own quota, usually takes over.

## Environment

Docker Desktop (must be running), Python 3.10, `kaggle.json` in `~/.kaggle/`. **An Application Control policy on this PC blocks the `.exe` launchers of Python packages (`uvicorn.exe`, `pip.exe`, …): always run them as modules, `python -m uvicorn …`, `python -m pip …`, `python -m pytest`.** The assistant must
not run git commands; the user manages GitHub. On this machine Docker Hub pulls sometimes fail at
first ("server gave HTTP response to HTTPS client" / TLS timeout) right after Docker Desktop
starts. Retrying `docker pull postgres:16-alpine` a few times fixes it. The image is now cached
locally.

## Milestone 1: DB schema + seed data ✅ DONE

Commands: see "ALL COMMANDS" above (scripts 00–04). All randomness uses `RANDOM_SEED = 42` (`scripts/_common.py`), so every run gives identical data.

### Files
```
docker-compose.yml               postgres:16-alpine, named volume, healthcheck
requirements.txt                 pandas, sqlalchemy, psycopg2-binary, python-dotenv, kaggle, tabulate, pytest
db/schema.sql                    9 tables + v_store_catalog view (drops & recreates, re-runnable)
data/raw/                        BigBasket Products.csv, 27,555 rows (gitignored)
data/processed/catalog_clean.csv 849 sampled products (gitignored, regenerated by script 02)
data/seed/coupons_seed.csv           19 hand-authored coupons (checked in)
data/seed/coupon_conflicts_seed.csv  12 mutually-exclusive coupon pairs (checked in)
scripts/_common.py               shared paths, RANDOM_SEED, get_engine(), UTF-8 stdout fix for ₹
scripts/00..04_*.py              the pipeline above
```

### What is in the database (current numbers)
| table | rows | real or synthetic |
|---|---|---|
| products | 849 | **real** BigBasket names/brands/categories/MRP/selling price/rating |
| stores | 1 | synthetic: "SmartMart Kolhapur" |
| store_map | 849 | synthetic: 9 aisles, 64 shelves |
| inventory | 849 | synthetic stock levels; price = real BigBasket selling price |
| coupons | 19 | hand-authored |
| coupon_conflicts | 12 | hand-authored |
| carts / cart_items / orders | 0 | filled at runtime. Tests and the demo create temporary carts and delete them afterwards |

### Design decisions (and why). These are the talking points for the guide.

1. **Catalog vs live data are separate tables.** `products.base_price` = MRP (rarely changes).
   `inventory.current_price` + `stock_qty` = live values. A daily price/stock refresh touches only
   `inventory`. Tool functions must read prices from `inventory` (or `v_store_catalog`), never
   from `products.base_price`.
2. **`cart_items` stores no price.** The bill is always recomputed from `inventory`, so it can
   never go stale and no number can come from the LLM. `orders` is the only place prices are
   frozen: an immutable snapshot at checkout, including a `line_items` JSONB, for audit.
   DB constraint: `final_total = subtotal - discount_total`.
3. **Catalogue sampling (script 02).** Kept 9 everyday supermarket categories (dropped Gourmet and
   Kitchen/Garden/Pets). Sampled ~100 products per category *grouped by product_type* (staple
   types get 8 products each, other types 4, and types with fewer than 3 products are skipped).
   This guarantees every product has same-type alternatives, which substitution needs. Staple
   types (milk, coffee, oats, rice, atta, eggs, detergent, …) are always included so natural
   demo requests resolve. Eggs, Meat & Fish only reaches 52 products because the source data is
   thin there.
4. **Data cleaning.** Stripped whitespace (brands had trailing spaces), dropped rows with no
   name/brand or prices ≤ 0, forced MRP ≥ selling price, de-duplicated on (name, brand).
   `pack_size` is parsed from the product name by regex, but only ~5% of names contain a size
   (the dataset has no size column), so it is mostly NULL.
5. **Store map.** One aisle per category, ordered like a real store (fresh produce at aisle 1 near
   the entrance, baby care at aisle 9). One shelf per sub-category: `shelf_code` 'A2-S5' = aisle 2,
   shelf 5. `shelf_level` 1–5 is random.
6. **Inventory.** 51 products (6.0%) are out of stock, 85 are low stock (1–9 units), and the rest
   have 10–150 units. Out-of-stock products are chosen as **at most one per product_type, only in
   types with ≥ 2 products**, so every out-of-stock item has an in-stock substitute. Script 04
   verifies this.
7. **Coupon model** (this is what the optimizer reasons over):
   - `discount_type` PERCENT or FLAT. `max_discount` caps PERCENT coupons.
   - `scope` CART / CATEGORY / SUB_CATEGORY / BRAND + `scope_value`.
   - `min_cart_value` is checked against the **subtotal of eligible items** (whole cart for CART
     scope). Example: BEV75 needs ₹300 of Beverages, not a ₹300 cart.
   - `valid_from/valid_to` + `is_active`. MONSOON20 is deliberately expired and TEA40
     deliberately disabled, so tests can prove the optimizer never applies them.
   - `coupon_conflicts`: pairwise mutual exclusion, stored once per pair (coupon_a < coupon_b is
     enforced by CHECK). Three kinds of conflict exist: all 4 cart-level coupons are mutually
     exclusive (6 pairs); SAVE10 ✕ BEV75 (store-wide % vs category flat, the example from the
     synopsis); and overlapping offers on the same items (DAIRY10✕AMUL5, FRESH20✕FRESHO25,
     STAPLES50✕BBROYAL10, BEV75✕COFFEE30, SNACK15✕BRIT20).
   - So "best combination" is a real combinatorial problem: e.g. SAVE10 blocks BEV75 but
     FLAT100 does not, so the best choice depends on the cart.
8. **Fuzzy search ready.** `pg_trgm` extension + trigram index on `lower(products.name)`, for
   `locate("toned milk")`-style lookups in milestone 2.
9. **`v_store_catalog` view** joins products + store_map + inventory: one row per product with
   location, live price, stock and `in_stock`. Use it as the read path for `locate()` and
   `check_inventory()`.

### Verification (script 04): all 10 checks PASS
Every product has a location + inventory row · OOS share 6.01% (target 5–8%) · every OOS product
has an in-stock same-type substitute · selling price ≤ MRP everywhere · one category per aisle ·
every scoped coupon matches ≥ 1 product · 19 coupons · 12 conflict pairs · ≥ 1 expired and ≥ 1
disabled coupon. It also prints demo tables (where milk is, OOS items + closest substitute, aisle
layout, coupon list, conflict pairs), which work well to show live in a review.

## Milestone 2 (+3): the six tool functions + offer optimizer ✅ DONE

### Files
```
smartcart/db.py                 get_engine() (reads DATABASE_URL from .env), DEFAULT_STORE_ID = 1
smartcart/tools/__init__.py     public API: the 6 tools + create_cart + errors
smartcart/tools/models.py       typed results (dataclasses), money() rounding, error classes
smartcart/tools/catalog.py      locate(), check_inventory(), find_substitutes()
smartcart/tools/cart.py         create_cart(), update_cart(), compute_bill()
smartcart/tools/offers.py       optimize_offers() + pure optimizer choose_best_offers()
tests/conftest.py               fixtures: temp cart (auto-deleted), skips DB tests if DB is down
tests/test_offers.py            optimizer: 12 rule tests + brute-force optimality proofs
tests/test_catalog.py           locate / check_inventory / find_substitutes vs real DB
tests/test_cart.py              update_cart / compute_bill / optimize_offers vs real DB
pytest.ini                      pythonpath=. , testpaths=tests, "db" marker
scripts/05_demo_tools.py        scripted end-to-end shopping trip (no LLM)
```

### The six tools (what each one does)
| tool | input → output | how |
|---|---|---|
| `locate(query, limit=5)` | text → products with aisle/shelf/level, live price, stock | pg_trgm fuzzy match on brand+name and product_type. Typo-tolerant ("cofee" works). Ranked by match score, then in-stock first, then cheaper |
| `check_inventory(product_id, quantity=1)` | → stock_qty, price, in_stock, can_fulfil, low_stock | reads `inventory` |
| `find_substitutes(product_id, quantity=1, limit=3)` | → ranked in-stock alternatives | same product_type first, then same sub_category. Then closest price (relative), most similar name, higher rating. Only items with ≥ quantity in stock |
| `update_cart(cart_id, product_id, quantity, mode="set"\|"add")` | → CartUpdate(ok, quantity, available_stock, message) | refuses (ok=False, cart unchanged) if it would exceed live stock. quantity 0 removes. Locks the cart row. Only ACTIVE carts |
| `compute_bill(cart_id)` | → itemised Bill: subtotal, MRP total + savings, applied coupons, final_total, rejected coupons with reasons, warnings | prices joined live from `inventory` every call. Runs the optimizer. Warns if an item went out of stock |
| `optimize_offers(cart_id)` | → OfferResult(applied, total_discount, rejected) | see below |

Helper: `create_cart(session_id)` → cart_id. Errors: `ProductNotFound`, `CartNotFound`,
`CartNotActive` (all subclass `ToolError`). Business outcomes like "not enough stock" are
returned as data (ok=False), not raised, so the agent can react, e.g. by offering a substitute.

### Offer optimizer: how it works (main talking point)
- **Stacking rule (decided with the user, 2026-10-12): INDEPENDENT.** Each coupon's discount
  is computed on the original, pre-discount subtotal of its eligible items, and discounts add up.
  Order never matters. Total discount is capped at the cart subtotal.
- **Step 1, filter:** each coupon is rejected with a reason (`inactive`, `not_started`,
  `expired`, `no_eligible_items`, `below_minimum` + `shortfall` ₹) or gets a fixed discount value.
  PERCENT = eligible × % (capped by max_discount). FLAT = value. Both are capped at the eligible
  subtotal.
- **Step 2, select:** choosing the best non-conflicting subset is a **maximum-weight independent
  set** on the conflict graph (NP-hard in general). With tens of coupons, an **exact
  branch-and-bound** search is instant: include/exclude each coupon (biggest first), and prune a
  branch when current + all remaining discounts can't beat the best found. Ties: fewer coupons,
  then alphabetical (deterministic).
- **Why not greedy:** `test_beats_greedy`. A=₹100 conflicts with B=₹60 and C=₹60. Greedy takes A
  (₹100), but the optimum is B+C (₹120).
- **Proof of optimality:** tests compare against brute force over every subset, on 500 random
  problems and 200 random carts using the real seeded coupons. They always match.
- Coupons not chosen are explained: `conflict` ("Cannot be combined with BEV75, which saves
  more"). `below_minimum` coupons carry a shortfall, so the agent can say "add ₹34 more Amul to
  unlock AMUL5". All of these numbers are computed by code, not the LLM.
- `choose_best_offers()` is a pure function (no DB), which is what makes it easy to test.
  `optimize_offers()` and `compute_bill()` load the cart and coupons and call it.

### Tests: 45 passing (`python -m pytest -q`)
- Optimizer rules: empty cart, % + cap, flat ≤ eligible, minimum checked on eligible items,
  scopes, expired/not-started/disabled never applied, conflicts, beats greedy, independent
  stacking, cap at subtotal, deterministic ties, every coupon applied-or-explained.
- Grounding: every number `locate()` returns equals the DB row. The bill subtotal equals a SQL
  sum. **Changing a price in `inventory` changes the next bill** (proves nothing is cached).
- Stock: can't add out-of-stock items, can't exceed stock (cart unchanged), and every one of the
  51 out-of-stock products gets an in-stock same-type substitute.
- DB tests modify data only temporarily (temp carts are deleted; price/stock changes are
  restored in `finally`).

### Demo output (scripts/05_demo_tools.py), worth showing
Shopping list: 2 toned milk, oats, instant coffee, Britannia brown bread, 3 tea, budget ₹600.
- Britannia Brown Bread is out of stock → `find_substitutes` → Britannia Multigrain Bread
  (same type, +₹5), added instead.
- Bill: subtotal ₹708.90 (MRP ₹898). The optimizer picks **BEV75 (−₹75)** over SAVE10 (10% =
  ₹70.89) because they conflict. Final ₹633.90, which is over the ₹600 budget. Also prints
  "almost unlocked" hints, e.g. AMUL5 needs ₹34 more.
- The over-budget result is intentional: in milestone 5 the agent should react to it, e.g. by
  suggesting cheaper substitutes.

### Known limitations / notes
- `locate()` needs a clean product phrase ("toned milk"). Turning "2 litres milk" into
  (query="milk", qty=2) is the LLM's job in milestone 5.
- Stock is checked when items are added but not reserved. It is decremented only at
  `checkout()` (added in 2b).
- Dates: tools default to `date.today()`. Tests pin `today=2026-10-12` so coupon validity is
  stable.

## Milestone 2b: FastAPI + checkout ✅ DONE

### Files
```
smartcart/api/main.py      FastAPI app: 12 endpoints, error → HTTP mapping, CORS for a future React dev server
smartcart/tools/cart.py    + checkout(). compute_bill() now shares _build_bill(conn, ...) with checkout
smartcart/tools/models.py  + Order, CheckoutResult
tests/test_api.py          11 API tests via FastAPI TestClient (no server needed)
tests/conftest.py          + restore_inventory fixture, delete_session() (also deletes orders)
```

### Endpoints (interactive docs at http://127.0.0.1:8000/docs)
| method + path | tool | notes |
|---|---|---|
| GET `/health` | – | DB reachable + product count |
| GET `/products/search?q=&limit=` | `locate` | |
| GET `/products/{id}/stock?quantity=` | `check_inventory` | |
| GET `/products/{id}/substitutes?quantity=&limit=` | `find_substitutes` | |
| GET `/coupons` | – | all rules, incl. expired/disabled (transparency) |
| POST `/carts` `{session_id}` | `create_cart` | 201 → `{cart_id}` |
| PUT `/carts/{id}/items/{product_id}` `{quantity, mode}` | `update_cart` | not enough stock → **200 with ok=false** + available_stock |
| DELETE `/carts/{id}/items/{product_id}` | `update_cart(…, 0)` | |
| GET `/carts/{id}/bill?today=` | `compute_bill` | `today` optional, to test coupon dates |
| GET `/carts/{id}/offers?today=` | `optimize_offers` | |
| POST `/carts/{id}/checkout` | `checkout` | ok=false + problems if empty / short of stock |
| GET `/orders/{id}` | – | the stored order snapshot |

Error mapping: ProductNotFound / CartNotFound → 404. CartNotActive (e.g. editing a checked-out
cart) → 409. Bad input → 422.

### Design decisions (talking points)
- **The API adds no business logic.** Each endpoint calls exactly one tool, so the agent and the
  frontend see the same grounded numbers.
- **Money is sent as JSON strings** ("33.00", Pydantic's default for Decimal), never floats, so
  no rounding errors and the bill is exact to the paisa.
- **`checkout()` is one atomic transaction:** lock the cart → lock the inventory rows
  (`SELECT … FOR UPDATE`, in product_id order to avoid deadlocks) → compute the final bill
  inside the same transaction → verify stock → decrement stock → insert the `orders` snapshot
  (line_items JSONB, applied coupon codes) → mark the cart CHECKED_OUT. If anything is short,
  nothing is written. Prices and stock can't change between pricing and saving, so two shoppers
  can never both buy the last unit.
- "Not enough stock" is a normal answer (200, ok=false), not an error, because the agent is
  expected to react to it by offering a substitute.

### Tests: 56 total, all passing
Includes: checkout totals equal the bill; stock decremented by exactly the cart quantities; cart
becomes CHECKED_OUT; second checkout → CartNotActive; empty cart refused; stock dropping after
adding → checkout refused and **nothing written**. API: full flow (create → add → refused OOS add
→ bill → offers → checkout → fetch order → 409 on editing the closed cart), validation 422s, 404s,
money serialised as strings. Verified: after the whole suite, inventory totals are identical to a
fresh seed (57,202 units / ₹197,193.74), and there are 0 leftover carts/orders.

## Milestone 5: LangGraph agent ✅ DONE (verified live with Gemini, 2026-10-12)

### Live results (gemini-3.5-flash-lite, real conversation)
| shopper says | what the agent did | time | grounded |
|---|---|---|---|
| "I need 2 toned milk, oats, instant coffee and Britannia brown bread. Budget 600 rupees." | set_budget → 4 parallel searches → 3 adds → bread out of stock → find_substitutes → added Fresho brown bread, told the shopper and listed the alternatives. Total ₹273.20, ₹326.80 left | 6.4 s | ✅ |
| "Add the Britannia multigrain bread instead" | removed the Fresho bread (set 0), added Britannia Multigrain. New total ₹284.20 | 4.0 s | ✅ |
| "Where can I find basmati rice?" | search → "Aisle 4, shelf A4-S7", named the brands | 2.3 s | ✅ |

With the user's original 3.1-flash-lite-preview the same flow worked but took 35–47 s per turn.

### Reliability (`call_llm` in graph.py)
- Main model fails → **fallback model** (separate quota). Verified live by breaking the main
  model on purpose: the fallback answered correctly and grounded.
- **429 rate limit** with "retry in Ns" (N ≤ 15 s) → wait N s, retry the same model once.
- Both models down → **polite reply instead of a crash** ("AI request limit reached… your cart
  is saved"). The cart is never affected.
- **Free tier = 15 requests/min per model.** A shopping turn makes 2–5 LLM calls (the model
  batches tool calls in parallel). For real use, enable billing on the Google AI Studio project.

### Files
```
smartcart/agent/llm.py         get_llm() / get_fallback_llm(): Gemini models from .env. LLMNotConfigured if no key
smartcart/agent/prompts.py     SYSTEM_PROMPT (grounding rules + workflow), grounding retry note
smartcart/agent/tools.py       7 LLM-facing tools (JSON out) + bill_summary() (budget math done by code)
smartcart/agent/graph.py       ShopState + the StateGraph (nodes, conditional edges)
smartcart/agent/grounding.py   grounding check: every ₹ amount / aisle in a reply must come from a tool result
smartcart/agent/assistant.py   ShoppingAssistant.chat(session_id, text) -> ChatReply (used by CLI, API, tests)
scripts/06_chat.py             terminal chat (--trace shows tool calls)
smartcart/api/main.py          + POST /chat (503 if no key; assistant created lazily)
tests/test_agent.py            8 graph tests with ScriptedLLM (fake LLM; no key/network)
tests/test_agent_live.py       3 live Gemini tests, only with `-m live`
pytest.ini                     addopts -m "not live"
```

### The graph (main talking point)
```
START → agent ──tool calls──► tools ──► [stock failure?] ─► auto_substitutes ─┐
          ▲   │                  │      [cart changed?]  ─► refresh_bill ◄────┘ (if cart also changed)
          │   │                  └──── otherwise ─► agent
          │   └──final answer──► grounding_check ──ungrounded (1st time)──► agent
          │                                     └──ok / already retried──► END
          └──────────── auto_substitutes / refresh_bill ────────────┘
```
- **State** (`ShopState`): messages, session_id, cart_id, budget, grounding_retries, ungrounded.
  Memory is per session via the LangGraph checkpointer (`InMemorySaver`, keyed by session_id).
  The cart itself lives in Postgres.
- **The LLM decides what to do** (split the request, which product to pick, what to say).
  **The graph enforces what must not depend on the LLM remembering:**
  1. `auto_substitutes`: any `update_cart` refused for stock, or `check_stock` with
     can_fulfil=false, ALWAYS gets ranked substitutes attached (conditional edge).
  2. `refresh_bill`: any successful cart change ALWAYS gets the freshly computed bill attached,
     including `over_budget_by` / `budget_remaining` computed by code.
  3. `grounding_check`: every final answer is scanned. Any ₹ amount or aisle number that never
     appeared in a tool result (or the shopper's own message) is flagged. The LLM is sent back
     to rewrite once. If it is still wrong, the reply is returned with `grounded=false` and the
     list of bad values (shown to the user, and usable as the metric in milestone 7).
- Attachments are merged into the triggering tool result (same message id) instead of faking
  extra tool calls. This keeps the conversation valid for Gemini's function-calling rules.
- **The LLM cannot touch cart_id or session_id**: they are injected from graph state
  (`InjectedState`). The budget is stored by the `set_budget` tool (a `Command` updating state).
- After a successful `checkout`, the tool opens a fresh cart so the chat can continue.
- LLM tools: search_products, check_stock, find_substitutes, update_cart (add/set), view_bill,
  set_budget, checkout.

### Tests (13 offline + 3 live): 69 offline pass
Reliability (offline): the fallback answers when the main model raises a 503; a short 429 →
wait and retry the same model; both down → polite reply.
Grounding detects invented ₹ amounts/aisles (incl. "Rs. 1,234.50"). An OOS add → substitutes
auto-attached → substitute added → bill attached → grounded reply. Budget: over_budget_by
computed by code. An invented "₹999.99 in aisle 42" → guard → LLM told exactly what was wrong →
rewritten, and grounded=true. Still wrong after the retry → grounded=false with the values listed.
Also: search → quote price/aisle is grounded; memory + same cart across turns; checkout via the
agent opens a new cart; POST /chat → 503 without a key and works with an injected fake LLM.

### Known limitations
- Conversation memory is in-process (`InMemorySaver`): it resets when the server restarts (the
  cart stays in Postgres). Upgrade path: `langgraph-checkpoint-postgres`.
- The grounding check covers ₹ amounts and aisle numbers, not product names or stock counts
  (a possible extension for milestone 7).

## Review II presentation (2026-10-12)

`docs/Group_No_D8_Review_II.pptx` (30 slides) is generated by `docs/build_review2_deck.py`.
- It is built from the approved Review I deck, so it uses the same college template, the same
  10-paper literature survey, gaps and methodology.
- **Updated slides:** Review II title, contents, objectives with a status pill each, and the
  architecture as implemented (Gemini, FastAPI). "Expected Outcomes" was dropped (replaced by the
  status pills).
- **New slides, mapped to the rubric:**
  - Comparison matrix: 10 papers × 7 capabilities (Literature Review)
  - Implementation progress, tech stack, dataset, database design
  - Optimizer mathematical model with a conflict-graph diagram, plus a worked calculation
    (Design Calculation / Analysis)
  - Search and substitution scoring, LangGraph agent graph, grounding guard
  - Testing (chart), live Gemini results (chart), sample output, work remaining, conclusion,
    thank you
- **Every new slide has speaker notes** explaining what to say.
- All numbers were measured from the running system:
  - Worked example: subtotal ₹708.90; SAVE10 ₹70.89 vs BEV75 ₹75 (they conflict) → final ₹633.90.
  - Optimizer timing: median 0.43 ms, max 3.1 ms on 1,000 random 40-item carts.
- The build clones the frame of slide 3 (title, rule, logo, bar). New slides need
  `showMasterSp="0"`, otherwise the layout's colour pattern shows.
- QA: the slides were rendered through PowerPoint COM, and the skill's `validate.py` passes.

## Review III presentation + project guide (2026-10-30)

- **`docs/Group_No_D8_Review_III.pptx`** (33 slides), built by `docs/build_review3_deck.py`. It's a
  copy of the Review II builder, updated as follows:
  - **Text/data changes:** title "Review – III"; 17-item contents; objective statuses (objective
    5 now says taxes (GST)); architecture with the web app/admin and 25 endpoints; progress 6/7;
    a Frontend row in the tech stack; GST in the data/DB slides.
  - **Agent and testing slides:** 8 tools and the budget-plan bullet; a testing chart with 9
    modules (96 tests); a live-results row for the ₹440 web demo (9.2 s).
  - **New slides:** "Budget Fit — Second Optimization Algorithm" and "GST Billing — Tax-Inclusive
    Invoice", both with worked examples from the DB; two screenshot slides (shopper view, store
    admin) with callouts.
  - **Closing slides:** the old CLI "Sample Output" slide was removed; work remaining,
    conclusion and references ([17]) were updated. `validate.py` passes.
- **`docs/assets/`**: real screenshots taken by Puppeteer from the running app
  (`ui-shop-cards-budget.png`, `ui-admin.png`, `ui-shop-gst.png`, `ui-receipt.png`,
  `ui-welcome.png`). The data was re-seeded afterwards.
- **`docs/SmartCart_Project_Guide.docx`** (13 pages, A4), for the team and the guide:
  - what the project is (with screenshots), architecture and algorithms, folder structure
  - prerequisites, first-time setup, daily running
  - testing: automated, live and a 9-step manual checklist with expected values
  - an 8-minute demo script, troubleshooting, a command reference
  - 12 likely viva Q&As, limitations

  It was generated with docx-js from a script in the session scratchpad (not kept in the repo).
  Edit the .docx directly in Word if it needs changes.
- Admin page layout change: **Recent orders now sits above Coupons**, and the coupon list scrolls
  inside its panel.

## Milestone 6: Web frontend ✅ DONE (2026-10-30)

### Files
```
frontend/                         Vite + React 19 + TypeScript (npm project; node_modules/ and dist/ are gitignored)
frontend/vite.config.ts           dev proxy /api/* -> http://127.0.0.1:8000
frontend/src/api.ts               typed API client; money kept as the server's exact strings; rupees() formatter
frontend/src/App.tsx              state: session id + chat history in localStorage, bill, busy, toast, receipt
frontend/src/components/Chat.tsx       welcome + example requests, messages (markdown), grounding badge, tool trace, composer
frontend/src/components/CartPanel.tsx  items (aisle/shelf, +/− stepper), pick route, bill, almost-unlocked, budget bar, pinned total + checkout
frontend/src/components/Receipt.tsx    order receipt dialog after checkout
frontend/src/index.css            all styles (navy/red palette from the slides, green = savings/grounded), responsive at ≤900px
smartcart/api/main.py             + /sessions endpoints, /health.llm_configured, serves frontend/dist at "/"
smartcart/agent/assistant.py      + session(), set_item(), checkout(), SessionNotFound
smartcart/tools/models.py, cart.py  BillLine now carries aisle_no, aisle_name, shelf_code
smartcart/agent/tools.py          bill_summary items include brand, stock, aisle, shelf
tests/test_api.py                 + test_session_endpoints_share_the_agents_cart
```

### New endpoints (used by the UI)
| method + path | what |
|---|---|
| GET `/sessions/{sid}` | cart_id, budget, live bill of a chat session (404 before its first message) |
| PUT `/sessions/{sid}/items/{product_id}` `{quantity}` | set a quantity in the agent's cart (0 removes) → `{update, session}` |
| POST `/sessions/{sid}/checkout` | checkout → `{result, session}`. On success the agent continues with a fresh cart |

### Design decisions (talking points)
- **The UI never computes money.** Every amount is the exact string the server returned. The
  only arithmetic is the budget bar's width.
- **One cart, two ways to edit it.** The agent and the +/− buttons edit the same Postgres cart
  (the session endpoints look the cart up in the agent's state). After a UI checkout the agent's
  state is switched to the new cart, so the chat keeps working.
- **Transparency per reply:** a "Grounded in database" badge (or "Unverified: ₹…" if the guard
  flagged something), plus an expandable trace of every tool call (e.g. `search_products
  "toned milk"`, `update_cart add #171 × 2`, `find_substitutes for #171`).
- **Pick route:** the aisles holding cart items, in walking order (aisle 1 is the entrance). This
  is the shelf-level location feature made visible.
- Chat history is kept in localStorage per session. If the server restarted (agent memory is
  in-process), the UI shows "Previous conversation expired" and starts fresh.
- The header shows server status: products live, and "Gemini agent ready" or "GOOGLE_API_KEY
  missing" (from `/health`). The composer is disabled if the AI isn't available.

### Verification (2026-10-30)
- `npm run build` (TypeScript strict) and `npm run lint` (oxlint) are clean. The backend has 70
  passing tests.
- End-to-end in headless Chrome (Puppeteer) against the real server + Gemini:
  - The example request → the agent tried the out-of-stock Britannia bread, the graph attached
    substitutes, and multigrain was added. 10 tool calls, grounded.
  - +1 milk → the total went ₹291 → ₹324 without the LLM.
  - A second question took 6 s.
  - After a reload, the chat and cart were restored.
  - Checkout → receipt "Order #21, paid ₹324.00", and the cart emptied.
  - Phone width: no horizontal scroll.
  - Coupon scenario: BEV75 −₹75, almost-unlocked SAVE10/AMUL5/DAIRY10, budget ₹400 → "Over by
    ₹12.90". No console errors.
- The first reply can take ~5–30 s, depending on Gemini load. Later replies take ~5 s.

## Milestone 6b: four extra features ✅ DONE (2026-10-30)

The user chose these from a ranked list. Each one fills a synopsis promise or a rubric item.

### (4) GST breakdown: synopsis objective 5 ("taxes")
- `products.gst_rate` (CHECK ∈ {0, 5, 18, 40}) comes from the hand-authored
  `data/seed/gst_rates_seed.csv` (rules by category → sub-category → product type, most
  specific wins; seeding fails if a rule matches nothing). Current split: 0% × 172, 5% × 465,
  18% × 190, 40% × 22. **The rates are simplified/illustrative.** Real GST depends on HSN codes,
  which the dataset doesn't have. Say so if asked.
- **Prices are GST-inclusive** (Indian MRP), so GST is *shown*, not added. A discount at sale
  reduces the taxable value, so `smartcart/tools/tax.py` works like this:
  1. Split each applied coupon across its eligible lines in proportion to their totals. The
     rounding remainder goes to the largest line, and any excess from overlapping coupons is
     moved to lines with room.
  2. Per line: taxable = net × 100/(100+rate), gst = net − taxable, CGST = gst/2,
     SGST = rest.
  3. Group the lines into rate slabs.
- **Invariants (tested):** the shares add up to the discount; no share exceeds its line;
  Σ taxable + Σ GST = final_total exactly.
- Bill/receipt: `gst_total` + `tax_breakup`. `orders.gst_total` is stored, and the line_items
  carry gst_rate/discount_share/gst.

### (3) "Fit my budget" optimizer: a second optimization algorithm (Design/Analysis talking point)
- `smartcart/tools/budget.py`, `fit_budget(cart_id, budget)` (read-only suggestion).
- **Candidates:** each line can keep its product or switch to a cheaper, in-stock product of
  the **same product type**, same quantity. Up to 3 per line: the closest-cheaper ones plus the
  cheapest.
- **Objective (lexicographic):** total ≤ budget, and
  1. the **fewest swaps** (least disruption)
  2. then the **highest total that still fits** (least downgrade)
  3. then a deterministic tie-break
- **Coupons are re-optimized for every plan**, because a swap can win or lose a coupon. Test:
  swapping to a ₹990 item loses a "₹100 off above ₹1000" coupon, so the planner picks the
  ₹900 item.
- **Exact search** by increasing k = number of swaps: Σ C(n,k)·m^k evaluations, each running the
  exact coupon optimizer. Proven against brute force over every plan on 150 random carts. If
  nothing fits it says so and reports the cheapest reachable total.
- **Graph-enforced** (like substitutes): whenever `refresh_bill` finds the cart over budget it
  attaches `budget_fit`, so the agent always offers the swaps and asks before applying them.
  Verified live: "swapping Homogenized Milk for Camel Milk brings your total to ₹431.90".
  Agent tool `fit_budget` exists too.
- UI: the budget is editable in the cart panel (`PUT /sessions/{sid}/budget`, the same state the
  agent uses). "Fit my budget" calls `GET /sessions/{sid}/budget-plan`, and "Apply swaps" calls
  `POST /sessions/{sid}/swaps`, which adds the new product first, so if stock refuses it the
  original stays.

### (2) Clickable product cards in chat: synopsis objective 4 (user confirms substitutes)
- `smartcart/agent/suggestions.py` builds `ChatReply.suggestions` from **this turn's tool
  results**: substitute groups (from find_substitutes or the graph's auto_substitutes) and
  search groups (only when none of their products were added, and not duplicating a
  substitute group). Card values are copied from DB tool output, never parsed from LLM text.
- UI `ProductCards.tsx`: the button shows **Add**, **Swap in** (when another option for the same
  item is in the cart → `/swaps`), **In cart · n**, or **Out of stock**. Substitute price
  differences show as green/amber chips. This also gives milestone 7 a way to measure
  substitution acceptance.

### (1) Store admin page: the live proof of the core design rule
- `smartcart/admin.py` is **deliberately not an agent tool**: the LLM can read prices but
  can't change them.
- Functions: `list_inventory` (search, filter all/out/low), `update_inventory` (price > 0 and
  **≤ MRP**, since selling above MRP is illegal in India; stock ≥ 0; → 422 otherwise),
  `list_coupons` (status live/disabled/expired + conflicts), `set_coupon_active`, `summary`
  (stock counts, live coupons, orders, revenue, discounts, GST), `recent_orders`.
- Endpoints: `GET /admin/summary`, `GET/PATCH /admin/inventory[/{id}]`,
  `GET/PATCH /admin/coupons[/{code}]`, `GET /admin/orders`. **No authentication** (local demo
  only). Mention this as a known limitation.
- UI `#/admin` (header tabs Shop | Store admin): stat cards, an editable inventory table, coupon
  switches, recent orders. The shopper page **polls its bill every 4 s** and shows "Store prices
  or stock changed — your bill was updated". Verified: a ₹10 price cut in admin → the shopper's
  total dropped ₹30 (qty 3) within one poll.

### Files added/changed
```
data/seed/gst_rates_seed.csv   GST rules            db/schema.sql  products.gst_rate, orders.gst_total, view + gst_rate
scripts/03_seed_database.py    apply_gst_rates()    smartcart/tools/tax.py      discount allocation + GST (pure)
smartcart/tools/budget.py      fit_budget / plan_budget_fit (pure planner)
smartcart/tools/offers.py      + line_matches()     smartcart/tools/cart.py     bill/checkout carry GST
smartcart/admin.py             staff operations     smartcart/agent/suggestions.py  product cards
smartcart/agent/{tools,graph,prompts,assistant}.py  fit_budget tool, auto budget_fit, set_budget/budget_plan/apply_swaps
smartcart/api/main.py          /sessions/{sid}/budget|budget-plan|swaps, /admin/*
frontend/src/components/       ProductCards.tsx, Admin.tsx (new); CartPanel/Chat/Receipt/App updated
tests/                         test_tax.py (7), test_budget.py (6), test_admin.py (7), + API/agent tests → 93 total
```

### Verification (2026-10-30)
- 93 offline tests pass. The frontend build and lint are clean.
- End-to-end in Chrome against live Gemini, with zero console errors:
  - cards: Swap in / In cart / Out of stock
  - budget plan: 1 swap, "3 plans checked" → applied → "₹8.10 left"
  - GST ₹16.33 split 0% / 5%
  - Swap in replaced the bread
  - admin price edit → the shopper tab updated itself
  - a price above MRP was rejected with "above the MRP ₹199.00"
  - checkout receipt with the GST table; the order showed in admin
  - admin page at phone width: no overflow
- Data was re-seeded afterwards: 57,202 units, 0 carts/orders.

## Milestone 7: Evaluation harness ✅ DONE (2026-11-12)

### Files
```
smartcart/eval/goals.py      12 scripted goals (Goal/Want): expectations as PRODUCT TYPES + quantities
smartcart/eval/metrics.py    pure scoring: brute-force coupon optimum, greedy + single-coupon baselines,
                             check_goal (task success), substitution_report, reply_values
smartcart/eval/runner.py     run_goal/run_goals (paced, retries on rate limit, deletes its carts),
                             summarize(), offline_offer_study() (300 random real carts, no LLM)
smartcart/eval/report.py     writes docs/evaluation/results.json + EVALUATION_REPORT.md
scripts/07_evaluate.py       CLI (see ALL COMMANDS)
docs/evaluation/             latest run + run1_baseline/, run2/, run3_final/ (kept for before/after)
smartcart/agent/assistant.py ChatReply + llm_calls, models, grounding_retried
smartcart/api/main.py        GET /admin/evaluation (26 endpoints now)
frontend/.../EvaluationPanel.tsx  "Evaluation" tab (#/eval): metric tiles + per-goal table
tests/test_eval.py           5 offline tests (baselines, scoring, substitution, endpoint, full run with fake LLM)
docs/build_final_deck.py     POE deck = Review III deck + 3 evaluation slides, 7/7 status
```

### The 12 goals (each one tests specific features)
G01 multi-item list · G02 named product out of stock · G03 two OOS items · G04 budget ₹440 +
coupon + OOS (main demo) · G05 navigation only ("where is basmati rice…") · G06 typos ("egs",
"buter") · G07 quantity above live stock (5 milk, 3 in stock) · G08 multi-turn edit ("make it 4,
remove the ketchup") · G09 staples with stacked coupons · G10 budget ₹500 · G11 GST question
(2 turns) · G12 personal care.

### How each metric is measured (all by code, NOT by an LLM judge)
- **Task success:** the cart is read back from PostgreSQL. Each requested item must be there as the
  right `product_type` with the exact quantity, removed items must be gone, the budget must be
  recorded, and where asked, the reply must quote the bill value (final_total / discount_total /
  gst_included). If an item couldn't be supplied and the agent showed substitute cards for the
  shopper to choose (synopsis objective 4: user confirms), that check is "pending": it passes the
  normal score and fails the **strict** score.
- **Grounding accuracy:** % of replies where every ₹ amount / aisle number appeared in a tool result.
- **Discount captured:** system discount ÷ brute-force optimum over every conflict-free subset of
  valid coupons, on the agent's final carts. Baselines: greedy (biggest first), single best coupon.
- **Substitution correct:** every unavailable product → a same-type, in-stock product in the cart
  (or offered). Also records whether it was the top-ranked substitute.
- **Latency / LLM calls per turn** (from the model's response metadata).

### Results (3 live runs, gemini-3.5-flash-lite, 2026-11-12)
| | run 1 (baseline) | run 2 | run 3 (final) |
|---|---|---|---|
| task success | 8/12 (10/12 rescored) | 11/12 | **12/12** (strict 10/12) |
| grounding | 100% | 100% | **100%** (105 values, 0 rewrites) |
| discount vs optimum | 100% | 100% | **100%** |
| substitution correct | 83% | 83% | **100%** |
| median latency/turn | 6.6 s | 13.1 s | 17.5 s (Gemini was slow that day) |

**What run 1 found (good viva story: this is what an evaluation is for):**
1. "Britannia Brown Bread" was OOS in the search results and the agent added *milk bread* (a
   different type) itself, bypassing the substitution path.
2. "Add 5 Amul toned milk" with 3 in stock: the agent silently added 3 (found in run 2).
3. It named coupons without the amount saved.

The fix was two prompt rules in `prompts.py` (named product OOS → still call update_cart /
find_substitutes; partial stock → request the full quantity, never silently add fewer; and quote
each coupon's discount). Re-run → 12/12. The agent often picks the 2nd-ranked substitute (e.g.
cheaper Fresho bread over Britannia multigrain): same type, valid, but "top-ranked" is only 33%.

**Offline coupon study (no LLM, 300 random real carts, today pinned to 2026-10-12):** our optimizer
300/300 optimal (100%); greedy 99.97% (1 cart below optimum); best single coupon only 55.6%.
Optimizer median 0.18 ms.

### Phase II re-run (2026-11-12, after the enhancements): 15 goals
G13 Hindi request, G14 Marathi request + navigation, G15 store comparison were added (plus a
"must call tool X" check). Result: **15/15 goals, 53/53 checks, strict 15/15, grounding 100% (147
values, 0 rewrites), discount 100% of optimum, substitution 100%**, median 9.2 s/turn, 4.2 LLM
calls/turn. Saved in `docs/evaluation/run4_phase2/` (and as the current results.json).

### Why not DeepEval / RAGAS? (likely viva question)
RAGAS targets retrieval-augmented generation (faithfulness to retrieved passages); our agent
retrieves no documents, it calls database tools. DeepEval has agent metrics (ToolCorrectness,
TaskCompletion, G-Eval), but most of them use an LLM as judge, which only gives an opinion. Our
core claims (no invented number, optimal discount) can be checked **exactly** by code against
PostgreSQL and brute force, which is stronger. An LLM-judge layer (DeepEval) could be added for
soft qualities like explanation clarity. It was discussed with the user (2026-11-12) but not
added.

### Notes
- The run is paced (`--pace 5` = 5 s reserved per LLM call ≈ 12 requests/min). On a rate limit it
  waits 65 s and replays the goal from scratch (max 2 retries). Rate-limited goals are reported as
  infra errors and excluded.
- No goal checks out, and each goal's carts are deleted, so the data stays identical
  (verified: 57,202 units, 0 carts, 0 orders after a run).
- Gemini latency varies a lot by day/time: ~1 s per call on 2026-10-12, ~5 s on 2026-11-12.
- `npm run lint` (oxlint) currently fails to start on this machine (native binding load error in
  oxlint itself, Node 24). `npm run build` (TypeScript strict) passes.

## Phase II enhancements ✅ DONE (2026-11-12)

The user asked to implement the deck's "Enhancements" + "Phase II deliverables" before the POE.
Cloud deployment was postponed by the user ("we will do deployment part later"); the Docker image
exists and was tested locally, but no cloud account was used and no deployment guide was written.

| feature | files | how it works / talking point |
|---|---|---|
| **Persistent chat memory** | `smartcart/agent/memory.py` | Our own LangGraph `BaseCheckpointSaver` on SQLAlchemy/psycopg2 (tables `agent_checkpoints`, `agent_checkpoint_writes`). The official `langgraph-checkpoint-postgres` needs psycopg 3, whose DLL is **blocked by an Application Control policy** on this PC (also `pip.exe` is blocked: always use `python -m pip`). ShoppingAssistant uses it by default. Test: a new assistant object (= restarted server) continues the chat. |
| **Staff login + roles + audit** | `smartcart/auth.py`, `admin.py`, tables `staff_users`, `admin_audit` | PBKDF2-SHA256 (200k iterations, salted), HMAC-signed 12-h token (`ADMIN_TOKEN_SECRET` in .env, else random per start). manager = prices/stock/coupons, staff = stock only (403 enforced server-side in admin.py). Every change audited (who, old → new), "Recent changes" panel. All `/admin/*` need `Authorization: Bearer`, except `/admin/login` and the public `/admin/evaluation`. Demo users created by the seed: manager/manager123, staff/staff123. |
| **Hindi / Marathi + voice** | `prompts.py` rule 9, `grounding.py`, `Chat.tsx` | Agent replies in the shopper's language but searches with English phrases. Grounding regex now handles Devanagari digits (४५), रुपये/रुपए/रुपयांना, and aisle words गलियारा/आयल/रांग (+ नंबर/क्रमांक). Also fixed: a trailing comma was captured in amounts ("₹50,"). Voice = browser Web Speech API (Chrome/Edge), language picker EN/हिंदी/मराठी. |
| **Multi-store comparison** | `smartcart/tools/stores.py`, table `store_prices`, `stores.is_home/accepts_coupons` | 2 synthetic stores: SmartMart Ichalkaranji (same chain, coupons valid, 787 products) and FreshBasket Sangli (competitor, no coupons, 779). Separate RNG per store, so the home store's data is **byte-identical** to before (md5 verified). Only the home store has an aisle map (design rationale unchanged). Recommends the cheapest store that can supply the WHOLE cart. Agent tool `compare_stores` (9 tools now), UI "Compare with other stores", `GET /sessions/{sid}/compare-stores`, `/carts/{id}/compare-stores`, `/stores`. |
| **User-study mode** | `smartcart/study.py`, `StudyPage.tsx` (#/study), `scripts/08_study_report.py`, table `study_runs` | Within-subjects: task A/B, assistant vs manual (search + Add), counterbalanced. Server times Start→Finish and scores the cart with the evaluation's `check_goal` (+ budget ≤ ₹600 for task B). `study_runs` has no FKs and is NOT dropped by the seed, so study data survives re-seeding. **No participant data exists yet: never invent study results.** |
| **Cloud-ready image** | `Dockerfile`, `.dockerignore`, `requirements-app.txt`, `docker-compose.prod.yml`, `scripts/09_staff.py` | 2-stage build (node:22 → python:3.10-slim), serves UI + API on `$PORT`, healthcheck. `db.py` accepts `postgres://` URLs. Verified locally against the dev DB on port 8001. |
| **Documents** | `docs/collect_facts.py`, `docs/build_documents.js`, `docs/package.json` | Rebuilt Project Guide (+ Phase II sections, login, study protocol), new **Project Report draft** (college format: certificate, abstract, 9 chapters, references, appendices) and **Research Paper draft** (IEEE-style 2 columns). All numbers from facts.json. |
| **Deck** | `docs/build_final_deck.py` | +2 slides (Phase II Enhancements; Hindi chat & store comparison), admin slide now shows login/roles/audit, counts read from facts.json. 38 slides. |

Numbers now: **15 tables**, **37 endpoints**, **108 offline + 3 live tests**, 9 agent tools.

Screenshots (docs/assets, taken by Puppeteer from the running app): ui-login, ui-admin-staff,
ui-admin-audit, ui-hindi-welcome, ui-hindi-chat, ui-compare, ui-study, ui-study-result, ui-eval.
Data was re-seeded afterwards.

Mistake to avoid: the slide-render helper (PowerPoint COM) once called `Quit()` on the user's
already-open PowerPoint and closed their deck. The helper now only quits PowerPoint if it started it.
