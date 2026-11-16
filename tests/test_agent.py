"""Agent graph tests with a SCRIPTED fake LLM (no API key, no network, deterministic).

They prove the parts the graph guarantees regardless of which LLM is plugged in:
auto-substitution on stock-outs, bill refresh after cart changes, budget status
computed by code, grounding check + retry, memory across turns, checkout.
"""
import json
import uuid
from decimal import Decimal as D
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field
from sqlalchemy import text

from smartcart.agent import ShoppingAssistant
from smartcart.agent.grounding import grounded_numbers, ungrounded_values
from tests.conftest import delete_session, pick


class ScriptedLLM(BaseChatModel):
    """Returns the next scripted step. A step is an AIMessage or fn(messages) -> AIMessage."""
    script: list[Any]
    seen: list[Any] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(list(messages))
        step = self.script[len(self.seen) - 1]
        if isinstance(step, Exception):
            raise step
        msg = step(messages) if callable(step) else step
        return ChatResult(generations=[ChatGeneration(message=msg)])


def call(name, **args) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:8]}",
                                      "type": "tool_call"}])


def last_tool(messages) -> dict:
    return json.loads(next(m for m in reversed(messages) if isinstance(m, ToolMessage)).content)


@pytest.fixture
def session():
    s = f"pytest-agent-{uuid.uuid4().hex[:8]}"
    yield s
    delete_session(s)


# ---------------------------------------------------------------- grounding unit tests (no DB)
def test_grounding_detects_invented_amounts_and_aisles():
    tool = ToolMessage(json.dumps({"price": "45.00", "aisle_no": 2, "detail": "Needs ₹100.00 of Amul"}),
                       tool_call_id="x")
    allowed = grounded_numbers([HumanMessage("budget under ₹600"), tool])
    assert ungrounded_values("It costs ₹45 in Aisle 2. Add ₹100 more; budget ₹600.", allowed) == []
    assert ungrounded_values("Total Rs. 1,234.50 at aisle 7", allowed) == ["₹1,234.50", "Aisle 7"]


def test_grounding_checks_hindi_and_marathi_replies():
    tool = ToolMessage(json.dumps({"price": "45.00", "aisle_no": 2}), tool_call_id="x")
    allowed = grounded_numbers([tool])
    assert ungrounded_values("ब्रेड ₹45.00 में है, Aisle 2 में मिलेगा।", allowed) == []
    assert ungrounded_values("ब्रेड ४५ रुपये, गलियारा २", allowed) == []              # Devanagari digits
    assert ungrounded_values("दूध ₹५०, गलियारा नंबर 7 मध्ये", allowed) == ["₹५०", "Aisle 7"]
    assert ungrounded_values("साखर 99 रुपयांना आहे, रांग 3", allowed) == ["₹99", "Aisle 3"]


# ---------------------------------------------------------------- graph behaviour (DB)
@pytest.mark.db
def test_out_of_stock_gets_substitutes_attached_automatically(db, session):
    oos = pick(db, "stock_qty = 0")

    def take_top_substitute(messages):
        result = last_tool(messages)
        assert result["ok"] is False and result["auto_substitutes"], "graph must attach substitutes"
        return call("update_cart", product_id=result["auto_substitutes"][0]["product_id"], quantity=1)

    def answer(messages):
        bill = last_tool(messages)["bill_after_change"]
        return AIMessage(f"Swapped it for a substitute. Total ₹{bill['final_total']}.")

    llm = ScriptedLLM(script=[call("update_cart", product_id=oos, quantity=1), take_top_substitute, answer])
    r = ShoppingAssistant(llm=llm).chat(session, "add it")
    assert [c["tool"] for c in r.tool_calls] == ["update_cart", "update_cart"]
    assert r.grounded and r.bill["item_count"] == 1
    assert f"₹{r.bill['final_total']}" in r.reply


@pytest.mark.db
def test_budget_status_is_computed_by_code(db, session):
    pid = pick(db, "stock_qty >= 10 AND current_price > 150")

    def answer(messages):
        bill = last_tool(messages)["bill_after_change"]
        assert bill["budget"] == "100.00" and "over_budget_by" in bill
        fit = bill["budget_fit"]                       # attached by the graph, not requested by the LLM
        assert set(fit) >= {"feasible", "new_total", "swaps", "message"}
        return AIMessage(f"You are over budget by ₹{bill['over_budget_by']}.")

    llm = ScriptedLLM(script=[call("set_budget", amount=100), call("update_cart", product_id=pid, quantity=1),
                              answer])
    r = ShoppingAssistant(llm=llm).chat(session, "under ₹100 please")
    assert r.grounded and r.bill["over_budget_by"] == r.bill["final_total"] - r.bill["budget"]


@pytest.mark.db
def test_invented_number_triggers_one_rewrite(session):
    good = AIMessage("Your cart is empty — what would you like to buy?")
    llm = ScriptedLLM(script=[AIMessage("Your total is ₹999.99, find it in aisle 42."), good])
    r = ShoppingAssistant(llm=llm).chat(session, "what's my total?")
    assert r.reply == good.content and r.grounded
    note = llm.seen[1][-1]                       # the LLM was told what was wrong
    assert isinstance(note, HumanMessage) and "₹999.99" in note.content and "Aisle 42" in note.content


@pytest.mark.db
def test_still_ungrounded_after_retry_is_reported(session):
    llm = ScriptedLLM(script=[AIMessage("Total ₹999.99"), AIMessage("Total is ₹888")])
    r = ShoppingAssistant(llm=llm).chat(session, "total?")
    assert not r.grounded and r.ungrounded == ["₹888"]


