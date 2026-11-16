# SmartCart Agent — Evaluation Report

Generated 2026-11-12 12:20 by `python scripts/07_evaluate.py`. Models: gemini-3.5-flash-lite.

## Headline metrics

| metric | result |
|---|---|
| Task success (goals fully achieved) | **15/15 (100.0%)**, checks passed 53/53 |
| Task success, strict (substitute already added, no confirmation pending) | 15/15; 0 goal(s) waiting for the shopper to pick a substitute |
| Grounding accuracy (replies with 0 invented ₹/aisle values) | **100.0%** of 18 replies; 147 values audited |
| Grounded on the first try (no guard rewrite needed) | 100.0% (0 rewrite(s) triggered by the guard) |
| Discount captured vs theoretical optimum (agent carts) | **100.0%** (₹806.39 of ₹806.39); 15/15 carts optimal |
| Discount captured on 300 random real carts | **100.0%** (greedy 99.97%, single coupon 55.61%) |
| Substitution correctness (same type, in stock) | **100.0%** of 6 cases; 6 added, 0 offered; top-ranked choice 50.0% |
| Latency per turn | median 9.19 s, p90 24.39 s, max 37.26 s |
| LLM calls / tool calls per turn | 4.22 / 4.89 |
| Offer optimizer time | median 0.197 ms, max 0.664 ms |

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
| G01 Multi-item basic list | multi-item, location, billing | ✅ | ✅ | 1 | 37.3 s | ₹284.20 | ₹0.00 / ₹0.00 |
| G02 Named product out of stock | out-of-stock, substitution | ✅ | ✅ | 1 | 16.4 s | ₹357.40 | ₹50.00 / ₹50.00 |
| G03 Two out-of-stock items | out-of-stock, substitution | ✅ | ✅ | 1 | 10.5 s | ₹205.00 | ₹0.00 / ₹0.00 |
| G04 Budget + coupon + out of stock (main demo) | budget, coupon, out-of-stock, budget-fit | ✅ | ✅ | 1 | 24.4 s | ₹451.90 | ₹75.00 / ₹75.00 |
| G05 Store navigation only | location | ✅ | ✅ | 1 | 3.8 s | ₹0.00 | ₹0.00 / ₹0.00 |
| G06 Typos in the request | typo-tolerance, multi-item | ✅ | ✅ | 1 | 6.4 s | ₹418.20 | ₹39.80 / ₹39.80 |
| G07 Quantity above live stock | stock-limit, substitution | ✅ | ✅ | 1 | 11.7 s | ₹160.55 | ₹8.45 / ₹8.45 |
| G08 Multi-turn cart edit | multi-turn, memory, cart-edit | ✅ | ✅ | 2 | 17.8 s | ₹593.32 | ₹121.48 / ₹121.48 |
| G09 Staples cart with stacked coupons | coupon, multi-item | ✅ | ✅ | 1 | 6.8 s | ₹763.60 | ₹140.40 / ₹140.40 |
| G10 Tight budget | budget, multi-item | ✅ | ✅ | 1 | 18.4 s | ₹417.10 | ₹101.90 / ₹101.90 |
| G11 GST question after shopping | gst, out-of-stock, multi-turn | ✅ | ✅ | 2 | 14.5 s | ₹160.00 | ₹0.00 / ₹0.00 |
| G12 Personal care items | multi-item, location | ✅ | ✅ | 1 | 7.7 s | ₹572.59 | ₹63.62 / ₹63.62 |
| G13 Hindi request | hindi, multi-item | ✅ | ✅ | 1 | 9.6 s | ₹451.66 | ₹130.74 / ₹130.74 |
| G14 Marathi request + navigation | marathi, location | ✅ | ✅ | 1 | 6.8 s | ₹208.00 | ₹0.00 / ₹0.00 |
| G15 Compare the cart across stores | multi-store, multi-turn | ✅ | ✅ | 2 | 11.8 s | ₹451.90 | ₹75.00 / ₹75.00 |

## Goal details

### G01 — Multi-item basic list

**Shopper:** I need 2 toned milk, oats, instant coffee and brown bread.

**Agent** (37.26 s, 11 LLM calls, tools: search_products, update_cart, search_products, update_cart, search_products, update_cart, update_cart, search_products, update_cart, update_cart):

