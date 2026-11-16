# POE Exam Guide: SmartCart Agent (Group D8)

Use this the evening before the exam and keep it open on the day. The slides are in
`docs/Group_No_D8_Final_POE_v2.pptx` (38 slides, includes the Phase II enhancements; every slide has speaker notes). Written guide, report draft and paper draft: `docs/SmartCart_Project_Guide.docx`, `docs/SmartCart_Project_Report.docx`, `docs/SmartCart_Research_Paper.docx`.

---

## 1. Before the exam (do this 30 minutes early)

1. Start **Docker Desktop** and wait until it says "running".
2. In PowerShell, in `D:\SmartCartAgent`:
   ```powershell
   docker compose up -d
   python scripts/03_seed_database.py     # fresh, identical data (undo earlier demos)
   python -m pytest -q                    # must say: 108 passed
   python -m uvicorn smartcart.api.main:app         # keep this window open
   ```
3. In Chrome, open three tabs:
   - `http://127.0.0.1:8000/`: Shop
   - `http://127.0.0.1:8000/#/admin`: Store admin (log in as **manager / manager123**)
   - `http://127.0.0.1:8000/#/eval`: Evaluation
4. Check the header shows **"849 products live"** and **"Gemini agent ready"**.
5. **Do not** run `pytest -m live` or `scripts/07_evaluate.py` just before the demo. They use the
   Gemini free quota (15 requests per minute).
6. Have `docs/evaluation/EVALUATION_REPORT.md` open in VS Code as a backup.

---

## 2. The 10-minute demo (who clicks what)

| min | show | say |
|---|---|---|
| 0–1 | slide: problem + idea | "A shopper types a natural request; the agent finds products, shelf location, stock, best coupons, substitutes and the bill. **The AI never invents a price.** Every number comes from PostgreSQL." |
| 1–4 | **Shop tab** → click the example, or type: *"I need 3 Instant Tea Premix Turmeric Ginger, 2 Homogenized Milk and Britannia Brown Bread. My budget is ₹440"* | Point out: bread out of stock → substituted automatically + **substitute cards** · aisle/shelf per item + pick route · **BEV75** coupon · "Over by ₹11.90" · **Grounded in database** badge · click "N tool calls" to show the trace. |
| 4–5 | **Fit my budget** → **Apply swaps** | "Second optimizer: fewest swaps to cheaper same-type items, coupons re-optimized for every plan → ₹8.10 left." |
| 5–6 | click the **GST** row; press **+/−** on an item | "Prices are GST-inclusive; discount is split across lines, then CGST/SGST per slab. The +/− buttons change the bill instantly without the AI." |
| 5–6 | **Compare with other stores** (cart panel) | "Same cart priced at 3 stores; coupons only where valid; we only recommend a store that has every item." |
| 6–7 | **New chat** → choose **हिंदी** (or मराठी) → click an example, or press the **microphone** and speak | "It answers in Hindi, and the badge shows every rupee amount was still checked against the database." |
| 7 | **Store admin**: log out, log in as **staff / staff123** (price boxes locked) → back to manager, change the tea price → Shop | "Roles are enforced by the server, every change is in the audit log, and the bill updates by itself: carts store **no prices**." |
| 7–8 | **Checkout** → receipt; admin shows the order | "Checkout is one database transaction: locks rows, re-prices, checks stock, decrements, saves an order snapshot." |
| 8–10 | **Evaluation tab** + evaluation slides | "15 scripted goals (incl. Hindi, Marathi, store comparison) run live through the same agent, scored by code: 15/15 task success, 100% grounding (147 values checked), 100% of the brute-force optimal discount, 100% correct substitutes. Run 1 found 3 real problems; we fixed them and re-ran." |

**If Gemini is slow** (on 12 Nov one turn took 10–37 s): keep talking while it answers. Explain the
tool trace or the architecture slide.

**If Gemini gives the rate-limit message** ("AI request limit reached…"): the cart is saved, so wait
about 60 s and send again. Meanwhile demo the parts that need no AI: the +/− buttons, Fit my
budget, GST, admin, checkout and the Evaluation tab. If needed, also run
`python scripts/05_demo_tools.py`, which goes through all the tools with no AI.

---

## 3. Explain it in one breath (each member should be able to say this)

