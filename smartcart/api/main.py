"""FastAPI wrapper around the tool functions.

Run:   uvicorn smartcart.api.main:app --reload
Docs:  http://127.0.0.1:8000/docs   (interactive Swagger UI — try every endpoint)

The API adds no business logic: each endpoint calls one tool function, so the
LangGraph agent (milestone 5) and the frontend (milestone 6) see exactly the
same grounded numbers. Money values are serialised as strings ("33.00") so no
precision is lost in JSON.
"""
import json
import os
from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text

from smartcart import admin, auth, study
from smartcart.admin import CouponNotFound
from smartcart.auth import AuthError, Forbidden, StaffUser
from smartcart.agent.assistant import SessionNotFound
from smartcart.agent.llm import LLMNotConfigured
from smartcart.db import get_engine
from smartcart.tools import (CartNotActive, CartNotFound, ProductNotFound, check_inventory,
                             checkout, compare_stores, compute_bill, create_cart, find_substitutes,
                             locate, optimize_offers, update_cart)
from smartcart.tools.models import (Bill, CartUpdate, CheckoutResult, Coupon, OfferResult,
                                    ProductLocation, StockStatus, Substitute)
from smartcart.tools.offers import load_coupons

app = FastAPI(
    title="Smart-Cart & Billing Assistant API",
    description="Tool functions of the Smart-Cart agent. Every price, stock count, location, "
                "discount and total comes from PostgreSQL — never from the LLM.",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],   # future React dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- errors -> HTTP
@app.exception_handler(ProductNotFound)
@app.exception_handler(CartNotFound)
@app.exception_handler(SessionNotFound)
@app.exception_handler(CouponNotFound)
async def not_found(_: Request, exc: Exception):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(CartNotActive)
async def conflict(_: Request, exc: Exception):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def bad_value(_: Request, exc: Exception):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(AuthError)
async def unauthorized(_: Request, exc: Exception):
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(Forbidden)
async def forbidden(_: Request, exc: Exception):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