> I have added your items to the cart:
> 
> - **2 × Fresh Toned Milk** (₹33.00 each) — Aisle 2, shelf A2-S5
> - **1 × Oats - 100% Natural** (₹85.00) — Aisle 5, shelf A5-S9
> - **Instant Coffee**: Nescafe Sunrise Instant Coffee was out of stock, so I added **1 × Grand Coffee** (₹83.20) as a substitute (other alternatives available: Caramel or Cappuccino Premix). It is in Aisle 6, shelf A6-S1.
> - **Brown Bread**: Britannia Brown Bread was out of stock, so I replaced it with **1 × Multigrain Bread** (₹50.00) from Aisle 2, shelf A2-S2 (Fresho Brown Bread is also available).
> 
> Your bill total is **₹284.20** (inclusive of GST ₹8.01).

Cart: 1 × Britannia Multigrain Bread [Brown, Wheat & Multigrain]; 2 × Amul Fresh Toned Milk [Milk]; 1 × Tata Coffee Grand Coffee [Instant Coffee]; 1 × Saffola Oats - 100% Natural [Oats & Porridge]

- ✅ 2 × Milk (cart has 2)
- ✅ 1 × Oats & Porridge (cart has 1)
- ✅ 1 × Instant Coffee (cart has 1)
- ✅ 1 × Brown, Wheat & Multigrain (cart has 1)
- ✅ quotes bill final_total ₹284.20 (from compute_bill)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G02 — Named product out of stock

**Shopper:** Add Britannia Brown Bread and 2 packs of Maggi masala noodles.

**Agent** (16.45 s, 4 LLM calls, tools: search_products, search_products, find_substitutes, update_cart, update_cart):

> Britannia Brown Bread is currently out of stock. As a replacement, I have added **Multigrain Bread** (₹50.00) located in Aisle 2, shelf A2-S2 (other options include Fresho Brown Bread - Safe, Preservative Free at ₹39.00 and Fresho Bread - Brown, Chemical Free 400G + Eggs - Regular 6pcs at ₹80.58).
> 
> I have also added 2 packs of **Noodles - Masala 280 gm + Ketchup Tomato 1 kg** (₹178.70 each) located in Aisle 5, shelf A5-S10.
> 
> **Bill Summary:**
> - Subtotal: ₹407.40
> - Applied Coupon: **SNACK15** (15% off Snacks & Branded Foods above ₹200) – discount of ₹50.00
> - Discount Total: ₹50.00
> - Final Total: ₹357.40 (inclusive of ₹14.64 GST)

Cart: 1 × Britannia Multigrain Bread [Brown, Wheat & Multigrain]; 2 × MAGGI Noodles - Masala 280 gm + Ketchup Tomato 1 kg [Instant Noodles]

- ✅ 1 × Brown, Wheat & Multigrain (cart has 1)
- ✅ 2 × Instant Noodles (cart has 2)
- ✅ unavailable #103 not over-sold (ok)
- substitution for #103: added, #105 (rank 1)
- coupons: SNACK15 → ₹50.00 (optimum ₹50.00, greedy ₹50.00, single ₹50.00)

### G03 — Two out-of-stock items

**Shopper:** I want Bagrrys Oats Atta and a Coke Zero.

