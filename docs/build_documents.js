// Builds the three Word documents of the project from one source:
//   docs/SmartCart_Project_Guide.docx    explanation + setup / run / test / demo guide
//   docs/SmartCart_Project_Report.docx   final project report (draft)
//   docs/SmartCart_Research_Paper.docx   research paper (draft, IEEE-style two columns)
//
//   python docs/collect_facts.py      # measure the numbers first (writes docs/facts.json)
//   cd docs; npm install; node build_documents.js
//
// Every figure quoted comes from facts.json (measured from the running system) or from the
// evaluation results; screenshots come from docs/assets (taken from the running app).
const fs = require('fs')
const path = require('path')
const {
  AlignmentType, BorderStyle, Document, Footer, HeadingLevel, ImageRun, LevelFormat, Packer, PageBreak,
  PageNumber, Paragraph, SectionType, ShadingType, Table, TableCell, TableOfContents, TableRow, TextRun, WidthType,
} = require('docx')

const DOCS = __dirname
const ASSETS = path.join(DOCS, 'assets')
const F = JSON.parse(fs.readFileSync(path.join(DOCS, 'facts.json'), 'utf8'))
const E = F.eval.summary
const O = F.eval.offline
const B = F.baseline
const DB = F.db
const NAVY = '002060'
const pct = (x) => `${Number(x).toFixed(1).replace(/\.0$/, '')}%`
const TEAM = [['Mayur Khamamkar', '2324000146'], ['Prathmesh Mhopare', '2324001087'], ['Aniket Mane', '2324000104'],
  ['Harshvardhan Magdum', '2324000418']]
const N_GOALS = E.goals_completed

// ===================================================================== building blocks
function makeKit(font, size) {
  const run = (t, o = {}) => new TextRun({ text: t, font: o.font ?? font, size: o.size ?? size, bold: o.bold, italics: o.italics,
    color: o.color, superScript: o.sup })
  // inline **bold** and `code` markup inside a string
  const runs = (s, o = {}) => s.split(/(\*\*[^*]+\*\*|`[^`]+`)/).filter(Boolean).map((part) =>
    part.startsWith('**') ? run(part.slice(2, -2), { ...o, bold: true })
      : part.startsWith('`') ? run(part.slice(1, -1), { ...o, font: 'Consolas', size: (o.size ?? size) - 2 })
        : run(part, o))
  const P = (s, o = {}) => new Paragraph({ children: typeof s === 'string' ? runs(s, o) : s, alignment: o.align ?? AlignmentType.JUSTIFIED,
    spacing: { after: o.after ?? 120, before: o.before ?? 0, line: o.line ?? 276 }, keepNext: o.keepNext, indent: o.indent })
  const bullet = (s, level = 0, ref = 'bullets') => new Paragraph({ children: runs(s), numbering: { reference: ref, level },
    spacing: { after: 60, line: 276 }, alignment: AlignmentType.LEFT })
  const numbered = (s, ref) => new Paragraph({ children: runs(s), numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 276 } })
  const H = (s, level) => new Paragraph({ heading: level, children: [run(s, { size: undefined })] })
  const code = (lines, codeSize) => lines.map((l, i) => new Paragraph({
    children: [run(l || ' ', { font: 'Consolas', size: codeSize ?? size - 3 })],
    shading: { type: ShadingType.CLEAR, color: 'auto', fill: 'F2F4F8' },
    spacing: { after: i === lines.length - 1 ? 140 : 0, line: 240 }, indent: { left: 200, right: 200 },
  }))
  return { run, runs, P, bullet, numbered, H, code }
}

function table(kit, rows, widths, o = {}) {
  const total = widths.reduce((a, b) => a + b, 0)
  const border = o.plain ? { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' }
    : { style: BorderStyle.SINGLE, size: 4, color: '9AA5B8' }
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0,
      cantSplit: true,
      children: r.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        borders: { top: border, bottom: border, left: border, right: border },
        shading: i === 0 && !o.plain ? { type: ShadingType.CLEAR, color: 'auto', fill: 'DCE3F0' }
          : o.highlight?.includes(i) ? { type: ShadingType.CLEAR, color: 'auto', fill: 'EEF5EE' } : undefined,
        margins: { top: 50, bottom: 50, left: 90, right: 90 },
        children: [new Paragraph({ children: kit.runs(String(c), { bold: i === 0 && !o.plain, size: i === 0 ? o.headSize ?? o.size : o.size }),
          alignment: o.align?.[j] ?? AlignmentType.LEFT, spacing: { after: 0, line: 252 } })],
      })),
    })),
  })
}

function pngSize(file) {
  const b = fs.readFileSync(file)
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }
}

let figNo = 0
let tabNo = 0
function figure(kit, file, caption, widthPx = 600) {
  const full = path.join(ASSETS, file)
  if (!fs.existsSync(full)) return [kit.P(`[missing screenshot: ${file}]`)]
  const { w, h } = pngSize(full)
  figNo += 1
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 },
      children: [new ImageRun({ type: 'png', data: fs.readFileSync(full),
        transformation: { width: widthPx, height: Math.round(widthPx * h / w) } })] }),
    kit.P(`Figure ${figNo}. ${caption}`, { align: AlignmentType.CENTER, italics: true, after: 200 }),
  ]
}
function tableCaption(kit, caption) {
  tabNo += 1
  return kit.P(`Table ${tabNo}. ${caption}`, { align: AlignmentType.CENTER, keepNext: true, before: 160, after: 80, bold: true })
}

const numbering = (refs) => ({
  config: [
    { reference: 'bullets', levels: [0, 1].map((level) => ({ level, format: LevelFormat.BULLET, text: level ? '–' : '•',
      alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360 + level * 360, hanging: 260 } } } })) },
    ...refs.map((reference) => ({ reference, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.',
      alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 300 } } } }] })),
  ],
})

const headingStyles = (font, sizes) => ({
  default: { document: { run: { font, size: sizes.body } } },
  paragraphStyles: [
    { id: 'Title', name: 'Title', basedOn: 'Normal', run: { font, size: sizes.title, bold: true, color: NAVY },
      paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 0, after: 200 }, keepNext: true } },
    { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { font, size: sizes.h1, bold: true, color: NAVY },
      paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, outlineLevel: 0 } },
    { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { font, size: sizes.h2, bold: true, color: NAVY },
      paragraph: { spacing: { before: 240, after: 100 }, keepNext: true, outlineLevel: 1 } },
    { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { font, size: sizes.h3, bold: true, color: '333333' },
      paragraph: { spacing: { before: 180, after: 80 }, keepNext: true, outlineLevel: 2 } },
  ],
})

const A4 = { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } }
const TEXT_W = 11906 - 2880

function footer(kit, label) {
  return new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
    kit.run(`${label}  ·  page `, { size: 18, color: '666666' }),
    new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '666666' })] })] })
}

// ===================================================================== shared content
const EVAL_ROWS = () => [
  ['Metric', 'Result', 'How it is measured'],
  ['Task success', `${E.goals_succeeded}/${N_GOALS} goals (${pct(E.task_success_pct)}); ${E.checks_passed}/${E.checks_total} checks`,
    'Final cart read from PostgreSQL: right product types and quantities, budget recorded, bill values quoted'],
  ['Task success, strict', `${E.goals_succeeded_strict}/${N_GOALS}`,
    'Goals where the agent asked the shopper to pick a substitute count as not finished'],
  ['Grounding accuracy', `${pct(E.grounding_accuracy_pct)} of ${E.turns} replies`,
    `Every ₹ amount and aisle in every reply (${E.values_audited} values) matched against tool results`],
  ['Discount captured', `${pct(E.discount_captured_pct)} of optimum`, 'Applied discount ÷ brute-force optimum over every valid coupon subset'],
  ['Substitution correct', `${pct(E.substitution_correct_pct)} of ${E.substitution_cases} cases`,
    'Unavailable product replaced (or offered) by an in-stock product of the same type'],
  ['Latency per turn', `median ${E.latency_median_s} s, max ${E.latency_max_s} s`, `Wall-clock time; ${E.llm_calls_per_turn} Gemini calls per turn`],
]
const OFFLINE_ROWS = () => [
  ['Method', 'Discount given', 'Share of optimum', 'Carts below optimum'],
  ['Brute force (theoretical optimum)', `₹${O.discount_optimum_total}`, '100%', '0'],
  ['Proposed branch-and-bound', `₹${O.discount_system_total}`, pct(O.system_captured_pct), String(O.carts - O.optimal_carts)],
  ['Greedy (largest coupon first)', `₹${O.discount_greedy_total}`, `${O.greedy_captured_pct}%`, String(O.greedy_suboptimal_carts)],
  ['Best single coupon', `₹${O.discount_single_total}`, `${O.single_coupon_captured_pct}%`, String(O.single_suboptimal_carts)],
]
const GOAL_ROWS = () => [['Goal', 'What it tests', 'Result', 'Grounded', 'Time'],
  ...F.eval.goals.map((g) => [`${g.id} ${g.title}`, g.features.join(', '), g.infra_error ? 'rate-limited' : g.success ? '✓' : '✗',
    g.grounded ? '✓' : '✗', `${g.latency_s} s`])]
const LIT = [
  ['WebShop [1]', '2022', 'Grounded language agent navigating a simulated web store to search, customise and buy', 'Simulated store; no aisle map, live inventory or billing'],
  ['ReAct [2]', '2023', 'Interleaves reasoning traces with actions and observations', 'General-purpose; no shopping workflow'],
  ['Toolformer [3]', '2023', 'LM learns when and how to call external APIs', 'Tool use only; no cart or billing'],
  ['InteRecAgent [4]', '2023', 'LLM “brain” with recommender models as tools; planning, memory, reflection', 'Recommendation only; no coupons, aisle or billing'],
  ['RecMind [5]', '2024', 'Autonomous recommendation agent with Self-Inspiring planning', 'No physical-store execution or billing'],
  ['LLM-Rec [6]', '2024', 'Prompting strategies enrich item text for recommendation', 'Static; no actions, inventory or cart state'],
  ['Agent4Rec [7]', '2023', 'Generative user agents simulate recommendation behaviour', 'Simulated users; no real shopping'],
  ['Beyond Persuasion [8]', '2024', 'Credibility-aware conversational recommendation', 'No inventory, offers, substitution or transactions'],
  ['LORE [9]', '2019', 'Min-cost-flow offer recommendation under eligibility and capacity constraints', 'No LLM agent or conversational cart'],
  ['ShoppingBench [10]', '2026', 'Benchmark of grounded shopping intents incl. vouchers', 'Simulated environment; no aisle mapping or billing'],
]
const MATRIX = [['Work', 'NL conv.', 'Tool-grounded', 'Aisle/shelf', 'Live stock', 'Offer optim.', 'Substitution', 'Cart & bill'],
  ['WebShop', '✓', '◐', '✗', '◐', '✗', '✗', '◐'], ['ReAct', '✓', '✓', '✗', '✗', '✗', '✗', '✗'],
  ['Toolformer', '◐', '✓', '✗', '✗', '✗', '✗', '✗'], ['InteRecAgent', '✓', '✓', '✗', '✗', '✗', '◐', '✗'],
  ['RecMind', '✓', '✓', '✗', '✗', '✗', '◐', '✗'], ['LLM-Rec', '◐', '✗', '✗', '✗', '✗', '◐', '✗'],
  ['Agent4Rec', '✓', '✗', '✗', '✗', '✗', '◐', '✗'], ['Beyond Persuasion', '✓', '✗', '✗', '✗', '✗', '◐', '✗'],
  ['LORE', '✗', '✗', '✗', '◐', '✓', '✗', '✗'], ['ShoppingBench', '✓', '✓', '✗', '◐', '◐', '✗', '◐'],
  ['Proposed (D8)', '✓', '✓', '✓', '✓', '✓', '✓', '✓']]