> "It's a conversational shopping agent for one supermarket. The LLM, Google Gemini inside a
> LangGraph state graph, only **understands and plans**: it splits the request and decides which
> tool to call. **Every transactional value** (price, stock, aisle, discount, GST, total) comes
> from **tool functions reading PostgreSQL**. The graph enforces the safety parts in code:
> - out of stock → ranked substitutes are always attached
> - cart changed → the bill is always recomputed
> - over budget → a swap plan is attached
> - every reply → a grounding check, so any ₹ amount or aisle that no tool returned is caught
>
> Coupons are chosen by an exact branch-and-bound over the conflict graph, verified against
> brute force."

### Numbers to remember
| what | value |
|---|---|
| products / categories / aisles / shelves | 849 real BigBasket products · 9 categories · 9 aisles · 64 shelves |
| out of stock / low stock | 51 / 85 |
| coupons / conflict pairs | 19 / 12 (1 expired, 1 disabled on purpose) |
| tools / API endpoints / tables | 9 agent tools · 37 endpoints · 15 database tables |
| automated tests | 108 offline + 3 live Gemini = 111 |
| coupon optimizer | optimal on 700 test cases + 300 evaluation carts; median ~0.2 ms |
| evaluation (final run) | 15/15 goals · 53/53 checks · grounding 100% (147 values) · discount 100% of optimum · substitution 100% |
| single coupon only | gets just 55.6% of the possible discount |
| model | gemini-3.5-flash-lite, fallback gemini-3.1-flash-lite-preview |

---

## 4. Likely viva questions

**Q1. What is the novelty?**
Five things in one tool-grounded agent over one shared cart: shelf-level location, live
inventory, optimal coupon combination, ranked substitution and live billing (plus budget fit and
GST). In our 10-paper survey none covers more than three (comparison matrix slide).

**Q2. How do you guarantee the AI doesn't make up a price?**
In three layers:
1. Architecture: the LLM has no number source except tool results, and carts store no prices.
2. The graph computes totals and budget differences itself.
3. A grounding guard scans every reply: any ₹ amount or aisle number not found in a tool result
   is sent back for a rewrite, and flagged to the user if it is still wrong.

The evaluation measured 100% grounding over 105 values.

**Q3. Why is coupon selection hard? Why not greedy?**
Coupons conflict pairwise, so picking the best set is a maximum-weight independent set problem,
which is NP-hard in general. Greedy can fail: A = ₹100 conflicts with B = ₹60 and C = ₹60. Greedy
takes A (₹100), but B + C = ₹120. We use exact branch-and-bound. With about 20 coupons it takes
under 4 ms, and it matches brute force on every case we tested.

**Q4. Then why did greedy reach 99.97% in your study?**
Our store's 19 coupons rarely create the bad pattern, so greedy was wrong on only 1 of 300 carts.
But greedy is *not guaranteed*, and a single coupon (how most checkouts work) gets only 55.6%.
Exact costs nothing extra (0.2 ms), so there is no reason to accept a heuristic.

**Q5. How did you evaluate?**
12 scripted goals (multi-item, typos, out of stock, stock limits, budgets, coupons, multi-turn,
navigation, GST) are run live through the same agent the web app uses, then scored **by code**:
- the cart is read back from PostgreSQL
- reply numbers are matched against tool results
- the discount is compared with a brute-force optimum

Run 1 scored 8/12 and exposed 3 real behaviour problems. We fixed the prompt and the final run
scored 12/12.

**Q6. Why not RAGAS or DeepEval?**
RAGAS is built for retrieval-augmented generation (answers checked against retrieved
documents); we retrieve no documents. DeepEval's agent metrics mostly use another LLM as the
judge, which gives an *opinion*. Our key claims (no invented number, optimal discount) can be
verified **exactly** against the database and brute force, which is stronger evidence. An LLM
judge could be added later for soft qualities like politeness or clarity.

**Q7. What does "strict 10/12" mean?**
In 2 goals the agent added what was available and *asked* the shopper which substitute to use
for the rest. The synopsis says the shopper confirms substitutes, so that counts as success.
Strict scoring counts it as not finished.

**Q8. What happens if two shoppers buy the last unit?**
Checkout locks the inventory rows (`SELECT … FOR UPDATE`, in product-id order to avoid
deadlocks), re-prices inside the same transaction and checks stock. The second shopper is
refused and nothing is written.

