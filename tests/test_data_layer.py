"""Tests for the data layer against the real provided CSVs.

These assert on the data-driven edge cases that the agent must handle correctly:
active vs inactive promotions, discontinued products, and cancelled orders with
no tracking.
"""

from __future__ import annotations


def test_categories_loaded(store):
    cats = store.get_categories()
    assert len(cats) == 9
    names = {c.name for c in cats}
    assert "Violões" in names
    assert "Guitarras" in names


def test_get_product_by_id(store):
    p = store.get_product(81)
    assert p is not None
    assert p.product_id == 81
    assert p.is_active
    assert p.pricing.list_price > 0


def test_find_product_by_name(store):
    p = store.find_product_by_name("Takamine GD20")
    assert p is not None
    assert "Takamine GD20" in p.name


def test_only_active_promotion_applied(store):
    # Product 94 has an ACTIVE promotion (8%) per promotions.csv.
    p = store.get_product(94)
    assert p.pricing.has_active_promotion is True
    assert p.pricing.promotion_discount_percent == 8


def test_inactive_promotion_not_applied(store):
    # Product 102 has a promotion row but is_active == 0 -> must be ignored.
    p = store.get_product(102)
    assert p.pricing.has_active_promotion is False
    assert p.pricing.promo_price is None


def test_discontinued_product_not_in_stock(store):
    p = store.get_product(113)
    assert p.is_discontinued is True
    assert p.in_stock is False


def test_cancelled_order_has_no_tracking_but_has_reason(store):
    o = store.get_order(17)
    assert o.is_cancelled is True
    assert o.tracking_code is None
    assert o.cancellation_reason  # non-empty reason from notes


def test_delivered_order_has_tracking_and_items(store):
    o = store.get_order(1)
    assert o.status == "delivered"
    assert o.tracking_code
    assert len(o.items) >= 1


def test_missing_order_returns_none(store):
    assert store.get_order(99999) is None


def test_search_respects_price_ceiling_and_stock(store):
    res = store.search_products(category_name="Violões", max_price=1000.0)
    assert res.count > 0
    for p in res.products:
        assert p.best_price <= 1000.0
        assert p.in_stock is True
    # Results are sorted by best price ascending.
    prices = [p.best_price for p in res.products]
    assert prices == sorted(prices)


def test_search_discontinued_excluded(store):
    res = store.search_products(query="Shelby", only_in_stock=True)
    assert all(p.product_id != 113 for p in res.products)
