# SmartCart Agent — Evaluation Report

Generated 2026-11-12 10:47 by `python scripts/07_evaluate.py`. Models: gemini-3.5-flash-lite.

## Headline metrics

| metric | result |
|---|---|
| Task success (goals fully achieved) | **8/12 (66.67%)**, checks passed 39/44 |
| Grounding accuracy (replies with 0 invented ₹/aisle values) | **100.0%** of 14 replies; 77 values audited |
| Grounded on the first try (no guard rewrite needed) | 100.0% (0 rewrite(s) triggered by the guard) |
| Discount captured vs theoretical optimum (agent carts) | **100.0%** (₹592.20 of ₹592.20); 12/12 carts optimal |
| Discount captured on 300 random real carts | **100.0%** (greedy 100.0%, single coupon 55.58%) |
| Substitution correctness (same type, in stock) | **83.33%** of 6 cases; 2 added, 3 offered; top-ranked choice 0.0% |
| Latency per turn | median 6.55 s, p90 10.28 s, max 14.73 s |
| LLM calls / tool calls per turn | 3.07 / 4.79 |
| Offer optimizer time | median 0.307 ms, max 10.677 ms |

## How each metric is measured

- **Task success**: after the conversation the cart is read from PostgreSQL. Every requested item must be present as the right *product type* in the exact quantity, removed items must be gone, the budget must be recorded, and where asked, the reply must quote the bill's value.
- **Grounding accuracy**: every ₹ amount and aisle number in each final reply is checked against the values the tools returned in that conversation (the same guard that runs live).
- **Discount captured**: for the final cart, the discount the system applied is compared with the theoretical optimum, found by brute force over every conflict-free subset of the valid coupons. Greedy (biggest coupon first) and best-single-coupon are baselines.
- **Substitution**: for every product that could not be supplied (out of stock or quantity above stock), a correct outcome is an in-stock product of the same product type in the cart, or substitute cards shown for the shopper to pick.
- **Latency / LLM calls**: wall-clock time of each turn and the number of Gemini requests it made (the run is paced to respect the 15 requests/min free tier).

## Offline coupon study (no LLM)

300 random carts (3–25 products from the real catalogue, quantity 1–4), the real 19 coupons and 12 conflict pairs:

| method | discount given | share of optimum | carts below optimum |
|---|---|---|---|
| Brute force (theoretical optimum) | ₹202628.53 | 100% | 0 |
| **SmartCart branch-and-bound** | ₹202628.53 | **100.0%** | 0 |
| Greedy (biggest first) | ₹202628.53 | 100.0% | 0 |
| Best single coupon | ₹112616.30 | 55.58% | 297 |

## Per-goal results

| goal | features | success | grounded | turns | latency | final total | discount (system / optimum) |
|---|---|---|---|---|---|---|---|
| G01 Multi-item basic list | multi-item, location, billing | ✅ | ✅ | 1 | 10.2 s | ₹273.20 | ₹0.00 / ₹0.00 |
| G02 Named product out of stock | out-of-stock, substitution | ❌ | ✅ | 1 | 7.8 s | ₹352.40 | ₹50.00 / ₹50.00 |
| G03 Two out-of-stock items | out-of-stock, substitution | ❌ | ✅ | 1 | 5.2 s | ₹0.00 | ₹0.00 / ₹0.00 |
| G04 Budget + coupon + out of stock (main demo) | budget, coupon, out-of-stock, budget-fit | ✅ | ✅ | 1 | 6.8 s | ₹451.90 | ₹75.00 / ₹75.00 |
| G05 Store navigation only | location | ✅ | ✅ | 1 | 14.7 s | ₹0.00 | ₹0.00 / ₹0.00 |
| G06 Typos in the request | typo-tolerance, multi-item | ✅ | ✅ | 1 | 6.5 s | ₹418.20 | ₹39.80 / ₹39.80 |
| G07 Quantity above live stock | stock-limit, substitution | ❌ | ✅ | 1 | 10.3 s | ₹99.00 | ₹0.00 / ₹0.00 |
| G08 Multi-turn cart edit | multi-turn, memory, cart-edit | ✅ | ✅ | 2 | 12.4 s | ₹593.32 | ₹121.48 / ₹121.48 |
| G09 Staples cart with stacked coupons | coupon, multi-item | ❌ | ✅ | 1 | 5.7 s | ₹763.60 | ₹140.40 / ₹140.40 |
| G10 Tight budget | budget, multi-item | ✅ | ✅ | 1 | 6.6 s | ₹417.10 | ₹101.90 / ₹101.90 |
| G11 GST question after shopping | gst, out-of-stock, multi-turn | ✅ | ✅ | 2 | 7.4 s | ₹160.00 | ₹0.00 / ₹0.00 |
| G12 Personal care items | multi-item, location | ✅ | ✅ | 1 | 4.6 s | ₹572.59 | ₹63.62 / ₹63.62 |

