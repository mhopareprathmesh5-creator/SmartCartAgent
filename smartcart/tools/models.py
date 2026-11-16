"""Typed results returned by the tool functions.

Every money value is a Decimal read from (or computed by code from) PostgreSQL —
never produced by the LLM.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

PAISA = Decimal("0.01")


def money(value) -> Decimal:
    """Round to 2 decimal places, half-up (how Indian retail bills round)."""
    return Decimal(value).quantize(PAISA, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------- errors
class ToolError(Exception):
    """Base class for errors a tool reports back to the agent."""


class ProductNotFound(ToolError):
    pass


class CartNotFound(ToolError):
    pass


class CartNotActive(ToolError):
    pass


# ---------------------------------------------------------------- catalogue
@dataclass(frozen=True)
class ProductLocation:
    product_id: int
    name: str
    brand: str
    category: str
    sub_category: str
    product_type: str
    pack_size: Optional[str]
    price: Decimal          # live selling price (inventory.current_price)
    mrp: Decimal
    stock_qty: int
    in_stock: bool
    aisle_no: int
    aisle_name: str
    shelf_code: str
    shelf_label: str
    shelf_level: int
    match_score: float


@dataclass(frozen=True)
class StockStatus:
    product_id: int
    name: str
    brand: str
    price: Decimal
    stock_qty: int
    requested_qty: int
    in_stock: bool
    can_fulfil: bool        # stock_qty >= requested_qty
    low_stock: bool         # 0 < stock_qty < reorder_level


@dataclass(frozen=True)
class Substitute:
    product_id: int
    name: str
    brand: str
    product_type: str
    price: Decimal
    price_difference: Decimal   # substitute price - original price (negative = cheaper)
    stock_qty: int
    rating: Optional[Decimal]
    aisle_no: int
    shelf_code: str
    match: str                  # 'same_type' or 'same_sub_category'


# ---------------------------------------------------------------- cart
@dataclass(frozen=True)
class CartUpdate:
    ok: bool
    cart_id: int
    product_id: int
    quantity: int               # quantity now in the cart (0 = not in cart)
    available_stock: int
    message: str


# ---------------------------------------------------------------- offers
@dataclass(frozen=True)
class CartLine:
    """One cart line as the offer optimizer sees it."""
    product_id: int
    category: str
    sub_category: str
    brand: str
    line_total: Decimal


@dataclass(frozen=True)
class Coupon:
    coupon_id: int
    code: str
    description: str
    discount_type: str          # 'PERCENT' | 'FLAT'
    discount_value: Decimal
    max_discount: Optional[Decimal]
    min_cart_value: Decimal
    scope: str                  # 'CART' | 'CATEGORY' | 'SUB_CATEGORY' | 'BRAND'
    scope_value: Optional[str]
    valid_from: date
    valid_to: date
    is_active: bool


@dataclass(frozen=True)
class AppliedCoupon:
    code: str
    description: str
    eligible_subtotal: Decimal
    discount: Decimal


@dataclass(frozen=True)
class RejectedCoupon:
    code: str
    reason: str                 # 'inactive' | 'not_started' | 'expired' | 'no_eligible_items'
                                # | 'below_minimum' | 'conflict' | 'not_needed'
    detail: str
    shortfall: Optional[Decimal] = None   # for below_minimum: how much more to spend to unlock it


@dataclass(frozen=True)
class OfferResult:
    applied: list[AppliedCoupon]
    total_discount: Decimal
    rejected: list[RejectedCoupon]


# ---------------------------------------------------------------- bill
@dataclass(frozen=True)
class BillLine:
    product_id: int
    name: str
    brand: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    stock_qty: int
    aisle_no: Optional[int] = None
    aisle_name: Optional[str] = None
    shelf_code: Optional[str] = None
    gst_rate: Decimal = Decimal("0")
    discount_share: Decimal = Decimal("0.00")   # this line's share of the coupon discounts
    gst: Decimal = Decimal("0.00")              # GST included in (line_total − discount_share)


@dataclass(frozen=True)
class TaxLine:
    rate: Decimal
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal


@dataclass(frozen=True)
class Bill:
    cart_id: int
    lines: list[BillLine]
    item_count: int
    subtotal: Decimal
    mrp_total: Decimal
    savings_vs_mrp: Decimal
    applied_coupons: list[AppliedCoupon]
    discount_total: Decimal
    final_total: Decimal
    rejected_coupons: list[RejectedCoupon] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    gst_total: Decimal = Decimal("0.00")        # GST included in final_total (prices are GST-inclusive)
    tax_breakup: list[TaxLine] = field(default_factory=list)


# ---------------------------------------------------------------- multi-store comparison
@dataclass(frozen=True)
class MissingItem:
    product_id: int
    name: str
    quantity: int
    reason: str                 # 'not_carried' | 'out_of_stock' | 'not_enough_stock'


@dataclass(frozen=True)
class StoreQuote:
    store_id: int
    name: str
    city: str
    is_home: bool
    accepts_coupons: bool
    items_available: int        # cart lines this store can supply in full
    items_total: int
    complete: bool              # can supply the whole cart
    subtotal: Decimal           # of the available lines only
    discount: Decimal           # best valid coupons (0 if the store doesn't take SmartMart coupons)
    coupons: list[str]
    final_total: Decimal
    missing: list[MissingItem]


@dataclass(frozen=True)
class StoreComparison:
    cart_id: int
    quotes: list[StoreQuote]        # home store first, then cheapest complete first
    best_store_id: Optional[int]    # cheapest store that can supply the whole cart
    saving_vs_home: Decimal         # home final_total − best final_total (0 if home is best)
    message: str


# ---------------------------------------------------------------- checkout
@dataclass(frozen=True)
class Order:
    order_id: int
    cart_id: int
    subtotal: Decimal
    discount_total: Decimal
    final_total: Decimal
    applied_coupons: list[str]
    lines: list[BillLine]
    placed_at: datetime
    gst_total: Decimal = Decimal("0.00")
    tax_breakup: list[TaxLine] = field(default_factory=list)


@dataclass(frozen=True)
class CheckoutResult:
    ok: bool
    order: Optional[Order]
    problems: list[str]         # why checkout was refused (empty cart, items short of stock)
