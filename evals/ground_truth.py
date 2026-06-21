"""Ground truth for the answer-quality tier, computed from the data layer.

Expectations are derived from ``StoreData`` at run time, never hard-coded, so
they cannot drift away from the CSVs. If a price or order detail changes, the
ground truth changes with it and the eval stays honest.
"""

from __future__ import annotations

from functools import lru_cache

from emporio_agente.data.store import StoreData
from emporio_agente.models import OrderStatus, Product, ProductSearchResult


@lru_cache(maxsize=1)
def store() -> StoreData:
    return StoreData()


def product_by_name(name: str) -> Product | None:
    return store().find_product_by_name(name)


def best_price(name: str) -> float | None:
    p = product_by_name(name)
    return p.pricing.best_price if p else None


def order(order_id: int) -> OrderStatus | None:
    return store().get_order(order_id)


def search(category: str, max_price: float | None = None) -> ProductSearchResult:
    return store().search_products(category_name=category, max_price=max_price)


def price_variants(value: float) -> list[str]:
    """Plausible textual renderings of a BRL amount (pt-BR and plain), so a
    substring check can confirm the agent quoted the real number however it
    chose to format it."""
    cents = f"{value:.2f}"  # "2089.05"
    intp = int(value)
    thousands = f"{intp:,}".replace(",", ".")  # "2.089"
    return sorted({
        cents,                                   # 2089.05
        cents.replace(".", ","),                 # 2089,05
        f"{thousands},{cents.split('.')[1]}",    # 2.089,05
        str(intp),                               # 2089
        thousands,                               # 2.089
    })
