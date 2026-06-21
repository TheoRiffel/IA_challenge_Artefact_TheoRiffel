"""Pricing engine.

The single place where money is computed. The store's rules (policy section 6.2):

- The table price is ``price_brl``.
- An *active* promotion (is_active == 1) discounts the table price.
- PIX gives 5% off the table price, but is NOT cumulative with a promotion:
  "O desconto de PIX (5%) não se aplica sobre preços já promocionais."
- The best price the customer can actually pay is the lower of the available
  options, presented transparently against the original price.

The model never does this arithmetic. It receives a ``PriceBreakdown`` and
phrases it. This keeps prices correct and the logic unit-testable.
"""

from __future__ import annotations

from .config import PIX_DISCOUNT_PERCENT
from .models import PriceBreakdown


def _round2(value: float) -> float:
    return round(value + 1e-9, 2)


def compute_price(
    list_price: float,
    *,
    active_promo_percent: int | None = None,
    active_promo_label: str | None = None,
) -> PriceBreakdown:
    """Resolve a product's pricing into a ``PriceBreakdown``.

    Parameters
    ----------
    list_price:
        The table price (``price_brl``).
    active_promo_percent:
        Discount percent of the *active* promotion, or ``None`` if there is no
        active promotion for this product.
    active_promo_label:
        Human-readable promotion name (e.g. "Black Friday").
    """
    pix_price = _round2(list_price * (1 - PIX_DISCOUNT_PERCENT / 100))

    has_promo = active_promo_percent is not None and active_promo_percent > 0
    promo_price = (
        _round2(list_price * (1 - active_promo_percent / 100)) if has_promo else None
    )

    # Determine the best price the customer can actually pay.
    # PIX is non-cumulative with a promotion, so the two are alternatives, and
    # we pick whichever is genuinely cheaper.
    if has_promo:
        if promo_price <= pix_price:
            best_price = promo_price
            reason = (
                f"Preço promocional '{active_promo_label}' "
                f"({active_promo_percent}% off). O desconto PIX não acumula "
                f"com promoção."
            )
        else:
            best_price = pix_price
            reason = (
                f"Pagamento via PIX (5% off) sai mais barato que a promoção "
                f"'{active_promo_label}'. Os descontos não são cumulativos."
            )
    else:
        best_price = pix_price
        reason = "Pagamento via PIX garante 5% de desconto sobre o preço de tabela."

    return PriceBreakdown(
        list_price=_round2(list_price),
        has_active_promotion=has_promo,
        promotion_label=active_promo_label if has_promo else None,
        promotion_discount_percent=active_promo_percent if has_promo else None,
        promo_price=promo_price,
        pix_price=pix_price,
        best_price=best_price,
        best_price_reason=reason,
    )