const REFS = [
  'S. Yao, H. Chen, J. Yang and K. Narasimhan, “WebShop: Towards scalable real-world web interaction with grounded language agents,” in Proc. NeurIPS, 2022.',
  'S. Yao et al., “ReAct: Synergizing reasoning and acting in language models,” in Proc. ICLR, 2023.',
  'T. Schick et al., “Toolformer: Language models can teach themselves to use tools,” in Proc. NeurIPS, 2023.',
  'X. Huang et al., “Recommender AI agent: Integrating large language models for interactive recommendations (InteRecAgent),” arXiv:2308.16505, 2023.',
  'Y. Wang et al., “RecMind: Large language model powered agent for recommendation,” in Findings of NAACL, 2024.',
  'H. Lyu et al., “LLM-Rec: Personalized recommendation via prompting large language models,” in Findings of NAACL, 2024.',
  'A. Zhang et al., “On generative agents in recommendation (Agent4Rec),” in Proc. SIGIR, 2024.',
  'Qin et al., “Beyond persuasion: Towards conversational recommender system with credible explanations,” in Findings of EMNLP, 2024.',
  'R. Makhijani et al., “LORE: A large-scale offer recommendation engine with eligibility and capacity constraints,” in Proc. ACM RecSys, 2019.',
  'Wang et al., “ShoppingBench: A benchmark for grounded real-world shopping intents,” 2026.',
  'BigBasket Entire Product List (28K data points), Kaggle dataset.',
  'LangGraph documentation, LangChain Inc.',
  'Google Gemini API documentation: function calling and models; LangChain Google GenAI integration.',
  'PostgreSQL 16 documentation, including the pg_trgm trigram-similarity extension; FastAPI documentation.',
  'Goods and Services Tax (GST) rate schedules, Central Board of Indirect Taxes and Customs, Government of India.',
  'R. M. Karp, “Reducibility among combinatorial problems,” in Complexity of Computer Computations, 1972 (NP-completeness of maximum independent set).',
]

const pngExists = (f) => fs.existsSync(path.join(ASSETS, f))

