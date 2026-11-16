# SmartCart Agent — Evaluation Report

Generated 2026-11-12 10:56 by `python scripts/07_evaluate.py`. Models: gemini-3.5-flash-lite.

## Headline metrics

| metric | result |
|---|---|
| Task success (goals fully achieved) | **11/12 (91.67%)**, checks passed 43/44 |
| Task success, strict (substitute already added, no confirmation pending) | 11/12; 0 goal(s) waiting for the shopper to pick a substitute |
| Grounding accuracy (replies with 0 invented ₹/aisle values) | **100.0%** of 14 replies; 86 values audited |
| Grounded on the first try (no guard rewrite needed) | 100.0% (0 rewrite(s) triggered by the guard) |
| Discount captured vs theoretical optimum (agent carts) | **100.0%** (₹642.20 of ₹642.20); 12/12 carts optimal |
| Discount captured on 300 random real carts | **100.0%** (greedy 99.97%, single coupon 55.61%) |
| Substitution correctness (same type, in stock) | **83.33%** of 6 cases; 5 added, 0 offered; top-ranked choice 40.0% |
| Latency per turn | median 13.07 s, p90 31.87 s, max 33.58 s |
| LLM calls / tool calls per turn | 3.5 / 5.43 |
| Offer optimizer time | median 0.17 ms, max 0.88 ms |

## How each metric is measured

- **Task success**: after the conversation the cart is read from PostgreSQL. Every requested item must be present as the right *product type* in the exact quantity, removed items must be gone, the budget must be recorded, and where asked, the reply must quote the bill's value. If an item could not be supplied and the agent showed substitute cards for the shopper to choose (the confirm-substitute behaviour of synopsis objective 4), that item counts as ⏳ pending: it passes the normal score and fails the strict score.
- **Grounding accuracy**: every ₹ amount and aisle number in each final reply is checked against the values the tools returned in that conversation (the same guard that runs live).
- **Discount captured**: for the final cart, the discount the system applied is compared with the theoretical optimum, found by brute force over every conflict-free subset of the valid coupons. Greedy (biggest coupon first) and best-single-coupon are baselines.
- **Substitution**: for every product that could not be supplied (out of stock or quantity above stock), a correct outcome is an in-stock product of the same product type in the cart, or substitute cards shown for the shopper to pick.
- **Latency / LLM calls**: wall-clock time of each turn and the number of Gemini requests it made (the run is paced to respect the 15 requests/min free tier).

## Offline coupon study (no LLM)

300 random carts (3–25 products from the real catalogue, quantity 1–4), the real 19 coupons and 12 conflict pairs:

| method | discount given | share of optimum | carts below optimum |
|---|---|---|---|
| Brute force (theoretical optimum) | ₹202655.89 | 100% | 0 |
| **SmartCart branch-and-bound** | ₹202655.89 | **100.0%** | 0 |
| Greedy (biggest first) | ₹202590.81 | 99.97% | 1 |
| Best single coupon | ₹112688.58 | 55.61% | 296 |

## Per-goal results

