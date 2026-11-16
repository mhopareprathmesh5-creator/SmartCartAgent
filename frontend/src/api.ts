// Typed client for the FastAPI backend.
// Money is always the exact decimal string the server sent ("66.00"); the UI never does price math.

export type Money = string

export interface BillItem {
  product_id: number
  name: string
  brand: string
  qty: number
  unit_price: Money
  line_total: Money
  stock_qty: number
  aisle_no: number | null
  aisle_name: string | null
  shelf_code: string | null
  gst_rate: Money
}

export interface GstSlab {
  rate: Money
  taxable_value: Money
  cgst: Money
  sgst: Money
}

export interface Bill {
  items: BillItem[]
  item_count: number
  subtotal: Money
  mrp_total: Money
  savings_vs_mrp: Money
  coupons_applied: { code: string; description: string; discount: Money }[]
  discount_total: Money
  final_total: Money
  coupons_skipped_due_to_conflict: { code: string; why: string }[]
  almost_unlocked: { code: string; add_amount: Money; detail: string }[]
  warnings: string[]
  gst_included: Money
  gst_breakup: GstSlab[]
  budget?: Money
  over_budget_by?: Money
  budget_remaining?: Money
}

export interface Card {
  product_id: number
  name: string
  brand: string
  price: Money
  mrp?: Money
  stock_qty: number
  in_stock: boolean
  aisle_no: number | null
  shelf_code: string | null
  price_difference?: Money
}

export interface SuggestionGroup {
  kind: 'substitutes' | 'search'
  title: string
  for_product_id: number | null
  items: Card[]
}

export interface Swap {
  from_product_id: number
  from_name: string
  to_product_id: number
  to_name: string
  to_brand: string
  quantity: number
  from_unit_price: Money
  to_unit_price: Money
  saving: Money
  aisle_no: number | null
  shelf_code: string | null
}

export interface BudgetPlan {
  feasible: boolean
  budget: Money
  current_total: Money
  new_total: Money
  total_saving: Money
  swaps: Swap[]
  plans_evaluated: number
  message: string
}

export interface AdminSummary {
  products: number
  out_of_stock: number
  low_stock: number
  live_coupons: number
  orders: number
  revenue: Money
  discounts: Money
  gst: Money
}

export interface AdminProduct {
  product_id: number
  name: string
  brand: string
  category: string
  product_type: string
  mrp: Money
  price: Money
  stock_qty: number
  gst_rate: Money
  aisle_no: number
  shelf_code: string
  updated_at: string
}

export interface AdminCoupon {
  code: string
  description: string
  status: 'live' | 'disabled' | 'expired' | 'not started'
  is_active: boolean
  valid_from: string
  valid_to: string
  conflicts_with: string[]
}

export interface AdminOrder {
  order_id: number
  placed_at: string
  final_total: Money
  discount_total: Money
  gst_total: Money
  applied_coupons: string[]
  items: number
}

export interface ToolCall {
  tool: string
  args: Record<string, unknown>
}

export interface ChatReply {
  session_id: string
  cart_id: number
  reply: string
  grounded: boolean
  ungrounded: string[]
  tool_calls: ToolCall[]
  bill: Bill
  suggestions: SuggestionGroup[]
}

export interface SessionView {
  session_id: string
  cart_id: number
  budget: Money | null
  bill: Bill
}

export interface CartUpdate {
  ok: boolean
  product_id: number
  quantity: number
  available_stock: number
  message: string
}

export interface OrderLine {
  product_id: number
  name: string
  quantity: number
  unit_price: Money
  line_total: Money
}

export interface Order {
  order_id: number
  cart_id: number
  subtotal: Money
  discount_total: Money
  final_total: Money
  applied_coupons: string[]
  lines: OrderLine[]
  placed_at: string
  gst_total: Money
  tax_breakup: { rate: Money; taxable_value: Money; cgst: Money; sgst: Money }[]
}

export interface CheckoutResult {
  ok: boolean
  order: Order | null
  problems: string[]
}

export interface Health {
  status: string
  products: number
  llm_configured: boolean
}

export interface StaffSession {
  username: string
  full_name: string
  role: 'manager' | 'staff'
}

export interface AuditEntry {
  audit_id: number
  username: string
  role: string
  action: 'price' | 'stock' | 'coupon'
  target: string
  detail: { name?: string; from?: string | number; to: string | number }
  at: string
}

export interface StoreQuote {
  store_id: number
  name: string
  city: string
  is_home: boolean
  accepts_coupons: boolean
  items_available: number
  items_total: number
  complete: boolean
  subtotal: Money
  discount: Money
  coupons: string[]
  final_total: Money
  missing: { product_id: number; name: string; quantity: number; reason: string }[]
}

export interface StoreComparison {
  cart_id: number
  quotes: StoreQuote[]
  best_store_id: number | null
  saving_vs_home: Money
  message: string
}

export interface StudyTask { task_id: string; title: string; instructions: string }
export interface StudyRun {
  run_id: number; session_id: string; cart_id: number; mode: 'assistant' | 'manual'
  task_id: string; title: string; instructions: string
}
export interface StudyResult {
  run_id: number; seconds: Money; success: boolean; final_total: Money
  checks: { check: string; passed: boolean; detail: string }[]
}
export interface StudySummary {
  runs: number
  modes: Record<'assistant' | 'manual', { runs: number; success_pct: number | null; mean_seconds: number | null;
    median_seconds: number | null }>
  paired_participants: number
  mean_seconds_saved?: number
  mean_time_saved_pct?: number
}
export interface SearchHit {
  product_id: number; name: string; brand: string; price: Money; mrp: Money; stock_qty: number; in_stock: boolean
  aisle_no: number; shelf_code: string
}
export interface RawBill {
  lines: { product_id: number; name: string; brand: string; quantity: number; line_total: Money }[]
  discount_total: Money
  final_total: Money
}

