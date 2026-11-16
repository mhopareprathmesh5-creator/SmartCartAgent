"""Milestone 7: the evaluation harness itself is tested offline (scripted fake LLM, no key)."""
from datetime import date
from decimal import Decimal as D

import pytest
from langchain_core.messages import AIMessage

from smartcart.agent import ShoppingAssistant
from smartcart.eval import Goal, Want, run_goal, summarize
from smartcart.eval.metrics import (brute_force_optimum, check_goal, discount_report, greedy_discount,
                                    single_best_discount, substitution_report)
from smartcart.tools.models import CartLine, Coupon
from tests.test_agent import ScriptedLLM, call, last_tool

TODAY = date(2026, 10, 12)


def C(code, value, min_value=0):
    return Coupon(0, code, code, "FLAT", D(value), None, D(min_value), "CART", None,
                  date(2026, 1, 1), date(2026, 12, 31), True)


def test_greedy_and_single_baselines_fall_short_of_the_optimum():
    lines = [CartLine(1, "X", "Y", "Z", D("1000.00"))]
    coupons = [C("A", 100), C("B", 60), C("CC", 60)]
    conflicts = {frozenset(("A", "B")), frozenset(("A", "CC"))}
    assert brute_force_optimum(lines, coupons, conflicts, TODAY) == D("120.00")
    assert greedy_discount(lines, coupons, conflicts, TODAY) == D("100.00")
    assert single_best_discount(lines, coupons, TODAY) == D("100.00")
    r = discount_report(lines, coupons, conflicts, TODAY)
    assert r["is_optimal"] and r["system"] == D("120.00") and sorted(r["system_codes"]) == ["B", "CC"]


def test_check_goal_scores_types_quantities_budget_and_quotes():
    goal = Goal("T", "t", ["x"], want=[Want("Milk", 2)], absent=["Curd"], budget=D("500.00"),
                mention=["final_total"])
    cart = [{"product_id": 1, "product_type": "Milk", "qty": 2, "stock_qty": 9}]
    checks = check_goal(goal, cart, {"final_total": "66.00"}, "500.00", ["Total ₹66.00"], {})
    assert all(c["passed"] for c in checks) and len(checks) == 4
    wrong = check_goal(goal, [{**cart[0], "qty": 1}], {"final_total": "33.00"}, None, ["Total ₹30"], {})
    assert [c["passed"] for c in wrong] == [False, True, False, False]
    pending = check_goal(goal, [{**cart[0], "qty": 1}], {"final_total": "33.00"}, "500.00", ["Total ₹33.00"],
                         {}, offered_types=frozenset({"Milk"}))
    assert pending[0]["passed"] and pending[0]["pending"]


def test_substitution_outcomes():
    goal = Goal("T", "t", ["x"], unavailable=[103, 779, 314])
    cart = [{"product_id": 104, "product_type": "Bread", "qty": 1, "stock_qty": 50}]
    catalog = {103: "Bread", 779: "Oats", 314: "Cola"}
    rep = substitution_report(goal, cart, catalog, {103: [104, 102]}, offered={779})
    assert [(s["outcome"], s["rank"]) for s in rep] == [("added", 1), ("offered", None), ("missing", None)]


def test_admin_evaluation_endpoint_serves_latest_run():
    from fastapi.testclient import TestClient
    from smartcart.api.main import EVAL_RESULTS, app
    r = TestClient(app).get("/admin/evaluation")
    if not EVAL_RESULTS.is_file():
        assert r.status_code == 404
        return
    body = r.json()
    assert r.status_code == 200 and {"summary", "offline", "goals"} <= set(body)
    assert all({"id", "success", "grounded", "failed"} <= set(g) for g in body["goals"])


@pytest.mark.db
def test_run_goal_end_to_end_with_scripted_llm(db):
    """Out-of-stock bread: the scripted agent takes the top auto-substitute; the harness must score
    success, grounding, a rank-1 same-type substitution and an optimal discount, then clean up."""
    def take_substitute(messages):
        return call("update_cart", product_id=last_tool(messages)["auto_substitutes"][0]["product_id"], quantity=1)

    def answer(messages):
        return AIMessage(f"Swapped in a substitute. Total ₹{last_tool(messages)['bill_after_change']['final_total']}.")

    bot = ShoppingAssistant(llm=ScriptedLLM(script=[call("update_cart", product_id=103, quantity=1),
                                                    take_substitute, answer]))
    goal = Goal("T1", "oos bread", ["add britannia brown bread"], want=[Want("Brown, Wheat & Multigrain", 1)],
                unavailable=[103], mention=["final_total"])
    r = run_goal(bot, goal, pace=0, log=lambda *_: None)
    assert r["success"] and r["turns"][0]["grounded"] and r["turns"][0]["llm_calls"] == 3
    assert r["substitutions"][0]["outcome"] == "added" and r["substitutions"][0]["rank"] == 1
    assert r["discount"]["is_optimal"]
    s = summarize([r])
    assert s["task_success_pct"] == 100.0 and s["grounding_accuracy_pct"] == 100.0
    assert s["substitution_correct_pct"] == 100.0 and s["discount_captured_pct"] == 100.0
    from sqlalchemy import text
    assert db.execute(text("SELECT count(*) FROM carts WHERE session_id LIKE 'eval-T1-%'")).scalar() == 0
