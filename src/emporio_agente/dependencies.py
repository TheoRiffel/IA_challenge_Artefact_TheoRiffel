"""Agent dependencies.

A single typed container injected into every tool via Pydantic AI's
``RunContext``. Tools become pure functions of ``(deps, args)``, so they are
trivially unit-testable with a fake ``StoreData`` / ``PolicyRetriever`` and the
data source and retriever are swappable independently of the model.
"""

from __future__ import annotations

from dataclasses import dataclass

from .data.store import StoreData
from .policies.retriever import PolicyRetriever


@dataclass
class AgentDependencies:
    store: StoreData
    policies: PolicyRetriever

    @classmethod
    def build(cls) -> "AgentDependencies":
        store = StoreData()
        policies = PolicyRetriever().build()
        return cls(store=store, policies=policies)
