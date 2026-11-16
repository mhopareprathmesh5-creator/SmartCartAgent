# SmartCart Agent — Evaluation Report

Generated 2026-11-12 11:01 by `python scripts/07_evaluate.py`. Models: gemini-3.5-flash-lite.

## Headline metrics

| metric | result |
|---|---|
| Task success (goals fully achieved) | **12/12 (100.0%)**, checks passed 44/44 |
| Task success, strict (substitute already added, no confirmation pending) | 10/12; 2 goal(s) waiting for the shopper to pick a substitute |
| Grounding accuracy (replies with 0 invented ₹/aisle values) | **100.0%** of 14 replies; 105 values audited |
| Grounded on the first try (no guard rewrite needed) | 100.0% (0 rewrite(s) triggered by the guard) |
| Discount captured vs theoretical optimum (agent carts) | **100.0%** (₹592.20 of ₹592.20); 12/12 carts optimal |
| Discount captured on 300 random real carts | **100.0%** (greedy 99.97%, single coupon 55.61%) |
| Substitution correctness (same type, in stock) | **100.0%** of 6 cases; 3 added, 3 offered; top-ranked choice 33.33% |
| Latency per turn | median 17.52 s, p90 27.28 s, max 37.04 s |
| LLM calls / tool calls per turn | 3.21 / 5.14 |
| Offer optimizer time | median 0.182 ms, max 0.577 ms |

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
| G01 Multi-item basic list | multi-item, location, billing | ✅ | ✅ | 1 | 13.0 s | ₹273.20 | ₹0.00 / ₹0.00 |
| G02 Named product out of stock | out-of-stock, substitution | ✅ | ✅ | 1 | 27.3 s | ₹84.60 | ₹0.00 / ₹0.00 |
| G03 Two out-of-stock items | out-of-stock, substitution | ✅ | ✅ | 1 | 17.2 s | ₹0.00 | ₹0.00 / ₹0.00 |
| G04 Budget + coupon + out of stock (main demo) | budget, coupon, out-of-stock, budget-fit | ✅ | ✅ | 1 | 37.0 s | ₹451.90 | ₹75.00 / ₹75.00 |
| G05 Store navigation only | location | ✅ | ✅ | 1 | 16.6 s | ₹0.00 | ₹0.00 / ₹0.00 |
| G06 Typos in the request | typo-tolerance, multi-item | ✅ | ✅ | 1 | 9.8 s | ₹418.20 | ₹39.80 / ₹39.80 |
| G07 Quantity above live stock | stock-limit, substitution | ✅ | ✅ | 1 | 20.5 s | ₹99.00 | ₹0.00 / ₹0.00 |
| G08 Multi-turn cart edit | multi-turn, memory, cart-edit | ✅ | ✅ | 2 | 34.4 s | ₹593.32 | ₹121.48 / ₹121.48 |
| G09 Staples cart with stacked coupons | coupon, multi-item | ✅ | ✅ | 1 | 15.7 s | ₹763.60 | ₹140.40 / ₹140.40 |
| G10 Tight budget | budget, multi-item | ✅ | ✅ | 1 | 19.3 s | ₹417.10 | ₹101.90 / ₹101.90 |
| G11 GST question after shopping | gst, out-of-stock, multi-turn | ✅ | ✅ | 2 | 27.6 s | ₹302.04 | ₹50.00 / ₹50.00 |
| G12 Personal care items | multi-item, location | ✅ | ✅ | 1 | 17.8 s | ₹572.59 | ₹63.62 / ₹63.62 |

## Goal details

### G01 — Multi-item basic list

**Shopper:** I need 2 toned milk, oats, instant coffee and brown bread.

**Agent** (13.01 s, 4 LLM calls, tools: search_products, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart, update_cart, update_cart):

> I have added your items to the cart:
> 
> - **2 × Fresh Toned Milk** (Amul) – Aisle 2, Shelf A2-S5
> - **1 × Oats - 100% Natural** (Saffola) – Aisle 5, Shelf A5-S9
> - **1 × Grand Coffee** (Tata Coffee) – *Note: Sunrise Instant Coffee was out of stock, so I replaced it with Grand Coffee as the top substitute.* Found in Aisle 6, Shelf A6-S1 (other alternatives include Continental Cappuccino and Caramel premixes).
> - **1 × Brown Bread - Safe, Preservative Free** (Fresho) – *Note: Britannia Brown Bread was out of stock, so I replaced it with Fresho Brown Bread.* Found in Aisle 2, Shelf A2-S2 (other alternatives include Multigrain Bread and Fresho Brown Bread with Eggs).
> 
> Your final total is **₹273.20** (including ₹8.01 GST).