// ===================================================================== 1. PROJECT GUIDE
function buildGuide() {
  figNo = 0; tabNo = 0
  const k = makeKit('Arial', 21)
  const { P, H, bullet, code } = k
  const T = (rows, widths, o) => table(k, rows, widths, { size: 19, ...o })
  const W = TEXT_W
  const c = []
  // ---- cover
  c.push(P('KIT’s College of Engineering (Empowered Autonomous), Kolhapur', { align: AlignmentType.CENTER, bold: true, before: 1200 }),
    P('Department of Computer Science & Engineering (AIML)', { align: AlignmentType.CENTER, after: 600 }),
    new Paragraph({ style: 'Title', children: [k.run('Conversational Smart-Cart & Billing Assistant Agent', { size: 44, bold: true, color: NAVY })] }),
    P('Project Guide: what the system is, how to set it up, run it, test it and demonstrate it', { align: AlignmentType.CENTER, italics: true, after: 600 }),
    P('Group D8', { align: AlignmentType.CENTER, bold: true }),
    ...TEAM.map(([n, prn]) => P(`${n}  ·  ${prn}`, { align: AlignmentType.CENTER, after: 40 })),
    P('Under the guidance of', { align: AlignmentType.CENTER, before: 400, after: 40 }),
    P('Prof. Vrishali Prabhu, Assistant Professor', { align: AlignmentType.CENTER, bold: true }),
    P('Project Phase I · Final demonstration (POE) · November 2026', { align: AlignmentType.CENTER, before: 400 }),
    new Paragraph({ children: [new PageBreak()] }))

  // ---- 1 overview
  c.push(H('1. Project overview', HeadingLevel.HEADING_1), H('1.1 The problem', HeadingLevel.HEADING_2),
    P('Supermarket shopping is full of small manual tasks: finding each product in an unfamiliar layout, checking whether it is in stock, working out which coupons apply (and which cannot be combined), deciding what to buy when something is out of stock, and adding up the bill. Existing shopping apps offer search and a cart, but leave all of these decisions to the customer.'),
    H('1.2 What our system does', HeadingLevel.HEADING_2),
    P('A shopper types or speaks a request in English, Hindi or Marathi, for example “I need 3 tea premix, 2 milk and Britannia brown bread, my budget is ₹440”. An AI agent then does the whole job:'),
    ...['Finds each product and tells the shopper the aisle, shelf and shelf level.',
      'Checks live stock and price from the store database.',
      'Replaces out-of-stock items with ranked, in-stock alternatives of the same type, shown as clickable cards.',
      'Applies the best combination of coupons: an exact optimizer that respects conflicting coupons.',
      'Fits the cart into the budget: a second optimizer proposes the fewest swaps to cheaper products.',
      'Compares the same cart with two other stores and recommends the cheapest store that has everything.',
      'Keeps a running bill with MRP savings, coupons and the GST included, recalculated on every change.',
      'Checks out in one safe database transaction and prints a receipt with a GST table.',
      'Store staff log in (manager or staff role) to change prices, stock and coupons; every change is logged and open carts update by themselves.',
      'Remembers each conversation in the database, so a chat continues after a server restart.'].map((s) => bullet(s)),
    H('1.3 The one rule the whole design follows', HeadingLevel.HEADING_2),
    P('**The AI plans, understands and explains. It never produces a price, stock count, aisle, discount, tax or total.** Every such number is read from the PostgreSQL database by a tool function. A “grounding guard” checks every reply, in English, Hindi or Marathi, before the shopper sees it and rejects any rupee amount or aisle number that did not come from a tool.'),
    P('This is what makes the system trustworthy near real money, and it is the main idea to explain in any review.'),
    H('1.4 What it looks like', HeadingLevel.HEADING_2),
    ...figure(k, 'ui-shop-cards-budget.png', 'Shopper view: chat with grounding badge, substitute cards, live cart, budget plan'),
    ...(pngExists('ui-hindi-chat.png') ? figure(k, 'ui-hindi-chat.png', 'A Hindi request: the reply is in Hindi, every amount is still checked against the database') : []),
    ...(pngExists('ui-admin-audit.png') ? figure(k, 'ui-admin-audit.png', 'Store admin after login: live prices and stock, recent changes (audit log), coupons')
      : figure(k, 'ui-admin.png', 'Store admin: live prices and stock, recent orders, coupon switches')),
    H('1.5 Real data and synthesized data', HeadingLevel.HEADING_2),
    T([['Data', 'Source'],
      ['Product names, brands, categories, MRP, selling price, ratings', `Real: BigBasket product dataset (Kaggle), 27,555 products, sampled to ${DB.products}`],
      ['Aisle / shelf map, stock levels', 'Synthesized (no public dataset exists), fixed random seed 42, identical on every run'],
      [`Coupons (${DB.coupons}) and conflict pairs (${DB.conflicts})`, 'Hand-authored in data/seed/*.csv'],
      ['GST rates (0 / 5 / 18 / 40 %)', 'Hand-authored, simplified rules by category (real rates depend on HSN codes, not in the dataset)'],
      [`Two comparison stores (${DB.store_price_rows} price rows)`, 'Synthesized price/stock feeds: home price × a random factor with a category bias, never above MRP']],
    [3600, W - 3600]))

  // ---- 2 architecture
  c.push(H('2. Architecture and key algorithms', HeadingLevel.HEADING_1), H('2.1 Layers', HeadingLevel.HEADING_2),
    T([['Layer', 'Technology', 'What it does'],
      ['Web app', 'React 19 + TypeScript + Vite', 'Shop (chat, voice, cart, bill), Store admin (login), Evaluation and User study pages. Never computes money.'],
      ['API', `FastAPI + Uvicorn (${F.endpoints} endpoints)`, 'Tools, agent chat sessions, store comparison, staff login, admin, study. Also serves the web app.'],
      ['AI agent', 'LangGraph + Google Gemini 3.5 Flash-Lite', 'Understands the request (EN / HI / MR), decides which tools to call, explains the result.'],
      ['Tools', 'Python 3.10', 'locate, stock, substitutes, cart, bill, coupon optimizer, budget fit, GST, store comparison.'],
      ['Database', 'PostgreSQL 16 in Docker', `Single source of truth (${DB.tables} tables): catalogue, store map, inventory, coupons, carts, orders, other stores, staff, audit log, chat memory, study runs.`]],
    [1500, 2700, W - 4200]),
    H('2.2 The agent (LangGraph state graph)', HeadingLevel.HEADING_2),
    P('The LLM decides what to do. The graph enforces the things that must never depend on the LLM remembering them:'),
    ...['**agent**: Gemini reads the conversation and chooses tool calls (search, add to cart, compare stores …).',
      '**tools**: the 9 tools run against the database and return exact values.',
      '**auto_substitutes**: if an item is out of stock, ranked alternatives are always attached.',
      '**refresh_bill**: after every cart change the fresh bill (coupons, GST, budget status) is attached; if over budget, the fewest-swaps plan is attached too.',
      '**grounding_check**: every final reply is scanned; an invented ₹ amount or aisle sends it back for one rewrite, otherwise it is flagged.'].map((s) => bullet(s)),
    P('The cart id is injected from the graph state, so the AI cannot even choose which cart it edits. The conversation state is saved in PostgreSQL after every step (our own LangGraph checkpointer), so chats survive a restart. If Gemini is overloaded, a fallback model answers; if both fail, the shopper gets a polite message and the cart is safe.'),
    H('2.3 Coupon optimizer (main algorithm)', HeadingLevel.HEADING_2),
    P(`Each coupon has a scope (whole cart, category, sub-category or brand), a minimum spend on its eligible items, a percent or flat value, an optional cap and validity dates. Some pairs can never be used together. Choosing the best set is a **maximum-weight independent set** problem on the conflict graph (NP-hard in general). We solve it exactly with branch and bound. It matched brute force on 700 test cases and on ${O.carts} evaluation carts, with a median time of ${O.optimizer_ms_median} ms.`),
    P('Example: cart ₹708.90. SAVE10 gives ₹70.89 and BEV75 gives ₹75.00, but they conflict, so BEV75 is chosen; final ₹633.90. Greedy (biggest coupon first) is not enough: if A = ₹100 conflicts with B = ₹60 and C = ₹60, greedy gives ₹100 but the optimum is ₹120.'),
    H('2.4 Budget fit (second algorithm)', HeadingLevel.HEADING_2),
    P('When the cart is over budget, every item may keep its product or switch to a cheaper in-stock product of the same type. The planner finds the plan with the **fewest swaps** that fits the budget, and among those the one closest to what the shopper chose. Coupons are re-optimized for every plan, because a swap can win or lose a coupon. The search is exact (checked against brute force on 150 carts).'),
    P('Example: cart ₹451.90, budget ₹440 → 1 swap (Homogenized Milk → Amul Camel Milk) → ₹431.90, ₹8.10 left.'),
    H('2.5 GST on the bill', HeadingLevel.HEADING_2),
    P('Indian prices already include GST, so the bill shows the tax rather than adding it. A coupon lowers the taxable value, so each coupon is shared across its items; then for each line: taxable = net × 100 / (100 + rate), GST = net − taxable, split equally into CGST and SGST. Taxable value plus GST always equals the amount paid, to the paisa.'),
    H('2.6 Search and substitutes', HeadingLevel.HEADING_2),
    P('Product search uses PostgreSQL trigram similarity, so typos still work (“cofee” finds coffee). Substitutes are ranked: same product type first, then the closest price, then the most similar name and higher rating, and only items with enough stock are offered.'),
    H('2.7 Multi-store comparison', HeadingLevel.HEADING_2),
    P('Two more stores publish a price and stock feed: **SmartMart Ichalkaranji** (same chain, coupons valid) and **FreshBasket Sangli** (a competitor, SmartMart coupons not valid). The aisle map exists only for the home store, because navigation only makes sense where the shopper is standing. “Compare with other stores” re-prices the exact cart at every store: items a store cannot supply are listed as missing, the same coupon optimizer runs where coupons are valid, and the recommendation is the cheapest store that can supply the **whole** cart, so an incomplete store is never shown as a saving.'),
    H('2.8 Hindi, Marathi and voice input', HeadingLevel.HEADING_2),
    P('The shopper can type or speak in English, Hindi or Marathi. Voice uses the browser’s speech recognition (Chrome / Edge) with the chosen language. The agent always searches the catalogue with an English product phrase (दूध → milk, साखर → sugar) and answers in the shopper’s language. The grounding guard understands Devanagari digits (४५), “रुपये” and the Hindi/Marathi words for aisle, so Hindi and Marathi replies are checked exactly like English ones.'),
    H('2.9 Staff login, roles and audit log', HeadingLevel.HEADING_2),
    P('The admin page needs a login. A **manager** can change prices, stock and coupons; **staff** can only update stock (the server refuses a price change with HTTP 403). Passwords are stored as salted PBKDF2-SHA256 hashes and a signed token (HMAC-SHA256, 12 hours) proves the login. Every change is written to an audit log (who, what, old → new), shown as “Recent changes”. Demo accounts: manager / manager123 and staff / staff123 (change them with scripts/09_staff.py).'))

  // ---- 3 folders
  c.push(H('3. Project folder structure', HeadingLevel.HEADING_1),
    T([['Path', 'What it contains'],
      ['docker-compose.yml', 'The PostgreSQL 16 database container'],
      ['.env / .env.example', 'Settings: database login, Gemini API key, model names, admin token secret (.env is private)'],
      ['requirements.txt', 'Python packages (requirements-app.txt: only what the web app needs)'],
      ['db/schema.sql', `The ${DB.tables} database tables and the catalogue view`],
      ['data/raw, data/processed', `BigBasket CSV and the cleaned ${DB.products}-product catalogue (not in Git; regenerated by scripts)`],
      ['data/seed/*.csv', 'Hand-authored coupons, coupon conflicts and GST rules'],
      ['scripts/00 … 09', 'Setup, dataset, cleaning, seeding, verification, tool demo, terminal chat, evaluation, study report, staff accounts'],
      ['smartcart/tools/', 'The grounded tools: catalogue, cart, bill, coupon optimizer, budget fit, GST, store comparison'],
      ['smartcart/agent/', 'The LangGraph agent: graph, LLM tools, prompts, grounding guard, product cards, PostgreSQL memory'],
      ['smartcart/admin.py, auth.py', 'Store-staff operations (not available to the AI), login, roles, audit log'],
      ['smartcart/eval/, study.py', 'Evaluation harness (scripted goals, metrics, report) and user-study mode'],
      ['smartcart/api/main.py', `The FastAPI server (${F.endpoints} endpoints), also serves the web app`],
      ['frontend/', 'The React web app (Shop, Store admin, Evaluation, User study)'],
      ['tests/', `${F.tests_offline} automated tests (+${F.tests_live} live Gemini tests)`],
      ['docs/', 'Presentations, these documents, evaluation results, screenshots'],
      ['CLAUDE.md', 'Detailed technical notes for every milestone and the full command list']],
    [2900, W - 2900]))

  // ---- 4 prerequisites + 5 setup
  c.push(H('4. Prerequisites', HeadingLevel.HEADING_1),
    T([['Software', 'Version', 'Why'], ['Windows 10 / 11', '–', 'All commands are for PowerShell'],
      ['Docker Desktop', 'any recent', 'Runs the PostgreSQL database'], ['Python', '3.10', 'Backend, tools, agent, tests'],
      ['Node.js', '20 or newer (we use 24)', 'Builds the web app'], ['Chrome or Edge', 'recent', 'Voice input (Web Speech API)'],
      ['Google Gemini API key', 'free tier is enough', 'The AI agent (aistudio.google.com/apikey)'],
      ['Kaggle API key (kaggle.json)', 'only on a fresh machine', 'Downloads the BigBasket dataset']],
    [2900, 2300, W - 5200]),
    H('5. First-time setup (once per computer)', HeadingLevel.HEADING_1),
    P('Open PowerShell in the project folder (D:\\SmartCartAgent). In VS Code: Terminal → New Terminal.'),
    H('Step 1: Create the settings file', HeadingLevel.HEADING_3),
    P('Copy .env.example to .env and put your Gemini key after GOOGLE_API_KEY= (never share this file):'),
    ...code(['copy .env.example .env', '# inside .env:', 'GOOGLE_API_KEY=your-key-here', 'GEMINI_MODEL=gemini-3.5-flash-lite',
      'GEMINI_FALLBACK_MODEL=gemini-3.1-flash-lite-preview', 'ADMIN_TOKEN_SECRET=any-long-random-text']),
    H('Step 2: Install the Python packages', HeadingLevel.HEADING_3), ...code(['python -m pip install -r requirements.txt']),
    H('Step 3: Build the web app', HeadingLevel.HEADING_3), ...code(['cd frontend', 'npm install', 'npm run build', 'cd ..']),
    H('Step 4: Get the dataset (skip if data/raw already has the CSV)', HeadingLevel.HEADING_3),
    P('Put kaggle.json in your Downloads folder, then:'),
    ...code(['python scripts/00_setup_kaggle_creds.py', 'python scripts/01_fetch_dataset.py']),
    H('Step 5: Start the database', HeadingLevel.HEADING_3), P('Open Docker Desktop and wait for “Engine running”, then:'),
    ...code(['docker compose up -d', 'docker compose ps          # must say "healthy"']),
    H('Step 6: Build the store data', HeadingLevel.HEADING_3),
    ...code(['python scripts/02_clean_catalog.py', 'python scripts/03_seed_database.py', 'python scripts/04_verify_seed.py   # must end with "ALL CHECKS PASSED"']),
    H('Step 7: Check everything works', HeadingLevel.HEADING_3), ...code([`python -m pytest -q             # expect: ${F.tests_offline} passed`]))

  // ---- 6 running
  c.push(H('6. Running the project (every time)', HeadingLevel.HEADING_1),
    H('Step 1: Start Docker Desktop, then the database', HeadingLevel.HEADING_3), ...code(['docker compose up -d']),
    H('Step 2: Start the server', HeadingLevel.HEADING_3), ...code(['python -m uvicorn smartcart.api.main:app']),
    H('Step 3: Open the app in a browser', HeadingLevel.HEADING_3),
    T([['Page', 'Address'], ['Shop (chat, voice, cart, bill)', 'http://127.0.0.1:8000/'],
      ['Store admin (log in: manager / manager123 or staff / staff123)', 'http://127.0.0.1:8000/#/admin'],
      ['Evaluation results', 'http://127.0.0.1:8000/#/eval'], ['User study', 'http://127.0.0.1:8000/#/study'],
      ['API documentation (try every endpoint)', 'http://127.0.0.1:8000/docs']], [5200, W - 5200]),
    H('Step 4: Stop', HeadingLevel.HEADING_3),
    P('Press Ctrl + C in the terminal to stop the server. Optionally run `docker compose down` to stop the database (data is kept).'),
    P('**Reset the data after a demo.** Checkout and admin edits really change stock and prices. To restore the original store, run `python scripts/03_seed_database.py`. Chat memory is cleared too; user-study results are kept.'),
    H('Other ways to run', HeadingLevel.HEADING_3),
    T([['Command', 'What it shows'], ['python scripts/05_demo_tools.py', 'A scripted shopping trip through all tools, without the AI'],
      ['python scripts/06_chat.py --trace', 'Chat with the agent in the terminal, printing every tool call'],
      ['python scripts/07_evaluate.py', `The evaluation: ${N_GOALS} scripted goals with live Gemini (about 10 minutes)`],
      ['python scripts/08_study_report.py', 'User-study results (assistant vs manual) and a CSV export'],
      ['python scripts/09_staff.py list', 'Staff accounts; also add, password, disable']], [3800, W - 3800]))

  // ---- 7 testing
  const files = Object.entries(F.tests_per_file).sort((a, b) => b[1] - a[1])
  const WHAT = { 'test_offers.py': 'Coupon rules; optimizer equals brute force on 500 random problems + 200 real carts',
    'test_catalog.py': 'Search finds the right products; every out-of-stock item has an in-stock substitute',
    'test_cart.py': 'Stock limits; bill equals database prices; checkout is all-or-nothing',
    'test_tax.py': 'GST split and invariants (taxable + GST = amount paid)',
    'test_budget.py': 'Budget fit equals brute force on 150 random carts; coupons re-optimized per plan',
    'test_admin.py': 'Price/stock edits show in carts; login required; staff cannot reprice; audit log',
    'test_api.py': 'All HTTP endpoints, sessions, budget, swaps, errors',
    'test_agent.py': 'Graph: substitutes, budget plan, grounding guard (also Hindi/Marathi), fallback, memory survives restart',
    'test_eval.py': 'Evaluation harness: scoring, baselines, a full scripted run, results endpoint',
    'test_stores.py': 'Store comparison equals database prices; incomplete store never recommended; tokens',
    'test_study.py': 'User-study runs are timed and scored by code' }
  c.push(H('7. Testing', HeadingLevel.HEADING_1), H('7.1 Automated tests (no API key, no cost)', HeadingLevel.HEADING_2),
    ...code([`python -m pytest -q        # expect: ${F.tests_offline} passed in about 10 seconds`]),
    P('The tests use a scripted fake AI, so they are free and give the same result every time. They restore any data they change.'),
    T([['Test file', 'Tests', 'What it proves'], ...files.map(([f, n]) => [f, String(n), WHAT[f] ?? ''])], [2000, 900, W - 2900],
      { align: [AlignmentType.LEFT, AlignmentType.CENTER, AlignmentType.LEFT] }),
    H('7.2 Live tests with real Gemini (optional)', HeadingLevel.HEADING_2),
    ...code([`python -m pytest -m live -v     # ${F.tests_live} tests, about 15 seconds`]),
    P('These use about 10 of the 15 free Gemini requests per minute, so wait one minute before chatting afterwards.'),
    H('7.3 Evaluation harness', HeadingLevel.HEADING_2),
    P(`\`python scripts/07_evaluate.py\` plays ${N_GOALS} scripted shopping goals through the real agent and scores them by code (latest run, ${F.eval.generated}):`),
    T(EVAL_ROWS(), [2000, 2700, W - 4700]),
    H('7.4 Manual test checklist (web app)', HeadingLevel.HEADING_2),
    P('Start the server and open http://127.0.0.1:8000/. Expected values are for freshly seeded data.'),
    T([['#', 'Do this', 'You should see'],
      ['1', 'Type: “I need 3 Instant Tea Premix Turmeric Ginger, 2 Homogenized Milk and Britannia Brown Bread. My budget is ₹440”', 'Bread out of stock and replaced; substitute cards; BEV75; “Over by ₹11.90”; the agent offers a swap; “Grounded in database”'],
      ['2', 'Click “N tool calls” under the reply', 'The list of tools the agent used'],
      ['3', 'Click “Fit my budget”, then “Apply swaps”', '1 swap (Homogenized Milk → Camel Milk); ₹431.90; “₹8.10 left”'],
      ['4', 'Click “Compare with other stores”', 'Three stores with totals and missing items; the cheapest complete store is highlighted'],
      ['5', 'Click the “GST included” row', 'CGST/SGST table by slab'],
      ['6', 'New chat → choose हिंदी → click a Hindi example (or press the microphone and speak)', 'Hindi reply with aisle/shelf; grounding badge still shown'],
      ['7', 'Store admin: log in as staff / staff123', 'Price boxes and coupon switches are disabled; stock can be saved'],
      ['8', 'Log out, log in as manager / manager123, change the tea price', 'Shopper tab updates within 4 s; “Recent changes” shows manager: price old → new'],
      ['9', 'In admin, try a price above the MRP', 'Rejected with “above the MRP”'],
      ['10', 'Click Checkout', 'Receipt with GST table; the order appears in admin'],
      ['11', 'Restart uvicorn, reload the Shop tab, send another message', 'The agent still remembers the conversation'],
      ['12', 'Run python scripts/03_seed_database.py', 'Data restored for the next test']],
    [500, 4100, W - 4600]))

  // ---- 8 demo
  c.push(H('8. Demo script for the POE (about 10 minutes)', HeadingLevel.HEADING_1),
    P('Before the examiners arrive: start Docker, run `docker compose up -d`, run `python scripts/03_seed_database.py`, start uvicorn, and open tabs: Shop, Store admin (logged in as manager), Evaluation. Do not run the live tests or the evaluation just before (they use the Gemini quota).'),
    T([['Time', 'Show', 'Say'],
      ['1 min', 'Slides: problem and the one rule', '“The AI never creates a number; every price, stock count, aisle, discount and tax comes from the database.”'],
      ['2 min', 'Shop: the ₹440 request', 'Substitution, cards, coupon, “Grounded in database” badge; open the tool trace.'],
      ['1 min', 'Fit my budget → Apply swaps; Compare with other stores', '“Two exact optimizers; the comparison only recommends a store that has everything.”'],
      ['1 min', 'New chat in Hindi or Marathi (voice)', '“The reply is in Hindi, yet every rupee amount is still checked against the database.”'],
      ['1 min', 'Admin: staff cannot reprice; manager changes the tea price → Shop updates', '“Carts store no prices; the AI has no tool to change prices; every change is audited.”'],
      ['1 min', 'Checkout → receipt → admin Recent orders', '“Checkout is one database transaction; two shoppers can never buy the last unit.”'],
      ['2 min', 'Evaluation tab + slides', `“${N_GOALS} goals, ${pct(E.grounding_accuracy_pct)} grounding, ${pct(E.discount_captured_pct)} of the optimal discount; the first run found real bugs, we fixed them.”`],
      ['1 min', 'Terminal: python -m pytest -q', `“${F.tests_offline} tests; both optimizers are proven against brute force.”`]],
    [1000, 3300, W - 4300]),
    P('**Free-tier limit:** Gemini allows 15 requests per minute and one shopping message uses 2–5. Wait about 15 seconds between messages. If you see “AI request limit reached”, wait a minute; everything except the chat keeps working.'))

  // ---- 9 troubleshooting
  c.push(H('9. Troubleshooting', HeadingLevel.HEADING_1),
    T([['Problem', 'Fix'],
      ['“Server offline” in the app, or “Connection refused”', 'Docker is not running: start Docker Desktop, then docker compose up -d.'],
      ['Browser shows {"detail":"Not Found"} at http://127.0.0.1:8000/', 'The web app is not built: cd frontend; npm run build; cd .. then restart uvicorn.'],
      ['“GOOGLE_API_KEY missing” in the header', 'Add the key to .env and restart uvicorn.'],
      ['“AI request limit reached”', 'Free tier allows 15 requests/minute: wait one minute.'],
      ['Admin page asks to log in again', 'Login tokens end after 12 hours, or when the server restarts without ADMIN_TOKEN_SECRET in .env.'],
      ['Microphone button missing or not working', 'Use Chrome or Edge on http://127.0.0.1:8000 and allow the microphone when asked.'],
      ['Numbers in the demo differ from this guide', 'The data was changed by a checkout or admin edit: python scripts/03_seed_database.py.'],
      ['Changed something in frontend/ but the page did not change', 'Rebuild: cd frontend; npm run build; cd .. then press Ctrl+F5.'],
      ['Port 8000 already in use', 'Another uvicorn is running: close that terminal, or use --port 8001.']],
    [4200, W - 4200]))

  // ---- 10 commands
  c.push(H('10. Command reference', HeadingLevel.HEADING_1),
    ...code(['# start', 'docker compose up -d                      # database', 'python -m uvicorn smartcart.api.main:app            # web app + API on http://127.0.0.1:8000',
      '# data', 'python scripts/02_clean_catalog.py        # clean + sample the dataset', 'python scripts/03_seed_database.py        # (re)create the store data',
      'python scripts/04_verify_seed.py          # 10 integrity checks', '# tests and evaluation', `python -m pytest -q                       # ${F.tests_offline} offline tests`,
      `python -m pytest -m live -v               # ${F.tests_live} live Gemini tests`, `python scripts/07_evaluate.py             # ${N_GOALS}-goal evaluation (live)`,
      'python scripts/08_study_report.py         # user-study results', '# demos without the browser', 'python scripts/05_demo_tools.py           # tools only, no AI',
      'python scripts/06_chat.py --trace         # agent in the terminal', '# staff accounts', 'python scripts/09_staff.py list | add | password | disable',
      '# documents and slides', 'python docs/collect_facts.py; cd docs; node build_documents.js; cd ..', 'python docs/build_final_deck.py',
      '# database shell and stopping', 'docker exec -it smartcart_db psql -U smartcart -d smartcart', 'docker compose down                       # stop the database (data kept)']))

  // ---- 11 Q&A
  const QA = [
    ['Why not let the AI calculate the bill?', 'Language models can produce wrong numbers that look right. In a billing system that is unacceptable, so every number comes from the database through tools, and a grounding guard checks each reply.'],
    ['How do you know the AI never shows an invented number?', `The grounding guard compares every ₹ amount and aisle in a reply with the numbers the tools returned. In the evaluation, ${E.values_audited} values in ${E.turns} replies were checked and ${pct(E.grounding_accuracy_pct)} of replies were fully grounded.`],
    ['Why is choosing coupons hard? Why not the biggest coupon?', 'Conflicting coupons make it a maximum-weight independent set problem (NP-hard in general). Greedy can lose: A = ₹100 conflicts with B = ₹60 and C = ₹60; greedy gives ₹100, the optimum is ₹120. Our exact search matched brute force on every case.'],
    ['How did you evaluate the system?', `${N_GOALS} scripted shopping goals (typos, out of stock, budgets, coupons, Hindi, Marathi, store comparison …) run live through the agent and scored by code against the database: ${E.goals_succeeded}/${N_GOALS} succeeded, discount ${pct(E.discount_captured_pct)} of the optimum. The first run scored ${B.goals_succeeded}/12 and exposed real mistakes, which we fixed.`],
    ['Why not RAGAS or DeepEval?', 'RAGAS evaluates retrieval-augmented generation; our agent retrieves no documents. DeepEval’s agent metrics mostly use another LLM as judge, which gives an opinion. Our key claims (no invented number, optimal discount) can be checked exactly against the database and brute force.'],
    ['Does Hindi / Marathi weaken the grounding?', 'No. The guard understands Devanagari digits, “रुपये” and the Hindi/Marathi words for aisle, and the agent is told to write amounts as ₹ + the exact digits. Tests cover Hindi and Marathi replies.'],
    ['Why is multi-store only a price comparison?', 'Navigation needs a store map and only the home store has one: the shopper is standing there. Other stores publish prices and stock, which is what a comparison needs. The cheapest complete store is recommended, so missing items never look like savings.'],
    ['How is the admin page protected?', 'Login with salted PBKDF2 password hashes and a signed, expiring token. Staff can only change stock; managers can change prices and coupons. The server enforces the roles (HTTP 403) and logs every change.'],
    ['What happens if the server restarts during a chat?', 'Nothing is lost: the cart is in PostgreSQL and so is the conversation state (our LangGraph checkpointer), so the chat continues. A test simulates exactly this.'],
    ['What if two shoppers buy the last item at the same time?', 'Checkout locks the stock rows, recomputes the bill inside the same transaction and checks stock. Only one checkout can succeed.'],
    ['Can the AI change prices?', 'No. Admin functions are not agent tools. Only logged-in staff can change data, and the AI can only read it.'],
    ['Is the time saving proven?', 'The user-study mode is built (assistant vs manual, timed and scored by code). The numbers come only from real participants; see section 12.'],
  ]
  c.push(H('11. Likely review questions and answers', HeadingLevel.HEADING_1),
    ...QA.flatMap(([q, a]) => [P(`**Q. ${q}**`, { after: 40, keepNext: true }), P(`A. ${a}`)]))

  // ---- 12 study
  c.push(H('12. Running the user study', HeadingLevel.HEADING_1),
    P('Objective 6 of the synopsis asks for time saved. The study page (http://127.0.0.1:8000/#/study) runs a within-subjects comparison:'),
    ...['Recruit 6–10 participants (classmates are fine). Give each a code (P01, P02 …); no names are stored.',
      'Two task lists of equal size: **A** (breakfast list, includes an out-of-stock bread) and **B** (weekly basics under ₹600).',
      'Each participant does one task **with the assistant** and the other **manually** (search box + Add buttons). Alternate the order: P01 assistant-first, P02 manual-first, and so on, and alternate which task goes with which method.',
      'Press Start, let the participant work without help, press Finish when they say they are done. The server records the time and scores the cart automatically (right items, quantities, budget).',
      'Afterwards run `python scripts/08_study_report.py`: mean/median time per method, success rate, and the average time saved by participants who did both.',
      'Rehearsal runs: use codes starting with TEST and delete them with `python scripts/08_study_report.py --delete-prefix TEST`.'].map((s) => k.numbered(s, 'study')),
    P('Report only what was measured: participants, number of runs, mean and median times, success rates. Mention the small sample size as a limitation.'))

  // ---- 13 limitations
  c.push(H('13. Known limitations and next steps', HeadingLevel.HEADING_1),
    ...['GST rates are simplified by category (no HSN codes in the dataset).',
      'The free Gemini tier allows 15 requests per minute and its speed varies by day; a billed key removes the limit.',
      'Only about 5% of product names include a pack size, so sizes like “2 litres” are interpreted by the AI.',
      'Comparison stores are synthetic price feeds; with real partner feeds the same code would work unchanged.',
      'Voice input depends on the browser (Chrome / Edge).',
      'The grounding guard checks ₹ amounts and aisle numbers, not product names.',
      'Cloud deployment is prepared (Dockerfile) but not yet done; planned for Phase II together with the user study and the paper.'].map((s) => bullet(s)))

  return new Document({
    creator: 'Group D8', title: 'SmartCart Project Guide', description: 'Project guide',
    styles: headingStyles('Arial', { body: 21, title: 44, h1: 32, h2: 26, h3: 22 }),
    numbering: numbering(['study']),
    sections: [{ properties: { page: A4 }, footers: { default: footer(k, 'SmartCart Project Guide · Group D8') }, children: c }],
  })
}

