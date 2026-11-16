"""User study (Phase II): is shopping faster and as correct with the assistant than by hand?

Within-subjects design: each participant does a shopping task twice — once with the AI
assistant (chat) and once manually (search box + add buttons, the classic e-commerce
way) — on two different but equally sized task lists, in counterbalanced order. The
server records the time from Start to Finish and scores the final cart with exactly the
same code as the evaluation harness (right product types, quantities, budget), so the
comparison is objective. Results: GET /study/summary or scripts/08_study_report.py.

No numbers are invented: every run in the table is a real person's session.
"""
import statistics
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import text

from smartcart import tools as T
from smartcart.db import get_engine
from smartcart.eval.goals import Goal, Want
from smartcart.eval.metrics import check_goal

# Two task lists of similar size and difficulty (each has 4 items, one has an out-of-stock item).
TASKS = {
    "A": Goal("A", "Breakfast list",
              ["Buy: 2 toned milk, 1 oats, 1 instant coffee and 1 Britannia brown bread "
               "(if it is out of stock, take any other brown bread)."],
              want=[Want("Milk", 2), Want("Oats & Porridge", 1), Want("Instant Coffee", 1),
                    Want("Brown, Wheat & Multigrain", 1)]),
    "B": Goal("B", "Weekly basics",
              ["Buy: 1 atta, 1 toor dal, 1 sunflower oil and 2 packs of Maggi masala noodles. "
               "Keep the total under ₹600."],
              want=[Want("Atta Whole Wheat", 1), Want("Toor, Channa & Moong Dal", 1),
                    Want("Sunflower, Rice Bran Oil", 1), Want("Instant Noodles", 2)],
              budget=Decimal("600.00")),
}


def _ensure_table(conn):
    conn.execute(text("""CREATE TABLE IF NOT EXISTS study_runs (
        run_id SERIAL PRIMARY KEY, participant TEXT NOT NULL,
        mode TEXT NOT NULL CHECK (mode IN ('assistant', 'manual')), task_id TEXT NOT NULL,
        session_id TEXT NOT NULL, cart_id INTEGER NOT NULL, started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        finished_at TIMESTAMPTZ, seconds NUMERIC(8,1), success BOOLEAN, checks JSONB, cart JSONB,
        final_total NUMERIC(10,2), messages INTEGER)"""))


def tasks() -> list[dict]:
    return [{"task_id": t.id, "title": t.title, "instructions": t.turns[0]} for t in TASKS.values()]


def start_run(participant: str, mode: str, task_id: str) -> dict:
    """Begin a timed run. Manual mode gets a plain cart now; assistant mode uses the chat session's
    cart (created by the first chat message), so the cart id is resolved at finish."""
    if mode not in ("assistant", "manual"):
        raise ValueError("mode must be 'assistant' or 'manual'")
    if task_id not in TASKS:
        raise ValueError(f"task must be one of {sorted(TASKS)}")
    if not participant.strip():
        raise ValueError("participant code is required")
    session = f"study-{mode}-{uuid.uuid4().hex[:8]}"
    cart_id = T.create_cart(session) if mode == "manual" else 0
    with get_engine().begin() as conn:
        _ensure_table(conn)
        run_id = conn.execute(text("""INSERT INTO study_runs (participant, mode, task_id, session_id, cart_id)
                                      VALUES (:p, :m, :t, :s, :c) RETURNING run_id"""),
                              {"p": participant.strip(), "m": mode, "t": task_id, "s": session, "c": cart_id}).scalar()
    return {"run_id": run_id, "session_id": session, "cart_id": cart_id, "mode": mode, **tasks_by_id(task_id)}


def tasks_by_id(task_id: str) -> dict:
    t = TASKS[task_id]
    return {"task_id": t.id, "title": t.title, "instructions": t.turns[0]}


