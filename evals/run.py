"""CLI runner: ``python -m evals.run`` (add ``--live`` for the answer tier).

Prints a small score table for Tier 1 (always) and Tier 2 (only with --live and
a reachable model).
"""

from __future__ import annotations

import argparse

from .answer_quality import run_answer_quality
from .live import live_model_available
from .routing import run_routing, score


def _print_routing() -> int:
    results = run_routing()
    print("Tier 1 — Tool routing (offline, deterministic stub)\n")
    print(f"  {'id':<22}{'scenario':<26}{'expected':<26}{'got':<26}ok")
    print(f"  {'-' * 96}")
    for r in results:
        exp = ",".join(r.case.expected_tools) or "—"
        got = ",".join(r.called_tools) or "—"
        mark = "✓" if r.passed else "✗"
        print(f"  {r.case.id:<22}{r.case.scenario_tag:<26}{exp:<26}{got:<26}{mark}")
    hits, total = score(results)
    pct = 100 * hits / total if total else 0
    print(f"\n  Score: {hits}/{total} ({pct:.0f}%)\n")
    return 0 if hits == total else 1


def _print_answer_quality() -> int:
    ok, reason = live_model_available()
    print("Tier 2 — Answer quality (live, end-to-end)\n")
    if not ok:
        print(f"  SKIPPED — {reason}. Set the provider key/endpoint to run.\n")
        return 0
    print(f"  Running against: {reason}\n")
    results = run_answer_quality()
    hits = 0
    for r in results:
        mark = "✓" if r.passed else "✗"
        hits += r.passed
        print(f"  {mark} {r.case.id:<18} {r.detail}")
        if not r.passed:
            print(f"      reply: {r.reply[:140].strip()!r}")
    total = len(results)
    pct = 100 * hits / total if total else 0
    print(f"\n  Score: {hits}/{total} ({pct:.0f}%)\n")
    return 0 if hits == total else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Empório agent evals.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="also run the live answer-quality tier (needs a real model).",
    )
    args = parser.parse_args(argv)

    rc = _print_routing()
    if args.live:
        rc |= _print_answer_quality()
    else:
        print("(use --live to also run Tier 2 answer-quality evals)\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