| goal | features | success | grounded | turns | latency | final total | discount (system / optimum) |
|---|---|---|---|---|---|---|---|
| G01 Multi-item basic list | multi-item, location, billing | ✅ | ✅ | 1 | 11.0 s | ₹284.20 | ₹0.00 / ₹0.00 |
| G02 Named product out of stock | out-of-stock, substitution | ✅ | ✅ | 1 | 19.6 s | ₹346.40 | ₹50.00 / ₹50.00 |
| G03 Two out-of-stock items | out-of-stock, substitution | ✅ | ✅ | 1 | 17.6 s | ₹205.00 | ₹0.00 / ₹0.00 |
| G04 Budget + coupon + out of stock (main demo) | budget, coupon, out-of-stock, budget-fit | ✅ | ✅ | 1 | 33.6 s | ₹451.90 | ₹75.00 / ₹75.00 |
| G05 Store navigation only | location | ✅ | ✅ | 1 | 4.4 s | ₹0.00 | ₹0.00 / ₹0.00 |
| G06 Typos in the request | typo-tolerance, multi-item | ✅ | ✅ | 1 | 11.6 s | ₹418.20 | ₹39.80 / ₹39.80 |
| G07 Quantity above live stock | stock-limit, substitution | ❌ | ✅ | 1 | 13.2 s | ₹99.00 | ₹0.00 / ₹0.00 |
| G08 Multi-turn cart edit | multi-turn, memory, cart-edit | ✅ | ✅ | 2 | 19.7 s | ₹593.32 | ₹121.48 / ₹121.48 |
| G09 Staples cart with stacked coupons | coupon, multi-item | ✅ | ✅ | 1 | 13.0 s | ₹763.60 | ₹140.40 / ₹140.40 |
| G10 Tight budget | budget, multi-item | ✅ | ✅ | 1 | 15.5 s | ₹417.10 | ₹101.90 / ₹101.90 |
| G11 GST question after shopping | gst, out-of-stock, multi-turn | ✅ | ✅ | 2 | 39.8 s | ₹302.04 | ₹50.00 / ₹50.00 |
| G12 Personal care items | multi-item, location | ✅ | ✅ | 1 | 25.8 s | ₹572.59 | ₹63.62 / ₹63.62 |

## Goal details

### G01 — Multi-item basic list

**Shopper:** I need 2 toned milk, oats, instant coffee and brown bread.

**Agent** (10.99 s, 4 LLM calls, tools: search_products, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart, update_cart, update_cart):

> I have added the items to your cart:
> 
> * **2 × Fresh Toned Milk** (Amul) — Aisle 2, Shelf A2-S5
> * **1 × Oats - 100% Natural** (Saffola) — Aisle 5, Shelf A5-S9
> * **1 × Grand Coffee** (Tata Coffee) — *Note:* Sunrise Instant Coffee was out of stock, so I replaced it with Grand Coffee (other alternatives include Continental Caramel and Cappuccino premixes). Found in Aisle 6, Shelf A6-S1.
> * **1 × Multigrain Bread** (Britannia) — *Note:* Britannia Brown Bread was out of stock, so I replaced it with Britannia Multigrain Bread (other alternatives include Fresho Brown Bread or Fresho Brown Bread + Eggs combo). Found in Aisle 2, Shelf A2-S2.
> 
> Your current final total is **₹284.20** (including ₹8.01 GST).

Cart: 1 × Britannia Multigrain Bread [Brown, Wheat & Multigrain]; 2 × Amul Fresh Toned Milk [Milk]; 1 × Tata Coffee Grand Coffee [Instant Coffee]; 1 × Saffola Oats - 100% Natural [Oats & Porridge]

- ✅ 2 × Milk (cart has 2)
- ✅ 1 × Oats & Porridge (cart has 1)
- ✅ 1 × Instant Coffee (cart has 1)
- ✅ 1 × Brown, Wheat & Multigrain (cart has 1)
- ✅ quotes bill final_total ₹284.20 (from compute_bill)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G02 — Named product out of stock

**Shopper:** Add Britannia Brown Bread and 2 packs of Maggi masala noodles.

**Agent** (19.55 s, 4 LLM calls, tools: search_products, search_products, update_cart, update_cart, update_cart):

> Britannia Brown Bread was out of stock, so I've added **Brown Bread - Safe, Preservative Free** (Fresho) instead. Other available alternatives were Multigrain Bread and a combo pack of Brown Bread with Eggs.
> 
> Here are your items and their locations:
> - **Noodles - Masala 280 gm + Ketchup Tomato 1 kg** (2 packs) — Aisle 5, Shelf A5-S10
> - **Brown Bread - Safe, Preservative Free** (1 pack) — Aisle 2, Shelf A2-S2
> 
> **Bill Summary:**
> - **Final Total:** ₹346.40
> - **Coupon Applied:** SNACK15 (15% off Snacks & Branded Foods above ₹200) — Discount: ₹50.00

Cart: 1 × Fresho Brown Bread - Safe, Preservative Free [Brown, Wheat & Multigrain]; 2 × MAGGI Noodles - Masala 280 gm + Ketchup Tomato 1 kg [Instant Noodles]

