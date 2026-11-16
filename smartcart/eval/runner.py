"""Evaluation harness: plays the scripted goals through ShoppingAssistant and scores them.

    run_goals(assistant, goals)  -> list of per-goal results (dicts, JSON-ready)
    summarize(results)           -> the headline metrics
    offline_offer_study()        -> optimizer vs brute force / greedy / single coupon on random
                                    real carts (no LLM), for the "discount captured" analysis

Each goal runs in its own chat session and its carts are deleted afterwards, so an
evaluation run leaves the database unchanged (no goal checks out).
"""
import random
import statistics
import time
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import text

from smartcart import tools as T
from smartcart.agent.graph import LLM_RATE_LIMITED_REPLY, LLM_UNAVAILABLE_REPLY
from smartcart.agent.memory import delete_thread_memory
from smartcart.db import get_engine
from smartcart.eval.metrics import (check_goal, discount_report, pct, reply_values,
                                    substitution_report)
from smartcart.tools.models import CartLine
from smartcart.tools.offers import choose_best_offers, load_cart_lines, load_conflicts, load_coupons

SERVICE_ERRORS = (LLM_RATE_LIMITED_REPLY, LLM_UNAVAILABLE_REPLY)


def delete_session(session: str):
    with get_engine().begin() as conn:
        delete_thread_memory(conn, session)
        conn.execute(text("DELETE FROM orders WHERE cart_id IN "
                          "(SELECT cart_id FROM carts WHERE session_id = :s)"), {"s": session})
        conn.execute(text("DELETE FROM carts WHERE session_id = :s"), {"s": session})


def _cart_rows(conn, cart_id: int) -> list[dict]:
    rows = conn.execute(text("""
        SELECT ci.product_id, v.name, v.brand, v.product_type, ci.quantity AS qty, v.stock_qty
        FROM cart_items ci JOIN v_store_catalog v ON v.product_id = ci.product_id
        WHERE ci.cart_id = :c ORDER BY ci.product_id"""), {"c": cart_id}).mappings().all()
    return [dict(r) for r in rows]


def _type_aisles(conn) -> dict[str, int]:
    return dict(conn.execute(text("SELECT DISTINCT ON (product_type) product_type, aisle_no "
                                  "FROM v_store_catalog ORDER BY product_type, aisle_no")).all())


def _play(assistant, goal, pace: float, log) -> tuple[str, list[dict], list]:
    session = f"eval-{goal.id}-{uuid.uuid4().hex[:6]}"
    turns, replies = [], []
    for message in goal.turns:
        t0 = time.perf_counter()
        r = assistant.chat(session, message)
        latency = time.perf_counter() - t0
        replies.append(r)
        turns.append({
            "message": message, "reply": r.reply, "latency_s": round(latency, 2),
            "llm_calls": r.llm_calls, "models": r.models,
            "tool_calls": [c["tool"] for c in r.tool_calls],
            "grounded": r.grounded, "ungrounded": r.ungrounded,
            "grounding_retried": r.grounding_retried, "values_audited": reply_values(r.reply),
            "service_error": r.reply in SERVICE_ERRORS,
        })
        log(f"    turn {len(turns)}: {latency:5.1f}s  {r.llm_calls} LLM calls  {len(r.tool_calls)} tools  "
            f"{'grounded' if r.grounded else 'UNGROUNDED ' + str(r.ungrounded)}")
        if turns[-1]["service_error"]:
            break
        time.sleep(max(0.0, r.llm_calls * pace - latency))   # stay under the free-tier requests/minute
    return session, turns, replies