// ===================================================================== 2. PROJECT REPORT
function buildReport() {
  figNo = 0; tabNo = 0
  const k = makeKit('Times New Roman', 24)
  const { P, H, bullet, code } = k
  const T = (rows, widths, o) => table(k, rows, widths, { size: 20, ...o })
  const W = TEXT_W
  const center = (s, o = {}) => P(s, { align: AlignmentType.CENTER, ...o })
  const brk = () => new Paragraph({ children: [new PageBreak()] })
  const c = []

  // ---- title page
  c.push(center('A PROJECT REPORT ON', { bold: true, before: 600 }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 300 },
      children: [k.run('CONVERSATIONAL SMART-CART & BILLING ASSISTANT AGENT', { size: 36, bold: true, color: NAVY })] }),
    center('An Agentic AI System for Intelligent Product Location, Offer Optimization, Substitution and Automated Billing', { italics: true, after: 400 }),
    center('Submitted in partial fulfilment of the requirements for the degree of', { after: 40 }),
    center('BACHELOR OF TECHNOLOGY', { bold: true, after: 40 }),
    center('in Computer Science & Engineering (Artificial Intelligence & Machine Learning / Data Science)', { after: 400 }),
    center('Submitted by (Group D8)', { bold: true }),
    T([['Name', 'PRN'], ...TEAM], [4000, 2600], { align: [AlignmentType.LEFT, AlignmentType.CENTER] }),
    center('Under the guidance of', { before: 400, after: 40 }), center('Prof. Vrishali Prabhu', { bold: true, after: 40 }),
    center('Assistant Professor', { after: 600 }),
    center('Department of Computer Science & Engineering (AIML)', { bold: true, after: 40 }),
    center('Kolhapur Institute of Technology’s College of Engineering (Empowered Autonomous), Kolhapur', { after: 40 }),
    center('R. S. No. 199B/1-3, Gokul Shirgaon, Kolhapur – 416 234', { after: 40 }), center('Academic Year 2026–27', { bold: true }), brk())

  // ---- certificate
  c.push(center('CERTIFICATE', { bold: true, size: 32, before: 400, after: 400 }),
    P('This is to certify that the project report entitled **“Conversational Smart-Cart & Billing Assistant Agent”** is a bonafide record of the work carried out by Mayur Khamamkar (2324000146), Prathmesh Mhopare (2324001087), Aniket Mane (2324000104) and Harshvardhan Magdum (2324000418) in partial fulfilment of the requirements for the degree of Bachelor of Technology in Computer Science & Engineering (AIML) of Kolhapur Institute of Technology’s College of Engineering (Empowered Autonomous), Kolhapur, during the academic year 2026–27.', { line: 360 }),
    P('', { before: 1200 }),
    T([['______________________', '______________________'], ['Prof. Vrishali Prabhu', 'Head of Department'],
      ['Project Guide', 'CSE (AIML)']], [W / 2, W / 2],
    { align: [AlignmentType.CENTER, AlignmentType.CENTER], plain: true, size: 24 }),
    P('', { before: 600 }), P('External Examiner: ______________________          Date: ____________', { align: AlignmentType.LEFT }), brk())

  // ---- acknowledgement + abstract
  c.push(center('ACKNOWLEDGEMENT', { bold: true, size: 32, before: 200, after: 300 }),
    P('We express our sincere gratitude to our guide, Prof. Vrishali Prabhu, for her continuous guidance, encouragement and valuable suggestions throughout this project. We thank the Head of the Department and all faculty members of the Department of Computer Science & Engineering (AIML) for their support, and the review panel for their feedback at every review, which shaped the design and the evaluation of this work. We also thank our classmates who took part in testing the system.', { line: 360 }),
    P('Group D8', { align: AlignmentType.RIGHT, bold: true, before: 400 }), brk(),
    center('ABSTRACT', { bold: true, size: 32, before: 200, after: 300 }),
    P(`Supermarket shopping still requires customers to locate products, check availability, find applicable offers, handle out-of-stock items and verify the bill by themselves. Large language models (LLMs) can understand such requests, but they are known to produce plausible yet wrong numbers, which is unacceptable when real money is involved. This project presents a conversational smart-cart agent in which **the LLM only plans, understands and explains, while every transactional value (price, stock, aisle, discount, tax and total) is fetched from a PostgreSQL database through tool functions**. The agent is built as a LangGraph state graph on Google Gemini 3.5 Flash-Lite; the graph enforces automatic substitution for out-of-stock items, a fresh bill after every cart change, a budget-fit plan when over budget, and a grounding guard that rejects any rupee amount or aisle number that did not come from a tool. Coupon selection is modelled as a maximum-weight independent set on a coupon-conflict graph and solved exactly by branch and bound; a second exact optimizer finds the fewest swaps that bring a cart within budget, re-optimizing coupons for every plan. The system uses ${DB.products} real BigBasket products with a synthesized store map, inventory and ${DB.coupons} coupon rules, and offers a React web application with a shelf-level pick route, GST-inclusive invoices, a multi-store price comparison, Hindi and Marathi chat with voice input, and a role-based store-admin console with an audit log. An evaluation harness of ${N_GOALS} scripted shopping goals, run live and scored by code, achieved ${E.goals_succeeded}/${N_GOALS} task success, ${pct(E.grounding_accuracy_pct)} grounding accuracy over ${E.values_audited} audited values and ${pct(E.discount_captured_pct)} of the brute-force optimal discount; on ${O.carts} random carts the optimizer was always optimal, whereas applying the single best coupon captured only ${O.single_coupon_captured_pct}% of the achievable discount. The system is supported by ${F.tests_offline + F.tests_live} automated tests.`, { line: 360 }),
    P('**Keywords:** agentic AI, large language models, tool grounding, LangGraph, conversational commerce, coupon optimization, maximum-weight independent set, smart retail.', { line: 360 }), brk())

  // ---- contents
  c.push(center('TABLE OF CONTENTS', { bold: true, size: 32, after: 200 }),
    new TableOfContents('Table of Contents', { hyperlink: true, headingStyleRange: '1-2' }), brk())

  // ---- chapter 1
  c.push(H('Chapter 1: Introduction', HeadingLevel.HEADING_1), H('1.1 Background', HeadingLevel.HEADING_2),
    P('Supermarket shopping consists of many small, repetitive decisions: where a product is, whether it is in stock, which coupons apply and can be combined, what to buy instead when an item is unavailable, and whether the bill is within budget. Conventional shopping applications offer only search and a cart and leave these decisions to the customer. Recent advances in large language models, tool calling and agentic AI make it possible for software to understand a goal stated in natural language and to act on it through external tools.'),
    H('1.2 Motivation', HeadingLevel.HEADING_2),
    P('An LLM that answers a shopper directly will sometimes state a wrong price, an outdated stock level or an incorrect total, because it generates text rather than reading facts. In a billing context such errors directly cost money and trust. The motivation of this project is to obtain the convenience of a conversational assistant **without** letting any transactional number originate from the model.'),
    H('1.3 Problem statement', HeadingLevel.HEADING_2),
    P('Traditional supermarket shopping requires customers to manually locate products, verify stock availability, identify applicable offers, handle out-of-stock items and calculate the final payable amount. Existing shopping assistants address these tasks independently and lack autonomous multi-step decision-making. There is therefore a need for a tool-grounded agentic AI system that can understand a shopper’s intent, interact with product and inventory data, optimize applicable offers, recommend suitable substitutions and maintain an accurate running bill.'),
    H('1.4 Objectives', HeadingLevel.HEADING_2),
    ...['Develop a conversational shopping assistant capable of understanding natural-language shopping requests.',
      'Implement tool-grounded product and inventory retrieval for accurate availability, price, aisle and shelf information.',
      'Develop an offer optimization module that evaluates applicable and compatible coupons to maximize customer savings.',
      'Develop a substitution module that identifies and ranks suitable alternatives when requested products are unavailable.',
      'Maintain a dynamic cart and billing system that recalculates subtotal, discounts, taxes (GST) and the final payable amount.',
      'Evaluate the system on time saved, discount captured, substitution acceptance and grounding accuracy.'].map((s) => k.numbered(s, 'obj')),
    H('1.5 Scope', HeadingLevel.HEADING_2),
    P('The system targets a single physical supermarket (the “home store”) in which aisle and shelf navigation is meaningful, with a price comparison against two other stores. The product catalogue is real (BigBasket); store layout, stock levels, coupons, GST rules and the comparison stores are synthesized because no public dataset contains them. The interface is a web application served from one server; deployment to the cloud is prepared but outside the evaluated scope.'),
    H('1.6 Organisation of the report', HeadingLevel.HEADING_2),
    P('Chapter 2 reviews related work and the research gaps. Chapter 3 lists the requirements. Chapter 4 presents the system design and Chapter 5 the algorithms. Chapter 6 describes the implementation, Chapter 7 the testing and evaluation, Chapter 8 the results, and Chapter 9 concludes with future scope.'))

  // ---- chapter 2
  c.push(H('Chapter 2: Literature Survey', HeadingLevel.HEADING_1), H('2.1 Related work', HeadingLevel.HEADING_2),
    P('Ten representative works on grounded language agents, tool use, LLM-based recommendation and offer optimization were reviewed. Table 1 summarises their approach and limitations with respect to supermarket shopping.'),
    tableCaption(k, 'Summary of reviewed literature'),
    T([['Work', 'Year', 'Key idea', 'Limitation for our problem'], ...LIT], [1800, 650, 3400, W - 5850], { size: 18 }),
    H('2.2 Comparison matrix', HeadingLevel.HEADING_2),
    P('Table 2 compares the works on the seven capabilities our system integrates (✓ addressed, ◐ partially, ✗ not addressed, based on each paper’s reported scope). No prior work covers more than three; the proposed system covers all seven, which is the novelty claim of this project.'),
    tableCaption(k, 'Capability comparison'),
    T(MATRIX, [2000, ...Array(7).fill(Math.floor((W - 2000) / 7))], { size: 18, align: [AlignmentType.LEFT, ...Array(7).fill(AlignmentType.CENTER)], highlight: [11] }),
    H('2.3 Research gaps', HeadingLevel.HEADING_2),
    ...['**Fragmented assistance**: existing systems target individual tasks such as search or recommendation rather than an end-to-end shopping workflow.',
      '**Limited autonomy**: e-commerce assistants mainly respond to queries instead of planning and executing multiple tool-based actions.',
      '**Offer optimization**: promotions are recommended, but the combination problem of overlapping and mutually incompatible coupons is rarely solved.',
      '**Stock-out handling**: substitution is suggested in isolation and seldom integrated with real-time inventory and live cart state.',
      '**Grounding of transactional data**: LLM assistants can hallucinate price, stock and bill values unless every such field is fetched from authoritative backend tools.'].map((s) => bullet(s)))

  // ---- chapter 3
  c.push(H('Chapter 3: System Requirements', HeadingLevel.HEADING_1), H('3.1 Functional requirements', HeadingLevel.HEADING_2),
    ...['FR1: Accept shopping requests in natural language (English, Hindi, Marathi), typed or spoken.',
      'FR2: Locate products with aisle, shelf and shelf level; tolerate spelling mistakes.',
      'FR3: Report live price and stock; refuse quantities above stock.',
      'FR4: Rank in-stock substitutes of the same type for unavailable products and let the shopper confirm them.',
      'FR5: Choose the best valid, non-conflicting coupon combination automatically.',
      'FR6: Maintain a running bill with MRP savings, coupons and GST; propose budget-fitting swaps.',
      'FR7: Compare the cart’s cost across stores.',
      'FR8: Check out atomically and store an immutable order record.',
      'FR9: Let authenticated store staff change prices, stock and coupons according to their role, with an audit log.',
      'FR10: Measure task success, grounding, discount optimality, substitution and latency, and support a user study.'].map((s) => bullet(s)),
    H('3.2 Non-functional requirements', HeadingLevel.HEADING_2),
    ...['**Correctness**: no price, stock, aisle, discount, tax or total may originate from the LLM.',
      '**Consistency**: concurrent checkouts can never oversell; money is exact to the paisa (decimal, never floating point).',
      '**Reliability**: model fallback and graceful degradation when the LLM service is unavailable; conversations survive restarts.',
      '**Performance**: optimizers respond in milliseconds; a conversational turn in seconds.',
      '**Security**: hashed passwords, signed expiring tokens, role-based authorization for staff operations.',
      '**Testability**: automated tests without network or API key, repeatable synthetic data (fixed seed).'].map((s) => bullet(s)),
    H('3.3 Hardware and software', HeadingLevel.HEADING_2),
    T([['Component', 'Specification'], ['Processor / memory', 'Any 64-bit x86 PC, 8 GB RAM'], ['Operating system', 'Windows 10/11 (Linux for deployment)'],
      ['Database', 'PostgreSQL 16 (Docker), pg_trgm extension'], ['Backend', 'Python 3.10, FastAPI, SQLAlchemy, LangGraph, LangChain'],
      ['LLM', 'Google Gemini 3.5 Flash-Lite (fallback Gemini 3.1 Flash-Lite Preview)'], ['Frontend', 'React 19, TypeScript, Vite; Chrome/Edge for voice'],
      ['Testing', 'pytest, scripted fake LLM, Puppeteer']], [3000, W - 3000]))

  // ---- chapter 4
  c.push(H('Chapter 4: System Design', HeadingLevel.HEADING_1), H('4.1 Architecture', HeadingLevel.HEADING_2),
    P('The system has five layers (Table 3). The decisive design choice is the separation of responsibilities: the LLM agent decides **what** to do; deterministic tools decide **every number**. The API adds no business logic: each endpoint calls one tool, so the agent and the web interface see exactly the same values.'),
    tableCaption(k, 'System layers'),
    T([['Layer', 'Technology', 'Responsibility'],
      ['Interface', 'React web app, terminal chat, REST API', 'Chat (typed/voice), cart, bill, admin console, evaluation and study pages'],
      ['API', `FastAPI, ${F.endpoints} endpoints`, 'Exposes tools, agent sessions, comparison, staff login, admin, study'],
      ['Agent', 'LangGraph + Gemini', 'Intent understanding, planning, tool calling, explanation; enforced safety nodes'],
      ['Tools', 'Python', 'Search, stock, substitutes, cart, bill, coupon optimizer, budget fit, GST, store comparison'],
      ['Data', 'PostgreSQL 16', 'Single authoritative source of all transactional values']], [1500, 2600, W - 4100]),
    H('4.2 Database design', HeadingLevel.HEADING_2),
    P(`The database has ${DB.tables} tables (Table 4). Two design decisions matter most. First, catalogue data (products, MRP) is separated from live data (inventory: price and stock), so price updates touch one table. Second, **cart items store no price**: the bill is recomputed from inventory on every request, so it can never be stale and no number can come from the model. Orders are the only place prices are frozen, as an immutable snapshot at checkout, with the constraint final_total = subtotal − discount_total.`),
    tableCaption(k, 'Database tables'),
    T([['Table', 'Purpose'], ['products', `${DB.products} real products: name, brand, category, sub-category, type, MRP, GST rate, rating`],
      ['stores, store_map', `Home store + ${DB.stores - 1} comparison stores; aisle/shelf/level of every product in the home store (${DB.aisles} aisles, ${DB.shelves} shelves)`],
      ['inventory', `Live price and stock per product (${DB.out_of_stock} out of stock, ${DB.low_stock} low stock)`],
      ['store_prices', `Price/stock feeds of the comparison stores (${DB.store_price_rows} rows)`],
      ['coupons, coupon_conflicts', `${DB.coupons} rules (scope, type, value, cap, minimum, validity) and ${DB.conflicts} mutually exclusive pairs`],
      ['carts, cart_items', 'Shopping carts linked to chat sessions; quantities only, no prices'],
      ['orders', 'Immutable checkout snapshot with line items, coupons and GST (JSONB)'],
      ['staff_users, admin_audit', 'Staff accounts with roles and hashed passwords; log of every admin change'],
      ['agent_checkpoints, agent_checkpoint_writes', 'Persistent conversation state of the LangGraph agent'],
      ['study_runs', 'Timed, scored runs of the user study (kept across re-seeding)']], [3300, W - 3300]),
    H('4.3 Agent state graph', HeadingLevel.HEADING_2),
    P('The agent is a LangGraph state machine with five nodes. The state holds the messages, session id, cart id, budget and grounding status.'),
    ...code(['START → agent ──tool calls──► tools ──► [stock failure?] ─► auto_substitutes ─┐',
      '          ▲   │                  │      [cart changed?]  ─► refresh_bill ◄────┘',
      '          │   │                  └──── otherwise ─► agent',
      '          │   └──final answer──► grounding_check ──ungrounded (1st time)──► agent',
      '          │                                     └──ok / already retried──► END',
      '          └──────────── auto_substitutes / refresh_bill ────────────┘'], 15),
    ...['**agent** calls Gemini with nine tools: search_products, check_stock, find_substitutes, update_cart, view_bill, set_budget, fit_budget, compare_stores and checkout.',
      '**auto_substitutes** always attaches ranked substitutes to a tool result that reports insufficient stock.',
      '**refresh_bill** always attaches the recomputed bill after a successful cart change, including budget status computed by code and, when over budget, the budget-fit plan.',
      '**grounding_check** scans the final reply; unknown values send the reply back for one rewrite, after which remaining ones are reported to the user.'].map((s) => bullet(s)),
    P('The cart id and session id are injected from the graph state into the tools, so the model cannot select, invent or mistype a cart. Attachments are merged into the triggering tool result, keeping the conversation a valid call/response sequence for the LLM provider.'),
    H('4.4 Work-flow', HeadingLevel.HEADING_2),
    P('A request is understood and split into items; each item is searched, stock-checked and added; a stock-out leads to ranked alternatives which the shopper confirms; every cart change re-optimizes coupons and refreshes the bill; the loop continues until the shopper checks out, when one database transaction produces the order and the receipt.'))

  // ---- chapter 5
  c.push(H('Chapter 5: Methodology and Algorithms', HeadingLevel.HEADING_1), H('5.1 Data preparation', HeadingLevel.HEADING_2),
    P(`The BigBasket dataset (27,555 rows) was cleaned (whitespace, missing values, MRP ≥ selling price, duplicates) and sampled to ${DB.products} products in ${DB.categories} everyday categories, grouped by product type so that every product has same-type alternatives (${DB.product_types} product types). One aisle per category and one shelf per sub-category form the store map. Stock levels are synthetic with a fixed seed: ${DB.out_of_stock} products are out of stock, chosen at most one per type so that a substitute always exists, and ${DB.low_stock} are low. GST rates (0/5/18/40%) are assigned by hand-authored rules; slab sizes: ${Object.entries(DB.gst_slabs).map(([r, n]) => `${r}% × ${n}`).join(', ')}.`),
    H('5.2 Fuzzy product search and substitution ranking', HeadingLevel.HEADING_2),
    P('Search uses PostgreSQL trigram similarity on brand + name and on product type, so misspellings such as “cofee” or “buter” still match. Results are ranked by match score, then in-stock first, then lower price. Substitutes for a product are in-stock items with enough quantity, ranked by: same product type before same sub-category, closest relative price, most similar name, higher rating.'),
    H('5.3 Coupon optimization', HeadingLevel.HEADING_2),
    P('Let C be the set of coupons and E ⊆ C × C the set of conflicting pairs. For a cart, each coupon c is first evaluated independently: it is rejected with a reason if inactive, not yet valid, expired, without eligible items, or if its eligible subtotal s_c is below its minimum; otherwise its discount is fixed as'),
    P('d_c = min( s_c × p_c / 100, cap_c, s_c ) for percentage coupons,    d_c = min( v_c, s_c ) for flat coupons.', { align: AlignmentType.CENTER, italics: true }),
    P('Because discounts are independent (each is computed on the original subtotal of its eligible items), the problem is:'),
    P('maximise  min( Σ_{c∈S} d_c , subtotal )   subject to   S ⊆ C_valid,   no pair {a, b} ⊆ S with (a, b) ∈ E,', { align: AlignmentType.CENTER, italics: true }),
    P('which is a maximum-weight independent set on the conflict graph, NP-hard in general [16]. Since a store has tens of coupons, an exact **branch-and-bound** search is practical: coupons are sorted by discount; each is included (if it conflicts with none chosen) or excluded; a branch is pruned when the current value plus all remaining discounts cannot beat the best found. Ties are broken by fewer coupons, then alphabetically, making the result deterministic. Every coupon that is not applied is returned with an explanation (conflict, minimum not met with the shortfall, expired …), which the agent uses for hints such as “add ₹34 more to unlock AMUL5”.'),
    P('Greedy selection is not sufficient: with A = ₹100 conflicting with B = ₹60 and C = ₹60, greedy returns ₹100 while the optimum B + C is ₹120.'),
    H('5.4 Budget fit', HeadingLevel.HEADING_2),
    P('If the payable total exceeds the shopper’s budget, each line may keep its product or switch to a cheaper in-stock product of the same type (up to three candidates per line: the closest cheaper ones and the cheapest). The objective is lexicographic: (1) total ≤ budget; (2) the fewest swaps; (3) the highest total that still fits (least downgrade); (4) a deterministic tie-break. Plans are enumerated in increasing number of swaps k, evaluating Σ C(n,k)·m^k plans, and **coupons are re-optimized for every plan** because a swap can lose or win a coupon. The planner is exact and matched brute force on 150 random carts.'),
    H('5.5 GST computation', HeadingLevel.HEADING_2),
    P('Indian shelf prices include GST, so the bill extracts rather than adds tax. Each applied coupon is first allocated to its eligible lines in proportion to their totals (rounding remainder to the largest line). For each line with net amount n and rate r: taxable = n × 100 / (100 + r), GST = n − taxable, CGST = GST / 2, SGST = remainder. Lines are grouped into rate slabs. The invariant Σ taxable + Σ GST = final total holds exactly and is tested.'),
    H('5.6 Grounding guard', HeadingLevel.HEADING_2),
    P('All numbers appearing in tool results (and in the shopper’s own messages, such as a budget) form the allowed set. Every rupee amount and aisle number in the reply is extracted with patterns that cover “₹”, “Rs.”, “INR”, Hindi/Marathi “रुपये” and Devanagari digits, and the words for aisle in all three languages. Any value outside the allowed set is ungrounded: the reply is returned to the model once with the exact offending values, and if it is still ungrounded it is shown with a warning badge listing them.'),
    H('5.7 Multi-store comparison', HeadingLevel.HEADING_2),
    P('The cart is re-priced at every store. A line counts only if the store carries the product and has enough stock; otherwise it is listed as missing with the reason. Where SmartMart coupons are valid, the same exact optimizer selects the best combination for the lines that store can supply. The recommended store is the cheapest one able to supply the whole cart; the saving versus the home store is computed only between complete carts.'),
    H('5.8 Reliability and persistence', HeadingLevel.HEADING_2),
    P('LLM calls go to the main model first; on failure the fallback model is used; short rate-limit errors (HTTP 429 with a retry delay ≤ 15 s) are retried after the delay; if both models fail the shopper receives a polite message and the cart is unaffected. The LangGraph state is persisted after every step by a PostgreSQL checkpointer implemented for this project, so conversations survive server restarts.'))

  // ---- chapter 6
  c.push(H('Chapter 6: Implementation', HeadingLevel.HEADING_1), H('6.1 Modules', HeadingLevel.HEADING_2),
    tableCaption(k, 'Main source modules'),
    T([['Module', 'Responsibility'], ['smartcart/tools/catalog.py', 'locate(), check_inventory(), find_substitutes()'],
      ['smartcart/tools/cart.py', 'create_cart(), update_cart(), compute_bill(), checkout() (one transaction, row locks)'],
      ['smartcart/tools/offers.py', 'Coupon evaluation and exact branch-and-bound selection'], ['smartcart/tools/budget.py', 'Budget-fit planner'],
      ['smartcart/tools/tax.py', 'Discount allocation and GST'], ['smartcart/tools/stores.py', 'Multi-store comparison'],
      ['smartcart/agent/graph.py', 'LangGraph state graph, model fallback, enforced nodes'], ['smartcart/agent/grounding.py', 'Grounding guard (EN/HI/MR)'],
      ['smartcart/agent/memory.py', 'PostgreSQL checkpointer (persistent memory)'], ['smartcart/auth.py, admin.py', 'Staff login, roles, audit log, store operations'],
      ['smartcart/eval/', 'Evaluation harness: goals, metrics, runner, report'], ['smartcart/study.py', 'User-study runs, timing and scoring'],
      ['smartcart/api/main.py', `FastAPI application (${F.endpoints} endpoints)`], ['frontend/src/', 'React application: Shop, Store admin, Evaluation, User study']],
    [3400, W - 3400]),
    H('6.2 Transactions and money', HeadingLevel.HEADING_2),
    P('Money is handled as Python Decimal rounded half-up to the paisa and transmitted as JSON strings, never as floating point. Checkout locks the cart, then the inventory rows in product-id order (avoiding deadlocks), recomputes the bill inside the same transaction, verifies stock, decrements it, writes the order snapshot and closes the cart; if any item is short, nothing is written.'),
    H('6.3 User interface', HeadingLevel.HEADING_2),
    P('The web application never computes money: every amount displayed is the exact string returned by the server. Each assistant reply shows a “Grounded in database” badge and an expandable trace of the tool calls. Product cards for substitutes and search results are built from tool results, not parsed from the model’s text.'),
    ...figure(k, 'ui-shop-cards-budget.png', 'Shopper view: chat with grounding badge and tool trace, substitute cards, live cart with aisle route and budget plan'),
    ...(pngExists('ui-hindi-chat.png') ? figure(k, 'ui-hindi-chat.png', 'Hindi conversation: grounded reply with aisle and shelf') : []),
    ...(pngExists('ui-compare.png') ? figure(k, 'ui-compare.png', 'Multi-store comparison of the same cart') : []),
    ...(pngExists('ui-admin-audit.png') ? figure(k, 'ui-admin-audit.png', 'Store admin console (manager): live prices, stock, audit log and coupons') : figure(k, 'ui-admin.png', 'Store admin console')),
    ...(pngExists('ui-admin-staff.png') ? figure(k, 'ui-admin-staff.png', 'Staff role: price editing and coupon switches disabled, stock editable') : []),
    ...figure(k, 'ui-receipt.png', 'Checkout receipt with GST table', 420))

  // ---- chapter 7
  const files = Object.entries(F.tests_per_file).sort((a, b) => b[1] - a[1])
  c.push(H('Chapter 7: Testing and Evaluation', HeadingLevel.HEADING_1), H('7.1 Automated testing', HeadingLevel.HEADING_2),
    P(`${F.tests_offline} automated tests run without network access or API key, using a scripted fake LLM that returns predetermined tool calls, plus ${F.tests_live} live tests against Gemini. Tests that modify data restore it. Both optimizers are verified against brute force (coupons: 500 random problems and 200 real carts; budget fit: 150 carts); GST invariants are checked to the paisa; the checkout is shown to write nothing when stock drops between adding and paying.`),
    tableCaption(k, 'Automated tests by module'),
    T([['Test file', 'Tests'], ...files.map(([f, n]) => [f, String(n)])], [4000, 1500], { align: [AlignmentType.LEFT, AlignmentType.CENTER] }),
    H('7.2 Evaluation harness', HeadingLevel.HEADING_2),
    P(`Objective 6 is addressed by an evaluation harness that plays ${N_GOALS} scripted shopping goals through the same agent the web application uses, against the live Gemini model, and scores the outcome **by code**: the final cart is read back from PostgreSQL and compared with the expected product types and quantities; every rupee amount and aisle number in every reply is matched against the tool results; the applied discount is compared with a brute-force optimum over every conflict-free subset of the valid coupons; and every unavailable product must be replaced (or offered) by an in-stock product of the same type. The goals cover multi-item lists, typing errors, out-of-stock items, quantities above stock, budgets, stacked coupons, multi-turn edits, navigation questions, GST questions, Hindi, Marathi and store comparison. The run is paced for the free-tier rate limit and leaves the database unchanged.`),
    tableCaption(k, `Evaluation results (${F.eval.generated}, ${E.models_used.join(', ')})`), T(EVAL_ROWS(), [2000, 2600, W - 4600]),
    tableCaption(k, 'Results per goal'), T(GOAL_ROWS(), [3300, 3300, 900, 900, W - 8400], { size: 18,
      align: [AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.RIGHT] }),
    H('7.3 Iterative improvement', HeadingLevel.HEADING_2),
    P(`The first run (12 goals) achieved ${B.goals_succeeded}/12 and revealed three behavioural faults that unit tests could not show: (i) when a named product appeared out of stock in the search results, the model added a different type of product itself instead of using the substitution path; (ii) when stock was short, it silently added fewer units than requested; (iii) it named applied coupons without the amount saved. Each was fixed by an explicit rule in the system prompt, after which all goals succeeded. Grounding was 100% in every run, which supports the central design decision: even when the model’s behaviour was wrong, no number it showed was invented.`),
    H('7.4 Offline study of the coupon optimizer', HeadingLevel.HEADING_2),
    P(`Independently of the LLM, ${O.carts} random carts of 3 to 25 real products were priced with the real ${O.coupons} coupons and ${O.conflict_pairs} conflict pairs (Table ${tabNo + 1}).`),
    tableCaption(k, 'Optimizer versus baselines'), T(OFFLINE_ROWS(), [3200, 2000, 1800, W - 7000],
      { align: [AlignmentType.LEFT, AlignmentType.RIGHT, AlignmentType.RIGHT, AlignmentType.RIGHT] }),
    P(`The optimizer was optimal on every cart with a median time of ${O.optimizer_ms_median} ms. A single best coupon, as many checkouts allow, captures only ${O.single_coupon_captured_pct}% of the achievable discount. Greedy selection is close on this coupon set but not guaranteed (${O.greedy_suboptimal_carts} cart below optimum); exactness costs nothing in practice.`),
    H('7.5 User study design', HeadingLevel.HEADING_2),
    P('To measure time saved, the application includes a study mode with a within-subjects design: each participant completes one of two equivalent task lists with the assistant and the other manually with a conventional search-and-add interface, in counterbalanced order. The server measures the time from start to finish and scores the cart with the same code as the evaluation harness. ' +
      (DB.study_runs > 0 ? `${DB.study_runs} runs have been recorded so far.` : 'The study is scheduled with student participants in Phase II; no participant data is reported in this draft.')))

  // ---- chapter 8
  c.push(H('Chapter 8: Results and Discussion', HeadingLevel.HEADING_1),
    P(`The system meets its objectives. Natural-language requests in three languages are understood and executed through tools (objective 1). Every transactional value comes from the database, and in the evaluation ${pct(E.grounding_accuracy_pct)} of replies were fully grounded across ${E.values_audited} audited values (objective 2). Coupon selection is provably optimal and fast (objective 3). Unavailable products were replaced by same-type in-stock products in ${pct(E.substitution_correct_pct)} of cases, with the shopper able to choose from ranked cards (objective 4). The bill, including GST, is recomputed from live data on every change and stays exact to the paisa (objective 5). The evaluation harness measures objective 6; the time-saved component requires the user study.`),
    H('8.1 Observations', HeadingLevel.HEADING_2),
    ...['**Grounding is structural, not behavioural.** The model made behavioural mistakes in early runs, yet never displayed an invented number, because numbers can only reach it through tools and the guard checks every reply.',
      '**Enforcing steps in the graph is more reliable than prompting.** Substitution on stock-outs and bill refreshes are guaranteed by graph edges; only behaviour the graph cannot observe (such as a silently reduced quantity) needed prompt rules.',
      `**Latency is dominated by the LLM.** A turn makes about ${E.llm_calls_per_turn} model calls; the median turn took ${E.latency_median_s} s on the free tier, while tools and optimizers take milliseconds.`,
      '**Multilingual use does not weaken correctness**, because the tools are language-independent and the guard recognises Devanagari numerals and words.'].map((s) => bullet(s)),
    H('8.2 Limitations', HeadingLevel.HEADING_2),
    ...['Store layout, stock, coupons, GST rates and comparison-store prices are synthetic; GST rates are simplified (no HSN codes).',
      'Free-tier LLM latency and rate limits; latency varied between runs.',
      'Pack sizes appear in only about 5% of product names, so size requests are interpreted by the model.',
      'The grounding guard covers rupee amounts and aisle numbers, not product names.',
      'The evaluation uses scripted goals; the user study with real participants is pending.'].map((s) => bullet(s)))

  // ---- chapter 9
  c.push(H('Chapter 9: Conclusion and Future Scope', HeadingLevel.HEADING_1), H('9.1 Conclusion', HeadingLevel.HEADING_2),
    P('This project shows that an LLM-based shopping assistant can be made trustworthy near real money by architecture rather than by hope: the model plans and explains, deterministic tools over a single database produce every number, and a state graph enforces the steps that must never be forgotten. Integrating shelf-level location, live inventory, exact coupon optimization, ranked substitution, budget fitting, GST billing and store comparison over one shared cart, the system covers all seven capabilities that no surveyed work combines, and an automated evaluation confirms its grounding and optimality claims.'),
    H('9.2 Future scope', HeadingLevel.HEADING_2),
    ...['User study with real shoppers measuring time saved and substitution acceptance.',
      'Cloud deployment (the Docker image is prepared) and a mobile interface with barcode scanning.',
      'Real partner price feeds for the store comparison and real HSN-based GST rates.',
      'Personalised recommendations from order history, and loyalty offers in the optimizer.',
      'Extending the grounding guard to product names and stock counts.'].map((s) => bullet(s)))

  // ---- references + appendix
  c.push(H('References', HeadingLevel.HEADING_1), ...REFS.map((r, i) => P(`[${i + 1}]  ${r}`, { align: AlignmentType.LEFT, after: 80 })),
    H('Appendix A: Running the system', HeadingLevel.HEADING_1),
    ...code(['docker compose up -d                       # PostgreSQL', 'python scripts/03_seed_database.py         # load the store data',
      'python -m uvicorn smartcart.api.main:app             # http://127.0.0.1:8000', `python -m pytest -q                        # ${F.tests_offline} tests`,
      'python scripts/07_evaluate.py              # evaluation harness']),
    H('Appendix B: API endpoints', HeadingLevel.HEADING_1),
    T([['Method and path'], ...F.endpoint_list.map((e) => [e])], [W], { size: 18 }))

  return new Document({
    creator: 'Group D8', title: 'Conversational Smart-Cart & Billing Assistant Agent: Project Report', description: 'Project report (draft)',
    styles: headingStyles('Times New Roman', { body: 24, title: 36, h1: 32, h2: 28, h3: 24 }),
    numbering: numbering(['obj']),
    sections: [{ properties: { page: A4 }, footers: { default: footer(k, 'Conversational Smart-Cart & Billing Assistant Agent') }, children: c }],
  })
}