**Q9. Where does the data come from? Is it real?**
Product names, brands, categories, MRP and prices are real (BigBasket Kaggle dataset, 27,555 →
849 cleaned and sampled). Stock levels, the aisle map, coupons and GST rates are synthetic or
hand-authored, because no public dataset has them, and they are generated with a fixed seed. The
GST rates are simplified (real GST depends on HSN codes, which the dataset doesn't have).

**Q10. Why Gemini 3.5 Flash-Lite?**
It was measured on our key: about 1 s per call versus about 11 s for 3.1 Flash-Lite Preview,
which also returned "high demand" errors. The old model is kept as an automatic fallback. Both
are on the free tier (15 requests per minute), so we pace calls, retry after short rate-limit
waits and reply politely instead of crashing.

**Q11. Why LangGraph and not a simple prompt loop?**
We need a state machine with **code-enforced** steps after the LLM's choices: substitutes,
bill refresh, budget plan and grounding check, plus loops ("more actions?") and per-session
memory. The cart id is injected from the graph state, so the LLM can't mistype it.

**Q12. How does substitution rank alternatives?**
Only in-stock items with enough quantity. Same product type comes first, then the same
sub-category. Ties are broken by closest price (relative), then name similarity, then rating.

**Q13. How does budget fit work?**
Every line can keep its product or swap to a cheaper same-type product. Plans are searched by
increasing number of swaps (fewest swaps first), then the highest total that still fits. Coupons
are re-optimized for every plan, because a swap can lose a coupon. It is exact and was verified
against brute force on 150 carts.

**Q14. How is GST calculated if prices already include it?**
Each coupon is split across its eligible lines in proportion to their totals. Then for each
line, taxable value = net × 100 / (100 + rate) and GST = net − taxable, split equally into CGST
and SGST. Tested invariant: total taxable + total GST = amount paid, to the paisa.

**Q15. Limitations?**
- one simulated store
- chat memory is in-process (resets on a server restart; the cart survives in Postgres)
- the admin page has no login
- simplified GST rates
- free-tier latency and rate limit
- the grounding check covers ₹ amounts and aisles, not product names

**Q16. Future scope?**
- user study (time saved vs manual shopping)
- persistent memory (Postgres checkpointer)
- admin authentication
- Hindi/Marathi + voice
- cloud deployment
- multi-store price comparison (future scope in the synopsis)

---

## 5. Where things are (if asked to show code)

| topic | file |
|---|---|
| database schema | `db/schema.sql` |
| the 6 tools | `smartcart/tools/catalog.py`, `cart.py`, `offers.py` |
| coupon optimizer (branch-and-bound) | `smartcart/tools/offers.py`, `best_combination()` |
| budget fit | `smartcart/tools/budget.py` |
| GST | `smartcart/tools/tax.py` |
| agent graph | `smartcart/agent/graph.py` |
| grounding guard | `smartcart/agent/grounding.py` |
| system prompt | `smartcart/agent/prompts.py` |
| evaluation goals / scoring | `smartcart/eval/goals.py`, `metrics.py` |
| evaluation report | `docs/evaluation/EVALUATION_REPORT.md` |
| API | `smartcart/api/main.py` (Swagger at `/docs`) |

**After the exam:** run `python scripts/03_seed_database.py` to undo the demo's checkout and
price edits.

---

## 6. Phase II enhancements: likely questions

**Q. How does memory survive a restart?**
LangGraph saves the agent state after every step through a "checkpointer". We wrote our own
PostgreSQL checkpointer (`smartcart/agent/memory.py`), because the official package needs a
driver that is blocked on our machine. A test creates a new assistant object, like a restarted
server, and checks that it continues the same chat.

**Q. How is the admin page secured?**
Passwords are stored as salted PBKDF2-SHA256 hashes. After login the server issues a token
signed with HMAC-SHA256 that is valid for 12 hours. A manager can change prices, stock and
coupons; staff can change stock only. The **server** enforces this with HTTP 403, not just the
page. Every change goes into the audit log.

**Q. Hindi/Marathi: can the AI now sneak in numbers?**
No. The grounding guard reads Devanagari digits (४५), "रुपये" and the Hindi/Marathi words for
aisle. The agent must write amounts as ₹ plus the exact digits. Goals G13 (Hindi) and G14
(Marathi) passed live and were grounded.

**Q. Why does multi-store only compare prices?**
Navigation needs a store map, and only the store you're standing in has one. Other stores
publish prices and stock. We recommend the cheapest store that has **every** item, so a missing
item never looks like a saving. Coupons are applied only where they are valid.

**Q. Where are the user-study results?**
The study mode is built: User study tab → assistant vs manual, timed and scored by code. It
needs real participants, and we will not invent numbers, so it runs in Phase II. To run it: see
section 12 of the Project Guide. Results: `python scripts/08_study_report.py`.

**Q. Is it deployed?**
Not yet. The production Docker image (UI + API in one container) is built and was tested
locally. Cloud deployment is planned for Phase II.
