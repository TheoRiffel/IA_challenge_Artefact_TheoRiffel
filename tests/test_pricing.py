"""Tests for the pricing engine.

These are the most important tests in the suite: they pin down the store's
money rules (policy 6.2) with zero LLM involvement.
"""

from __future__ import annotations

from emporio_agente.pricing import compute_price


def test_pix_only_when_no_promotion():
    bd = compute_price(1000.0)
    assert bd.pix_price == 950.0
    assert bd.has_active_promotion is False
    assert bd.promo_price is None
    assert bd.best_price == 950.0
    assert "PIX" in bd.best_price_reason


def test_promotion_beats_pix_and_is_not_cumulative():
    # 20% promo on 1000 -> 800 promo; PIX would be 950. Promo wins, no stacking.
    bd = compute_price(1000.0, active_promo_percent=20, active_promo_label="Black Friday")
    assert bd.promo_price == 800.0
    assert bd.pix_price == 950.0
    assert bd.best_price == 800.0
    # The 5% PIX discount must NOT be applied on top of the promo price.
    assert bd.best_price != round(800.0 * 0.95, 2)
    assert "não acumula" in bd.best_price_reason.lower() or "não são cumulativos" in bd.best_price_reason.lower()


def test_pix_beats_small_promotion():
    # A 3% promo (970) is worse than PIX (950); PIX should win.
    bd = compute_price(1000.0, active_promo_percent=3, active_promo_label="Oferta")
    assert bd.promo_price == 970.0
    assert bd.best_price == 950.0
    assert "PIX" in bd.best_price_reason


def test_rounding_is_two_decimals():
    bd = compute_price(599.9, active_promo_percent=18, active_promo_label="Desconto")
    assert bd.promo_price == round(599.9 * 0.82, 2)
    assert bd.best_price == bd.promo_price
