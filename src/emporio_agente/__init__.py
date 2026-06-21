"""Empório da Música — agente de atendimento.

A text-based customer-support agent for a fictional musical-instrument store.

The deterministic layer (``data``, ``pricing``, ``policies``) imports without
the LLM stack. The agent-facing entry points (``build_agent``, ``ChatSession``)
are exposed lazily so importing this package for data-layer tests does not
require ``pydantic_ai`` to be installed.
"""

from __future__ import annotations

__all__ = ["build_agent", "ChatSession", "AgentDependencies"]
__version__ = "0.1.0"


def __getattr__(name: str):
    if name == "build_agent":
        from .agent import build_agent

        return build_agent
    if name == "ChatSession":
        from .session import ChatSession

        return ChatSession
    if name == "AgentDependencies":
        from .dependencies import AgentDependencies

        return AgentDependencies
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
