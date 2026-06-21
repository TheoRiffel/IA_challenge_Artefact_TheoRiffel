"""Tier 1 — tool-routing harness.

Runs every :data:`evals.cases.CASES` message through the agent, captures the
tool set the agent actually invoked, and scores it against ``expected_tools``.

Notes on construction:
- We build the agent directly with the test model rather than constructing the
  real provider and then ``Agent.override(...)``-ing it. The configured Ollama
  provider raises at construction time when ``OLLAMA_BASE_URL`` is unset, so
  building the real model would make the offline tier fail in CI. Passing the
  model in at build time is the supported, env-free path and keeps Tier 1 truly
  offline. The same harness accepts a real model for the live routing check.
- Offline deps use the real :class:`StoreData` (deterministic, fast, no
  network) and a fake policy retriever, so the policy tool executes without
  downloading the embedding model.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai.messages import ModelResponse, ToolCallPart

from emporio_agente.agent import build_agent
from emporio_agente.data.store import StoreData
from emporio_agente.dependencies import AgentDependencies
from emporio_agente.models import PolicyAnswer, PolicyChunk

from .cases import CASES, RoutingCase
from .stub_model import routing_stub_model


class _FakePolicyRetriever:
    """Stand-in for PolicyRetriever so the policy tool runs without embeddings."""

    def search(self, question: str, top_k: int | None = None) -> PolicyAnswer:
        return PolicyAnswer(
            query=question,
            chunks=[
                PolicyChunk(
                    section_id="0",
                    title="stub",
                    text="Política (stub determinístico para o eval offline).",
                    score=1.0,
                )
            ],
        )


def build_eval_deps() -> AgentDependencies:
    return AgentDependencies(store=StoreData(), policies=_FakePolicyRetriever())


@dataclass
class CaseResult:
    case: RoutingCase
    called_tools: tuple[str, ...]
    passed: bool


def _called_tools(result) -> tuple[str, ...]:
    return tuple(
        part.tool_name
        for msg in result.all_messages()
        if isinstance(msg, ModelResponse)
        for part in msg.parts
        if isinstance(part, ToolCallPart)
    )


def run_routing(model=None, deps: AgentDependencies | None = None, cases=CASES) -> list[CaseResult]:
    """Score routing for every case.

    ``model`` defaults to the deterministic offline stub. Pass a real model (or
    ``"provider:model"`` string) to measure a live model's routing instead.
    """
    model = model if model is not None else routing_stub_model()
    deps = deps if deps is not None else build_eval_deps()
    agent = build_agent(model=model)

    results: list[CaseResult] = []
    for case in cases:
        run = agent.run_sync(case.user_message, deps=deps)
        called = _called_tools(run)
        passed = set(called) == set(case.expected_tools)
        results.append(CaseResult(case, called, passed))
    return results


def score(results: list[CaseResult]) -> tuple[int, int]:
    return sum(r.passed for r in results), len(results)