def run_goal(assistant, goal, pace: float = 5.0, retries: int = 2, log=print) -> dict:
    for attempt in range(retries + 1):
        session, turns, replies = _play(assistant, goal, pace, log)
        if not any(t["service_error"] for t in turns):
            break
        delete_session(session)
        if attempt < retries:
            log("    AI service limit hit; waiting 65 s and retrying this goal from scratch")
            time.sleep(65)
    else:
        return {"id": goal.id, "title": goal.title, "features": goal.features, "infra_error": True,
                "turns": turns}

    today = date.today()
    try:
        state = assistant.session(session)
        with get_engine().connect() as conn:
            cart = _cart_rows(conn, state["cart_id"])
            lines = load_cart_lines(conn, state["cart_id"])
            coupons, conflicts = load_coupons(conn), load_conflicts(conn)
            type_aisles = _type_aisles(conn)
            catalog = dict(conn.execute(text("SELECT product_id, product_type FROM products")).all())
        bill = state["bill"]
        want_qty = {w.product_type: w.qty for w in goal.want}
        ranked = {pid: [s.product_id for s in T.find_substitutes(pid, quantity=want_qty.get(catalog[pid], 1),
                                                                   limit=5)]
                  for pid in goal.unavailable}
        offered = {g["for_product_id"] for r in replies for g in r.suggestions if g["kind"] == "substitutes"}
        offered_types = frozenset(catalog[p] for p in goal.unavailable if p in offered)
        tools_called = frozenset(c["tool"] for r in replies for c in r.tool_calls)
        checks = check_goal(goal, cart, bill, state["budget"], [r.reply for r in replies], type_aisles,
                            offered_types, tools_called)
        result = {
            "id": goal.id, "title": goal.title, "features": goal.features, "infra_error": False,
            "turns": turns,
            "cart": [{k: r[k] for k in ("product_id", "brand", "name", "product_type", "qty")} for r in cart],
            "final_total": bill["final_total"], "budget": state["budget"],
            "over_budget_by": bill.get("over_budget_by"),
            "checks": checks, "success": all(c["passed"] for c in checks),
            "success_strict": all(c["passed"] and not c["pending"] for c in checks),
            "substitutions": substitution_report(goal, cart, catalog, ranked, offered),
            "discount": discount_report(lines, coupons, conflicts, today),
        }
    finally:
        delete_session(session)
    return result


def run_goals(assistant, goals, pace: float = 5.0, log=print) -> list[dict]:
    results = []
    for i, goal in enumerate(goals, 1):
        log(f"[{i}/{len(goals)}] {goal.id} {goal.title}")
        r = run_goal(assistant, goal, pace=pace, log=log)
        results.append(r)
        if not r["infra_error"]:
            failed = [c["check"] for c in r["checks"] if not c["passed"]]
            log(f"    -> {'SUCCESS' if r['success'] else 'FAILED: ' + '; '.join(failed)}")
    return results


# ---------------------------------------------------------------- summary
def summarize(results: list[dict]) -> dict:
    done = [r for r in results if not r["infra_error"]]
    turns = [t for r in done for t in r["turns"]]
    subs = [s for r in done for s in r["substitutions"]]
    disc = [r["discount"] for r in done]
    lat = sorted(t["latency_s"] for t in turns)
    opt_total = sum((Decimal(str(d["optimum"])) for d in disc), Decimal("0"))
    added = [s for s in subs if s["outcome"] == "added"]
    return {
        "goals": len(results), "goals_completed": len(done),
        "infra_errors": len(results) - len(done),
        "task_success_pct": pct(Decimal(sum(r["success"] for r in done)), Decimal(len(done) or 0)),
        "goals_succeeded": sum(r["success"] for r in done),
        "goals_succeeded_strict": sum(r["success_strict"] for r in done),
        "goals_pending_confirmation": sum(r["success"] and not r["success_strict"] for r in done),
        "checks_passed": sum(c["passed"] for r in done for c in r["checks"]),
        "checks_total": sum(len(r["checks"]) for r in done),
        "turns": len(turns),
        "grounding_accuracy_pct": pct(Decimal(sum(t["grounded"] for t in turns)), Decimal(len(turns) or 0)),
        "first_try_grounded_pct": pct(Decimal(sum(t["grounded"] and not t["grounding_retried"] for t in turns)),
                                      Decimal(len(turns) or 0)),
        "guard_rewrites": sum(t["grounding_retried"] for t in turns),
        "values_audited": sum(t["values_audited"] for t in turns),
        "ungrounded_values": sorted({v for t in turns for v in t["ungrounded"]}),
        "discount_captured_pct": pct(sum((Decimal(str(d["system"])) for d in disc), Decimal("0")), opt_total),
        "carts_at_optimum": sum(d["is_optimal"] for d in disc),
        "greedy_captured_pct": pct(sum((Decimal(str(d["greedy"])) for d in disc), Decimal("0")), opt_total),
        "single_coupon_captured_pct": pct(sum((Decimal(str(d["single_best"])) for d in disc), Decimal("0")),
                                          opt_total),
        "discount_system_total": str(sum((Decimal(str(d["system"])) for d in disc), Decimal("0"))),
        "discount_optimum_total": str(opt_total),
        "substitution_cases": len(subs),
        "substitution_correct_pct": pct(Decimal(sum(s["same_type"] and s["in_stock"] for s in subs)),
                                        Decimal(len(subs) or 0)),
        "substitutes_added": len(added),
        "substitutes_offered": sum(s["outcome"] == "offered" for s in subs),
        "substitute_top1_pct": pct(Decimal(sum(s["rank"] == 1 for s in added)), Decimal(len(added) or 0)),
        "latency_median_s": round(statistics.median(lat), 2) if lat else None,
        "latency_p90_s": lat[min(len(lat) - 1, int(0.9 * len(lat)))] if lat else None,
        "latency_max_s": lat[-1] if lat else None,
        "llm_calls_per_turn": round(statistics.mean(t["llm_calls"] for t in turns), 2) if turns else None,
        "tool_calls_per_turn": round(statistics.mean(len(t["tool_calls"]) for t in turns), 2) if turns else None,
        "models_used": sorted({m for t in turns for m in t["models"] if m}),
    }