- ✅ 1 × Brown, Wheat & Multigrain (cart has 1)
- ✅ 2 × Instant Noodles (cart has 2)
- ✅ unavailable #103 not over-sold (ok)
- substitution for #103: added, #104 (rank 2)
- coupons: SNACK15 → ₹50.00 (optimum ₹50.00, greedy ₹50.00, single ₹50.00)

### G03 — Two out-of-stock items

**Shopper:** I want Bagrrys Oats Atta and a Coke Zero.

**Agent** (17.62 s, 4 LLM calls, tools: search_products, search_products, find_substitutes, find_substitutes, update_cart, update_cart):

> Bagrrys Oats Atta and Coke Zero are currently out of stock. 
> 
> I have added the following substitutes to your cart instead:
> - **Saffola Oats - 100% Natural** (Aisle 5, Shelf A5-S9) – replaced Bagrrys Oats Atta. Other alternatives included GoodDiet Millet Masala Oats, Quaker Oats, Kelloggs Oats, and Quaker Oats + Aashirvaad Atta combo.
> - **Shunya Fizz - Lime Lemon Classic Cola 300 ml + Fizz - Lime Lemon 300 ml** (Aisle 6, Shelf A6-S2) – replaced Coke Zero. Other alternatives included Pepsi Soft Drink Black Slim, Limca, Kingfisher Radler, and Glucon-D.
> 
> Your final total is ₹205.00.

Cart: 1 × Shunya Fizz - Lime Lemon Classic Cola 300 ml + Fizz - Lime Lemon 300 ml [Cold Drinks]; 1 × Saffola Oats - 100% Natural [Oats & Porridge]

- ✅ 1 × Oats & Porridge (cart has 1)
- ✅ 1 × Cold Drinks (cart has 1)
- ✅ unavailable #779 not over-sold (ok)
- ✅ unavailable #314 not over-sold (ok)
- substitution for #779: added, #836 (rank 2)
- substitution for #314: added, #315 (rank 1)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G04 — Budget + coupon + out of stock (main demo)

**Shopper:** I need 3 Instant Tea Premix Turmeric Ginger, 2 Homogenized Milk and Britannia Brown Bread. My budget is ₹440

**Agent** (33.58 s, 9 LLM calls, tools: set_budget, search_products, search_products, search_products, update_cart, update_cart, update_cart, find_substitutes, update_cart, fit_budget, view_bill, view_bill, view_bill):

> Here are the items added to your cart:
> 
> 1. **Instant Tea Premix - Turmeric Ginger** (3 packs) — Located in Aisle 6, Shelf A6-S5.
> 2. **Homogenized Milk** (2 packs) — Located in Aisle 2, Shelf A2-S5.
> 3. **Brown Bread** was out of stock, so I've replaced it with **Brown Bread - Safe, Preservative Free** (1 pack) — Located in Aisle 2, Shelf A2-S2. (Other alternatives include Multigrain Bread and Bread - Brown, Chemical Free 400G + Eggs - Regular 6pcs).
> 
> Coupon applied: **BEV75** (₹75.00 off).
> 
> Your bill total is **₹451.90**, which puts you over your ₹440 budget by **₹11.90**. 
> 
> To fit your budget, we can swap **Homogenized Milk** (2 units) with **Camel Milk** to bring the new total to **₹431.90**. Would you like me to apply this swap?

Cart: 1 × Fresho Brown Bread - Safe, Preservative Free [Brown, Wheat & Multigrain]; 2 × Amul Homogenized Milk [Milk]; 3 × VAHDAM Instant Tea Premix - Turmeric Ginger [Tea Bags]

- ✅ 3 × Tea Bags (cart has 3)
- ✅ 2 × Milk (cart has 2)
- ✅ 1 × Brown, Wheat & Multigrain (cart has 1)
- ✅ unavailable #103 not over-sold (ok)
- ✅ budget ₹440.00 recorded (recorded 440.00)
- substitution for #103: added, #104 (rank 2)
- coupons: BEV75 → ₹75.00 (optimum ₹75.00, greedy ₹75.00, single ₹75.00)