def staff_user(authorization: Optional[str] = Header(default=None)) -> StaffUser:
    """Dependency for every /admin endpoint: a valid `Authorization: Bearer <token>` from /admin/login."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Please log in as store staff")
    return auth.read_token(authorization.split(" ", 1)[1].strip())


# ---------------------------------------------------------------- request bodies
class NewCart(BaseModel):
    session_id: str = Field(min_length=1, examples=["chat-session-42"])


class CartItemChange(BaseModel):
    quantity: int = Field(ge=0, examples=[2])
    mode: Literal["set", "add"] = "set"


class CartCreated(BaseModel):
    cart_id: int
    session_id: str


# ---------------------------------------------------------------- endpoints
@app.get("/health", tags=["meta"])
def health():
    with get_engine().connect() as conn:
        products = conn.execute(text("SELECT count(*) FROM products")).scalar_one()
    return {"status": "ok", "products": products, "llm_configured": bool(os.environ.get("GOOGLE_API_KEY"))}


@app.get("/products/search", response_model=list[ProductLocation], tags=["catalogue"])
def search_products(q: str = Query(min_length=1, examples=["toned milk"]),
                    limit: int = Query(5, ge=1, le=50)):
    """locate(): fuzzy product search with aisle / shelf location, live price and stock."""
    return locate(q, limit=limit)


@app.get("/products/{product_id}/stock", response_model=StockStatus, tags=["catalogue"])
def product_stock(product_id: int, quantity: int = Query(1, ge=1)):
    """check_inventory(): can `quantity` units be supplied right now?"""
    return check_inventory(product_id, quantity)


@app.get("/products/{product_id}/substitutes", response_model=list[Substitute], tags=["catalogue"])
def product_substitutes(product_id: int, quantity: int = Query(1, ge=1),
                        limit: int = Query(3, ge=1, le=20)):
    """find_substitutes(): ranked in-stock alternatives."""
    return find_substitutes(product_id, quantity=quantity, limit=limit)


@app.get("/coupons", response_model=list[Coupon], tags=["offers"])
def list_coupons():
    """All coupon rules (including expired / disabled ones, for transparency)."""
    with get_engine().connect() as conn:
        return load_coupons(conn)


@app.post("/carts", response_model=CartCreated, status_code=201, tags=["cart"])
def new_cart(body: NewCart):
    return CartCreated(cart_id=create_cart(body.session_id), session_id=body.session_id)


@app.put("/carts/{cart_id}/items/{product_id}", response_model=CartUpdate, tags=["cart"])
def set_cart_item(cart_id: int, product_id: int, body: CartItemChange):
    """update_cart(). A refused change (not enough stock) returns 200 with ok=false and
    available_stock, so the caller can offer the remaining units or a substitute."""
    return update_cart(cart_id, product_id, body.quantity, mode=body.mode)


@app.delete("/carts/{cart_id}/items/{product_id}", response_model=CartUpdate, tags=["cart"])
def remove_cart_item(cart_id: int, product_id: int):
    return update_cart(cart_id, product_id, 0)


@app.get("/carts/{cart_id}/bill", response_model=Bill, tags=["cart"])
def cart_bill(cart_id: int, today: Optional[date] = None):
    """compute_bill(): live itemised bill with the optimal coupon combination.
    `today` (optional) evaluates coupon validity as of another date."""
    return compute_bill(cart_id, today=today)


@app.get("/carts/{cart_id}/offers", response_model=OfferResult, tags=["offers"])
def cart_offers(cart_id: int, today: Optional[date] = None):
    """optimize_offers(): best coupon set, plus why every other coupon was not used."""
    return optimize_offers(cart_id, today=today)


@app.get("/carts/{cart_id}/compare-stores", tags=["offers"])
def cart_compare_stores(cart_id: int, today: Optional[date] = None):
    """This cart priced at every store (home + comparison stores), coupons applied where valid."""
    return _json(compare_stores(cart_id, today))


@app.get("/stores", tags=["offers"])
def list_stores():
    with get_engine().connect() as conn:
        return [dict(r) for r in conn.execute(text(
            "SELECT store_id, name, city, address, is_home, accepts_coupons FROM stores ORDER BY store_id"
        )).mappings().all()]


@app.post("/carts/{cart_id}/checkout", response_model=CheckoutResult, tags=["cart"])
def cart_checkout(cart_id: int):
    """checkout(): one transaction — final bill, stock decrement, order snapshot.
    Returns ok=false with problems if the cart is empty or short of stock."""
    return checkout(cart_id)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, examples=["web-session-1"])
    message: str = Field(min_length=1, examples=["2 toned milk, oats and instant coffee under ₹600"])


class SessionItemChange(BaseModel):
    quantity: int = Field(ge=0, examples=[2])


_assistant = None


def get_assistant():
    """Created on first use, so every other endpoint works without an LLM key."""
    global _assistant
    if _assistant is None:
        from smartcart.agent import ShoppingAssistant
        _assistant = ShoppingAssistant()
    return _assistant


def _json(obj) -> JSONResponse:
    """Dataclasses/dicts -> JSON with Decimals as exact strings."""
    if is_dataclass(obj):
        obj = asdict(obj)
    return JSONResponse(content=json.loads(json.dumps(obj, default=str)))


def _bot_or_503():
    try:
        return get_assistant(), None
    except LLMNotConfigured as e:
        return None, JSONResponse(status_code=503, content={"detail": str(e)})


@app.post("/chat", tags=["agent"])
def chat(body: ChatRequest):
    """Talk to the LangGraph agent. Returns the reply, the tools it called, the grounding
    check result and the live bill. Conversation memory is kept per session_id
    (in memory: it resets when the server restarts; the cart itself is in PostgreSQL)."""
    bot, err = _bot_or_503()
    return err or _json(bot.chat(body.session_id, body.message))


@app.get("/sessions/{session_id}", tags=["agent"])
def get_session(session_id: str):
    """Cart id, budget and live bill of a chat session (404 until its first chat message)."""
    bot, err = _bot_or_503()
    if err:
        return err
    view = bot.session(session_id)
    if view is None:
        raise SessionNotFound(f"No chat session {session_id!r}")
    return _json(view)


@app.put("/sessions/{session_id}/items/{product_id}", tags=["agent"])
def set_session_item(session_id: str, product_id: int, body: SessionItemChange):
    """Set a quantity in the session's cart from the UI (0 removes). Same cart the agent uses."""
    bot, err = _bot_or_503()
    if err:
        return err
    update, view = bot.set_item(session_id, product_id, body.quantity)
    return _json({"update": asdict(update), "session": view})


