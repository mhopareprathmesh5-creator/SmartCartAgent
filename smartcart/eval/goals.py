"""Scripted shopping goals for the evaluation harness.

Each goal is what a shopper types (one or more turns) plus what a correct outcome
looks like. Expectations are written as PRODUCT TYPES (the catalogue's
product_type), not product ids, so the agent is free to pick any suitable brand,
but "toned milk" must end up as a Milk product, in the right quantity.

The goals cover every feature the project claims: multi-item requests, typos,
out-of-stock items (substitution), quantity above stock, budgets (budget fit),
coupons, multi-turn edits, store navigation (aisle/shelf) and GST questions.
Product ids in `unavailable` refer to the deterministic seed (RANDOM_SEED = 42).
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class Want:
    product_type: str
    qty: int


@dataclass(frozen=True)
class Goal:
    id: str
    title: str
    turns: list[str]
    want: list[Want] = field(default_factory=list)           # must be in the final cart (exact qty per type)
    absent: list[str] = field(default_factory=list)          # product types that must NOT be in the cart
    unavailable: list[int] = field(default_factory=list)     # products that cannot be supplied -> substitution
    budget: Optional[Decimal] = None                         # budget the agent must record
    aisle_for: list[str] = field(default_factory=list)       # reply must name the aisle of these types
    mention: list[str] = field(default_factory=list)         # bill fields whose value the last reply must quote
    empty_cart: bool = False                                 # information-only request: nothing added
    tools: list[str] = field(default_factory=list)           # agent tools that must be called at least once
    features: list[str] = field(default_factory=list)


GOALS = [
    Goal("G01", "Multi-item basic list",
         ["I need 2 toned milk, oats, instant coffee and brown bread."],
         want=[Want("Milk", 2), Want("Oats & Porridge", 1), Want("Instant Coffee", 1),
               Want("Brown, Wheat & Multigrain", 1)],
         mention=["final_total"], features=["multi-item", "location", "billing"]),

    Goal("G02", "Named product out of stock",
         ["Add Britannia Brown Bread and 2 packs of Maggi masala noodles."],
         want=[Want("Brown, Wheat & Multigrain", 1), Want("Instant Noodles", 2)],
         unavailable=[103], features=["out-of-stock", "substitution"]),

    Goal("G03", "Two out-of-stock items",
         ["I want Bagrrys Oats Atta and a Coke Zero."],
         want=[Want("Oats & Porridge", 1), Want("Cold Drinks", 1)],
         unavailable=[779, 314], features=["out-of-stock", "substitution"]),

    Goal("G04", "Budget + coupon + out of stock (main demo)",
         ["I need 3 Instant Tea Premix Turmeric Ginger, 2 Homogenized Milk and Britannia Brown Bread. "
          "My budget is ₹440"],
         want=[Want("Tea Bags", 3), Want("Milk", 2), Want("Brown, Wheat & Multigrain", 1)],
         unavailable=[103], budget=Decimal("440.00"),
         features=["budget", "coupon", "out-of-stock", "budget-fit"]),

    Goal("G05", "Store navigation only",
         ["Where can I find basmati rice and sunflower oil?"],
         aisle_for=["Basmati Rice", "Sunflower, Rice Bran Oil"], empty_cart=True,
         features=["location"]),

    Goal("G06", "Typos in the request",
         ["I need a pack of egs, amul paneer and some buter"],
         want=[Want("Farm Eggs", 1), Want("Paneer, Tofu & Cream", 1), Want("Butter & Margarine", 1)],
         features=["typo-tolerance", "multi-item"]),

    Goal("G07", "Quantity above live stock",
         ["Add 5 Amul Fresh Toned Milk"],
         want=[Want("Milk", 5)], unavailable=[171],
         features=["stock-limit", "substitution"]),

    Goal("G08", "Multi-turn cart edit",
         ["Add 2 Maggi masala noodles and Mapro tomato ketchup.",
          "Make the noodles 4 and remove the ketchup."],
         want=[Want("Instant Noodles", 4)], absent=["Tomato Ketchup & Sauces"],
         mention=["final_total"], features=["multi-turn", "memory", "cart-edit"]),

    Goal("G09", "Staples cart with stacked coupons",
         ["Add Aashirvaad Select Atta, bb Royal Biryani Basmati Rice, 2 Sunpure sunflower oil and "
          "Himalayan Natives toor dal. Which coupons did I get?"],
         want=[Want("Atta Whole Wheat", 1), Want("Basmati Rice", 1), Want("Sunflower, Rice Bran Oil", 2),
               Want("Toor, Channa & Moong Dal", 1)],
         mention=["discount_total"], features=["coupon", "multi-item"]),

    Goal("G10", "Tight budget",
         ["Weekly basics under ₹500: atta, toor dal, sunflower oil and eggs."],
         want=[Want("Atta Whole Wheat", 1), Want("Toor, Channa & Moong Dal", 1),
               Want("Sunflower, Rice Bran Oil", 1), Want("Farm Eggs", 1)],
         budget=Decimal("500.00"), features=["budget", "multi-item"]),

    Goal("G11", "GST question after shopping",
         ["Add 2 Dark Fantasy bourbon biscuits and a Cadbury Dairy Milk Silk Mousse.",
          "How much GST is included in my bill?"],
         want=[Want("Cream Biscuits & Wafers", 2), Want("Chocolates", 1)],
         unavailable=[783], mention=["gst_included"], features=["gst", "out-of-stock", "multi-turn"]),

    Goal("G12", "Personal care items",
         ["Add Pampers diaper pants and Clinic Plus shampoo."],
         want=[Want("Diapers", 1), Want("Shampoo & Conditioner", 1)],
         features=["multi-item", "location"]),

    # ---- Phase II enhancements
    Goal("G13", "Hindi request",
         ["मुझे 2 पैकेट मैगी मसाला नूडल्स और अमूल मक्खन चाहिए।"],
         want=[Want("Instant Noodles", 2), Want("Butter & Margarine", 1)],
         mention=["final_total"], features=["hindi", "multi-item"]),

    Goal("G14", "Marathi request + navigation",
         ["बासमती तांदूळ कुठे मिळेल? आणि एक पॅकेट साखर कार्टमध्ये टाका."],
         want=[Want("Sugar & Jaggery", 1)], aisle_for=["Basmati Rice"],
         features=["marathi", "location"]),

    Goal("G15", "Compare the cart across stores",
         ["Add 3 Instant Tea Premix Turmeric Ginger, 2 Amul Homogenized Milk and Fresho brown bread.",
          "Is this cart cheaper at another store?"],
         want=[Want("Tea Bags", 3), Want("Milk", 2), Want("Brown, Wheat & Multigrain", 1)],
         tools=["compare_stores"], features=["multi-store", "multi-turn"]),
]