export interface EvalGoal {
  id: string
  title: string
  features: string[]
  infra_error: boolean
  success: boolean
  grounded: boolean
  latency_s: number
  turns: number
  final_total: Money | null
  discount: Money | null
  optimum: Money | null
  failed: string[]
}

export interface Evaluation {
  generated: string
  summary: {
    goals: number; goals_completed: number; goals_succeeded: number; task_success_pct: number
    checks_passed: number; checks_total: number; turns: number
    grounding_accuracy_pct: number; first_try_grounded_pct: number; guard_rewrites: number; values_audited: number
    discount_captured_pct: number; greedy_captured_pct: number
    substitution_cases: number; substitution_correct_pct: number; substitute_top1_pct: number
    latency_median_s: number; latency_max_s: number; llm_calls_per_turn: number; infra_errors: number
    models_used: string[]
  }
  offline: {
    carts: number; optimal_carts: number; system_captured_pct: number; greedy_captured_pct: number
    single_coupon_captured_pct: number; greedy_suboptimal_carts: number; optimizer_ms_median: number
  }
  goals: EvalGoal[]
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Dev server proxies /api -> FastAPI; the production build is served by FastAPI itself.
const BASE = import.meta.env.DEV ? '/api' : ''

// Store-staff login token (admin pages only). Kept in localStorage; the server signs and checks it.
const TOKEN_KEY = 'smartcart.adminToken'
export const adminToken = {
  get: (): string | null => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } },
  set: (t: string | null) => {
    try { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY) } catch { /* private mode */ }
  },
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = path.startsWith('/admin') ? adminToken.get() : null
  if (token) headers.Authorization = `Bearer ${token}`
  try {
    res = await fetch(BASE + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is uvicorn running?')
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : `Request failed (${res.status})`
    throw new ApiError(res.status, detail)
  }
  return data as T
}

export const api = {
  health: () => request<Health>('GET', '/health'),
  chat: (sessionId: string, message: string) =>
    request<ChatReply>('POST', '/chat', { session_id: sessionId, message }),
  session: (sessionId: string) => request<SessionView>('GET', `/sessions/${encodeURIComponent(sessionId)}`),
  setItem: (sessionId: string, productId: number, quantity: number) =>
    request<{ update: CartUpdate; session: SessionView }>(
      'PUT', `/sessions/${encodeURIComponent(sessionId)}/items/${productId}`, { quantity }),
  checkout: (sessionId: string) =>
    request<{ result: CheckoutResult; session: SessionView }>(
      'POST', `/sessions/${encodeURIComponent(sessionId)}/checkout`),
  setBudget: (sessionId: string, amount: string | null) =>
    request<SessionView>('PUT', `/sessions/${encodeURIComponent(sessionId)}/budget`, { amount }),
  budgetPlan: (sessionId: string) =>
    request<BudgetPlan>('GET', `/sessions/${encodeURIComponent(sessionId)}/budget-plan`),
  swap: (sessionId: string, swaps: { from_product_id: number; to_product_id: number; quantity: number }[]) =>
    request<{ results: CartUpdate[]; session: SessionView }>(
      'POST', `/sessions/${encodeURIComponent(sessionId)}/swaps`, { swaps }),

  search: (q: string) => request<SearchHit[]>('GET', `/products/search?${new URLSearchParams({ q, limit: '8' })}`),
  cartSet: (cartId: number, productId: number, quantity: number) =>
    request<CartUpdate>('PUT', `/carts/${cartId}/items/${productId}`, { quantity, mode: 'set' }),
  cartBill: (cartId: number) => request<RawBill>('GET', `/carts/${cartId}/bill`),
  study: {
    tasks: () => request<StudyTask[]>('GET', '/study/tasks'),
    start: (participant: string, mode: 'assistant' | 'manual', taskId: string) =>
      request<StudyRun>('POST', '/study/runs', { participant, mode, task_id: taskId }),
    finish: (runId: number, messages?: number) =>
      request<StudyResult>('POST', `/study/runs/${runId}/finish`, { messages: messages ?? null }),
    summary: () => request<StudySummary>('GET', '/study/summary'),
  },
  compareStores: (sessionId: string) =>
    request<StoreComparison>('GET', `/sessions/${encodeURIComponent(sessionId)}/compare-stores`),

  admin: {
    login: (username: string, password: string) =>
      request<StaffSession & { token: string }>('POST', '/admin/login', { username, password }),
    me: () => request<StaffSession>('GET', '/admin/me'),
    audit: () => request<AuditEntry[]>('GET', '/admin/audit'),
    summary: () => request<AdminSummary>('GET', '/admin/summary'),
    inventory: (q: string, filter: 'all' | 'out' | 'low', limit = 50) =>
      request<{ total: number; items: AdminProduct[] }>(
        'GET', `/admin/inventory?${new URLSearchParams({ q, filter, limit: String(limit) })}`),
    updateProduct: (id: number, change: { price?: string; stock_qty?: number }) =>
      request<AdminProduct>('PATCH', `/admin/inventory/${id}`, change),
    coupons: () => request<AdminCoupon[]>('GET', '/admin/coupons'),
    setCoupon: (code: string, isActive: boolean) =>
      request<AdminCoupon>('PATCH', `/admin/coupons/${encodeURIComponent(code)}`, { is_active: isActive }),
    orders: () => request<AdminOrder[]>('GET', '/admin/orders'),
    evaluation: () => request<Evaluation>('GET', '/admin/evaluation'),
  },
}

/** "5.00" -> "5%", "18.00" -> "18%" */
export const pct = (m: Money) => `${parseFloat(m)}%`

export const rupees = (m: Money) => `₹${m}`
