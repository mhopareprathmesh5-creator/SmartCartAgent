"""The LangGraph state machine.

    START ─► agent ──(tool calls?)──► tools ──► route_after_tools
               ▲  │                               │  stock failure  ─► auto_substitutes ─┐
               │  │                               │  cart changed   ─► refresh_bill ◄────┘ (if cart changed)
               │  │                               │  otherwise      ─► agent
               │  └──(final answer)──► grounding_check ──(ungrounded, 1st time)──► agent
               │                                   └──(grounded / retried)──► END
               └──────────────── auto_substitutes / refresh_bill ───────────────┘

The LLM decides WHAT to do (which tools, which products). The graph enforces
the parts that must not depend on the LLM remembering:
  - an out-of-stock result ALWAYS gets ranked substitutes attached,
  - every cart change ALWAYS gets the freshly computed bill (with budget status) attached,
  - every final answer is grounding-checked before the shopper sees it.
Attachments are merged into the triggering tool result (same message id), so the
conversation stays a valid call/response sequence for any LLM provider.
"""
import json
import logging
import re
import time
from dataclasses import asdict
from decimal import Decimal
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from smartcart import tools as T
from smartcart.agent.grounding import grounded_numbers, message_text, ungrounded_values
from smartcart.agent.prompts import GROUNDING_RETRY_NOTE, SYSTEM_PROMPT
from smartcart.agent.tools import AGENT_TOOLS, bill_summary, to_json

MAX_GROUNDING_RETRIES = 1
LLM_UNAVAILABLE_REPLY = ("Sorry, the AI service is busy right now. Your cart is saved — "
                         "please send your message again in a moment.")
LLM_RATE_LIMITED_REPLY = ("Sorry, the AI request limit was reached (Gemini free tier allows a few "
                          "requests per minute). Your cart is saved — please try again in a minute.")
MAX_RATE_LIMIT_WAIT = 15     # seconds we are willing to pause inside one turn
log = logging.getLogger(__name__)


class ShopState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    session_id: str
    cart_id: int
    budget: Optional[str]              # rupees as a string, set by the set_budget tool
    grounding_retries: int
    ungrounded: list[str]              # values flagged in the last final answer (empty = clean)


# ---------------------------------------------------------------- helpers
def last_step_results(state: ShopState) -> tuple[AIMessage, list[ToolMessage]]:
    """The last AI tool-calling message and the tool results that answered it."""
    msgs = state["messages"]
    i = max(k for k, m in enumerate(msgs) if isinstance(m, AIMessage))
    return msgs[i], [m for m in msgs[i + 1:] if isinstance(m, ToolMessage)]


def _payload(m: ToolMessage):
    try:
        return json.loads(message_text(m))
    except json.JSONDecodeError:
        return None


def stock_failures(state: ShopState) -> list[tuple[ToolMessage, int, int]]:
    """(tool message, product_id, quantity) for each result saying stock is insufficient."""
    ai, results = last_step_results(state)
    args = {c["id"]: c["args"] for c in ai.tool_calls}
    out = []
    for m in results:
        p = _payload(m)
        if not isinstance(p, dict) or "auto_substitutes" in p:
            continue
        if m.name == "update_cart" and p.get("ok") is False:
            out.append((m, p["product_id"], int(args.get(m.tool_call_id, {}).get("quantity", 1))))
        elif m.name == "check_stock" and p.get("can_fulfil") is False:
            out.append((m, p["product_id"], p["requested_qty"]))
    return out


def cart_changes(state: ShopState) -> list[ToolMessage]:
    _, results = last_step_results(state)
    return [m for m in results if m.name == "update_cart"
            and isinstance(p := _payload(m), dict) and p.get("ok") is True and "bill_after_change" not in p]


def _augment(m: ToolMessage, **extra) -> ToolMessage:
    """Same message (same id -> replaced in state) with extra fields merged into its JSON."""
    return ToolMessage(to_json({**_payload(m), **extra}), tool_call_id=m.tool_call_id,
                       name=m.name, id=m.id)


# ---------------------------------------------------------------- graph
def _retry_delay(error: Exception) -> Optional[float]:
    """Seconds Google asks us to wait on a rate-limit (429) error, if stated."""
    m = re.search(r"retry in (\d+(?:\.\d+)?)s", str(error))
    return float(m.group(1)) if m and "429" in str(error) else None