### G05 — Store navigation only

**Shopper:** Where can I find basmati rice and sunflower oil?

**Agent** (4.36 s, 2 LLM calls, tools: search_products, search_products):

> You can find both basmati rice and sunflower oil in Aisle 4 (Foodgrains, Oil & Masala):
> 
> - **Basmati Rice** is located on shelf **A4-S7** (levels 2, 3, and 4), with brands like Kohinoor, India Gate, and Daawat available.
> - **Sunflower Oil** is located on shelf **A4-S4** (levels 1 and 5), with options like Sunpure, Gold Winner, and Sundrop. 
> 
> Let me know if you would like to add any of these to your cart!

Cart: empty

- ✅ cart stays empty (0 line(s))
- ✅ names aisle of Basmati Rice (expected Aisle 4)
- ✅ names aisle of Sunflower, Rice Bran Oil (expected Aisle 4)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G06 — Typos in the request

**Shopper:** I need a pack of egs, amul paneer and some buter

**Agent** (11.57 s, 3 LLM calls, tools: search_products, search_products, search_products, update_cart, update_cart, update_cart):

> I've added the following items to your cart:
> - **Eggs - White Leghorn**: Located in Aisle 3 (Shelf A3-S1).
> - **Malai Paneer - Block**: Located in Aisle 2 (Shelf A2-S5).
> - **Unsalted Butter**: Located in Aisle 2 (Shelf A2-S5).
> 
> Your total comes to **₹418.20**. Coupon **DAIRY10** has been applied, giving you a discount of **₹39.80**.

Cart: 1 × Amul Unsalted Butter [Butter & Margarine]; 1 × Amul Malai Paneer - Block [Paneer, Tofu & Cream]; 1 × Mpm Eggs - White Leghorn [Farm Eggs]

- ✅ 1 × Farm Eggs (cart has 1)
- ✅ 1 × Paneer, Tofu & Cream (cart has 1)
- ✅ 1 × Butter & Margarine (cart has 1)
- coupons: DAIRY10 → ₹39.80 (optimum ₹39.80, greedy ₹39.80, single ₹39.80)

### G07 — Quantity above live stock

**Shopper:** Add 5 Amul Fresh Toned Milk

**Agent** (13.15 s, 3 LLM calls, tools: search_products, update_cart):

> We only have 3 packs of Fresh Toned Milk in stock, so I have added all 3 packs to your cart. 
> 
> You can find Fresh Toned Milk in Aisle 2, Shelf A2-S5.
> 
> Your current bill total is ₹99.00. 
> *(Note: Coupon AMUL5 is almost unlocked—adding just ₹1.00 more of Amul products will unlock it!)*

Cart: 3 × Amul Fresh Toned Milk [Milk]

- ❌ 5 × Milk (cart has 3)
- ✅ unavailable #171 not over-sold (ok)
- substitution for #171: missing
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G08 — Multi-turn cart edit

**Shopper:** Add 2 Maggi masala noodles and Mapro tomato ketchup.

