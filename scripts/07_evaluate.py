"""Milestone 7: evaluate the agent on scripted shopping goals (needs GOOGLE_API_KEY for the live part).

    python scripts/07_evaluate.py                  # all 15 goals live + offline coupon study (~8-12 min)
    python scripts/07_evaluate.py --goals G04 G07  # only some goals
    python scripts/07_evaluate.py --offline        # only the coupon study (no LLM, ~10 s)
    python scripts/07_evaluate.py --pace 6         # seconds reserved per LLM call (default 5 = 12 req/min)

Writes docs/evaluation/results.json and docs/evaluation/EVALUATION_REPORT.md.
The run leaves the database unchanged (each goal's cart is deleted, nothing is checked out).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import _common  # noqa: E402,F401  (UTF-8 console for ₹)
from smartcart.eval import GOALS, offline_offer_study, run_goals, summarize  # noqa: E402
from smartcart.eval.report import write_reports  # noqa: E402

OUT = ROOT / "docs" / "evaluation"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goals", nargs="*", help="goal ids to run (default: all)")
    ap.add_argument("--offline", action="store_true", help="only the offline coupon study")
    ap.add_argument("--pace", type=float, default=5.0)
    ap.add_argument("--out", type=Path, default=OUT, help="report folder (default docs/evaluation)")
    args = ap.parse_args()
    out = args.out

    print("Offline coupon study: exact optimizer vs brute force / greedy / single coupon …")
    offline = offline_offer_study()
    print(f"  {offline['carts']} carts: optimizer {offline['system_captured_pct']}% of optimum "
          f"({offline['optimal_carts']}/{offline['carts']} optimal), greedy {offline['greedy_captured_pct']}%, "
          f"single coupon {offline['single_coupon_captured_pct']}%, median {offline['optimizer_ms_median']} ms\n")

    if args.offline:
        prev = out / "results.json"
        if prev.exists():     # keep the last live results, refresh only the offline part
            data = json.loads(prev.read_text(encoding="utf-8"))
            write_reports(out, data["summary"], data["goals"], offline)
        else:
            out.mkdir(parents=True, exist_ok=True)
            (out / "offline_offer_study.json").write_text(json.dumps(offline, indent=2), encoding="utf-8")
        return

    from smartcart.agent import ShoppingAssistant
    from smartcart.agent.llm import LLMNotConfigured
    try:
        bot = ShoppingAssistant()
    except LLMNotConfigured as e:
        sys.exit(str(e))

    goals = [g for g in GOALS if not args.goals or g.id in args.goals]
    results = run_goals(bot, goals, pace=args.pace)
    summary = summarize(results)
    js, md = write_reports(out, summary, results, offline)

    s = summary
    print("\n================ EVALUATION SUMMARY ================")
    print(f"Task success          {s['goals_succeeded']}/{s['goals_completed']} goals ({s['task_success_pct']}%), "
          f"{s['checks_passed']}/{s['checks_total']} checks")
    print(f"Grounding accuracy    {s['grounding_accuracy_pct']}% of {s['turns']} replies "
          f"({s['values_audited']} ₹/aisle values audited, {s['guard_rewrites']} guard rewrites)")
    print(f"Discount captured     {s['discount_captured_pct']}% of the brute-force optimum "
          f"(greedy would get {s['greedy_captured_pct']}%)")
    print(f"Substitution          {s['substitution_correct_pct']}% correct of {s['substitution_cases']} cases, "
          f"top-ranked {s['substitute_top1_pct']}%")
    print(f"Latency per turn      median {s['latency_median_s']} s, max {s['latency_max_s']} s; "
          f"{s['llm_calls_per_turn']} LLM calls/turn")
    if s["infra_errors"]:
        print(f"Rate-limited goals    {s['infra_errors']} (excluded)")
    print(f"\nReport: {md}\nData:   {js}")


if __name__ == "__main__":
    main()
