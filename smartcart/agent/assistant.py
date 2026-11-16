"""ShoppingAssistant: one object that runs conversations through the graph.

Each chat session (thread) gets its own cart and its own conversation memory
(LangGraph checkpointer keyed by session_id, stored in PostgreSQL).
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage
from smartcart import tools as T
from smartcart.agent.graph import build_graph
from smartcart.agent.grounding import message_text
from smartcart.agent.memory import PostgresSaver
from smartcart.agent.suggestions import build_suggestions
from smartcart.agent.tools import bill_summary
from smartcart.tools.budget import BudgetPlan
from smartcart.tools.models import CartUpdate, CheckoutResult, money


@dataclass
class ChatReply:
    session_id: str
    cart_id: int
    reply: str
    grounded: bool                 # True if every ₹ amount / aisle in the reply came from a tool
    ungrounded: list[str]
    tool_calls: list[dict]         # what the agent did this turn: [{"tool", "args"}]
    bill: dict = field(default_factory=dict)
    suggestions: list[dict] = field(default_factory=list)   # product cards (see suggestions.py)
    llm_calls: int = 0             # LLM requests this turn (for evaluation / rate-limit pacing)
    models: list[str] = field(default_factory=list)          # which model answered each call
    grounding_retried: bool = False   # True if the guard had to send the LLM back to rewrite


class ShoppingAssistant:
    def __init__(self, llm=None, checkpointer=None, recursion_limit: int = 40, fallback_llm=None):
        if llm is None:
            from smartcart.agent.llm import get_fallback_llm, get_llm
            llm, fallback_llm = get_llm(), get_fallback_llm()
        # conversation memory lives in PostgreSQL, so it survives a server restart (memory.py)
        self.graph = build_graph(llm, checkpointer or PostgresSaver(), fallback_llm)
        self.recursion_limit = recursion_limit

    def _config(self, session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}, "recursion_limit": self.recursion_limit}

    def chat(self, session_id: str, message: str) -> ChatReply:
        config = self._config(session_id)
        existing = self.graph.get_state(config).values
        before = len(existing.get("messages", []))

        inputs = {"messages": [HumanMessage(message)]}
        if not existing:                                 # first message of this session
            inputs.update(session_id=session_id, cart_id=T.create_cart(session_id),
                          budget=None, grounding_retries=0, ungrounded=[])
        state = self.graph.invoke(inputs, config)

        new = state["messages"][before:]
        final = next(m for m in reversed(new) if isinstance(m, AIMessage) and not m.tool_calls)
        calls = [{"tool": c["name"], "args": c["args"]}
                 for m in new if isinstance(m, AIMessage) for c in m.tool_calls]
        bill = bill_summary(T.compute_bill(state["cart_id"]), state.get("budget"))
        answers = [m for m in new if isinstance(m, AIMessage) and m.name != "service_error"]
        return ChatReply(session_id, state["cart_id"], message_text(final),
                         not state.get("ungrounded"), state.get("ungrounded", []), calls, bill,
                         build_suggestions(new), len(answers),
                         [m.response_metadata.get("model_name", "") for m in answers],
                         any(isinstance(m, HumanMessage) and m.name == "grounding_guard" for m in new))

    # ---- direct cart actions from the UI (same cart as the agent, so both stay in sync) ----
    def session(self, session_id: str) -> Optional[dict]:
        """Current cart + bill of a session, or None if the session doesn't exist (yet)."""
        state = self.graph.get_state(self._config(session_id)).values
        if not state:
            return None
        return {"session_id": session_id, "cart_id": state["cart_id"], "budget": state.get("budget"),
                "bill": bill_summary(T.compute_bill(state["cart_id"]), state.get("budget"))}

    def set_item(self, session_id: str, product_id: int, quantity: int) -> tuple[CartUpdate, dict]:
        view = self._require(session_id)
        update = T.update_cart(view["cart_id"], product_id, quantity, mode="set")
        return update, self.session(session_id)

    def checkout(self, session_id: str) -> tuple[CheckoutResult, dict]:
        view = self._require(session_id)
        result = T.checkout(view["cart_id"])
        if result.ok:   # same behaviour as the agent's checkout tool: continue with a fresh cart
            self.graph.update_state(self._config(session_id), {"cart_id": T.create_cart(session_id)})
        return result, self.session(session_id)

    def set_budget(self, session_id: str, amount: Optional[Decimal]) -> dict:
        """Set (or clear, with None) the session budget — the same value the agent's set_budget stores."""
        self._require(session_id)
        value = None if amount is None else str(money(amount))
        self.graph.update_state(self._config(session_id), {"budget": value})
        return self.session(session_id)

    def budget_plan(self, session_id: str) -> BudgetPlan:
        view = self._require(session_id)
        if view["budget"] is None:
            raise ValueError("No budget set for this session")
        return T.fit_budget(view["cart_id"], Decimal(view["budget"]))

    def apply_swaps(self, session_id: str, swaps: list[tuple[int, int, int]]) -> tuple[list[CartUpdate], dict]:
        """Replace products: each (from_product_id, to_product_id, quantity). The new product is
        added first, so if it is refused (stock) the original stays in the cart."""
        view = self._require(session_id)
        results = []
        for old, new, qty in swaps:
            add = T.update_cart(view["cart_id"], new, qty, mode="set")
            results.append(add)
            if add.ok and old != new:
                T.update_cart(view["cart_id"], old, 0)
        return results, self.session(session_id)

    def _require(self, session_id: str) -> dict:
        view = self.session(session_id)
        if view is None:
            raise SessionNotFound(f"No chat session {session_id!r} — send a chat message first")
        return view


class SessionNotFound(T.ToolError):
    pass