**Agent** (9.5 s, 3 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> I have added 2 packs of Noodles - Masala 280 gm + Ketchup Tomato 1 kg and 1 Tomato Ketchup to your cart. 
> 
> Both items are located in Aisle 5, Shelf A5-S10.
> 
> **Bill Summary:**
> - **Subtotal:** ₹447.40
> - **Coupon Applied:** `SNACK15` (15% off Snacks & Branded Foods above ₹200) - ₹50.00 discount
> - **Final Total:** ₹397.40
> - *(Includes ₹18.93 GST)*

**Shopper:** Make the noodles 4 and remove the ketchup.

**Agent** (10.17 s, 2 LLM calls, tools: update_cart, update_cart):

> I have updated your cart to 4 packs of Noodles - Masala 280 gm + Ketchup Tomato 1 kg (found in Aisle 5, Shelf A5-S10) and removed the Tomato Ketchup.
> 
> **Bill Summary:**
> - **Subtotal:** ₹714.80
> - **Coupons Applied:** 
>   - `SAVE10` (10% off on orders above ₹500): -₹71.48
>   - `SNACK15` (15% off Snacks & Branded Foods): -₹50.00
> - **Total Discount:** ₹121.48
> - **Final Total:** ₹593.32
> - *(Includes ₹28.25 GST)*

Cart: 4 × MAGGI Noodles - Masala 280 gm + Ketchup Tomato 1 kg [Instant Noodles]

- ✅ 4 × Instant Noodles (cart has 4)
- ✅ no Tomato Ketchup & Sauces (cart has 0)
- ✅ quotes bill final_total ₹593.32 (from compute_bill)
- coupons: SAVE10, SNACK15 → ₹121.48 (optimum ₹121.48, greedy ₹121.48, single ₹71.48)

### G09 — Staples cart with stacked coupons

**Shopper:** Add Aashirvaad Select Atta, bb Royal Biryani Basmati Rice, 2 Sunpure sunflower oil and Himalayan Natives toor dal. Which coupons did I get?

**Agent** (12.98 s, 3 LLM calls, tools: search_products, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> I have added the items to your cart:
> 
> * **Aashirvaad Select Atta**: Aisle 4, Shelf A4-S1
> * **bb Royal Biryani Basmati Rice**: Aisle 4, Shelf A4-S7
> * **Sunpure Sunflower Oil** (2 packs): Aisle 4, Shelf A4-S4
> * **Himalayan Natives Toor Dal**: Aisle 4, Shelf A4-S2
> 
> **Coupons Applied:**
> * **SAVE10**: ₹90.40 discount (10% off on orders above ₹500)
> * **STAPLES50**: ₹50.00 discount (₹50 off Foodgrains / Oil / Masala above ₹400)
> 
> Your total discount is ₹140.40, and the final total is ₹763.60.

Cart: 1 × Aashirvaad Select Atta/Godihittu [Atta Whole Wheat]; 1 × Himalayan Natives Natives Toor Dal//Togari Bele [Toor, Channa & Moong Dal]; 2 × Sunpure Refined - Sunflower Oil [Sunflower, Rice Bran Oil]; 1 × bb Royal Biryani Basmati Rice - Extra Long [Basmati Rice]

- ✅ 1 × Atta Whole Wheat (cart has 1)
- ✅ 1 × Basmati Rice (cart has 1)
- ✅ 2 × Sunflower, Rice Bran Oil (cart has 2)
- ✅ 1 × Toor, Channa & Moong Dal (cart has 1)
- ✅ quotes bill discount_total ₹140.40 (from compute_bill)
- coupons: SAVE10, STAPLES50 → ₹140.40 (optimum ₹140.40, greedy ₹140.40, single ₹90.40)

### G10 — Tight budget

**Shopper:** Weekly basics under ₹500: atta, toor dal, sunflower oil and eggs.

**Agent** (15.54 s, 4 LLM calls, tools: set_budget, search_products, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> I have added your weekly basics to the cart:
> 
> - **Chakki-Fresh-Wheat-Atta/Godihittu - Fortified** (bb Royal) – Aisle 4, Shelf A4-S1
> - **Natives Toor Dal/Togari Bele** (Himalayan Natives) – Aisle 4, Shelf A4-S2
> - **Refined Sunflower Oil** (Sunpure) – Aisle 4, Shelf A4-S4
> - **Eggs - White Leghorn** (Mpm) – Aisle 3, Shelf A3-S1
> 
> **Bill Summary:**
> - Applied Coupons: `SAVE10` and `STAPLES50`, saving a total of ₹101.90.
> - Final Total: ₹417.10 (inclusive of ₹17.29 GST).
> - Budget Status: Well within your ₹500 budget (₹82.90 remaining)!

Cart: 1 × Mpm Eggs - White Leghorn [Farm Eggs]; 1 × bb Royal Chakki-Fresh-Wheat-Atta/Godihittu - Fortified [Atta Whole Wheat]; 1 × Himalayan Natives Natives Toor Dal//Togari Bele [Toor, Channa & Moong Dal]; 1 × Sunpure Refined - Sunflower Oil [Sunflower, Rice Bran Oil]

- ✅ 1 × Atta Whole Wheat (cart has 1)
- ✅ 1 × Toor, Channa & Moong Dal (cart has 1)
- ✅ 1 × Sunflower, Rice Bran Oil (cart has 1)
- ✅ 1 × Farm Eggs (cart has 1)
- ✅ budget ₹500.00 recorded (recorded 500.00)
- coupons: SAVE10, STAPLES50 → ₹101.90 (optimum ₹101.90, greedy ₹101.90, single ₹51.90)

### G11 — GST question after shopping

**Shopper:** Add 2 Dark Fantasy bourbon biscuits and a Cadbury Dairy Milk Silk Mousse.

**Agent** (31.87 s, 4 LLM calls, tools: search_products, search_products, update_cart, update_cart, update_cart):

> I have added **2 packs** of **Dark Fantasy Bourbon Chocolate Cream Biscuits** to your cart (located in **Aisle 5, Shelf A5-S2**).
> 
> The **Cadbury Dairy Milk Silk Mousse** is currently out of stock. I have replaced it with the top substitute, **Cadbury Fuse Chocolate - Home Treats, 170.5 g** (located in **Aisle 5, Shelf A5-S4**). Other available alternatives include **Cadbury Dairy Milk Chocolate Bar - Champion Pack** and **LuvIt Dairy Rich Fruit & Nut Chocolate Bar**.
> 
> **Bill Summary:**
> - **Final Total:** ₹302.04 (includes ₹14.38 GST)
> - **Coupons Applied:** `SNACK15` (-₹50.00 discount)
> - **Total Discount:** ₹50.00

**Shopper:** How much GST is included in my bill?

**Agent** (7.88 s, 1 LLM calls, tools: none):

> The GST included in your bill is ₹14.38 (taxable value: ₹287.66 at a 5.00% rate, broken down as ₹7.19 CGST and ₹7.19 SGST).

Cart: 2 × Sunfeast Dark Fantasy Bourbon Chocolate Cream Biscuits [Cream Biscuits & Wafers]; 1 × Cadbury Fuse Chocolate - Home Treats, 170.5 g [Chocolates]

- ✅ 2 × Cream Biscuits & Wafers (cart has 2)
- ✅ 1 × Chocolates (cart has 1)
- ✅ unavailable #783 not over-sold (ok)
- ✅ quotes bill gst_included ₹14.38 (from compute_bill)
- substitution for #783: added, #781 (rank 1)
- coupons: SNACK15 → ₹50.00 (optimum ₹50.00, greedy ₹50.00, single ₹50.00)

### G12 — Personal care items

**Shopper:** Add Pampers diaper pants and Clinic Plus shampoo.

**Agent** (25.78 s, 3 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> I have added the following items to your cart:
> 
> 1. **Diaper Pants - New Baby** (Pampers) – ₹552.21, located in Aisle 9, Shelf A9-S4 (Level 5).
> 2. **Naturally Long Shikakai Shampoo** (Clinic Plus) – ₹84.00, located in Aisle 8, Shelf A8-S4 (Level 1).
> 
> **Bill Summary:**
> - **Subtotal:** ₹636.21
> - **Coupon Applied:** SAVE10 (10% off on orders above ₹500) – ₹63.62 discount
> - **Total Discount:** ₹63.62
> - **Final Total:** ₹572.59 (inclusive of ₹27.27 GST)
> 
> *Tip:* Add ₹47.79 more in Baby Care to unlock the `BABY12` coupon!

Cart: 1 × Pampers Diaper Pants - New Baby [Diapers]; 1 × Clinic Plus Naturally Long Shikakai Shampoo [Shampoo & Conditioner]

- ✅ 1 × Diapers (cart has 1)
- ✅ 1 × Shampoo & Conditioner (cart has 1)
- coupons: SAVE10 → ₹63.62 (optimum ₹63.62, greedy ₹63.62, single ₹63.62)
