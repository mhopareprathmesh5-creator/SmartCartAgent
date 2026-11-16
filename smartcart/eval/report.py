"""Write the evaluation results as JSON (machine-readable) and Markdown (for the report/viva)."""
import json
from datetime import datetime
from pathlib import Path


def _yes(b) -> str:
    return "✅" if b else "❌"


def write_reports(out_dir: Path, summary: dict, results: list[dict], offline: dict) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    data = {"generated": stamp, "summary": summary, "offline_offer_study": offline, "goals": results}
    js = out_dir / "results.json"
    js.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    s, o = summary, offline
    md = [
        "# SmartCart Agent — Evaluation Report",
        "",
        f"Generated {stamp} by `python scripts/07_evaluate.py`. "
        f"Models: {', '.join(s['models_used']) or 'n/a'}.",
        "",
        "## Headline metrics",
        "",
        "| metric | result |",
        "|---|---|",
        f"| Task success (goals fully achieved) | **{s['goals_succeeded']}/{s['goals_completed']} "
        f"({s['task_success_pct']}%)**, checks passed {s['checks_passed']}/{s['checks_total']} |",
        f"| Task success, strict (substitute already added, no confirmation pending) | "
        f"{s['goals_succeeded_strict']}/{s['goals_completed']}; {s['goals_pending_confirmation']} goal(s) "
        f"waiting for the shopper to pick a substitute |",
        f"| Grounding accuracy (replies with 0 invented ₹/aisle values) | **{s['grounding_accuracy_pct']}%** "
        f"of {s['turns']} replies; {s['values_audited']} values audited |",
        f"| Grounded on the first try (no guard rewrite needed) | {s['first_try_grounded_pct']}% "
        f"({s['guard_rewrites']} rewrite(s) triggered by the guard) |",
        f"| Discount captured vs theoretical optimum (agent carts) | **{s['discount_captured_pct']}%** "
        f"(₹{s['discount_system_total']} of ₹{s['discount_optimum_total']}); "
        f"{s['carts_at_optimum']}/{s['goals_completed']} carts optimal |",
        f"| Discount captured on {o['carts']} random real carts | **{o['system_captured_pct']}%** "
        f"(greedy {o['greedy_captured_pct']}%, single coupon {o['single_coupon_captured_pct']}%) |",
        f"| Substitution correctness (same type, in stock) | **{s['substitution_correct_pct']}%** "
        f"of {s['substitution_cases']} cases; {s['substitutes_added']} added, "
        f"{s['substitutes_offered']} offered; top-ranked choice {s['substitute_top1_pct']}% |",
        f"| Latency per turn | median {s['latency_median_s']} s, p90 {s['latency_p90_s']} s, "
        f"max {s['latency_max_s']} s |",
        f"| LLM calls / tool calls per turn | {s['llm_calls_per_turn']} / {s['tool_calls_per_turn']} |",
        f"| Offer optimizer time | median {o['optimizer_ms_median']} ms, max {o['optimizer_ms_max']} ms |",
        "",
    ]
    if s["infra_errors"]:
        md += [f"> {s['infra_errors']} goal(s) could not run because of the Gemini rate limit "
               "and are excluded from the percentages.", ""]
    if s["ungrounded_values"]:
        md += [f"Ungrounded values that reached the shopper: {', '.join(s['ungrounded_values'])}", ""]

    md += [
        "## How each metric is measured",
        "",
        "- **Task success**: after the conversation the cart is read from PostgreSQL. Every requested "
        "item must be present as the right *product type* in the exact quantity, removed items must be "
        "gone, the budget must be recorded, and where asked, the reply must quote the bill's value. "
        "If an item could not be supplied and the agent showed substitute cards for the shopper to choose "
        "(the confirm-substitute behaviour of synopsis objective 4), that item counts as ⏳ pending: it "
        "passes the normal score and fails the strict score.",
        "- **Grounding accuracy**: every ₹ amount and aisle number in each final reply is checked "
        "against the values the tools returned in that conversation (the same guard that runs live).",
        "- **Discount captured**: for the final cart, the discount the system applied is compared with "
        "the theoretical optimum, found by brute force over every conflict-free subset of the valid "
        "coupons. Greedy (biggest coupon first) and best-single-coupon are baselines.",
        "- **Substitution**: for every product that could not be supplied (out of stock or quantity "
        "above stock), a correct outcome is an in-stock product of the same product type in the cart, "
        "or substitute cards shown for the shopper to pick.",
        "- **Latency / LLM calls**: wall-clock time of each turn and the number of Gemini requests it made "
        "(the run is paced to respect the 15 requests/min free tier).",
        "",
        "## Offline coupon study (no LLM)",
        "",
        f"{o['carts']} random carts (3–25 products from the real catalogue, quantity 1–4), the real "
        f"{o['coupons']} coupons and {o['conflict_pairs']} conflict pairs:",
        "",
        "| method | discount given | share of optimum | carts below optimum |",
        "|---|---|---|---|",
        f"| Brute force (theoretical optimum) | ₹{o['discount_optimum_total']} | 100% | 0 |",
        f"| **SmartCart branch-and-bound** | ₹{o['discount_system_total']} | **{o['system_captured_pct']}%** | "
        f"{o['carts'] - o['optimal_carts']} |",
        f"| Greedy (biggest first) | ₹{o['discount_greedy_total']} | {o['greedy_captured_pct']}% | "
        f"{o['greedy_suboptimal_carts']} |",
        f"| Best single coupon | ₹{o['discount_single_total']} | {o['single_coupon_captured_pct']}% | "
        f"{o['single_suboptimal_carts']} |",
        "",
        "## Per-goal results",
        "",
        "| goal | features | success | grounded | turns | latency | final total | discount (system / optimum) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r["infra_error"]:
            md.append(f"| {r['id']} {r['title']} | {', '.join(r['features'])} | rate-limited | – | – | – | – | – |")
            continue
        lat = sum(t["latency_s"] for t in r["turns"])
        d = r["discount"]
        md.append(f"| {r['id']} {r['title']} | {', '.join(r['features'])} | {_yes(r['success'])} | "
                  f"{_yes(all(t['grounded'] for t in r['turns']))} | {len(r['turns'])} | {lat:.1f} s | "
                  f"₹{r['final_total']} | ₹{d['system']} / ₹{d['optimum']} |")
    md += ["", "## Goal details", ""]
    for r in results:
        md += [f"### {r['id']} — {r['title']}", ""]
        for t in r["turns"]:
            md += [f"**Shopper:** {t['message']}", "",
                   f"**Agent** ({t['latency_s']} s, {t['llm_calls']} LLM calls, tools: "
                   f"{', '.join(t['tool_calls']) or 'none'}):", "",
                   "> " + t["reply"].replace("\n", "\n> "), ""]
        if r["infra_error"]:
            md += ["Not scored: the Gemini rate limit was hit on every attempt.", ""]
            continue
        md += ["Cart: " + ("; ".join(f"{c['qty']} × {c['brand']} {c['name']} [{c['product_type']}]"
                                      for c in r["cart"]) or "empty"), ""]
        md += [f"- {'⏳' if c.get('pending') else _yes(c['passed'])} {c['check']} ({c['detail']})"
               for c in r["checks"]]
        for sub in r["substitutions"]:
            md.append(f"- substitution for #{sub['product_id']}: {sub['outcome']}"
                      + (f", #{sub['substitute']} (rank {sub['rank']})" if sub["substitute"] else ""))
        d = r["discount"]
        md += [f"- coupons: {', '.join(d['system_codes']) or 'none'} → ₹{d['system']} "
               f"(optimum ₹{d['optimum']}, greedy ₹{d['greedy']}, single ₹{d['single_best']})", ""]
    mdp = out_dir / "EVALUATION_REPORT.md"
    mdp.write_text("\n".join(md), encoding="utf-8")
    return js, mdp
