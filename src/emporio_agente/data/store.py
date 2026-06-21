"""Data layer.

Loads the operational CSVs once into pandas DataFrames and exposes typed query
methods that return the domain models. This is the deterministic core: all
business facts (price, stock, promotions, order status, discontinued, scope)
are decided here and handed up as validated objects. No LLM is involved at this
layer, so it is fully unit-testable on its own.

The class is injected into tools via Pydantic AI's dependency mechanism, so the
data source is swappable (CSV today, a real DB tomorrow) without touching the
tools or the agent.
"""

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

import pandas as pd

from ..config import DATA_DIR, ORDER_STATUS_LABELS_PTBR
from ..models import (
    Category,
    OrderItem,
    OrderStatus,
    Product,
    ProductSearchResult,
    ProductSummary,
)
from ..pricing import compute_price


class StoreData:
    """In-memory store of the operational data with typed accessors."""

    def __init__(self, data_dir: Path | str = DATA_DIR) -> None:
        self.data_dir = Path(data_dir)
        self._load()

    # -- Loading ------------------------------------------------------------
    def _load(self) -> None:
        self.categories = pd.read_csv(self.data_dir / "categories.csv")
        self.customers = pd.read_csv(self.data_dir / "customers.csv")
        self.products = pd.read_csv(self.data_dir / "products.csv")
        self.orders = pd.read_csv(self.data_dir / "orders.csv")
        self.order_items = pd.read_csv(self.data_dir / "order_items.csv")
        self.promotions = pd.read_csv(self.data_dir / "promotions.csv")

        # Normalise dtypes that matter for lookups.
        self.products["product_id"] = self.products["product_id"].astype(int)
        self.products["stock_quantity"] = (
            pd.to_numeric(self.products["stock_quantity"], errors="coerce")
            .fillna(0)
            .astype(int)
        )
        self.orders["order_id"] = self.orders["order_id"].astype(int)

    @cached_property
    def _category_by_id(self) -> dict[int, str]:
        return dict(zip(self.categories["category_id"], self.categories["name"]))

    @cached_property
    def _active_promo_by_product(self) -> dict[int, dict]:
        """Map product_id -> {percent, label} for ACTIVE promotions only."""
        active = self.promotions[self.promotions["is_active"] == 1]
        out: dict[int, dict] = {}
        for _, row in active.iterrows():
            out[int(row["product_id"])] = {
                "percent": int(row["discount_percent"]),
                "label": str(row["description"]),
            }
        return out

    # -- Internal builders --------------------------------------------------
    def _build_product(self, row: pd.Series) -> Product:
        pid = int(row["product_id"])
        promo = self._active_promo_by_product.get(pid)
        pricing = compute_price(
            float(row["price_brl"]),
            active_promo_percent=promo["percent"] if promo else None,
            active_promo_label=promo["label"] if promo else None,
        )
        try:
            specs = json.loads(row["specs"]) if pd.notna(row.get("specs")) else {}
        except (json.JSONDecodeError, TypeError):
            specs = {}

        status = str(row["status"])
        return Product(
            product_id=pid,
            name=str(row["name"]),
            category_id=int(row["category_id"]),
            category_name=self._category_by_id.get(int(row["category_id"]), "—"),
            description=str(row.get("description", "") or ""),
            stock_quantity=int(row["stock_quantity"]),
            is_active=status == "active",
            is_discontinued=status == "discontinued",
            specs=specs,
            pricing=pricing,
        )

    # -- Public API: products ----------------------------------------------
    def get_categories(self) -> list[Category]:
        return [
            Category(
                category_id=int(r["category_id"]),
                name=str(r["name"]),
                description=str(r.get("description", "") or ""),
            )
            for _, r in self.categories.iterrows()
        ]

    def get_product(self, product_id: int) -> Product | None:
        match = self.products[self.products["product_id"] == int(product_id)]
        if match.empty:
            return None
        return self._build_product(match.iloc[0])

    def find_product_by_name(self, name: str) -> Product | None:
        """Best-effort exact-ish lookup by name (case-insensitive substring)."""
        q = name.strip().lower()
        mask = self.products["name"].str.lower().str.contains(q, regex=False, na=False)
        match = self.products[mask]
        if match.empty:
            return None
        # Prefer the shortest name that matches (closest to an exact hit).
        match = match.assign(_len=match["name"].str.len()).sort_values("_len")
        return self._build_product(match.iloc[0])

    def search_products(
        self,
        *,
        query: str | None = None,
        category_name: str | None = None,
        max_price: float | None = None,
        only_in_stock: bool = True,
        limit: int = 8,
    ) -> ProductSearchResult:
        df = self.products.copy()

        if query:
            q = query.strip().lower()
            name_hit = df["name"].str.lower().str.contains(q, regex=False, na=False)
            desc_hit = df["description"].str.lower().str.contains(
                q, regex=False, na=False
            )
            df = df[name_hit | desc_hit]

        if category_name:
            cat = category_name.strip().lower()
            cat_ids = [
                cid
                for cid, cname in self._category_by_id.items()
                if cat in cname.lower()
            ]
            df = df[df["category_id"].isin(cat_ids)]

        products = [self._build_product(r) for _, r in df.iterrows()]

        if max_price is not None:
            products = [p for p in products if p.pricing.best_price <= max_price]
        if only_in_stock:
            products = [p for p in products if p.in_stock]

        products.sort(key=lambda p: p.pricing.best_price)
        products = products[:limit]

        summaries = [
            ProductSummary(
                product_id=p.product_id,
                name=p.name,
                category_name=p.category_name,
                list_price=p.pricing.list_price,
                best_price=p.pricing.best_price,
                in_stock=p.in_stock,
            )
            for p in products
        ]

        parts = []
        if query:
            parts.append(f"'{query}'")
        if category_name:
            parts.append(f"categoria {category_name}")
        if max_price is not None:
            parts.append(f"até R$ {max_price:.2f}")
        summary = "busca por " + ", ".join(parts) if parts else "catálogo"

        return ProductSearchResult(
            query_summary=summary, count=len(summaries), products=summaries
        )

    # -- Public API: orders -------------------------------------------------
    def _order_items(self, order_id: int) -> list[OrderItem]:
        items = self.order_items[self.order_items["order_id"] == int(order_id)]
        out: list[OrderItem] = []
        for _, it in items.iterrows():
            prod = self.get_product(int(it["product_id"]))
            out.append(
                OrderItem(
                    product_id=int(it["product_id"]),
                    product_name=prod.name if prod else f"Produto {it['product_id']}",
                    quantity=int(it["quantity"]),
                )
            )
        return out

    def get_order(self, order_id: int) -> OrderStatus | None:
        match = self.orders[self.orders["order_id"] == int(order_id)]
        if match.empty:
            return None
        row = match.iloc[0]
        status = str(row["status"])
        is_cancelled = status == "cancelled"

        def _clean(value) -> str | None:
            if pd.isna(value):
                return None
            s = str(value).strip()
            return s or None

        return OrderStatus(
            order_id=int(row["order_id"]),
            found=True,
            status=status,
            status_label_ptbr=ORDER_STATUS_LABELS_PTBR.get(status, status),
            order_date=str(row["order_date"]),
            total_brl=float(row["total_brl"]),
            payment_method=str(row["payment_method"]),
            tracking_code=None if is_cancelled else _clean(row.get("tracking_code")),
            estimated_delivery=(
                None if is_cancelled else _clean(row.get("estimated_delivery"))
            ),
            is_cancelled=is_cancelled,
            cancellation_reason=_clean(row.get("notes")) if is_cancelled else None,
            items=self._order_items(int(row["order_id"])),
        )