@app.post("/sessions/{session_id}/checkout", tags=["agent"])
def checkout_session(session_id: str):
    """Check out the session's cart; on success the session continues with a fresh cart."""
    bot, err = _bot_or_503()
    if err:
        return err
    result, view = bot.checkout(session_id)
    return _json({"result": asdict(result), "session": view})


class BudgetBody(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=0, examples=["600"])   # null clears the budget


class SwapBody(BaseModel):
    from_product_id: int
    to_product_id: int
    quantity: int = Field(ge=1)


class SwapsBody(BaseModel):
    swaps: list[SwapBody] = Field(min_length=1)


@app.put("/sessions/{session_id}/budget", tags=["agent"])
def set_session_budget(session_id: str, body: BudgetBody):
    """Set or clear the session's budget (the same value the agent's set_budget tool stores)."""
    bot, err = _bot_or_503()
    return err or _json(bot.set_budget(session_id, body.amount))


@app.get("/sessions/{session_id}/budget-plan", tags=["agent"])
def session_budget_plan(session_id: str):
    """fit_budget(): fewest same-type swaps that bring the cart within budget (read-only suggestion)."""
    bot, err = _bot_or_503()
    return err or _json(bot.budget_plan(session_id))


@app.get("/sessions/{session_id}/compare-stores", tags=["agent"])
def session_compare_stores(session_id: str):
    """The session's cart priced at every store (same result as the agent's compare_stores tool)."""
    bot, err = _bot_or_503()
    if err:
        return err
    return _json(compare_stores(bot._require(session_id)["cart_id"]))


@app.post("/sessions/{session_id}/swaps", tags=["agent"])
def session_apply_swaps(session_id: str, body: SwapsBody):
    """Replace products in the session's cart (budget plan or a substitute card)."""
    bot, err = _bot_or_503()
    if err:
        return err
    results, view = bot.apply_swaps(session_id, [(s.from_product_id, s.to_product_id, s.quantity)
                                                 for s in body.swaps])
    return _json({"results": [asdict(r) for r in results], "session": view})


# ---------------------------------------------------------------- store admin
class InventoryChange(BaseModel):
    price: Optional[Decimal] = Field(default=None, examples=["45.00"])
    stock_qty: Optional[int] = Field(default=None, examples=[20])


class CouponChange(BaseModel):
    is_active: bool


class LoginBody(BaseModel):
    username: str = Field(min_length=1, examples=["manager"])
    password: str = Field(min_length=1, examples=["manager123"])


@app.post("/admin/login", tags=["admin"])
def admin_login(body: LoginBody):
    """Staff login → signed token for the other /admin endpoints. Demo accounts:
    manager / manager123 (prices, stock, coupons), staff / staff123 (stock only)."""
    user, token = auth.login(body.username, body.password)
    return {"token": token, **asdict(user)}


@app.get("/admin/me", tags=["admin"])
def admin_me(user: StaffUser = Depends(staff_user)):
    return asdict(user)


@app.get("/admin/summary", tags=["admin"])
def admin_summary(user: StaffUser = Depends(staff_user)):
    return _json(admin.summary())


@app.get("/admin/inventory", tags=["admin"])
def admin_inventory(q: str = "", filter: Literal["all", "out", "low"] = "all",
                    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                    user: StaffUser = Depends(staff_user)):
    return _json(admin.list_inventory(q, filter, limit, offset))


@app.patch("/admin/inventory/{product_id}", tags=["admin"])
def admin_update_inventory(product_id: int, body: InventoryChange, user: StaffUser = Depends(staff_user)):
    """Change live price and/or stock. Price must be > 0 and ≤ MRP; stock ≥ 0. Only a manager may
    change prices (403 for staff). Shopper bills reflect the change on their next refresh."""
    return _json(admin.update_inventory(product_id, body.price, body.stock_qty, by=user))


@app.get("/admin/coupons", tags=["admin"])
def admin_coupons(user: StaffUser = Depends(staff_user)):
    return _json(admin.list_coupons())


