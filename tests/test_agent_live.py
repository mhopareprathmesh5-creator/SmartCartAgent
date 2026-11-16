"""LIVE tests against the real Gemini model. Not run by default (they cost API calls).

    python -m pytest -m live -v
"""
import os
import uuid

import pytest

from tests.conftest import delete_session

pytestmark = [pytest.mark.live, pytest.mark.db,
              pytest.mark.skipif(not os.environ.get("GOOGLE_API_KEY"), reason="GOOGLE_API_KEY not set")]


@pytest.fixture(scope="module")
def bot():
    from smartcart.agent import ShoppingAssistant
    return ShoppingAssistant()


@pytest.fixture
def session():
    s = f"pytest-live-{uuid.uuid4().hex[:8]}"
    yield s
    delete_session(s)


def test_shopping_request_fills_cart_with_grounded_reply(bot, session):
    r = bot.chat(session, "I need 2 toned milk, oats and instant coffee. Budget ₹600.")
    tools = [c["tool"] for c in r.tool_calls]
    assert "search_products" in tools and "update_cart" in tools and "set_budget" in tools
    assert r.bill["item_count"] >= 4
    assert r.grounded, f"ungrounded values: {r.ungrounded}\n{r.reply}"


def test_out_of_stock_item_is_substituted(bot, session):
    r = bot.chat(session, "Add one Britannia Brown Bread please.")
    names = [i["name"] for i in r.bill["items"]]          # Britannia "Brown Bread" is out of stock
    assert r.bill["item_count"] >= 1 and "Brown Bread" not in names
    assert "update_cart" in [c["tool"] for c in r.tool_calls]
    assert r.grounded, f"ungrounded values: {r.ungrounded}\n{r.reply}"


def test_location_question_is_grounded(bot, session):
    r = bot.chat(session, "Where can I find basmati rice?")
    assert "search_products" in [c["tool"] for c in r.tool_calls]
    assert r.grounded, f"ungrounded values: {r.ungrounded}\n{r.reply}"