# ---------------------------------------------------------------- offline study (no LLM)
def offline_offer_study(carts: int = 300, seed: int = 7, today: date = date(2026, 10, 12)) -> dict:
    """Random carts priced from the real catalogue, scored with the real coupons: exact optimizer vs
    brute force vs greedy vs one coupon. Also times the optimizer."""
    from smartcart.eval.metrics import brute_force_optimum, greedy_discount, single_best_discount
    with get_engine().connect() as conn:
        coupons, conflicts = load_coupons(conn), load_conflicts(conn)
        products = conn.execute(text("SELECT product_id, category, sub_category, brand, current_price "
                                     "FROM v_store_catalog ORDER BY product_id")).all()
    rng = random.Random(seed)
    sums = {"system": Decimal("0"), "optimum": Decimal("0"), "greedy": Decimal("0"), "single": Decimal("0")}
    optimal = greedy_worse = single_worse = 0
    times = []
    for _ in range(carts):
        lines = [CartLine(p[0], p[1], p[2], p[3], p[4] * rng.randint(1, 4))
                 for p in rng.sample(products, rng.randint(3, 25))]
        t0 = time.perf_counter()
        system = choose_best_offers(lines, coupons, conflicts, today).total_discount
        times.append((time.perf_counter() - t0) * 1000)
        best = brute_force_optimum(lines, coupons, conflicts, today)
        greedy = greedy_discount(lines, coupons, conflicts, today)
        single = single_best_discount(lines, coupons, today)
        sums["system"] += system
        sums["optimum"] += best
        sums["greedy"] += greedy
        sums["single"] += single
        optimal += system == best
        greedy_worse += greedy < best
        single_worse += single < best
    times.sort()
    return {
        "carts": carts, "coupons": len(coupons), "conflict_pairs": len(conflicts),
        "optimal_carts": optimal,
        "system_captured_pct": pct(sums["system"], sums["optimum"]),
        "greedy_captured_pct": pct(sums["greedy"], sums["optimum"]),
        "single_coupon_captured_pct": pct(sums["single"], sums["optimum"]),
        "greedy_suboptimal_carts": greedy_worse, "single_suboptimal_carts": single_worse,
        "discount_optimum_total": str(sums["optimum"]), "discount_system_total": str(sums["system"]),
        "discount_greedy_total": str(sums["greedy"]), "discount_single_total": str(sums["single"]),
        "optimizer_ms_median": round(statistics.median(times), 3), "optimizer_ms_max": round(times[-1], 3),
    }
