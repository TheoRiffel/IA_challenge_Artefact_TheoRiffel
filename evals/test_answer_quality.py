"""Tier 2 pytest integration — opt-in, needs a real model.

Marked ``live`` and skipped when the configured provider's key/endpoint is
absent, so CI without secrets stays green. Run explicitly with:

    pytest evals/ -m live
"""

from __future__ import annotations

import pytest

from .answer_quality import run_answer_quality
from .live import live_model_available

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def live_results():
    available, reason = live_model_available()
    if not available:
        pytest.skip(f"live model unavailable: {reason}")
    return run_answer_quality()


def test_answers_match_data_layer_ground_truth(live_results):
    failures = [
        f"{r.case.id}: {r.detail} | reply={r.reply[:120].strip()!r}"
        for r in live_results
        if not r.passed
    ]
    assert not failures, "answer-quality failures:\n" + "\n".join(failures)