def finish_run(run_id: int, cart_id: Optional[int] = None, messages: Optional[int] = None,
               budget: Optional[str] = None) -> dict:
    """Stop the clock and score the cart by code (same checks as the evaluation harness)."""
    with get_engine().begin() as conn:
        run = conn.execute(text("SELECT * FROM study_runs WHERE run_id = :r FOR UPDATE"), {"r": run_id}).mappings().first()
        if run is None:
            raise ValueError(f"No study run {run_id}")
        if run["finished_at"] is not None:
            raise ValueError("This run is already finished")
        cart_id = cart_id or run["cart_id"]
        rows = [dict(r) for r in conn.execute(text("""
            SELECT ci.product_id, v.name, v.brand, v.product_type, ci.quantity AS qty, v.stock_qty
            FROM cart_items ci JOIN v_store_catalog v ON v.product_id = ci.product_id
            WHERE ci.cart_id = :c ORDER BY ci.product_id"""), {"c": cart_id}).mappings().all()] if cart_id else []
        bill = T.compute_bill(cart_id) if cart_id else None
        goal = TASKS[run["task_id"]]
        final_total = bill.final_total if bill else Decimal("0.00")
        # the budget is a constraint of the task itself, so check the total, not whether a budget was "set"
        checks = check_goal(Goal(goal.id, goal.title, goal.turns, want=goal.want), rows,
                            {"final_total": str(final_total)}, None, [], {})
        if goal.budget is not None:
            checks.append({"check": f"total ≤ ₹{goal.budget}", "passed": final_total <= goal.budget,
                           "detail": f"₹{final_total}", "pending": False})
        success = all(c["passed"] for c in checks)
        conn.execute(text("""
            UPDATE study_runs SET finished_at = now(), cart_id = :c,
                   seconds = round(EXTRACT(EPOCH FROM now() - started_at)::numeric, 1),
                   success = :ok, checks = CAST(:checks AS jsonb), cart = CAST(:cart AS jsonb),
                   final_total = :total, messages = :msgs
            WHERE run_id = :r"""),
            {"r": run_id, "c": cart_id or 0, "ok": success, "total": final_total, "msgs": messages,
             "checks": _json(checks), "cart": _json(rows)})
        done = conn.execute(text("SELECT * FROM study_runs WHERE run_id = :r"), {"r": run_id}).mappings().one()
    return dict(done)


def _json(obj) -> str:
    import json
    return json.dumps(obj, default=str, ensure_ascii=False)


def runs() -> list[dict]:
    with get_engine().begin() as conn:
        _ensure_table(conn)
        rows = conn.execute(text("SELECT run_id, participant, mode, task_id, started_at, finished_at, seconds, "
                                 "success, final_total, messages FROM study_runs ORDER BY run_id")).mappings().all()
    return [dict(r) for r in rows]


def summary() -> dict:
    """Per mode: completed runs, success rate, mean/median time. Paired: participants who did both modes."""
    done = [r for r in runs() if r["finished_at"] is not None]
    out = {"runs": len(done), "modes": {}}
    for mode in ("assistant", "manual"):
        rs = [r for r in done if r["mode"] == mode]
        secs = [float(r["seconds"]) for r in rs]
        out["modes"][mode] = {
            "runs": len(rs),
            "success_pct": round(100 * sum(r["success"] for r in rs) / len(rs), 1) if rs else None,
            "mean_seconds": round(statistics.mean(secs), 1) if secs else None,
            "median_seconds": round(statistics.median(secs), 1) if secs else None,
        }
    by_person: dict[str, dict] = {}
    for r in done:
        by_person.setdefault(r["participant"], {})[r["mode"]] = float(r["seconds"])
    paired = [(p["manual"], p["assistant"]) for p in by_person.values() if {"manual", "assistant"} <= set(p)]
    out["paired_participants"] = len(paired)
    if paired:
        saved = [m - a for m, a in paired]
        out["mean_seconds_saved"] = round(statistics.mean(saved), 1)
        out["mean_time_saved_pct"] = round(100 * statistics.mean(s / m for s, (m, _) in zip(saved, paired)), 1)
    return out


def delete_runs(participant_prefix: str) -> int:
    """Remove runs (e.g. a rehearsal) whose participant code starts with the prefix."""
    with get_engine().begin() as conn:
        _ensure_table(conn)
        return conn.execute(text("DELETE FROM study_runs WHERE participant LIKE :p"),
                            {"p": participant_prefix + "%"}).rowcount
