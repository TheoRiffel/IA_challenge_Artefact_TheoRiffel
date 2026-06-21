# Evals — Empório da Música agent

Makes the agent measurable and regression-proof across **three tiers**, from the
cheapest/most deterministic to the most expensive. The design protects the core
invariant from [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md): every fact
comes from the deterministic data layer, never the model.

| Tier | O que mede | Custo |
|------|------------|-------|
| **1 — Núcleo determinístico** | pricing, dados, chunking, validação (`pytest tests/`) | offline, sem modelo |
| **2 — Roteamento de tools** | a tool certa é chamada para cada mensagem | offline, stub determinístico |
| **3 — Qualidade de resposta** | contratos de [`docs/RESPONSE_CONTRACTS.md`](../docs/RESPONSE_CONTRACTS.md) vs. ground truth | opt-in, requer modelo real |

```
evals/
├── cases.py            # Tier-2 routing dataset (12 cases)
├── stub_model.py       # deterministic routing stub (stands in for the LLM offline)
├── routing.py          # Tier-2 harness: run cases, capture tools, score
├── ground_truth.py     # expectations computed from StoreData (never hard-coded)
├── answer_quality.py   # Tier-3 harness: end-to-end, contract checks
├── live.py             # is a real model configured/reachable?
├── run.py              # `python -m evals.run [--live]` score table
├── test_routing.py     # Tier-2 pytest (offline, CI)
└── test_answer_quality.py  # Tier-3 pytest (opt-in, marker `live`)
```

## How to run

```bash
pytest tests/ -q          # Tier 1 — deterministic core
python -m evals.run       # Tier 1 + Tier 2 (offline, no API key)
python -m evals.run --live  # + Tier 3 (answer quality, needs a real model)

# pytest entry points:
pytest evals/ -q          # Tier 2 (Tier 3 deselected by default)
pytest evals/ -m live -q  # Tier 3 (skips automatically without a key)
```

`live` tests are **deselected by default** (see `addopts` in `pyproject.toml`)
because they call a real model. When you opt in with `-m live`, they still
**skip** automatically if no provider key/endpoint is configured, so CI without
secrets stays green.

## Tier 1 — núcleo determinístico

The existing `tests/` suite (pricing rules, data-layer edge cases, policy
chunking, input validation). Pure Python, no model, no network — the foundation
the other tiers rest on. The runner reports its pass count by invoking pytest.

## Tier 2 — tool routing (offline)

For each user message, the harness runs the agent, captures the tools it
actually invoked (from the run's message history), and scores the tool *set*
against `expected_tools`. Covered scenarios: price lookup, catalogue search,
order status, policy question, out-of-scope accessory (no tool → refusal), and
off-topic (no tool → refusal).

**How it runs without an LLM — and what that does and doesn't prove.** Deciding
which tool to call is the model's job, so a real model is the only way to
measure a *model's* routing accuracy (that's the live tier). To stay offline and
in CI, Tier 2 swaps in a deterministic, keyword-rule **routing stub**
(`stub_model.py`) that plays the model's role. It is intentionally generic
heuristics, not a per-message answer table.

What Tier 2 therefore proves:
- the dataset, scoring, and expected-vs-actual comparison work and stay green;
- every expected tool is **registered and executes end-to-end against the real
  `StoreData`** (the policy tool uses a fake retriever so no embedding model is
  downloaded).

What it does **not** prove: that any particular LLM routes correctly. The same
dataset feeds the live routing check (`run_routing(model=...)`) for that.

## Tier 3 — answer quality (opt-in, live)

Runs the real agent end-to-end (real `StoreData` + real `PolicyRetriever` + the
configured model) on ~6 curated cases and checks the reply with **deterministic
substring / numeric / regex** assertions — **no LLM-as-judge**. The checks encode
the obligations in [`docs/RESPONSE_CONTRACTS.md`](../docs/RESPONSE_CONTRACTS.md);
expectations come from `ground_truth.py`, computed from the data layer, so they
never drift from the CSVs. Examples:

- a price answer must quote the **list price** AND the **best price** and, when a
  promotion is active, the **PIX-non-cumulative** note (case: Taylor 110e);
- a **cancelled** order reply must **not** contain a tracking code; a delivered
  one must contain the real one;
- an out-of-scope accessory reply must not invent a price.

Live scores depend on the model and **require an API key** — they are not
committed as a fixed number. As an illustration of what the tier surfaces, a
weak local 7B (qwen2.5 via Ollama) failed several cases with deferred lookups
("vou verificar" instead of answering) and a leaked `</tool_call>` token, while
a frontier model passed the same contracts. The eval is the gate that makes that
difference visible.

## Limitations (honest scope)

- **Tier 2 does not judge phrasing or the live model's judgment** — only the tool
  set, via a stand-in router. Real routing accuracy needs the live tier.
- **Tier 3 is a small curated set, not exhaustive**, and uses substring/numeric
  checks: it confirms the right facts appear, not that the surrounding prose is
  fully correct or well-toned.
- **Accessory vs. category ambiguity**: the router treats "cordas" as an
  accessory (out of scope), though the catalogue has a "Cordas Orquestrais"
  category — fine for these cases, but a sharper scope check would disambiguate.
- **No tool-argument-value scoring** in Tier 2 (e.g. that `max_price_brl` got the
  right number) — it scores which tools are called, not their arguments.
