"""Grounding check: is every number the agent tells the shopper backed by a tool result?

Collects every number that appeared in tool results (and in the shopper's own
messages, e.g. their budget), then finds every rupee amount and aisle number in
the agent's reply. Anything in the reply that is not in that set was invented
(or computed) by the LLM and is reported as ungrounded.
"""
import json
import re
from decimal import Decimal, InvalidOperation

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage

# Hindi / Marathi replies: "₹४५" or "४५ रुपये", "गलियारा 2" (Hindi) / "आयल 2", "रांग 2" (Marathi).
# \d in Python regex matches Devanagari digits too; _num() converts them to ASCII.
AMOUNT = r"(\d+(?:,\d+)*(?:\.\d+)?)"           # 1,234.50 — a trailing comma is punctuation, not part of it
MONEY_RE = re.compile(rf"(?:₹|\bRs\.?|\bINR|रु\.?)\s*{AMOUNT}"
                      rf"|{AMOUNT}\s*(?:रुपये|रुपए|रुपया|रुपयांना|रुपयांत)", re.IGNORECASE)
AISLE_RE = re.compile(r"(?:\baisle|गलियारा|गलियारे|आयल|आइल|रांग|रांगेत)\s*"
                      r"(?:no\.?\s*|नं\.?\s*|नंबर\s*|क्र\.?\s*|क्रमांक\s*|#\s*)?(\d+)",
                      re.IGNORECASE)
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
PAISA = Decimal("0.01")
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _num(s) -> Decimal | None:
    try:
        return Decimal(str(s).translate(DEVANAGARI_DIGITS).replace(",", "")).quantize(PAISA)
    except (InvalidOperation, ValueError):
        return None


def _money(m: re.Match) -> str:
    return m.group(1) or m.group(2)


def _collect(obj, out: set):
    if isinstance(obj, dict):
        for v in obj.values():
            _collect(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, out)
    elif isinstance(obj, bool) or obj is None:
        return
    elif isinstance(obj, (int, float)):
        out.add(_num(obj))
    elif isinstance(obj, str):
        for m in NUMBER_RE.findall(obj):     # also numbers inside text like "Needs ₹100.00 of Amul"
            if (n := _num(m)) is not None:
                out.add(n)


def message_text(m: BaseMessage) -> str:
    c = m.content
    if isinstance(c, str):
        return c
    return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)


def grounded_numbers(messages: list[BaseMessage]) -> set[Decimal]:
    allowed: set = set()
    for m in messages:
        if isinstance(m, ToolMessage):
            text = message_text(m)
            try:
                _collect(json.loads(text), allowed)
            except (json.JSONDecodeError, TypeError):
                _collect(text, allowed)
        elif isinstance(m, HumanMessage):
            _collect(message_text(m), allowed)
    allowed.discard(None)
    return allowed


def ungrounded_values(reply: str, allowed: set[Decimal]) -> list[str]:
    """Rupee amounts and aisle numbers in `reply` that are not in `allowed` (deduplicated)."""
    bad = []
    for m in MONEY_RE.finditer(reply):
        if _num(_money(m)) not in allowed:
            bad.append(f"₹{_money(m)}")
    for m in AISLE_RE.finditer(reply):
        if _num(m.group(1)) not in allowed:
            bad.append(f"Aisle {m.group(1)}")
    return list(dict.fromkeys(bad))