## Goal details

### G01 — Multi-item basic list

**Shopper:** I need 2 toned milk, oats, instant coffee and brown bread.

**Agent** (10.2 s, 3 LLM calls, tools: search_products, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> I have added the items to your cart:
> 
> * **2 × Fresh Toned Milk** (Amul) — Aisle 2, Shelf A2-S5 (Level 1)
> * **1 × Oats - 100% Natural** (Saffola) — Aisle 5, Shelf A5-S9 (Level 4)
> * **1 × Grand Coffee** (Tata Coffee) — Aisle 6, Shelf A6-S1 (Level 2)
> * **1 × Brown Bread - Safe, Preservative Free** (Fresho) — Aisle 2, Shelf A2-S2 (Level 1)
> 
> Your current bill total is **₹273.20** (including **₹8.01** GST).

Cart: 1 × Fresho Brown Bread - Safe, Preservative Free [Brown, Wheat & Multigrain]; 2 × Amul Fresh Toned Milk [Milk]; 1 × Tata Coffee Grand Coffee [Instant Coffee]; 1 × Saffola Oats - 100% Natural [Oats & Porridge]

- ✅ 2 × Milk (cart has 2)
- ✅ 1 × Oats & Porridge (cart has 1)
- ✅ 1 × Instant Coffee (cart has 1)
- ✅ 1 × Brown, Wheat & Multigrain (cart has 1)
- ✅ quotes bill final_total ₹273.20 (from compute_bill)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G02 — Named product out of stock

**Shopper:** Add Britannia Brown Bread and 2 packs of Maggi masala noodles.

**Agent** (7.79 s, 3 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> Britannia Brown Bread was out of stock, so I replaced it with **Milk Bread** (found in Aisle 2, Shelf 2). 
> 
> For the Maggi, I added **2 packs of Noodles - Masala 280 gm + Ketchup Tomato 1 kg** (found in Aisle 5, Shelf 10).
> 
> **Bill Summary:**
> - **Subtotal:** ₹402.40
> - **Discount:** ₹50.00 (via coupon `SNACK15`)
> - **Final Total:** ₹352.40

Cart: 1 × Britannia Milk Bread [Milk, White & Sandwich]; 2 × MAGGI Noodles - Masala 280 gm + Ketchup Tomato 1 kg [Instant Noodles]

- ❌ 1 × Brown, Wheat & Multigrain (cart has 0)
- ✅ 2 × Instant Noodles (cart has 2)
- ✅ unavailable #103 not over-sold (ok)
- substitution for #103: missing
- coupons: SNACK15 → ₹50.00 (optimum ₹50.00, greedy ₹50.00, single ₹50.00)

### G03 — Two out-of-stock items

**Shopper:** I want Bagrrys Oats Atta and a Coke Zero.

**Agent** (5.2 s, 3 LLM calls, tools: search_products, search_products, find_substitutes, find_substitutes):

> Bagrrys Oats - Atta and Coke Zero are currently out of stock. 
> 
> For the oats, we have alternatives like Saffola Oats - 100% Natural (₹85.00, Aisle 5, Shelf A5-S9), GoodDiet Millet Masala Oats, Quaker Oats, and Kelloggs Oats.
> For Coke Zero, we have alternatives like Shunya Fizz - Lime Lemon Classic Cola (₹120.00, Aisle 6, Shelf A6-S2), Pepsi Soft Drink, Limca, and Kingfisher Radler.
> 
> Would you like me to add any of these substitutes to your cart?

Cart: empty

- ❌ 1 × Oats & Porridge (cart has 0)
- ❌ 1 × Cold Drinks (cart has 0)
- ✅ unavailable #779 not over-sold (ok)
- ✅ unavailable #314 not over-sold (ok)
- substitution for #779: offered
- substitution for #314: offered
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G04 — Budget + coupon + out of stock (main demo)

**Shopper:** I need 3 Instant Tea Premix Turmeric Ginger, 2 Homogenized Milk and Britannia Brown Bread. My budget is ₹440

**Agent** (6.8 s, 5 LLM calls, tools: set_budget, search_products, search_products, search_products, update_cart, update_cart, find_substitutes, update_cart):

> Britannia Brown Bread is currently out of stock, so I added **Brown Bread - Safe, Preservative Free** (Fresho) instead.
> 
> Here are the locations of your items:
> - **Instant Tea Premix - Turmeric Ginger** (3 packs): Aisle 6, Shelf A6-S5
> - **Homogenized Milk** (2 packs): Aisle 2, Shelf A2-S5
> - **Brown Bread - Safe, Preservative Free** (1 pack): Aisle 2, Shelf A2-S2
> 
> Other bread alternatives available in Aisle 2 (Shelf A2-S2) include Multigrain Bread (Britannia) and Milk Bread (Britannia).
> 
> Your bill total is currently **₹451.90**, which is over your budget of **₹440.00** by **₹11.90**. 
> 
> Would you like me to apply the suggested swap to bring it within budget (replacing Homogenized Milk with Camel Milk, bringing the total to **₹431.90**)?

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

**Agent** (14.73 s, 2 LLM calls, tools: search_products, search_products):

> You can find both basmati rice and sunflower oil in Aisle 4 (Foodgrains, Oil & Masala). 
> 
> - **Basmati Rice** is located on **Shelf 7** (A4-S7). We have options such as Kohinoor Basmati Rice Royale (1 kg) priced at ₹111.00, Kohinoor Traditional at ₹174.00, bb Royal Biryani Basmati Rice at ₹228.00, India Gate Regular Choice at ₹380.00, and Daawat Devaaya at ₹459.00.
> - **Sunflower Oil** is located on **Shelf 4** (A4-S4). We have options like Sunpure Refined Sunflower Oil at ₹163.00, Gold Winner at ₹177.00, Sundrop Super Lite Advanced at ₹270.00, Nutriorg Organic Sunflower Oil at ₹446.50, and Sunpure Refined Sunflower Oil (larger pack) at ₹863.00.
> 
> Would you like me to add any of these to your cart?

Cart: empty

- ✅ cart stays empty (0 line(s))
- ✅ names aisle of Basmati Rice (expected Aisle 4)
- ✅ names aisle of Sunflower, Rice Bran Oil (expected Aisle 4)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G06 — Typos in the request

**Shopper:** I need a pack of egs, amul paneer and some buter

**Agent** (6.49 s, 3 LLM calls, tools: search_products, search_products, search_products, update_cart, update_cart, update_cart):

> I have added the following items to your cart:
> 
> 1. **Eggs - White Leghorn** (Aisle 3, Shelf A3-S1)
> 2. **Malai Paneer - Block** (Aisle 2, Shelf A2-S5)
> 3. **Unsalted Butter** (Aisle 2, Shelf A2-S5)
> 
> Your bill total is **₹418.20** (with **₹39.80** saved via coupon **DAIRY10**). 
> 
> *(Tip: Add just **₹42.00** more to unlock the **SAVE10** coupon!)* Let me know if you need anything else or if you are ready to check out!

Cart: 1 × Amul Unsalted Butter [Butter & Margarine]; 1 × Amul Malai Paneer - Block [Paneer, Tofu & Cream]; 1 × Mpm Eggs - White Leghorn [Farm Eggs]

- ✅ 1 × Farm Eggs (cart has 1)
- ✅ 1 × Paneer, Tofu & Cream (cart has 1)
- ✅ 1 × Butter & Margarine (cart has 1)
- coupons: DAIRY10 → ₹39.80 (optimum ₹39.80, greedy ₹39.80, single ₹39.80)

### G07 — Quantity above live stock

**Shopper:** Add 5 Amul Fresh Toned Milk

**Agent** (10.28 s, 4 LLM calls, tools: search_products, check_stock, update_cart):

> We only had 3 packs of Fresh Toned Milk in stock, so I've added all 3 available packs to your cart. 
> 
> You can find Fresh Toned Milk in Aisle 2, Shelf A2-S5.
> 
> Your current bill total is ₹99.00. 
> *(Hint: Add ₹1.00 more of Amul products to unlock the coupon AMUL5!)* 
> 
> Would you like to add anything else?

Cart: 3 × Amul Fresh Toned Milk [Milk]

- ❌ 5 × Milk (cart has 3)
- ✅ unavailable #171 not over-sold (ok)
- substitution for #171: offered
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G08 — Multi-turn cart edit

**Shopper:** Add 2 Maggi masala noodles and Mapro tomato ketchup.

**Agent** (7.46 s, 3 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> I've added 2 packs of Noodles - Masala 280 gm + Ketchup Tomato 1 kg and 1 pack of Mapro Tomato Ketchup to your cart. Both are located in Aisle 5, Shelf A5-S10.
> 
> Your current bill total is ₹397.40 (with a ₹50.00 discount applied using coupon `SNACK15`).

**Shopper:** Make the noodles 4 and remove the ketchup.

**Agent** (4.99 s, 2 LLM calls, tools: update_cart, update_cart):

> I've updated your cart to 4 packs of the Maggi noodles + ketchup combo and removed the separate Tomato Ketchup. 
> 
> Your final total is ₹593.32, with the coupons `SAVE10` and `SNACK15` applied for a total discount of ₹121.48!

Cart: 4 × MAGGI Noodles - Masala 280 gm + Ketchup Tomato 1 kg [Instant Noodles]

- ✅ 4 × Instant Noodles (cart has 4)
- ✅ no Tomato Ketchup & Sauces (cart has 0)
- ✅ quotes bill final_total ₹593.32 (from compute_bill)
- coupons: SAVE10, SNACK15 → ₹121.48 (optimum ₹121.48, greedy ₹121.48, single ₹71.48)

### G09 — Staples cart with stacked coupons

**Shopper:** Add Aashirvaad Select Atta, bb Royal Biryani Basmati Rice, 2 Sunpure sunflower oil and Himalayan Natives toor dal. Which coupons did I get?

**Agent** (5.66 s, 3 LLM calls, tools: search_products, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> I have added the items to your cart:
> 
> - **Aashirvaad Select Atta**: Aisle 4, Shelf A4-S1
> - **bb Royal Biryani Basmati Rice**: Aisle 4, Shelf A4-S7
> - **2 × Sunpure Sunflower Oil**: Aisle 4, Shelf A4-S4
> - **Himalayan Natives Toor Dal**: Aisle 4, Shelf A4-S2
> 
> The coupons applied to your order are:
> - **SAVE10** (10% off on orders above ₹500)
> - **STAPLES50** (₹50 off Foodgrains / Oil / Masala above ₹400)
> 
> Your final total is ₹763.60.

Cart: 1 × Aashirvaad Select Atta/Godihittu [Atta Whole Wheat]; 1 × Himalayan Natives Natives Toor Dal//Togari Bele [Toor, Channa & Moong Dal]; 2 × Sunpure Refined - Sunflower Oil [Sunflower, Rice Bran Oil]; 1 × bb Royal Biryani Basmati Rice - Extra Long [Basmati Rice]

- ✅ 1 × Atta Whole Wheat (cart has 1)
- ✅ 1 × Basmati Rice (cart has 1)
- ✅ 2 × Sunflower, Rice Bran Oil (cart has 2)
- ✅ 1 × Toor, Channa & Moong Dal (cart has 1)
- ❌ quotes bill discount_total ₹140.40 (from compute_bill)
- coupons: SAVE10, STAPLES50 → ₹140.40 (optimum ₹140.40, greedy ₹140.40, single ₹90.40)

### G10 — Tight budget

**Shopper:** Weekly basics under ₹500: atta, toor dal, sunflower oil and eggs.

**Agent** (6.61 s, 4 LLM calls, tools: set_budget, search_products, search_products, search_products, search_products, update_cart, update_cart, update_cart, update_cart):

> I have added your weekly basics to the cart:
> 
> 1. **Chakki-Fresh-Wheat-Atta/Godihittu - Fortified** (bb Royal) – Aisle 4, Shelf A4-S1, Level 5
> 2. **Natives Toor Dal//Togari Bele** (Himalayan Natives) – Aisle 4, Shelf A4-S2, Level 4
> 3. **Refined - Sunflower Oil** (Sunpure) – Aisle 4, Shelf A4-S4, Level 1
> 4. **Eggs - White Leghorn** (Mpm) – Aisle 3, Shelf A3-S1, Level 2
> 
> **Bill Summary:**
> - **Subtotal:** ₹519.00
> - **Coupons Applied:** SAVE10 (10% off) & STAPLES50 (₹50 off Foodgrains/Oil/Masala)
> - **Final Total:** ₹417.10 (well within your ₹500 budget, with ₹82.90 remaining!)

Cart: 1 × Mpm Eggs - White Leghorn [Farm Eggs]; 1 × bb Royal Chakki-Fresh-Wheat-Atta/Godihittu - Fortified [Atta Whole Wheat]; 1 × Himalayan Natives Natives Toor Dal//Togari Bele [Toor, Channa & Moong Dal]; 1 × Sunpure Refined - Sunflower Oil [Sunflower, Rice Bran Oil]

- ✅ 1 × Atta Whole Wheat (cart has 1)
- ✅ 1 × Toor, Channa & Moong Dal (cart has 1)
- ✅ 1 × Sunflower, Rice Bran Oil (cart has 1)
- ✅ 1 × Farm Eggs (cart has 1)
- ✅ budget ₹500.00 recorded (recorded 500.00)
- coupons: SAVE10, STAPLES50 → ₹101.90 (optimum ₹101.90, greedy ₹101.90, single ₹51.90)

### G11 — GST question after shopping

**Shopper:** Add 2 Dark Fantasy bourbon biscuits and a Cadbury Dairy Milk Silk Mousse.

**Agent** (5.92 s, 4 LLM calls, tools: search_products, search_products, update_cart, update_cart, update_cart):

> I've added 2 packs of Dark Fantasy Bourbon Chocolate Cream Biscuits to your cart. You can find them in **Aisle 5, Shelf A5-S2**.
> 
> Unfortunately, the Cadbury Dairy Milk Silk Mousse is currently out of stock. As a substitute, I've added a **Cadbury Dairy Milk Chocolate Bar - Champion Pack** for you, which is located in **Aisle 5, Shelf A5-S4**. Other available alternatives include Cadbury Fuse and LuvIt Dairy Rich Fruit & Nut Chocolate Bar.
> 
> Your current total is **₹160.00**.

**Shopper:** How much GST is included in my bill?

**Agent** (1.44 s, 1 LLM calls, tools: none):

> The total GST included in your bill is **₹7.62**.

Cart: 2 × Sunfeast Dark Fantasy Bourbon Chocolate Cream Biscuits [Cream Biscuits & Wafers]; 1 × Cadbury Dairy Milk Chocolate Bar - Champion Pack [Chocolates]

- ✅ 2 × Cream Biscuits & Wafers (cart has 2)
- ✅ 1 × Chocolates (cart has 1)
- ✅ unavailable #783 not over-sold (ok)
- ✅ quotes bill gst_included ₹7.62 (from compute_bill)
- substitution for #783: added, #782 (rank 2)
- coupons: none → ₹0.00 (optimum ₹0.00, greedy ₹0.00, single ₹0.00)

### G12 — Personal care items

**Shopper:** Add Pampers diaper pants and Clinic Plus shampoo.

**Agent** (4.6 s, 3 LLM calls, tools: search_products, search_products, update_cart, update_cart):

> I have added the following items to your cart:
> 
> 1. **Pampers Diaper Pants - New Baby** – Found in Aisle 9 (Shelf A9-S4).
> 2. **Clinic Plus Naturally Long Shikakai Shampoo** – Found in Aisle 8 (Shelf A8-S4).
> 
> **Bill Summary:**
> - **Subtotal:** ₹636.21
> - **Coupon Applied:** SAVE10 (10% off) – ₹63.62
> - **Final Total:** ₹572.59 (includes ₹27.27 GST)
> 
> *(Tip: You are just ₹47.79 away from unlocking the **BABY12** coupon for ordering ₹600.00 or more in Baby Care!)* 
> 
> Would you like to add anything else or proceed to checkout?

Cart: 1 × Pampers Diaper Pants - New Baby [Diapers]; 1 × Clinic Plus Naturally Long Shikakai Shampoo [Shampoo & Conditioner]

- ✅ 1 × Diapers (cart has 1)
- ✅ 1 × Shampoo & Conditioner (cart has 1)
- coupons: SAVE10 → ₹63.62 (optimum ₹63.62, greedy ₹63.62, single ₹63.62)
