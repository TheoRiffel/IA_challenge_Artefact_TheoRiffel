"""Domain models.

These Pydantic models are the *typed contracts* that the data layer and tools
return. The LLM never invents these values; it only receives them and phrases
the answer. Keeping every fact in a validated structure is what makes the
business layer testable without a single model call and keeps prices honest.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Category(BaseModel):
    """A product category (e.g. Violões, Guitarras)."""

    category_id: int
    name: str
    description: str = ""


class PriceBreakdown(BaseModel):
    """Resolved pricing for a product.

    Centralizes the store's pricing rules (policy section 6.2):
    - An active promotion discounts the table price.
    - PIX (5%) applies ONLY to the table price and is NOT cumulative with a
      promotion.
    - ``best_price`` is the lowest the customer can actually pay, with a short
      human-readable reason. The model presents this; it never computes it.
    """

    list_price: float = Field(..., description="Table price in BRL (price_brl).")
    has_active_promotion: bool = False
    promotion_label: str | None = None
    promotion_discount_percent: int | None = None
    promo_price: float | None = Field(
        None, description="Price after the active promotion, if any."
    )
    pix_price: float = Field(
        ..., description="Table price minus the 5% PIX discount."
    )
    best_price: float = Field(..., description="Lowest price the customer can pay.")
    best_price_reason: str = Field(
        ..., description="Why best_price is what it is (PIX vs promo, non-cumulative)."
    )


class Product(BaseModel):
    """A catalogue product with resolved pricing and availability."""

    product_id: int
    name: str
    category_id: int
    category_name: str
    description: str = ""
    stock_quantity: int
    is_active: bool
    is_discontinued: bool
    specs: dict = Field(default_factory=dict)
    pricing: PriceBreakdown

    @property
    def in_stock(self) -> bool:
        return self.is_active and not self.is_discontinued and self.stock_quantity > 0


class ProductSummary(BaseModel):
    """Lightweight product row for list/search results."""

    product_id: int
    name: str
    category_name: str
    list_price: float
    best_price: float
    in_stock: bool


class ProductSearchResult(BaseModel):
    """Result of a catalogue search."""

    query_summary: str
    count: int
    products: list[ProductSummary] = Field(default_factory=list)


class OrderItem(BaseModel):
    product_id: int
    product_name: str
    quantity: int


class OrderStatus(BaseModel):
    """Status of a single order.

    Cancelled orders have no tracking code; the data layer surfaces the reason
    from the order's notes so the agent can explain gracefully instead of
    inventing a tracking number.
    """

    order_id: int
    found: bool = True
    status: str
    status_label_ptbr: str
    order_date: str
    total_brl: float
    payment_method: str
    tracking_code: str | None = None
    estimated_delivery: str | None = None
    is_cancelled: bool = False
    cancellation_reason: str | None = None
    items: list[OrderItem] = Field(default_factory=list)


class PolicyChunk(BaseModel):
    """A retrieved slice of the store policy manual."""

    section_id: str
    title: str
    text: str
    score: float


class PolicyAnswer(BaseModel):
    """Result of a policy lookup: the most relevant manual sections."""

    query: str
    chunks: list[PolicyChunk] = Field(default_factory=list)

    @property
    def found(self) -> bool:
        return len(self.chunks) > 0
