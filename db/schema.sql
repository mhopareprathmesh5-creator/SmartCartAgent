-- =====================================================================
-- Smart-Cart & Billing Assistant Agent — PostgreSQL schema
--
-- Core rule: every price, stock count, aisle location, discount and
-- total the agent ever shows comes from these tables, never from the LLM.
--
-- 9 tables in 4 groups:
--   Catalog      : products
--   Store layer  : stores, store_map, inventory
--   Offers       : coupons, coupon_conflicts
--   Cart/Orders  : carts, cart_items, orders
--
-- Re-runnable: drops and recreates everything (used by 03_seed_database.py).
-- =====================================================================

DROP VIEW  IF EXISTS v_store_catalog;
DROP TABLE IF EXISTS agent_checkpoint_writes, agent_checkpoints,
                     admin_audit, staff_users, store_prices,
                     orders, cart_items, carts,
                     coupon_conflicts, coupons,
                     inventory, store_map, stores,
                     products CASCADE;

CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- fuzzy product-name search for locate()

-- ---------------------------------------------------------------------
-- CATALOG
-- ---------------------------------------------------------------------
-- Master product data (from the BigBasket dataset). Changes rarely.
-- base_price = MRP. It is NOT the selling price — see inventory.current_price.
CREATE TABLE products (
    product_id    SERIAL PRIMARY KEY,
    source_id     INTEGER UNIQUE,               -- row index in the BigBasket CSV (traceability)
    name          TEXT          NOT NULL,
    brand         TEXT          NOT NULL,
    category      TEXT          NOT NULL,
    sub_category  TEXT          NOT NULL,
    product_type  TEXT          NOT NULL,       -- finest grouping; used to find substitutes
    pack_size     TEXT,                         -- parsed from name when present (e.g. "500 g")
    base_price    NUMERIC(10,2) NOT NULL CHECK (base_price > 0),
    gst_rate      NUMERIC(4,2)  NOT NULL DEFAULT 0
                  CHECK (gst_rate IN (0, 5, 18, 40)),   -- % GST included in the price (data/seed/gst_rates_seed.csv)
    rating        NUMERIC(2,1)  CHECK (rating BETWEEN 0 AND 5),
    description   TEXT,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX idx_products_category     ON products (category);
CREATE INDEX idx_products_sub_category ON products (sub_category);
CREATE INDEX idx_products_type         ON products (product_type);
CREATE INDEX idx_products_brand        ON products (brand);
CREATE INDEX idx_products_name_trgm    ON products USING gin (lower(name) gin_trgm_ops);

-- ---------------------------------------------------------------------
-- STORE LAYER
-- ---------------------------------------------------------------------
-- Single simulated supermarket (multi-store is Future Scope), but keyed by
-- store_id so the design does not have to change if that is ever added.
CREATE TABLE stores (
    store_id   SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    city       TEXT NOT NULL,
    address    TEXT,
    num_aisles SMALLINT NOT NULL CHECK (num_aisles > 0),
    is_home          BOOLEAN NOT NULL DEFAULT FALSE,  -- the store the shopper is in (aisle map, carts)
    accepts_coupons  BOOLEAN NOT NULL DEFAULT TRUE    -- chain-wide coupons valid here
);

-- Multi-store comparison (Phase II): the OTHER stores publish only a price/stock
-- feed (no aisle map — navigation only makes sense inside the home store). The home
-- store's live prices stay in `inventory`, so every existing tool is unchanged.
CREATE TABLE store_prices (
    store_id    INTEGER       NOT NULL REFERENCES stores(store_id) ON DELETE CASCADE,
    product_id  INTEGER       NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    price       NUMERIC(10,2) NOT NULL CHECK (price > 0),
    stock_qty   INTEGER       NOT NULL CHECK (stock_qty >= 0),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (store_id, product_id)
);

-- Physical location of every product: aisle -> shelf -> level.
-- One aisle per category, one shelf per sub-category inside it.
CREATE TABLE store_map (
    store_id     INTEGER  NOT NULL REFERENCES stores(store_id) ON DELETE CASCADE,
    product_id   INTEGER  NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    aisle_no     SMALLINT NOT NULL CHECK (aisle_no > 0),
    aisle_name   TEXT     NOT NULL,
    shelf_code   TEXT     NOT NULL,             -- e.g. 'A3-S2' = aisle 3, shelf 2
    shelf_label  TEXT     NOT NULL,             -- human label = sub-category
    shelf_level  SMALLINT NOT NULL CHECK (shelf_level BETWEEN 1 AND 5),  -- 1 = bottom
    PRIMARY KEY (store_id, product_id)
);
CREATE INDEX idx_store_map_aisle ON store_map (store_id, aisle_no);

-- Live, frequently-changing data. Kept separate from products on purpose:
-- daily price/stock refreshes touch ONLY this table. Tool functions read
-- prices from here, never from products.base_price.
CREATE TABLE inventory (
    store_id       INTEGER       NOT NULL REFERENCES stores(store_id) ON DELETE CASCADE,
    product_id     INTEGER       NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    stock_qty      INTEGER       NOT NULL CHECK (stock_qty >= 0),
    current_price  NUMERIC(10,2) NOT NULL CHECK (current_price > 0),
    reorder_level  INTEGER       NOT NULL DEFAULT 10 CHECK (reorder_level >= 0),
    updated_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (store_id, product_id)
);
CREATE INDEX idx_inventory_out_of_stock ON inventory (store_id) WHERE stock_qty = 0;

-- ---------------------------------------------------------------------
-- OFFERS
-- ---------------------------------------------------------------------
-- A coupon gives PERCENT or FLAT discount on the items it is eligible for:
--   scope = CART         -> whole cart            (scope_value NULL)
--   scope = CATEGORY     -> items in that category
--   scope = SUB_CATEGORY -> items in that sub-category
--   scope = BRAND        -> items of that brand
-- min_cart_value is checked against the subtotal of the ELIGIBLE items
-- (for CART scope that is the whole cart). max_discount caps PERCENT coupons.
CREATE TABLE coupons (
    coupon_id       SERIAL PRIMARY KEY,
    code            TEXT          NOT NULL UNIQUE,
    description     TEXT          NOT NULL,
    discount_type   TEXT          NOT NULL CHECK (discount_type IN ('PERCENT', 'FLAT')),
    discount_value  NUMERIC(10,2) NOT NULL CHECK (discount_value > 0),
    max_discount    NUMERIC(10,2) CHECK (max_discount > 0),
    min_cart_value  NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (min_cart_value >= 0),
    scope           TEXT          NOT NULL CHECK (scope IN ('CART', 'CATEGORY', 'SUB_CATEGORY', 'BRAND')),
    scope_value     TEXT,
    valid_from      DATE          NOT NULL,
    valid_to        DATE          NOT NULL,
    is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
    CHECK (discount_type <> 'PERCENT' OR discount_value <= 100),
    CHECK ((scope = 'CART') = (scope_value IS NULL)),
    CHECK (valid_to >= valid_from)
);

-- Explicit pairwise mutual exclusion: coupon_a and coupon_b can never be
-- applied together. Stored once per pair (coupon_a < coupon_b).
-- This is what turns offer selection into a real combinatorial problem.
CREATE TABLE coupon_conflicts (
    coupon_a  INTEGER NOT NULL REFERENCES coupons(coupon_id) ON DELETE CASCADE,
    coupon_b  INTEGER NOT NULL REFERENCES coupons(coupon_id) ON DELETE CASCADE,
    reason    TEXT    NOT NULL,
    PRIMARY KEY (coupon_a, coupon_b),
    CHECK (coupon_a < coupon_b)
);

-- ---------------------------------------------------------------------
-- CART & ORDERS
-- ---------------------------------------------------------------------
CREATE TABLE carts (
    cart_id     SERIAL PRIMARY KEY,
    store_id    INTEGER     NOT NULL REFERENCES stores(store_id),
    session_id  TEXT        NOT NULL,           -- links to the agent's conversation thread
    status      TEXT        NOT NULL DEFAULT 'ACTIVE'
                            CHECK (status IN ('ACTIVE', 'CHECKED_OUT', 'ABANDONED')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_carts_session ON carts (session_id);

-- Deliberately stores NO price: the running bill is always recomputed from
-- inventory.current_price, so it can never go stale or be invented.
CREATE TABLE cart_items (
    cart_id     INTEGER     NOT NULL REFERENCES carts(cart_id) ON DELETE CASCADE,
    product_id  INTEGER     NOT NULL REFERENCES products(product_id),
    quantity    INTEGER     NOT NULL CHECK (quantity > 0),
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cart_id, product_id)
);

-- Immutable snapshot taken at checkout (the audit record).
CREATE TABLE orders (
    order_id         SERIAL PRIMARY KEY,
    cart_id          INTEGER       NOT NULL UNIQUE REFERENCES carts(cart_id),
    subtotal         NUMERIC(10,2) NOT NULL CHECK (subtotal >= 0),
    discount_total   NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (discount_total >= 0),
    final_total      NUMERIC(10,2) NOT NULL CHECK (final_total >= 0),
    applied_coupons  TEXT[]        NOT NULL DEFAULT '{}',
    gst_total        NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (gst_total >= 0),  -- GST included in final_total
    line_items       JSONB         NOT NULL,    -- [{product_id, name, qty, unit_price, line_total, gst_rate, discount_share, gst}]
    placed_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CHECK (final_total = subtotal - discount_total),
    CHECK (gst_total <= final_total)
);

-- ---------------------------------------------------------------------
-- STORE STAFF (admin login & roles, smartcart/auth.py)
--   manager : prices, stock, coupons      staff : stock only
-- Every admin change is written to admin_audit (who, what, before -> after).
-- ---------------------------------------------------------------------
CREATE TABLE staff_users (
    username       TEXT PRIMARY KEY,
    full_name      TEXT NOT NULL,
    role           TEXT NOT NULL CHECK (role IN ('manager', 'staff')),
    password_hash  TEXT NOT NULL,              -- pbkdf2_sha256$iterations$salt$hash
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE admin_audit (
    audit_id   SERIAL PRIMARY KEY,
    username   TEXT  NOT NULL,
    role       TEXT  NOT NULL,
    action     TEXT  NOT NULL,                 -- 'price', 'stock', 'coupon'
    target     TEXT  NOT NULL,                 -- product id / coupon code
    detail     JSONB NOT NULL,                 -- {"from": ..., "to": ..., "name": ...}
    at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- AGENT MEMORY (LangGraph checkpoints, smartcart/agent/memory.py)
-- Conversation state per chat session (thread_id = session_id), so a chat
-- continues after a server restart. Holds no prices: the bill is always
-- recomputed from inventory.
-- ---------------------------------------------------------------------
CREATE TABLE agent_checkpoints (
    thread_id      TEXT  NOT NULL,
    checkpoint_ns  TEXT  NOT NULL DEFAULT '',
    checkpoint_id  TEXT  NOT NULL,
    parent_id      TEXT,
    type           TEXT  NOT NULL,
    checkpoint     BYTEA NOT NULL,
    metadata_type  TEXT  NOT NULL,
    metadata       BYTEA NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
CREATE TABLE agent_checkpoint_writes (
    thread_id      TEXT    NOT NULL,
    checkpoint_ns  TEXT    NOT NULL DEFAULT '',
    checkpoint_id  TEXT    NOT NULL,
    task_id        TEXT    NOT NULL,
    idx            INTEGER NOT NULL,
    channel        TEXT    NOT NULL,
    type           TEXT    NOT NULL,
    value          BYTEA   NOT NULL,
    task_path      TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- ---------------------------------------------------------------------
-- USER STUDY (Phase II, smartcart/study.py): time + correctness of a shopping task
-- done with the assistant vs. manually. NOT dropped on re-seed (no foreign keys:
-- the final cart is copied into `cart`), so study data survives `03_seed_database.py`.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS study_runs (
    run_id       SERIAL PRIMARY KEY,
    participant  TEXT        NOT NULL,
    mode         TEXT        NOT NULL CHECK (mode IN ('assistant', 'manual')),
    task_id      TEXT        NOT NULL,
    session_id   TEXT        NOT NULL,
    cart_id      INTEGER     NOT NULL,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    seconds      NUMERIC(8,1),
    success      BOOLEAN,
    checks       JSONB,
    cart         JSONB,
    final_total  NUMERIC(10,2),
    messages     INTEGER                     -- chat messages sent (assistant mode)
);

-- ---------------------------------------------------------------------
-- Convenience view: one row per product with its location, stock and live price.
-- Tool functions (locate / check_inventory) can read from this.
-- ---------------------------------------------------------------------
CREATE VIEW v_store_catalog AS
SELECT  i.store_id,
        p.product_id, p.name, p.brand, p.category, p.sub_category, p.product_type,
        p.pack_size, p.base_price AS mrp, p.rating, p.gst_rate,
        i.current_price, i.stock_qty, (i.stock_qty > 0) AS in_stock,
        m.aisle_no, m.aisle_name, m.shelf_code, m.shelf_label, m.shelf_level
FROM products p
JOIN inventory i ON i.product_id = p.product_id
JOIN store_map m ON m.product_id = p.product_id AND m.store_id = i.store_id;