// ===================================================================== 3. RESEARCH PAPER (IEEE-style)
function buildPaper() {
  figNo = 0; tabNo = 0
  const k = makeKit('Times New Roman', 20)
  const { P } = k
  const colW = Math.floor((TEXT_W - 360) / 2)
  const T = (rows, widths, o) => table(k, rows, widths, { size: 16, ...o })
  const sec = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER, children: [k.run(s.toUpperCase(), { size: 20 })] })
  const sub = (s) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [k.run(s, { size: 20, italics: true })] })
  const head = [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [k.run('Tool-Grounded Conversational Shopping: An Agentic Smart-Cart with Exact Coupon Optimization and Verified Billing', { size: 44 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [k.run(TEAM.map(([n]) => n).join(', ') + ' and Vrishali Prabhu', { size: 22 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [k.run('Department of Computer Science & Engineering (AIML), KIT’s College of Engineering (Empowered Autonomous), Kolhapur, India', { size: 18, italics: true })] }),
  ]
  const body = [
    P(`**Abstract**—Large language models (LLMs) make conversational shopping assistants possible, but they can state plausible yet wrong prices, stock levels and totals. We present an agentic smart-cart for a supermarket in which the LLM only plans and explains, while every transactional value is produced by deterministic tools over a relational database. A LangGraph state graph enforces substitution on stock-outs, bill recomputation after every cart change, budget fitting and a grounding check that rejects any rupee amount or aisle number absent from tool results. Coupon selection is formulated as a maximum-weight independent set over a coupon-conflict graph and solved exactly by branch and bound; a second exact search finds the fewest product swaps that meet a budget. On ${N_GOALS} scripted shopping goals executed live with Gemini 3.5 Flash-Lite and scored by code, the system achieved ${E.goals_succeeded}/${N_GOALS} task success, ${pct(E.grounding_accuracy_pct)} grounding accuracy over ${E.values_audited} audited values and ${pct(E.discount_captured_pct)} of the optimal discount; on ${O.carts} random carts the optimizer was always optimal while a single best coupon captured ${O.single_coupon_captured_pct}% of the achievable discount.`, { size: 18 }),
    P('**Index Terms**—agentic AI, large language models, tool use, grounding, conversational commerce, coupon optimization, maximum-weight independent set.', { size: 18 }),
    sec('I. Introduction'),
    P('Supermarket shopping involves locating products, checking availability, combining offers, handling stock-outs and verifying the bill. LLM agents that reason and act through tools [2], [3] can automate such multi-step tasks, and shopping agents have been studied in simulated web stores [1], [10]. However, a model that generates a price or total from its own parameters can be wrong in ways that are hard to notice, which is unacceptable when money is involved.'),
    P('We therefore adopt a strict division of labour: **the LLM plans, understands and explains; it never generates a price, stock count, location, discount, tax or total.** Our contributions are: (1) an agent architecture that enforces this rule structurally, with graph-level guarantees and a multilingual grounding guard; (2) an exact coupon optimizer for conflicting, scoped, capped coupons and an exact budget-fit planner; (3) an integration of shelf-level location, live inventory, offer optimization, substitution, GST billing and store comparison over a single shared cart, which no surveyed work combines; and (4) an evaluation harness that scores live agent runs by code against the database.'),
    sec('II. Related Work'),
    P('WebShop [1] and ShoppingBench [10] evaluate agents in simulated online stores without physical layout or billing. ReAct [2] and Toolformer [3] establish reasoning-with-tools. InteRecAgent [4], RecMind [5], LLM-Rec [6] and Agent4Rec [7] apply LLMs to recommendation, and [8] studies credible explanations; none executes a cart with live inventory. LORE [9] optimizes offers under constraints but without a conversational agent. Table I summarises capability coverage.'),
    tableCaption(k, 'Capability coverage (✓ full, ◐ partial, ✗ none)'),
    T([['Work', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7'], ...MATRIX.slice(1).map((r) => [r[0].replace('Beyond Persuasion', 'Beyond Pers.').replace('ShoppingBench', 'ShopBench'), ...r.slice(1)])],
      [1500, ...Array(7).fill(Math.floor((colW - 1500) / 7))], { align: [AlignmentType.LEFT, ...Array(7).fill(AlignmentType.CENTER)] }),
    P('C1 natural-language conversation · C2 tool-grounded actions · C3 aisle/shelf location · C4 live inventory · C5 offer optimization · C6 substitution · C7 cart & billing.', { size: 16, italics: true }),
    sec('III. System Design'),
    sub('A. Data model'),
    P(`The store database holds ${DB.products} real products from the BigBasket catalogue [11] and a synthesized aisle/shelf map (${DB.aisles} aisles, ${DB.shelves} shelves), inventory (${DB.out_of_stock} out of stock), ${DB.coupons} coupons with ${DB.conflicts} conflict pairs, GST rates and two comparison stores. Cart items store quantities but **no prices**; every bill is recomputed from live inventory, and only the immutable order snapshot freezes prices.`),
    sub('B. Agent graph'),
    P('The agent is a LangGraph [12] state machine with nodes agent, tools, auto_substitutes, refresh_bill and grounding_check. The LLM (Gemini [13]) chooses among nine tools. Conditional edges guarantee that (i) any refused add or failed stock check receives ranked same-type substitutes, (ii) every successful cart change receives the recomputed bill, including budget status computed by code and a budget-fit plan when over budget, and (iii) every final answer is checked. Cart and session identifiers are injected from graph state, so the model cannot address a wrong cart. State is persisted in the database, so conversations survive restarts.'),
    sub('C. Grounding guard'),
    P('All numbers in tool results and user messages form an allowed set. Rupee amounts (₹, Rs., INR, and Hindi/Marathi “रुपये”, including Devanagari digits) and aisle numbers (in English, Hindi and Marathi) are extracted from the reply; any value outside the set is reported back to the model for one rewrite and otherwise surfaced to the user.'),
    sec('IV. Optimization'),
    sub('A. Coupon selection'),
    P('Each valid coupon c with eligible subtotal s_c ≥ min_c has a fixed discount d_c = min(s_c·p_c/100, cap_c, s_c) (percentage) or min(v_c, s_c) (flat). With independent stacking, the task is to maximise min(Σ_{c∈S} d_c, subtotal) over S containing no conflicting pair: a maximum-weight independent set, NP-hard in general [16]. We use exact branch and bound with discount-sorted include/exclude decisions and the bound “current + remaining ≤ best”. Greedy can fail: A = 100 conflicting with B = C = 60 yields 100 instead of 120.'),
    sub('B. Budget fit'),
    P('Each line may switch to a cheaper in-stock product of the same type. Plans are enumerated by increasing number of swaps; among feasible plans with the fewest swaps the one with the highest total (least downgrade) is chosen, and coupons are re-optimized for every plan since swaps change eligibility.'),
    sub('C. GST and store comparison'),
    P('Prices include GST; coupon discounts are allocated proportionally to eligible lines and tax is extracted per line as n − n·100/(100 + r), giving Σ taxable + Σ GST = total exactly. For comparison, the cart is re-priced at each store from its price feed; only stores able to supply the whole cart are recommended.'),
    sec('V. Evaluation'),
    P(`Unit tests (${F.tests_offline}, with a scripted fake LLM) verify both optimizers against brute force and the GST invariant. The evaluation harness runs ${N_GOALS} goals (typos, stock-outs, stock limits, budgets, stacked coupons, multi-turn edits, navigation, GST, Hindi, Marathi, store comparison) live and scores them by reading the cart from the database, matching every number in every reply against tool results, and comparing the discount with a brute-force optimum (Table II).`),
    tableCaption(k, 'Live evaluation results'),
    T([['Metric', 'Result'], [`Task success (${N_GOALS} goals)`, `${E.goals_succeeded}/${N_GOALS} (strict ${E.goals_succeeded_strict})`],
      ['Grounding accuracy', `${pct(E.grounding_accuracy_pct)} (${E.values_audited} values)`], ['Discount vs. optimum', pct(E.discount_captured_pct)],
      ['Substitution correct', `${pct(E.substitution_correct_pct)} (${E.substitution_cases} cases)`], ['Median latency / turn', `${E.latency_median_s} s`],
      ['LLM calls / turn', String(E.llm_calls_per_turn)]], [Math.round(colW * 0.55), colW - Math.round(colW * 0.55)]),
    P(`The first run scored ${B.goals_succeeded}/12 and exposed three behavioural faults (substituting a different product type from search results, silently reducing quantity on short stock, omitting coupon amounts); explicit instructions fixed them. Grounding was 100% in every run, so behavioural errors never produced invented numbers. Table III compares the optimizer with baselines on ${O.carts} random real carts.`),
    tableCaption(k, 'Coupon selection on random carts'),
    T([['Method', 'Share of optimum'], ['Branch and bound (ours)', pct(O.system_captured_pct)], ['Greedy', `${O.greedy_captured_pct}%`],
      ['Single best coupon', `${O.single_coupon_captured_pct}%`]], [Math.round(colW * 0.6), colW - Math.round(colW * 0.6)]),
    P(`The optimizer was optimal on all carts (median ${O.optimizer_ms_median} ms). Latency is dominated by LLM calls on the free tier; tools take milliseconds.`),
    sec('VI. Conclusion'),
    P('Separating planning (LLM) from all transactional values (tools over one database), and enforcing critical steps in the agent graph, yields a conversational shopping assistant whose numbers are verifiable. Future work includes a user study of time saved, real price feeds and HSN-based taxes, and extending grounding checks to product names.'),
    sec('References'),
    ...REFS.map((r, i) => P(`[${i + 1}] ${r}`, { size: 16, align: AlignmentType.LEFT, after: 40 })),
  ]
  return new Document({
    creator: 'Group D8', title: 'Tool-Grounded Conversational Shopping (paper draft)',
    styles: {
      default: { document: { run: { font: 'Times New Roman', size: 20 } } },
      paragraphStyles: [
        { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', run: { font: 'Times New Roman', size: 20 },
          paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 200, after: 100 }, keepNext: true, outlineLevel: 0 } },
        { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', run: { font: 'Times New Roman', size: 20, italics: true },
          paragraph: { spacing: { before: 120, after: 60 }, keepNext: true, outlineLevel: 1 } },
      ],
    },
    numbering: numbering([]),
    sections: [
      { properties: { page: { size: A4.size, margin: { top: 1080, bottom: 1080, left: 1000, right: 1000 } } }, children: head },
      { properties: { type: SectionType.CONTINUOUS, page: { size: A4.size, margin: { top: 1080, bottom: 1080, left: 1000, right: 1000 } },
        column: { count: 2, space: 360 } },
      footers: { default: footer(k, 'Draft · Group D8 · KIT’s College of Engineering, Kolhapur') }, children: body },
    ],
  })
}

// ===================================================================== write
;(async () => {
  const out = [['SmartCart_Project_Guide.docx', buildGuide()], ['SmartCart_Project_Report.docx', buildReport()],
    ['SmartCart_Research_Paper.docx', buildPaper()]]
  for (const [name, doc] of out) {
    fs.writeFileSync(path.join(DOCS, name), await Packer.toBuffer(doc))
    console.log('wrote', name)
  }
})()
