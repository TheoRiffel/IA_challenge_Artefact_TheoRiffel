# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A text customer-service agent for "Empório da Música", a fictional musical-instrument
store. It answers about products/prices/stock/orders (structured CSV data) and store
policies (a prose PDF manual), in the store's voice, and gracefully declines out-of-scope
requests. Built for an AI-Engineer technical challenge. Code comments are in English;
user-facing strings, tool docstrings, and docs are in Brazilian Portuguese.

## Commands

```bash
# Setup (downloads BGE-M3 embedding model ~2GB on first retriever build)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # installs runtime + pytest deps

cp .env.example .env             # then set EMPORIO_MODEL + the matching API key

# Run the CLI chat (commands inside: /reset, /sair)
python -m emporio_agente.cli     # or: emporio

# Tests — the deterministic core only, NO LLM calls, no network
pytest -q
pytest tests/test_pricing.py -q                          # one file
pytest tests/test_pricing.py::test_pix_beats_small_promotion   # one test
```

There is no linter/formatter configured. `pytest` config lives in `pyproject.toml`
(`pythonpath=["src"]`, `asyncio_mode=auto`).

## Architecture

The central design decision is a **hybrid split by data nature**, not RAG-for-everything:

- **Structured data** (products, orders, promotions) → **function calling** over a typed,
  deterministic data layer. Deliberately **NOT embedded** — prices/stock/status are exact
  lookups, so the model cannot hallucinate a number.
- **Policies** (PDF prose) → **lightweight per-section RAG** with local BGE-M3 embeddings +
  cosine similarity in numpy + keyword boost. No vector DB (~28 chunks don't justify one).

**The load-bearing invariant: numbers never come from the LLM.** Every fact (price, discount,
stock, order status, discontinued flag, scope) is computed by the data layer and returned as
a typed Pydantic object. The model only picks a tool and phrases the result. This is why the
agent is "thin" and the tools/data layer are "fat" — and why the whole business core is
unit-testable without any model call.

### Layers and data flow

```
cli.py → session.py (ChatSession, in-memory history)
       → agent.py (build_agent: swappable model + persona + tools)
       → tools/registry.py (4 typed tools, thin wrappers)
       → dependencies.py (AgentDependencies injected via RunContext)
            ├── data/store.py     (StoreData: CSVs → DataFrames → domain models)
            │       └── pricing.py (compute_price: the only place money is computed)
            └── policies/retriever.py (PolicyRetriever: embeddings + cosine + keyword)
                    └── policies/chunker.py (section-aware PDF chunking)
       models.py = Pydantic return contracts shared across all layers
       config.py = paths, model string, business constants
```

The 4 tools (`tools/registry.py`): `search_products`, `get_product_details`,
`get_order_status`, `search_policies`. Each just calls into `ctx.deps.store` or
`ctx.deps.policies` and returns a Pydantic model — keep them thin; put logic in the data layer.

### Key conventions when editing

- **Model swappability is a design goal.** The provider is the `EMPORIO_MODEL` env var
  (`"provider:model"`, e.g. `anthropic:claude-sonnet-4-5`, `openai:gpt-4o-mini`,
  `ollama:llama3.1`). `agent.py` reads `config.MODEL` and nothing else hardcodes a provider —
  keep it that way.
- **Business rules live in `pricing.py` / `store.py`, not in prompts.** PIX 5% is
  non-cumulative with promotions (`compute_price` picks the genuinely cheaper of the two);
  only `is_active==1` promotions apply (most of the 25 are inactive); `status=="discontinued"`
  and cancelled-orders-have-no-tracking are surfaced as typed fields. Tests in
  `tests/test_pricing.py` and `tests/test_data_layer.py` pin these — update them together.
- **Embeddings are cached** to `src/emporio_agente/policies/.embeddings.pkl` (gitignored).
  The cache is keyed by model name; changing `EMPORIO_EMBEDDING_MODEL` rebuilds it. The
  embedding model loads lazily so importing the package (e.g. for data-layer tests) pays no
  model-load cost.
- **The PDF chunker (`chunker.py`) is tuned to pypdf's real extraction**, which glues section
  headers onto body text. It splits on a leading `N`/`N.M` section number. If chunking changes,
  re-check `tests/test_policies.py`.