Cart: 1 × Fresho Brown Bread - Safe, Preservative Free [Brown, Wheat & Multigrain]; 2 × Amul Fresh Toned Milk [Milk]; 1 × Tata Coffee Grand Coffee [Instant Coffee]; 1 × Saffola Oats - 100% Natural [Oats & Porridge]

- ✅ 2 × Milk (cart has 2)
- ✅ 1 × Oats & Porridge (cart has 1)
- ✅ 1 × Instant Coffee (cart has 1)
- ✅ 1 × Brown, Wheat & Multigrain (cart has 1)
- ✅ quotes bill final_total ₹273.20 (from compute_bill)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G02 — Named product out of stock

**Shopper:** Add Britannia Brown Bread and 2 packs of Maggi masala noodles.

**Agent** (27.28 s, 5 LLM calls, tools: search_products, search_products, find_substitutes, search_products, search_products, update_cart, update_cart):

> Britannia Brown Bread is currently out of stock, so I replaced it with **Fresho Brown Bread - Safe, Preservative Free** (found in Aisle 2, Aisle Shelf A2-S2). Other alternatives available include Multigrain Bread and Milk Bread.
> 
> I also added 2 packs of **Maggi Masala 2 Minute Instant Noodles** (found in Aisle 5, Aisle Shelf A5-S6).
> 
> **Current Bill:**
> - Items: 3
> - Subtotal: ₹84.60
> - Final Total: ₹84.60 (inclusive of ₹2.17 GST)
> - Savings vs MRP: ₹2.40

Cart: 1 × Fresho Brown Bread - Safe, Preservative Free [Brown, Wheat & Multigrain]; 2 × MAGGI Masala 2 Minute Instant Noodles [Instant Noodles]

- ✅ 1 × Brown, Wheat & Multigrain (cart has 1)
- ✅ 2 × Instant Noodles (cart has 2)
- ✅ unavailable #103 not over-sold (ok)
- substitution for #103: added, #104 (rank 2)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G03 — Two out-of-stock items

**Shopper:** I want Bagrrys Oats Atta and a Coke Zero.

