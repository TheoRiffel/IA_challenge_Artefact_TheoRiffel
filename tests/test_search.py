"""Tests for the product search layer (no LLM).

Focus on this dataset's trap: "cordas" as an out-of-scope accessory vs. the
valid "Cordas Orquestrais" category, plus accent-insensitive synonyms and
conservative fuzzy name matching.
"""

from __future__ import annotations

from emporio_agente.data.search import (
    TermClass,
    classify_term,
    normalize,
)


# -- Normalization -----------------------------------------------------------
def test_normalize_strips_accents_and_case():
    assert normalize("Violão") == "violao"
    assert normalize("  Saxofone  ") == "saxofone"


# -- Accent-insensitive synonym category search ------------------------------
def test_violao_accent_insensitive_under_1000(store):
    # "violao" (no accent) must resolve to the "Violões" category.
    res = store.search_products(category_name="violao", max_price=1000.0)
    assert res.count > 0
    assert all(p.category_name == "Violões" for p in res.products)
    assert all(p.best_price <= 1000.0 for p in res.products)
    # Nylon and steel acoustics both live in this category.
    names = " ".join(normalize(p.name) for p in res.products)
    assert "nylon" in names and ("aco" in names or "folk" in names)


def test_synonym_query_routes_to_category(store):
    # A bare synonym passed as the free-text query is treated as a category.
    res = store.search_products(query="violao")
    assert res.count > 0
    assert all(p.category_name == "Violões" for p in res.products)


# -- Fuzzy name matching (conservative) --------------------------------------
def test_fuzzy_near_miss_still_matches(store):
    # Typo in a real product name: substring fails, fuzzy should still match.
    p = store.find_product_by_name("Takamne GD20")
    assert p is not None
    assert "Takamine GD20" in p.name


def test_fuzzy_rejects_garbage(store):
    assert store.find_product_by_name("xpto qwerty zzz") is None


# -- The "cordas" disambiguation trap ----------------------------------------
def test_bare_cordas_is_disambiguated_not_silent_category(store):
    res = store.search_products(query="cordas")
    # Must NOT silently return Cordas Orquestrais as a confident product search.
    assert res.count == 0
    assert res.products == []
    # The disambiguation signal must be present for the agent to act on.
    assert res.disambiguation is not None
    assert "ambígu" in res.disambiguation.lower()


def test_cordas_orquestrais_is_category():
    klass, canonical = classify_term("cordas orquestrais")
    assert klass is TermClass.CATEGORY
    assert canonical == "Cordas Orquestrais"


def test_cordas_avulsas_is_accessory():
    klass, _ = classify_term("cordas avulsas")
    assert klass is TermClass.ACCESSORY_OUT_OF_SCOPE


def test_bare_cordas_term_is_ambiguous():
    klass, _ = classify_term("cordas")
    assert klass is TermClass.AMBIGUOUS


# -- Out-of-scope accessories ------------------------------------------------
def test_accessory_terms_classified_out_of_scope():
    for term in ("palhetas", "cabo P10", "case rígido", "pedal de distorção"):
        klass, _ = classify_term(term)
        assert klass is TermClass.ACCESSORY_OUT_OF_SCOPE, term


def test_accessory_query_returns_no_products_with_signal(store):
    res = store.search_products(query="palhetas")
    assert res.count == 0
    assert res.disambiguation is not None
