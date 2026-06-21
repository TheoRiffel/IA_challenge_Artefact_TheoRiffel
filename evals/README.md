# Evals — Empório da Música agent

Makes two things measurable and regression-proof: **tool-selection routing** and
**answer correctness**. The design protects the core invariant from
[`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md): every fact comes from the
deterministic data layer, never the model. Routing is the part most likely to
regress, so it gets a dedicated, always-on tier.

```
evals/
├── cases.py            # Tier-1 routing dataset (12 cases)
├── stub_model.py       # deterministic routing stub (stands in for the LLM offline)
├── routing.py          # Tier-1 harness: run cases, capture tools, score
├── ground_truth.py     # expectations computed from StoreData (never hard-coded)
├── answer_quality.py   # Tier-2 harness: end-to-end, factual checks
├── live.py             # is a real model configured/reachable?
├── run.py              # `python -m evals.run [--live]` score tables
├── test_routing.py     # Tier-1 pytest (offline, CI)
└── test_answer_quality.py  # Tier-2 pytest (opt-in, marker `live`)
```

## How to run

```bash
# Tier 1 only — offline, deterministic, no API key (this is what CI runs)
pytest evals/ -q
python -m evals.run

# Tier 2 — opt-in, needs a real model (uses EMPORIO_MODEL from your .env)
pytest evals/ -m live -q
python -m evals.run --live
```

`live` tests are **deselected by default** (see `addopts` in `pyproject.toml`)
because they call a real model. When you do opt in with `-m live`, they still
**skip** automatically if no provider key/endpoint is configured, so CI without
secrets stays green either way.

## Tier 1 — tool routing (offline)

For each user message, the harness runs the agent, captures the tools it
actually invoked (from the run's message history), and scores the tool *set*
against `expected_tools`. Covered scenarios: price lookup, catalogue search,
order status, policy question, out-of-scope accessory (no tool → refusal), and
off-topic (no tool → refusal).

**How it runs without an LLM — and what that does and doesn't prove.** Deciding
which tool to call is the model's job, so a real model is the only way to
measure a *model's* routing accuracy (that's the live tier). To stay offline and
in CI, Tier 1 swaps in a deterministic, keyword-rule **routing stub**
(`stub_model.py`) that plays the model's role. It is intentionally generic
heuristics, not a per-message answer table.

What Tier 1 therefore proves:
- the dataset, scoring, and expected-vs-actual comparison work and stay green;
- every expected tool is **registered and executes end-to-end against the real
  `StoreData`** (the policy tool uses a fake retriever so no embedding model is
  downloaded).

What it does **not** prove: that any particular LLM routes correctly. The same
dataset feeds the live routing check (`run_routing(model=...)`) for that.

## Tier 2 — answer quality (opt-in, live)

Runs the real agent end-to-end (real `StoreData` + real `PolicyRetriever` + the
configured model) on ~6 curated cases and checks the reply with **deterministic
substring / numeric / regex** assertions — **no LLM-as-judge**. Expectations come
from `ground_truth.py`, computed from the data layer, so they never drift from
the CSVs. Examples:

- price reply must quote the `best_price` `StoreData` computes for that product;
- a **cancelled** order reply must **not** contain a tracking code; a delivered
  one must contain the real one;
- an out-of-scope accessory reply must not invent a price.

### Current live result (qwen2.5:7b via Ollama)

`python -m evals.run --live` scores **3/6** with the local 7B. The failures are
genuine model limitations the eval is meant to surface, not harness bugs:
deferred lookups ("vou verificar" instead of answering), asking for info already
given (order id), and a leaked `</tool_call>` token (a qwen-on-Ollama formatting
glitch). A stronger model is expected to score higher; the eval is the gate that
makes that difference visible.

## Limitations (honest scope)

- **Tier 1 does not judge phrasing or the live model's judgment** — only the tool
  set, via a stand-in router. Real routing accuracy needs the live tier.
- **Tier 2 is a small curated set, not exhaustive**, and uses substring/numeric
  checks: it can confirm the right number/fact appears, not that the surrounding
  prose is fully correct or well-toned.
- **Accessory vs. category ambiguity**: the router treats "cordas" as an
  accessory (out of scope), though the catalogue has a "Cordas Orquestrais"
  category — fine for these cases, but a sharper scope check would disambiguate.
- **No tool-argument-value scoring** in Tier 1 (e.g. that `max_price_brl` got the
  right number) — it scores which tools are called, not their arguments.
