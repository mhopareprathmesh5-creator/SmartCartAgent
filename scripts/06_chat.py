"""Chat with the shopping agent in the terminal (needs GOOGLE_API_KEY in .env).

    python scripts/06_chat.py            # add --trace to see every tool call

Try:  "I need 2 toned milk, oats, instant coffee and Britannia brown bread, budget ₹600"
      "where is basmati rice?"   "remove the coffee"   "check out"
Commands:  /bill   show the live bill      /quit   exit
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _common  # noqa: E402,F401  (UTF-8 console for ₹)
from smartcart.agent import ShoppingAssistant  # noqa: E402
from smartcart.agent.llm import LLMNotConfigured  # noqa: E402


def show_bill(bill: dict):
    if not bill["items"]:
        print("  (cart is empty)")
        return
    for it in bill["items"]:
        print(f"  {it['qty']} × {it['name'][:45]:<45} ₹{it['line_total']}")
    for c in bill["coupons_applied"]:
        print(f"  {c['code']:<12} -₹{c['discount']}")
    line = f"  TOTAL ₹{bill['final_total']}"
    if "over_budget_by" in bill:
        line += f"   (over budget by ₹{bill['over_budget_by']})"
    elif "budget_remaining" in bill:
        line += f"   (₹{bill['budget_remaining']} left of budget)"
    print(line)


def main():
    trace = "--trace" in sys.argv
    try:
        bot = ShoppingAssistant()
    except LLMNotConfigured as e:
        sys.exit(str(e))
    session = f"cli-{uuid.uuid4().hex[:6]}"
    print("SmartMart assistant — type your shopping request (/bill, /quit)\n")
    last_bill = None
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text == "/quit":
            break
        if text == "/bill":
            show_bill(last_bill) if last_bill else print("  (cart is empty)")
            continue
        r = bot.chat(session, text)
        last_bill = r.bill
        if trace:
            for c in r.tool_calls:
                print(f"  · {c['tool']}({', '.join(f'{k}={v!r}' for k, v in c['args'].items())})")
        print(f"\nassistant> {r.reply}\n")
        print(f"  [grounding: {'OK — every ₹ amount / aisle came from the database' if r.grounded else 'FLAGGED ' + str(r.ungrounded)}]")
        show_bill(r.bill)
        print()


if __name__ == "__main__":
    main()