**Agent** (10.47 s, 5 LLM calls, tools: search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> Bagrrys Oats - Atta and Coke Zero are currently out of stock. 
> 
> I have added these alternatives to your cart instead:
> - **Oats - 100% Natural** (Saffola) for ₹85.00 in Aisle 5, shelf A5-S9 (replaces Bagrrys Oats - Atta; other alternatives available include Millet Masala Oats and Quaker Oats).
> - **Fizz - Lime Lemon Classic Cola 300 ml + Fizz - Lime Lemon 300 ml** (Shunya) for ₹120.00 in Aisle 6, shelf A6-S2 (replaces Coke Zero; other alternatives available include Soft Drink - Black, Slim and Soft Drink - Lemon & Lime Flavoured).
> 
> Your bill total is ₹205.00 (inclusive of ₹38.34 GST).

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

**Agent** (24.39 s, 5 LLM calls, tools: set_budget, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> Your requested items have been added to the cart, with their locations:
> 
> * **Instant Tea Premix - Turmeric Ginger** (3 packs) — Aisle 6, shelf A6-S5
> * **Homogenized Milk** (2 packs) — Aisle 2, shelf A2-S5
> * **Brown Bread** was out of stock, so I replaced it with the top substitute **Brown Bread - Safe, Preservative Free** (1 pack) — Aisle 2, shelf A2-S2. (Other alternatives were Multigrain Bread and Bread - Brown, Chemical Free 400G + Eggs - Regular 6pcs).
> 
> **Coupon applied:**
> * `BEV75` (₹75.00 off Beverages above ₹300) — Total discount: ₹75.00
> 
> **Bill Status:**
> * Final Total: ₹451.90
> * Your budget: ₹440.00 (Over budget by ₹11.90)
> 
> Would you like to apply the suggested budget fit (swapping Homogenized Milk for Camel Milk, which brings the total to ₹431.90)?

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

**Agent** (3.75 s, 2 LLM calls, tools: search_products, search_products):

> You can find both basmati rice and sunflower oil in Aisle 4 (Foodgrains, Oil & Masala):
> 
> - **Basmati Rice** options (such as Kohinoor Basmati Rice- Royale 1 kg + Ready Masala- Hyderabadi Biryani 15g, priced at ₹111.00) are located on shelf A4-S7.
> - **Sunflower Oil** options (such as Sunpure Refined - Sunflower Oil, priced at ₹163.00) are located on shelf A4-S4.

Cart: empty

- ✅ cart stays empty (0 line(s))
- ✅ names aisle of Basmati Rice (expected Aisle 4)
- ✅ names aisle of Sunflower, Rice Bran Oil (expected Aisle 4)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G06 — Typos in the request

**Shopper:** I need a pack of egs, amul paneer and some buter

**Agent** (6.36 s, 3 LLM calls, tools: search_products, search_products, search_products, update_cart, update_cart, update_cart):

> I have added the following items to your cart:
> 
> 1. **Eggs - White Leghorn** (Aisle 3, shelf A3-S1)
> 2. **Malai Paneer - Block** (Aisle 2, shelf A2-S5)
> 3. **Unsalted Butter** (Aisle 2, shelf A2-S5)
> 
> **Bill Summary:**
> - **Subtotal:** ₹458.00
> - **Coupon Applied:** DAIRY10 (10% off Dairy above ₹200) saving ₹39.80.
> - **Discount Total:** ₹39.80
> - **Final Total:** ₹418.20 (inclusive of GST of ₹17.06)
> 
> *Tip:* Add ₹42.00 more to unlock the **SAVE10** coupon!

Cart: 1 × Amul Unsalted Butter [Butter & Margarine]; 1 × Amul Malai Paneer - Block [Paneer, Tofu & Cream]; 1 × Mpm Eggs - White Leghorn [Farm Eggs]

- ✅ 1 × Farm Eggs (cart has 1)
- ✅ 1 × Paneer, Tofu & Cream (cart has 1)
- ✅ 1 × Butter & Margarine (cart has 1)
- coupons: DAIRY10 → ₹39.80 (optimum ₹39.80, greedy ₹39.80, single ₹39.80)

### G07 — Quantity above live stock

**Shopper:** Add 5 Amul Fresh Toned Milk

**Agent** (11.65 s, 5 LLM calls, tools: search_products, update_cart, update_cart, update_cart):

> We only had 3 units of Fresh Toned Milk in stock (found in Aisle 2, shelf A2-S5), so I have added all 3 of those. 
> 
> To complete your request of 5 units, I also added 2 units of Amul Homogenized Milk, which is available in the same location (Aisle 2, shelf A2-S5). Other alternatives available were Amul Camel Milk and Nandini Slim Skimmed Milk.
> 
> Coupon AMUL5 applied, giving a discount of ₹8.45.
> Final total: ₹160.55.

Cart: 3 × Amul Fresh Toned Milk [Milk]; 2 × Amul Homogenized Milk [Milk]

- ✅ 5 × Milk (cart has 5)
- ✅ unavailable #171 not over-sold (ok)
- substitution for #171: added, #173 (rank 1)
- coupons: AMUL5 → ₹8.45 (optimum ₹8.45, greedy ₹8.45, single ₹8.45)

### G08 — Multi-turn cart edit

**Shopper:** Add 2 Maggi masala noodles and Mapro tomato ketchup.

**Agent** (12.83 s, 5 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> I have added your items to the cart:
> 
> - **2 × Noodles - Masala 280 gm + Ketchup Tomato 1 kg** (Aisle 5, shelf A5-S10)
> - **1 × Tomato Ketchup** (Aisle 5, shelf A5-S10)
> 
> **Bill Summary:**
> - **Subtotal:** ₹447.40
> - **Coupon Applied:** `SNACK15` (15% off Snacks & Branded Foods above ₹200) — discount of ₹50.00
> - **Final Total:** ₹397.40 *(includes ₹18.93 GST)*

**Shopper:** Make the noodles 4 and remove the ketchup.

**Agent** (4.94 s, 3 LLM calls, tools: update_cart, update_cart):

> I have updated your cart:
> - **Noodles - Masala 280 gm + Ketchup Tomato 1 kg** quantity is now set to 4 (Aisle 5, shelf A5-S10).
> - **Tomato Ketchup** has been removed.
> 
> **Bill Summary:**
> - **Subtotal:** ₹714.80
> - **Coupons Applied:** 
>   - `SAVE10` (10% off on orders above ₹500) — discount of ₹71.48
>   - `SNACK15` (15% off Snacks & Branded Foods above ₹200) — discount of ₹50.00
> - **Total Discounts:** ₹121.48
> - **Final Total:** ₹593.32 *(includes ₹28.25 GST)*

Cart: 4 × MAGGI Noodles - Masala 280 gm + Ketchup Tomato 1 kg [Instant Noodles]

- ✅ 4 × Instant Noodles (cart has 4)
- ✅ no Tomato Ketchup & Sauces (cart has 0)
- ✅ quotes bill final_total ₹593.32 (from compute_bill)
- coupons: SAVE10, SNACK15 → ₹121.48 (optimum ₹121.48, greedy ₹121.48, single ₹71.48)

### G09 — Staples cart with stacked coupons

**Shopper:** Add Aashirvaad Select Atta, bb Royal Biryani Basmati Rice, 2 Sunpure sunflower oil and Himalayan Natives toor dal. Which coupons did I get?

**Agent** (6.78 s, 3 LLM calls, tools: search_products, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> I have added the items to your cart:
> 
> 1. **Select Atta/Godihittu** (1 pack) – Aisle 4, shelf A4-S1
> 2. **Biryani Basmati Rice - Extra Long** (1 pack) – Aisle 4, shelf A4-S7
> 3. **Refined - Sunflower Oil** (2 packs) – Aisle 4, shelf A4-S4
> 4. **Natives Toor Dal//Togari Bele** (1 pack) – Aisle 4, shelf A4-S2
> 
> ### Coupons Applied:
> * **SAVE10** (10% off on orders above ₹500): ₹90.40 discount
> * **STAPLES50** (₹50 off Foodgrains / Oil / Masala above ₹400): ₹50.00 discount
> 
> Total discount applied: **₹140.40** (Final total: **₹763.60**).

Cart: 1 × Aashirvaad Select Atta/Godihittu [Atta Whole Wheat]; 1 × Himalayan Natives Natives Toor Dal//Togari Bele [Toor, Channa & Moong Dal]; 2 × Sunpure Refined - Sunflower Oil [Sunflower, Rice Bran Oil]; 1 × bb Royal Biryani Basmati Rice - Extra Long [Basmati Rice]

- ✅ 1 × Atta Whole Wheat (cart has 1)
- ✅ 1 × Basmati Rice (cart has 1)
- ✅ 2 × Sunflower, Rice Bran Oil (cart has 2)
- ✅ 1 × Toor, Channa & Moong Dal (cart has 1)
- ✅ quotes bill discount_total ₹140.40 (from compute_bill)
- coupons: SAVE10, STAPLES50 → ₹140.40 (optimum ₹140.40, greedy ₹140.40, single ₹90.40)

### G10 — Tight budget

**Shopper:** Weekly basics under ₹500: atta, toor dal, sunflower oil and eggs.

**Agent** (18.42 s, 10 LLM calls, tools: set_budget, search_products, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> I have added your weekly basics to the cart:
> 
> 1. **Chakki-Fresh-Wheat-Atta/Godihittu - Fortified** (bb Royal) — ₹194.00 — Aisle 4, shelf A4-S1
> 2. **Natives Toor Dal//Togari Bele** (Himalayan Natives) — ₹102.00 — Aisle 4, shelf A4-S2
> 3. **Refined - Sunflower Oil** (Sunpure) — ₹163.00 — Aisle 4, shelf A4-S4
> 4. **Eggs - White Leghorn** (Mpm) — ₹60.00 — Aisle 3, shelf A3-S1
> 
> **Bill Summary:**
> - **Subtotal:** ₹519.00
> - **Coupons Applied:** SAVE10 (₹51.90 discount) and STAPLES50 (₹50.00 discount) for a total discount of ₹101.90.
> - **Final Total:** ₹417.10 (well within your ₹500 budget, with ₹82.90 remaining).

Cart: 1 × Mpm Eggs - White Leghorn [Farm Eggs]; 1 × bb Royal Chakki-Fresh-Wheat-Atta/Godihittu - Fortified [Atta Whole Wheat]; 1 × Himalayan Natives Natives Toor Dal//Togari Bele [Toor, Channa & Moong Dal]; 1 × Sunpure Refined - Sunflower Oil [Sunflower, Rice Bran Oil]

- ✅ 1 × Atta Whole Wheat (cart has 1)
- ✅ 1 × Toor, Channa & Moong Dal (cart has 1)
- ✅ 1 × Sunflower, Rice Bran Oil (cart has 1)
- ✅ 1 × Farm Eggs (cart has 1)
- ✅ budget ₹500.00 recorded (recorded 500.00)
- coupons: SAVE10, STAPLES50 → ₹101.90 (optimum ₹101.90, greedy ₹101.90, single ₹51.90)

### G11 — GST question after shopping

**Shopper:** Add 2 Dark Fantasy bourbon biscuits and a Cadbury Dairy Milk Silk Mousse.

**Agent** (12.45 s, 4 LLM calls, tools: search_products, search_products, update_cart, update_cart, update_cart):

> I have added 2 packs of Dark Fantasy Bourbon Chocolate Cream Biscuits to your cart (located in Aisle 5, shelf A5-S2). 
> 
> The Cadbury Dairy Milk Silk Mousse is currently out of stock. As a substitute, I have added the Chocolate Bar - Champion Pack from Aisle 5, shelf A5-S4. Other available alternatives include Cadbury Fuse and LuvIt Dairy Rich Fruit & Nut Chocolate Bar.
> 
> Your current bill total is ₹160.00 (including ₹7.62 GST).

**Shopper:** How much GST is included in my bill?

**Agent** (2.02 s, 1 LLM calls, tools: none):

> The GST included in your bill is ₹7.62 (comprising ₹3.81 CGST and ₹3.81 SGST).

Cart: 2 × Sunfeast Dark Fantasy Bourbon Chocolate Cream Biscuits [Cream Biscuits & Wafers]; 1 × Cadbury Dairy Milk Chocolate Bar - Champion Pack [Chocolates]

- ✅ 2 × Cream Biscuits & Wafers (cart has 2)
- ✅ 1 × Chocolates (cart has 1)
- ✅ unavailable #783 not over-sold (ok)
- ✅ quotes bill gst_included ₹7.62 (from compute_bill)
- substitution for #783: added, #782 (rank 2)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G12 — Personal care items

**Shopper:** Add Pampers diaper pants and Clinic Plus shampoo.

**Agent** (7.69 s, 3 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> I have added the following items to your cart:
> 
> - **Diaper Pants - New Baby** (Pampers) – ₹552.21, located in Aisle 9, shelf A9-S4.
> - **Naturally Long Shikakai Shampoo** (Clinic Plus) – ₹84.00, located in Aisle 8, shelf A8-S4.
> 
> **Bill Summary:**
> - Subtotal: ₹636.21
> - Applied Coupon: **SAVE10** (10% off on orders above ₹500) – discount of ₹63.62
> - Total Savings vs MRP: ₹146.79
> - **Final Total:** ₹572.59 (inclusive of GST ₹27.27)
> 
> *Tip:* Add ₹47.79 more in Baby Care to unlock the **BABY12** coupon! Let me know if you need anything else or if you are ready to check out.

Cart: 1 × Pampers Diaper Pants - New Baby [Diapers]; 1 × Clinic Plus Naturally Long Shikakai Shampoo [Shampoo & Conditioner]

- ✅ 1 × Diapers (cart has 1)
- ✅ 1 × Shampoo & Conditioner (cart has 1)
- coupons: SAVE10 → ₹63.62 (optimum ₹63.62, greedy ₹63.62, single ₹63.62)

### G13 — Hindi request

**Shopper:** मुझे 2 पैकेट मैगी मसाला नूडल्स और अमूल मक्खन चाहिए।

**Agent** (9.58 s, 4 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> मैंने आपके कार्ट में निम्नलिखित चीज़ें जोड़ दी हैं:
> 
> 1. **Noodles - Masala 280 gm + Ketchup Tomato 1 kg** (2 पैकेट) — कीमत: ₹178.70 प्रति पैकेट (Aisle 5, shelf A5-S10)
> 2. **Cooking Butter - Unsalted** (1 पैकेट) — कीमत: ₹225.00 (Aisle 2, shelf A2-S5)
> 
> **बिल विवरण:**
> - सबटोटल: ₹582.40
> - लागू कूपन: 
>   - `SAVE10` (छूट: ₹58.24)
>   - `SNACK15` (छूट: ₹50.00)
>   - `DAIRY10` (छूट: ₹22.50)
> - कुल छूट: ₹130.74
> - अंतिम कुल (GST सहित): ₹451.66

Cart: 1 × Amul Cooking Butter - Unsalted [Butter & Margarine]; 2 × MAGGI Noodles - Masala 280 gm + Ketchup Tomato 1 kg [Instant Noodles]

- ✅ 2 × Instant Noodles (cart has 2)
- ✅ 1 × Butter & Margarine (cart has 1)
- ✅ quotes bill final_total ₹451.66 (from compute_bill)
- coupons: SAVE10, SNACK15, DAIRY10 → ₹130.74 (optimum ₹130.74, greedy ₹130.74, single ₹58.24)

### G14 — Marathi request + navigation

**Shopper:** बासमती तांदूळ कुठे मिळेल? आणि एक पॅकेट साखर कार्टमध्ये टाका.

**Agent** (6.75 s, 3 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> बासमती तांदूळ तुम्हाला **Aisle 4, shelf A4-S7** वर मिळेल आणि साखर **Aisle 4, shelf A4-S8** वर मिळेल. 
> 
> मी तुमच्या कार्टमध्ये Basmati Rice- Royale 1 kg + Ready Masala- Hyderabadi Biryani 15g (किंमत ₹111.00) आणि Organic Sugar/Shakar/Sakkare/Chini - Regular (किंमत ₹97.00) जोडले आहेत.
> 
> तुमच्या बिलाची माहिती खालीलप्रमाणे आहे:
> - **एकूण (Final Total):** ₹208.00
> - **बचत (Savings vs MRP):** ₹98.00
> - **GST समाविष्ट:** ₹9.91

Cart: 1 × Kohinoor Basmati Rice- Royale 1 kg + Ready Masala- Hyderabadi Biryani 15g [Basmati Rice]; 1 × Earthon Organic Sugar/Shakar/Sakkare/Chini - Regular [Sugar & Jaggery]

- ✅ 1 × Sugar & Jaggery (cart has 1)
- ✅ names aisle of Basmati Rice (expected Aisle 4)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G15 — Compare the cart across stores

**Shopper:** Add 3 Instant Tea Premix Turmeric Ginger, 2 Amul Homogenized Milk and Fresho brown bread.

**Agent** (8.8 s, 3 LLM calls, tools: search_products, search_products, search_products, update_cart, update_cart, update_cart):

> I have added the items to your cart:
> 
> - 3 × **Instant Tea Premix - Turmeric Ginger** (₹139.30 each) – Aisle 6, shelf A6-S5
> - 2 × **Homogenized Milk** (₹35.00 each) – Aisle 2, shelf A2-S5
> - 1 × **Brown Bread - Safe, Preservative Free** (₹39.00) – Aisle 2, shelf A2-S2
> 
> **Bill Summary:**
> - **Subtotal:** ₹526.90
> - **Applied Coupon:** BEV75 (₹75.00 off Beverages above ₹300)
> - **Discount Total:** ₹75.00
> - **Final Total:** ₹451.90 (includes ₹16.33 GST)

**Shopper:** Is this cart cheaper at another store?

**Agent** (3.0 s, 2 LLM calls, tools: compare_stores):

> No, SmartMart Kolhapur (this store) is the cheapest for this cart with a final total of ₹451.90. 
> 
> Here is how the other stores compare:
> - **SmartMart Ichalkaranji:** ₹462.00
> - **FreshBasket Sangli:** ₹510.00

Cart: 1 × Fresho Brown Bread - Safe, Preservative Free [Brown, Wheat & Multigrain]; 2 × Amul Homogenized Milk [Milk]; 3 × VAHDAM Instant Tea Premix - Turmeric Ginger [Tea Bags]

- ✅ 3 × Tea Bags (cart has 3)
- ✅ 2 × Milk (cart has 2)
- ✅ 1 × Brown, Wheat & Multigrain (cart has 1)
- ✅ calls compare_stores (called)
- coupons: BEV75 → ₹75.00 (optimum ₹75.00, greedy ₹75.00, single ₹75.00)