@pytest.mark.db
def test_search_then_quote_price_is_grounded(session):
    def quote(messages):
        top = last_tool(messages)[0]
        return AIMessage(f"{top['name']} is ₹{top['price']} in Aisle {top['aisle_no']}, shelf {top['shelf_code']}.")

    llm = ScriptedLLM(script=[call("search_products", query="toned milk"), quote])
    r = ShoppingAssistant(llm=llm).chat(session, "where is toned milk?")
    assert r.grounded and "Aisle 2" in r.reply


@pytest.mark.db
def test_memory_and_cart_persist_across_turns(db, session):
    pid = pick(db, "stock_qty >= 10")
    llm = ScriptedLLM(script=[call("update_cart", product_id=pid, quantity=2), AIMessage("Added."),
                              AIMessage("Anything else?")])
    bot = ShoppingAssistant(llm=llm)
    first = bot.chat(session, "add 2")
    second = bot.chat(session, "thanks")
    assert first.cart_id == second.cart_id and second.bill["item_count"] == 2
    assert any(isinstance(m, HumanMessage) and m.content == "add 2" for m in llm.seen[-1])


@pytest.mark.db
def test_conversation_memory_survives_a_server_restart(db, session):
    """Memory is stored in PostgreSQL: a NEW assistant object (= restarted server) continues the chat."""
    pid = pick(db, "stock_qty >= 10")
    first = ShoppingAssistant(llm=ScriptedLLM(script=[call("update_cart", product_id=pid, quantity=2),
                                                      AIMessage("Added.")])).chat(session, "add 2 please")
    later_llm = ScriptedLLM(script=[AIMessage("You asked for 2.")])
    restarted = ShoppingAssistant(llm=later_llm)
    assert restarted.session(session)["cart_id"] == first.cart_id
    second = restarted.chat(session, "what did I ask?")
    assert second.cart_id == first.cart_id and second.bill["item_count"] == 2
    assert any(isinstance(m, HumanMessage) and m.content == "add 2 please" for m in later_llm.seen[0])
    n = db.execute(text("SELECT count(*) FROM agent_checkpoints WHERE thread_id = :s"), {"s": session}).scalar()
    assert n > 0


@pytest.mark.db
def test_suggestion_cards_for_substitutes_and_unadded_search_results(db, session):
    oos = pick(db, "stock_qty = 0")

    def answer(messages):
        return AIMessage("Here are some options.")

    llm = ScriptedLLM(script=[call("update_cart", product_id=oos, quantity=1),
                              call("search_products", query="basmati rice"), answer])
    r = ShoppingAssistant(llm=llm).chat(session, "add it, and where is rice?")
    kinds = {g["kind"]: g for g in r.suggestions}
    subs = kinds["substitutes"]
    assert subs["for_product_id"] == oos and subs["items"]
    assert all(i["in_stock"] and i["price"] for i in subs["items"])
    search = kinds["search"]
    assert search["title"] == "Results for “basmati rice”" and len(search["items"]) <= 4

    # values on the cards are database values
    row = db.execute(text("SELECT current_price, shelf_code FROM v_store_catalog WHERE product_id = :p"),
                     {"p": search["items"][0]["product_id"]}).one()
    assert (D(str(search["items"][0]["price"])), search["items"][0]["shelf_code"]) == (row[0], row[1])


@pytest.mark.db
def test_search_results_that_were_added_are_not_shown_as_cards(db, session):
    def add_top(messages):
        return call("update_cart", product_id=last_tool(messages)[0]["product_id"], quantity=1)

    llm = ScriptedLLM(script=[call("search_products", query="toned milk"), add_top, AIMessage("Added.")])
    assert ShoppingAssistant(llm=llm).chat(session, "add toned milk").suggestions == []


@pytest.mark.db
def test_fallback_model_answers_when_main_model_is_overloaded(session):
    main = ScriptedLLM(script=[RuntimeError("503 UNAVAILABLE: high demand")])
    backup = ScriptedLLM(script=[AIMessage("Hi from the fallback model!")])
    r = ShoppingAssistant(llm=main, fallback_llm=backup).chat(session, "hi")
    assert r.reply == "Hi from the fallback model!" and len(main.seen) == 1


@pytest.mark.db
def test_short_rate_limit_waits_and_retries_same_model(session):
    main = ScriptedLLM(script=[RuntimeError("429 RESOURCE_EXHAUSTED. Please retry in 0.1s."),
                               AIMessage("Done after waiting.")])
    r = ShoppingAssistant(llm=main).chat(session, "hi")
    assert r.reply == "Done after waiting." and len(main.seen) == 2


@pytest.mark.db
def test_ai_service_down_gives_polite_reply_not_a_crash(session):
    from smartcart.agent.graph import LLM_UNAVAILABLE_REPLY
    down = RuntimeError("503 UNAVAILABLE")
    r = ShoppingAssistant(llm=ScriptedLLM(script=[down]),
                          fallback_llm=ScriptedLLM(script=[down])).chat(session, "hi")
    assert r.reply == LLM_UNAVAILABLE_REPLY and r.grounded


@pytest.mark.db
def test_checkout_through_agent_opens_a_new_cart(db, session, restore_inventory):
    pid = pick(db, "stock_qty >= 10")
    llm = ScriptedLLM(script=[call("update_cart", product_id=pid, quantity=1), AIMessage("Added."),
                              call("checkout"), lambda m: AIMessage(f"Order #{last_tool(m)['order']['order_id']} placed.")])
    bot = ShoppingAssistant(llm=llm)
    first = bot.chat(session, "add one")
    done = bot.chat(session, "check out")
    assert "placed" in done.reply and done.cart_id != first.cart_id and done.bill["item_count"] == 0
