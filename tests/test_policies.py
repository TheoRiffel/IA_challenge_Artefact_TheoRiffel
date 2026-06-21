"""Tests for policy chunking.

We don't test the embedding retriever here (it needs the model download); the
retriever's correctness rests on the chunker producing clean, complete sections,
which is what we assert.
"""

from __future__ import annotations

from emporio_agente.config import POLICY_PDF
from emporio_agente.policies.chunker import load_policy_chunks


def test_chunks_cover_key_sections():
    chunks = load_policy_chunks(POLICY_PDF)
    ids = {c.section_id for c in chunks}
    # Key policy areas the agent must be able to answer from.
    for required in {"2", "3", "4.1", "5.1", "6.2"}:
        assert required in ids, f"missing section {required}"


def test_return_policy_chunk_has_seven_day_window():
    chunks = load_policy_chunks(POLICY_PDF)
    ret = next(c for c in chunks if c.section_id == "4.1")
    assert "7" in ret.text
    assert "arrependimento" in ret.text.lower()


def test_non_cumulative_rule_present():
    chunks = load_policy_chunks(POLICY_PDF)
    promo = next(c for c in chunks if c.section_id == "6.2")
    assert "cumulativ" in promo.text.lower()


def test_no_empty_chunks():
    chunks = load_policy_chunks(POLICY_PDF)
    assert chunks
    assert all(len(c.text) > 40 for c in chunks)
