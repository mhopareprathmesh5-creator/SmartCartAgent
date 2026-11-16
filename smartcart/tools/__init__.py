"""The six tool functions the agent is allowed to call.

The LLM decides WHICH tool to call and explains the result; every price,
stock count, location, discount and total comes from these functions,
which read PostgreSQL.
"""
from smartcart.tools.budget import fit_budget
from smartcart.tools.cart import checkout, compute_bill, create_cart, update_cart
from smartcart.tools.catalog import check_inventory, find_substitutes, locate
from smartcart.tools.models import (CartNotActive, CartNotFound, ProductNotFound,
                                    ToolError)
from smartcart.tools.offers import choose_best_offers, optimize_offers
from smartcart.tools.stores import compare_stores

__all__ = [
    "locate", "check_inventory", "find_substitutes",
    "update_cart", "compute_bill", "optimize_offers",
    "create_cart", "checkout", "choose_best_offers", "fit_budget", "compare_stores",
    "ToolError", "ProductNotFound", "CartNotFound", "CartNotActive",
]