@app.patch("/admin/coupons/{code}", tags=["admin"])
def admin_update_coupon(code: str, body: CouponChange, user: StaffUser = Depends(staff_user)):
    return _json(admin.set_coupon_active(code, body.is_active, by=user))


@app.get("/admin/orders", tags=["admin"])
def admin_orders(limit: int = Query(10, ge=1, le=100), user: StaffUser = Depends(staff_user)):
    return _json(admin.recent_orders(limit))


@app.get("/admin/audit", tags=["admin"])
def admin_audit(limit: int = Query(15, ge=1, le=100), user: StaffUser = Depends(staff_user)):
    """Who changed which price / stock / coupon, newest first."""
    return _json(admin.recent_audit(limit))


# ---------------------------------------------------------------- user study (Phase II)
class StudyStart(BaseModel):
    participant: str = Field(min_length=1, examples=["P01"])
    mode: Literal["assistant", "manual"]
    task_id: Literal["A", "B"]


class StudyFinish(BaseModel):
    messages: Optional[int] = Field(default=None, ge=0)


@app.get("/study/tasks", tags=["study"])
def study_tasks():
    return study.tasks()


@app.post("/study/runs", tags=["study"], status_code=201)
def study_start(body: StudyStart):
    """Start the clock for one participant doing one task in one mode."""
    return _json(study.start_run(body.participant, body.mode, body.task_id))


@app.post("/study/runs/{run_id}/finish", tags=["study"])
def study_finish(run_id: int, body: StudyFinish):
    """Stop the clock and score the cart (assistant mode: the chat session's cart)."""
    run = next((r for r in study.runs() if r["run_id"] == run_id), None)
    cart_id = None
    if run and run["mode"] == "assistant":
        bot, err = _bot_or_503()
        if err:
            return err
        with get_engine().connect() as conn:
            sid = conn.execute(text("SELECT session_id FROM study_runs WHERE run_id = :r"), {"r": run_id}).scalar()
        view = bot.session(sid)
        cart_id = view["cart_id"] if view else None
    return _json(study.finish_run(run_id, cart_id, body.messages))


@app.get("/study/runs", tags=["study"])
def study_runs():
    return _json(study.runs())


@app.get("/study/summary", tags=["study"])
def study_summary():
    """Assistant vs manual: success rate, mean/median time, paired time saved."""
    return _json(study.summary())


EVAL_RESULTS = Path(__file__).resolve().parents[2] / "docs" / "evaluation" / "results.json"


@app.get("/admin/evaluation", tags=["admin"])
def admin_evaluation():
    """Latest evaluation run (milestone 7, written by scripts/07_evaluate.py): headline metrics,
    the offline coupon study and a compact per-goal table."""
    if not EVAL_RESULTS.is_file():
        return JSONResponse(status_code=404, content={"detail": "No evaluation yet: run scripts/07_evaluate.py"})
    data = json.loads(EVAL_RESULTS.read_text(encoding="utf-8"))
    goals = [{"id": g["id"], "title": g["title"], "features": g["features"],
              "infra_error": g["infra_error"], "success": g.get("success", False),
              "grounded": all(t["grounded"] for t in g["turns"]),
              "latency_s": round(sum(t["latency_s"] for t in g["turns"]), 1),
              "turns": len(g["turns"]), "final_total": g.get("final_total"),
              "discount": g.get("discount", {}).get("system"), "optimum": g.get("discount", {}).get("optimum"),
              "failed": [c["check"] for c in g.get("checks", []) if not c["passed"]]}
             for g in data["goals"]]
    return {"generated": data["generated"], "summary": data["summary"],
            "offline": data["offline_offer_study"], "goals": goals}


@app.get("/orders/{order_id}", tags=["cart"])
def get_order(order_id: int):
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT * FROM orders WHERE order_id = :o"), {"o": order_id}).mappings().first()
    if row is None:
        return JSONResponse(status_code=404, content={"detail": f"No order with id {order_id}"})
    return {**row, **{k: str(row[k]) for k in ("subtotal", "discount_total", "final_total")}}


# ---------------------------------------------------------------- web UI (milestone 6)
# `npm run build` in frontend/ produces frontend/dist; if present it is served at "/".
# Registered last, so every API route above takes precedence.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