**Agent** (17.23 s, 3 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> Bagrrys Oats Atta and Coke Zero are currently out of stock. 
> 
> For the Oats Atta, we have alternatives like Saffola Oats - 100% Natural (₹85.00, Aisle 5, Shelf A5-S9), GoodDiet Millet Masala Oats (₹90.50, Aisle 5, Shelf A5-S3), or Quaker Oats (₹249.00, Aisle 5, Shelf A5-S3).
> 
> For Coke Zero, we have alternatives like Shunya Fizz - Lime Lemon Classic Cola (₹120.00, Aisle 6, Shelf A6-S2), Pepsi Soft Drink - Black, Slim (₹180.00, Aisle 6, Shelf A6-S2), or Limca Soft Drink (₹95.00, Aisle 6, Shelf A6-S2).
> 
> Would you like me to add any of these substitutes to your cart?

Cart: empty

- ⏳ 1 × Oats & Porridge (cart has 0; substitutes offered for the rest, shopper to confirm)
- ⏳ 1 × Cold Drinks (cart has 0; substitutes offered for the rest, shopper to confirm)
- ✅ unavailable #779 not over-sold (ok)
- ✅ unavailable #314 not over-sold (ok)
- substitution for #779: offered
- substitution for #314: offered
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G04 — Budget + coupon + out of stock (main demo)

**Shopper:** I need 3 Instant Tea Premix Turmeric Ginger, 2 Homogenized Milk and Britannia Brown Bread. My budget is ₹440

**Agent** (37.04 s, 4 LLM calls, tools: set_budget, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> I have added your items to the cart:
> 
> - **Instant Tea Premix - Turmeric Ginger** (3 packs) – Aisle 6, Shelf A6-S5
> - **Homogenized Milk** (2 packs) – Aisle 2, Shelf A2-S5
> - **Brown Bread** – Britannia Brown Bread was out of stock, so I replaced it with **Brown Bread - Safe, Preservative Free** (Fresho) – Aisle 2, Shelf A2-S2. Other available alternatives were Multigrain Bread (Britannia) and Bread - Brown, Chemical Free 400G + Eggs - Regular 6pcs (Fresho).
> 
> Your applied coupon **BEV75** gives a discount of **₹75.00**, bringing your total discount to **₹75.00**. 
> 
> Your current final total is **₹451.90**, which puts you slightly over your ₹440.00 budget by **₹11.90**. 
> 
> Would you like to make the suggested budget-fitting swap (replacing Homogenized Milk with Camel Milk) to bring your final total down to **₹431.90**?

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

**Agent** (16.63 s, 2 LLM calls, tools: search_products, search_products):

> You can find both basmati rice and sunflower oil in Aisle 4 (Foodgrains, Oil & Masala). 
> 
> - **Basmati Rice** is located on **Shelf A4-S7**. We have several options in stock, such as Kohinoor Basmati Rice Royale (Shelf Level 2) and India Gate Basmati Rice (Shelf Level 2).
> - **Sunflower Oil** is located on **Shelf A4-S4**. We carry options like Sunpure Refined Sunflower Oil (Shelf Level 1) and Gold Winner Refined Sunflower Oil (Shelf Level 5). 
> 
> Would you like me to add any of these to your cart?

Cart: empty

- ✅ cart stays empty (0 line(s))
- ✅ names aisle of Basmati Rice (expected Aisle 4)
- ✅ names aisle of Sunflower, Rice Bran Oil (expected Aisle 4)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G06 — Typos in the request

**Shopper:** I need a pack of egs, amul paneer and some buter

**Agent** (9.76 s, 3 LLM calls, tools: search_products, search_products, search_products, update_cart, update_cart, update_cart):

> I have added the following items to your cart:
> 
> - **Eggs - White Leghorn**: Located in Aisle 3, Shelf A3-S1.
> - **Malai Paneer - Block**: Located in Aisle 2, Shelf A2-S5.
> - **Unsalted Butter**: Located in Aisle 2, Shelf A2-S5.
> 
> Coupon **DAIRY10** has been applied, giving you a discount of ₹39.80. 
> Your final total is ₹418.20 (inclusive of ₹17.06 GST).

Cart: 1 × Amul Unsalted Butter [Butter & Margarine]; 1 × Amul Malai Paneer - Block [Paneer, Tofu & Cream]; 1 × Mpm Eggs - White Leghorn [Farm Eggs]

- ✅ 1 × Farm Eggs (cart has 1)
- ✅ 1 × Paneer, Tofu & Cream (cart has 1)
- ✅ 1 × Butter & Margarine (cart has 1)
- coupons: DAIRY10 → ₹39.80 (optimum ₹39.80, greedy ₹39.80, single ₹39.80)

### G07 — Quantity above live stock

**Shopper:** Add 5 Amul Fresh Toned Milk

**Agent** (20.47 s, 4 LLM calls, tools: search_products, update_cart, update_cart):

> We only had 3 units of Amul Fresh Toned Milk in stock, so I have added those 3 units for you. 
> 
> It is located in **Aisle 2, Shelf A2-S5**.
> 
> Alternative options for the remaining 2 units include:
> - Amul Homogenized Milk (Aisle 2, Shelf A2-S5)
> - Amul Camel Milk (Aisle 2, Shelf A2-S5)
> - Nandini Slim Skimmed Milk (Aisle 2, Shelf A2-S5)
> 
> Would you like to add any of these substitutes for the remaining units?

Cart: 3 × Amul Fresh Toned Milk [Milk]

- ⏳ 5 × Milk (cart has 3; substitutes offered for the rest, shopper to confirm)
- ✅ unavailable #171 not over-sold (ok)
- substitution for #171: offered
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G08 — Multi-turn cart edit

**Shopper:** Add 2 Maggi masala noodles and Mapro tomato ketchup.

**Agent** (24.55 s, 3 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> I have added 2 packs of Noodles - Masala 280 gm + Ketchup Tomato 1 kg and 1 Mapro Tomato Ketchup to your cart. 
> 
> Both items can be found in Aisle 5, Shelf A5-S10.
> 
> **Bill Summary:**
> - **Subtotal:** ₹447.40
> - **Coupon Applied:** SNACK15 (15% off Snacks & Branded Foods above ₹200) – ₹50.00 discount
> - **Total Discount:** ₹50.00
> - **Final Total:** ₹397.40 (inclusive of ₹18.93 GST)

**Shopper:** Make the noodles 4 and remove the ketchup.

**Agent** (9.89 s, 2 LLM calls, tools: update_cart, update_cart):

> I have updated your cart to 4 packs of Noodles - Masala 280 gm + Ketchup Tomato 1 kg (found in Aisle 5, Shelf A5-S10) and removed the Mapro Tomato Ketchup.
> 
> **Bill Summary:**
> - **Subtotal:** ₹714.80
> - **Coupons Applied:** 
>   - SAVE10 (10% off on orders above ₹500) – ₹71.48 discount
>   - SNACK15 (15% off Snacks & Branded Foods above ₹200) – ₹50.00 discount
> - **Total Discount:** ₹121.48
> - **Final Total:** ₹593.32 (inclusive of ₹28.25 GST)

Cart: 4 × MAGGI Noodles - Masala 280 gm + Ketchup Tomato 1 kg [Instant Noodles]

- ✅ 4 × Instant Noodles (cart has 4)
- ✅ no Tomato Ketchup & Sauces (cart has 0)
- ✅ quotes bill final_total ₹593.32 (from compute_bill)
- coupons: SAVE10, SNACK15 → ₹121.48 (optimum ₹121.48, greedy ₹121.48, single ₹71.48)

### G09 — Staples cart with stacked coupons

**Shopper:** Add Aashirvaad Select Atta, bb Royal Biryani Basmati Rice, 2 Sunpure sunflower oil and Himalayan Natives toor dal. Which coupons did I get?

**Agent** (15.68 s, 3 LLM calls, tools: search_products, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> I have added the items to your cart:
> 
> 1. **Aashirvaad Select Atta** (Select Atta/Godihittu) – Aisle 4, Shelf A4-S1
> 2. **bb Royal Biryani Basmati Rice** (Biryani Basmati Rice - Extra Long) – Aisle 4, Shelf A4-S7
> 3. **2 Sunpure sunflower oil** (Refined - Sunflower Oil) – Aisle 4, Shelf A4-S4
> 4. **Himalayan Natives toor dal** (Natives Toor Dal//Togari Bele) – Aisle 4, Shelf A4-S2
> 
> **Coupons Applied:**
> * **SAVE10** (10% off on orders above ₹500, max ₹150): ₹90.40 discount
> * **STAPLES50** (₹50 off Foodgrains / Oil / Masala above ₹400): ₹50.00 discount
> 
> Total discount applied: ₹140.40.
> Your final total is ₹763.60.

Cart: 1 × Aashirvaad Select Atta/Godihittu [Atta Whole Wheat]; 1 × Himalayan Natives Natives Toor Dal//Togari Bele [Toor, Channa & Moong Dal]; 2 × Sunpure Refined - Sunflower Oil [Sunflower, Rice Bran Oil]; 1 × bb Royal Biryani Basmati Rice - Extra Long [Basmati Rice]

- ✅ 1 × Atta Whole Wheat (cart has 1)
- ✅ 1 × Basmati Rice (cart has 1)
- ✅ 2 × Sunflower, Rice Bran Oil (cart has 2)
- ✅ 1 × Toor, Channa & Moong Dal (cart has 1)
- ✅ quotes bill discount_total ₹140.40 (from compute_bill)
- coupons: SAVE10, STAPLES50 → ₹140.40 (optimum ₹140.40, greedy ₹140.40, single ₹90.40)

### G10 — Tight budget

**Shopper:** Weekly basics under ₹500: atta, toor dal, sunflower oil and eggs.

**Agent** (19.3 s, 4 LLM calls, tools: set_budget, search_products, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> I've added your weekly basics to the cart:
> 
> - **Chakki-Fresh-Wheat-Atta/Godihittu - Fortified** (Aisle 4, Shelf A4-S1)
> - **Natives Toor Dal//Togari Bele** (Aisle 4, Shelf A4-S2)
> - **Refined - Sunflower Oil** (Aisle 4, Shelf A4-S4)
> - **Eggs - White Leghorn** (Aisle 3, Shelf A3-S1)
> 
> **Bill Summary:**
> - **Subtotal:** ₹519.00
> - **Coupons Applied:** SAVE10 (₹51.90) and STAPLES50 (₹50.00), saving a total of ₹101.90.
> - **Final Total:** ₹417.10 (inclusive of ₹17.29 GST)
> - **Budget Status:** You are under your ₹500 budget with ₹82.90 remaining!

Cart: 1 × Mpm Eggs - White Leghorn [Farm Eggs]; 1 × bb Royal Chakki-Fresh-Wheat-Atta/Godihittu - Fortified [Atta Whole Wheat]; 1 × Himalayan Natives Natives Toor Dal//Togari Bele [Toor, Channa & Moong Dal]; 1 × Sunpure Refined - Sunflower Oil [Sunflower, Rice Bran Oil]

- ✅ 1 × Atta Whole Wheat (cart has 1)
- ✅ 1 × Toor, Channa & Moong Dal (cart has 1)
- ✅ 1 × Sunflower, Rice Bran Oil (cart has 1)
- ✅ 1 × Farm Eggs (cart has 1)
- ✅ budget ₹500.00 recorded (recorded 500.00)
- coupons: SAVE10, STAPLES50 → ₹101.90 (optimum ₹101.90, greedy ₹101.90, single ₹51.90)

### G11 — GST question after shopping

**Shopper:** Add 2 Dark Fantasy bourbon biscuits and a Cadbury Dairy Milk Silk Mousse.

**Agent** (17.95 s, 4 LLM calls, tools: search_products, search_products, update_cart, find_substitutes, update_cart):

> I have added 2 packs of **Dark Fantasy Bourbon Chocolate Cream Biscuits** (found in Aisle 5, Shelf A5-S2). 
> 
> The Cadbury Dairy Milk Silk Mousse is currently out of stock. I replaced it with the top substitute, **Cadbury Fuse Chocolate - Home Treats, 170.5 g** (also in Aisle 5, Shelf A5-S4). Other alternatives available include the Cadbury Dairy Milk Chocolate Bar - Champion Pack or LuvIt Dairy Rich Fruit & Nut Chocolate Bar.
> 
> Coupon **SNACK15** has been applied, giving you a discount of ₹50.00!
> 
> **Bill Summary:**
> - **Subtotal:** ₹352.04
> - **Discount Total:** ₹50.00
> - **Final Total:** ₹302.04 (includes ₹14.38 GST)

**Shopper:** How much GST is included in my bill?

**Agent** (9.65 s, 1 LLM calls, tools: none):

> The total GST included in your bill is **₹14.38** (broken down as ₹7.19 CGST and ₹7.19 SGST at a 5.00% tax rate on a taxable value of ₹287.66).

Cart: 2 × Sunfeast Dark Fantasy Bourbon Chocolate Cream Biscuits [Cream Biscuits & Wafers]; 1 × Cadbury Fuse Chocolate - Home Treats, 170.5 g [Chocolates]

- ✅ 2 × Cream Biscuits & Wafers (cart has 2)
- ✅ 1 × Chocolates (cart has 1)
- ✅ unavailable #783 not over-sold (ok)
- ✅ quotes bill gst_included ₹14.38 (from compute_bill)
- substitution for #783: added, #781 (rank 1)
- coupons: SNACK15 → ₹50.00 (optimum ₹50.00, greedy ₹50.00, single ₹50.00)

### G12 — Personal care items

**Shopper:** Add Pampers diaper pants and Clinic Plus shampoo.

**Agent** (17.81 s, 3 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> I have added the following items to your cart:
> 
> 1. **Diaper Pants - New Baby** (Pampers) – ₹552.21
>    - **Location:** Aisle 9, Shelf A9-S4 (Level 5)
> 2. **Naturally Long Shikakai Shampoo** (Clinic Plus) – ₹84.00
>    - **Location:** Aisle 8, Shelf A8-S4 (Level 1)
> 
> **Bill Summary:**
> - **Subtotal:** ₹636.21
> - **Discount Applied:** ₹63.62 (Coupon: `SAVE10` - 10% off on orders above ₹500)
> - **Final Total:** ₹572.59 (includes GST of ₹27.27)
> 
> *Tip:* Add ₹47.79 more in Baby Care to unlock the `BABY12` coupon! Let me know if you need anything else or if you are ready to check out.

Cart: 1 × Pampers Diaper Pants - New Baby [Diapers]; 1 × Clinic Plus Naturally Long Shikakai Shampoo [Shampoo & Conditioner]

- ✅ 1 × Diapers (cart has 1)
- ✅ 1 × Shampoo & Conditioner (cart has 1)
- coupons: SAVE10 → ₹63.62 (optimum ₹63.62, greedy ₹63.62, single ₹63.62)
