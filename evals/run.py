"""CLI runner for the three-tier eval suite.

    python -m evals.run            # Tier 1 + Tier 2 (offline, no API key)
    python -m evals.run --live     # + Tier 3 (answer quality, needs a model)

Tiers:
- Tier 1 — Núcleo determinístico: the pytest suite in ``tests/`` (pricing, data,
  chunking, validation). Offline, no model.
- Tier 2 — Roteamento de tools: offline routing eval (deterministic stub).
- Tier 3 — Qualidade de resposta: opt-in, live; checks the response contracts
  (docs/RESPONSE_CONTRACTS.md) against StoreData ground truth.

Prints per-tier detail followed by a compact score table.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

from .answer_quality import run_answer_quality
from .live import live_model_available
from .routing import run_routing, score

_API_KEY_REQUIRED = "requer chave de API"


def _run_tier1_pytest() -> tuple[int, int]:
    """Run the deterministic pytest suite and return ``(passed, total)``."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", out)) else 0
    failed = sum(
        int(m.group(1))
        for kw in ("failed", "error", "errors")
        if (m := re.search(rf"(\d+) {kw}", out))
    )
    return passed, passed + failed


def _print_tier1() -> tuple[int, int]:
    print("Tier 1 — Núcleo determinístico (pytest tests/)\n")
    passed, total = _run_tier1_pytest()
    mark = "✓" if passed == total and total else "✗"
    print(f"  {mark} {passed}/{total} testes (pricing, dados, chunking, validação)\n")
    return passed, total


def _print_tier2() -> tuple[int, int]:
    results = run_routing()
    print("Tier 2 — Roteamento de tools (offline, stub determinístico)\n")
    print(f"  {'id':<22}{'scenario':<26}{'expected':<26}{'got':<26}ok")
    print(f"  {'-' * 96}")
    for r in results:
        exp = ",".join(r.case.expected_tools) or "—"
        got = ",".join(r.called_tools) or "—"
        print(f"  {r.case.id:<22}{r.case.scenario_tag:<26}{exp:<26}{got:<26}{'✓' if r.passed else '✗'}")
    hits, total = score(results)
    print(f"\n  {hits}/{total} mensagens roteadas para a tool correta\n")
    return hits, total


def _print_tier3() -> tuple[int, int] | None:
    """Returns ``(hits, total)`` when run, or ``None`` when skipped (no key)."""
    ok, reason = live_model_available()
    print("Tier 3 — Qualidade de resposta (live, end-to-end)\n")
    if not ok:
        print(f"  SKIPPED — {_API_KEY_REQUIRED} ({reason}).\n")
        return None
    print(f"  Rodando contra: {reason}\n")
    results = run_answer_quality()
    hits = 0
    for r in results:
        hits += r.passed
        print(f"  {'✓' if r.passed else '✗'} {r.case.id:<18} {r.detail}")
        if not r.passed:
            print(f"      reply: {r.reply[:140].strip()!r}")
    total = len(results)
    print(f"\n  {hits}/{total} respostas cumprem o contrato\n")
    return hits, total


def _print_summary(t1, t2, t3) -> None:
    def cell(score_tuple) -> str:
        return f"{score_tuple[0]}/{score_tuple[1]}" if score_tuple else _API_KEY_REQUIRED

    print("Resumo")
    print(f"  {'Tier':<6}{'Descrição':<40}Score")
    print(f"  {'-' * 60}")
    print(f"  {'1':<6}{'Núcleo determinístico (pytest)':<40}{cell(t1)}")
    print(f"  {'2':<6}{'Roteamento de tools (offline)':<40}{cell(t2)}")
    print(f"  {'3':<6}{'Qualidade de resposta (live)':<40}{cell(t3)}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Empório agent evals.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="also run Tier 3 (answer quality) — needs a real model.",
    )
    args = parser.parse_args(argv)

    t1 = _print_tier1()
    t2 = _print_tier2()
    t3 = _print_tier3() if args.live else None
    if not args.live:
        print("(use --live para também rodar a Tier 3 de qualidade de resposta)\n")

    _print_summary(t1, t2, t3)

    # Exit code reflects the offline tiers (Tier 3 is opt-in / may need a key).
    offline_ok = t1[0] == t1[1] and t2[0] == t2[1]
    return 0 if offline_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
