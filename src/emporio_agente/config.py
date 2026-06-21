"""Configuration.

All environment-dependent and provider-dependent settings live here so the
rest of the codebase has no hard-coded provider, path, or business constant.
Swapping the LLM provider is a change to ``MODEL`` (or the ``EMPORIO_MODEL``
env var) and nothing else.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Paths -----------------------------------------------------------------
PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent.parent
DATA_DIR = Path(os.environ.get("EMPORIO_DATA_DIR", REPO_ROOT / "data"))
POLICY_PDF = DATA_DIR / "politicas_da_loja.pdf"
# Cache for computed policy embeddings so the model only runs once.
EMBEDDING_CACHE = Path(
    os.environ.get("EMPORIO_EMBED_CACHE", PACKAGE_ROOT / "policies" / ".embeddings.pkl")
)

# --- Model provider --------------------------------------------------------
# Pydantic AI accepts a "provider:model" string. Swapping providers is a
# one-line change here. Examples:
#   "anthropic:claude-sonnet-4-5"
#   "openai:gpt-4o-mini"
#   "ollama:llama3.1"  (local)
MODEL = os.environ.get("EMPORIO_MODEL", "anthropic:claude-sonnet-4-5")

# --- Embedding model (local, on-GPU via sentence-transformers) -------------
# BGE-M3 is multilingual and strong on PT-BR. MiniLM is the lighter fallback
# if reviewer setup time matters more than retrieval quality (see README).
EMBEDDING_MODEL = os.environ.get("EMPORIO_EMBEDDING_MODEL", "BAAI/bge-m3")
RETRIEVAL_TOP_K = int(os.environ.get("EMPORIO_RETRIEVAL_TOP_K", "3"))

# --- Business constants (from the policy manual) ---------------------------
PIX_DISCOUNT_PERCENT = 5  # policy section 3
FREE_SHIPPING_THRESHOLD_BRL = 500.0  # policy section 5.1
ONLINE_RETURN_WINDOW_DAYS = 7  # policy section 4.1

# Human-readable PT-BR labels for the raw order status values in the CSV.
ORDER_STATUS_LABELS_PTBR = {
    "pending": "Pendente",
    "confirmed": "Confirmado",
    "shipped": "Enviado",
    "delivered": "Entregue",
    "cancelled": "Cancelado",
}