def build_graph(llm, checkpointer=None, fallback_llm=None):
    # main model first; if it fails (503 overloaded / 429 quota) the fallback model is tried
    models = [llm.bind_tools(AGENT_TOOLS)]
    if fallback_llm is not None:
        models.append(fallback_llm.bind_tools(AGENT_TOOLS))

    def call_llm(messages):
        errors = []
        for model in models:
            for attempt in range(2):
                try:
                    return model.invoke(messages)
                except Exception as e:
                    errors.append(e)
                    delay = _retry_delay(e)
                    log.warning("LLM call failed (%s): %s", type(e).__name__, str(e)[:200])
                    if attempt == 0 and delay is not None and delay <= MAX_RATE_LIMIT_WAIT:
                        time.sleep(delay + 0.5)      # short rate-limit pause: wait, retry same model
                        continue
                    break
        raise errors[-1]

    def agent(state: ShopState):
        try:
            reply = call_llm([SystemMessage(SYSTEM_PROMPT)] + state["messages"])
        except Exception as e:       # AI service down: answer politely instead of crashing the session
            text = LLM_RATE_LIMITED_REPLY if "429" in str(e) else LLM_UNAVAILABLE_REPLY
            reply = AIMessage(text, name="service_error")
        return {"messages": [reply]}

    def route_after_agent(state: ShopState):
        last = state["messages"][-1]
        return "tools" if isinstance(last, AIMessage) and last.tool_calls else "grounding_check"

    def route_after_tools(state: ShopState):
        if stock_failures(state):
            return "auto_substitutes"
        if cart_changes(state):
            return "refresh_bill"
        return "agent"

    def auto_substitutes(state: ShopState):
        updated = []
        for m, pid, qty in stock_failures(state):
            subs = T.find_substitutes(pid, quantity=qty, limit=3)
            updated.append(_augment(m, auto_substitutes=[asdict(s) for s in subs],
                                    note="Substitutes attached automatically (ranked best first)."))
        return {"messages": updated}

    def route_after_substitutes(state: ShopState):
        return "refresh_bill" if cart_changes(state) else "agent"

    def refresh_bill(state: ShopState):
        changes = cart_changes(state)
        bill = bill_summary(T.compute_bill(state["cart_id"]), state.get("budget"))
        if "over_budget_by" in bill:     # over budget: always attach the fewest-swaps plan (computed by code)
            plan = T.fit_budget(state["cart_id"], Decimal(state["budget"]))
            bill["budget_fit"] = {
                "feasible": plan.feasible, "new_total": plan.new_total, "total_saving": plan.total_saving,
                "message": plan.message,
                "swaps": [{"replace": s.from_name, "with": s.to_name, "brand": s.to_brand,
                           "new_unit_price": s.to_unit_price, "quantity": s.quantity,
                           "from_product_id": s.from_product_id, "to_product_id": s.to_product_id}
                          for s in plan.swaps]}
        # attach the bill once, to the last cart change of this step
        return {"messages": [_augment(changes[-1], bill_after_change=bill)]}

    def grounding_check(state: ShopState):
        reply = message_text(state["messages"][-1])
        bad = ungrounded_values(reply, grounded_numbers(state["messages"]))
        retries = state.get("grounding_retries", 0)
        if bad and retries < MAX_GROUNDING_RETRIES:
            note = HumanMessage(GROUNDING_RETRY_NOTE.format(items=", ".join(bad)), name="grounding_guard")
            return {"messages": [note], "grounding_retries": retries + 1, "ungrounded": bad}
        return {"grounding_retries": 0, "ungrounded": bad}

    def route_after_grounding(state: ShopState):
        last = state["messages"][-1]
        return "agent" if isinstance(last, HumanMessage) and last.name == "grounding_guard" else END

    g = StateGraph(ShopState)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(AGENT_TOOLS))
    g.add_node("auto_substitutes", auto_substitutes)
    g.add_node("refresh_bill", refresh_bill)
    g.add_node("grounding_check", grounding_check)

    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route_after_agent, ["tools", "grounding_check"])
    g.add_conditional_edges("tools", route_after_tools, ["auto_substitutes", "refresh_bill", "agent"])
    g.add_conditional_edges("auto_substitutes", route_after_substitutes, ["refresh_bill", "agent"])
    g.add_edge("refresh_bill", "agent")
    g.add_conditional_edges("grounding_check", route_after_grounding, ["agent", END])
    return g.compile(checkpointer=checkpointer)
