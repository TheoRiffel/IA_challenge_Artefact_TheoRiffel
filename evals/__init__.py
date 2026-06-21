"""Evaluation suite for the Empório da Música agent.

Two tiers (see ``evals/README.md`` for the full rationale and limitations):

- **Tier 1 — tool routing** (``evals.routing``): deterministic, no API key,
  CI-friendly. Verifies the agent routes each user message to the right tool
  set and that every tool is wired and executable against the real data layer.
- **Tier 2 — answer quality** (``evals.answer_quality``): opt-in, needs a real
  model. Checks factual correctness of end-to-end replies against ground truth
  computed from the data layer itself (no LLM judge).
"""
