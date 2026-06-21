"""Defensive-validation tests (no LLM, no embedding model).

Cover the graceful-degradation paths added for robustness: bad order ids, blank
queries / limit clamping, and rebuilding from a corrupt or stale embeddings
cache.
"""

from __future__ import annotations

import pickle

import numpy as np

from emporio_agente.policies.retriever import PolicyRetriever


# -- Order id validation -----------------------------------------------------
def test_get_order_non_numeric_returns_none(store):
    assert store.get_order("abc") is None


def test_get_order_negative_or_zero_returns_none(store):
    assert store.get_order(-5) is None
    assert store.get_order(0) is None


def test_get_order_numeric_string_still_resolves(store):
    # Graceful coercion: a numeric string is accepted, not rejected.
    order = store.get_order("1")
    assert order is not None and order.order_id == 1


# -- search_products input handling ------------------------------------------
def test_blank_query_treated_as_no_query(store):
    blank = store.search_products(query="   ")
    catalogue = store.search_products(query=None)
    assert blank.count == catalogue.count


def test_search_limit_is_clamped(store):
    assert len(store.search_products(limit=9999).products) <= 50
    # A non-positive limit is clamped up to at least one result.
    assert len(store.search_products(limit=0).products) >= 1


# -- Retriever cache resilience ----------------------------------------------
def test_retriever_rebuilds_on_corrupt_cache(tmp_path, monkeypatch):
    cache = tmp_path / "bad.pkl"
    cache.write_bytes(b"this is not a valid pickle")

    r = PolicyRetriever(cache_path=cache)
    # Avoid loading the real embedding model: stub the embed step.
    monkeypatch.setattr(
        r, "_embed", lambda texts: np.zeros((len(texts), 8), dtype=np.float32)
    )

    r.build()  # must not raise; should rebuild from the PDF

    assert r.chunks, "expected chunks rebuilt from the policy PDF"
    assert r._matrix is not None
    assert cache.exists(), "cache should be rewritten after a rebuild"


def test_retriever_rebuilds_on_model_name_mismatch(tmp_path, monkeypatch):
    cache = tmp_path / "stale.pkl"
    with open(cache, "wb") as fh:
        pickle.dump(
            {
                "model_name": "some-other-embedding-model",
                "chunks": [],
                "matrix": np.zeros((0, 8), dtype=np.float32),
            },
            fh,
        )

    r = PolicyRetriever(cache_path=cache, model_name="expected-model")
    monkeypatch.setattr(
        r, "_embed", lambda texts: np.zeros((len(texts), 8), dtype=np.float32)
    )

    r.build()

    # The stale cache had zero chunks; a correct rebuild must repopulate them.
    assert r.chunks, "stale-model cache should be ignored and rebuilt"
