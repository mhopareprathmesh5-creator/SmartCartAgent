"""User-study results: assistant vs manual shopping (data collected on the web app's "User study" tab).

    python scripts/08_study_report.py                 # summary + every run, and writes docs/study/results.csv
    python scripts/08_study_report.py --delete-prefix TEST   # remove rehearsal runs (participant codes TEST...)

Only real sessions are in the table; nothing is simulated.
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import _common  # noqa: E402,F401  (UTF-8 console)
from smartcart import study  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete-prefix", help="delete runs whose participant code starts with this")
    args = ap.parse_args()
    if args.delete_prefix:
        print(f"Deleted {study.delete_runs(args.delete_prefix)} run(s)")
        return

    runs = [r for r in study.runs() if r["finished_at"] is not None]
    if not runs:
        print("No completed study runs yet. Run the study on http://127.0.0.1:8000/#/study")
        return
    print(f"{'run':>4} {'participant':<12} {'mode':<10} {'task':<5} {'seconds':>8} {'correct':<8} {'total':>9}")
    for r in runs:
        print(f"{r['run_id']:>4} {r['participant']:<12} {r['mode']:<10} {r['task_id']:<5} {r['seconds']:>8} "
              f"{'yes' if r['success'] else 'no':<8} {r['final_total']:>9}")
    s = study.summary()
    print()
    for mode, m in s["modes"].items():
        print(f"{mode:<10} runs {m['runs']:>3}   correct {m['success_pct']}%   "
              f"mean {m['mean_seconds']} s   median {m['median_seconds']} s")
    if s["paired_participants"]:
        print(f"\n{s['paired_participants']} participant(s) did both methods: the assistant saved "
              f"{s['mean_seconds_saved']} s on average ({s['mean_time_saved_pct']}% of their manual time).")
    out = ROOT / "docs" / "study"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(runs[0]))
        w.writeheader()
        w.writerows(runs)
    print(f"\nWrote {out / 'results.csv'}")


if __name__ == "__main__":
    main()
