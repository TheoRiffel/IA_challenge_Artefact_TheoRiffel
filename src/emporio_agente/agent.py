"""Agent assembly.

Wires the swappable model, the persona, and the typed tools into a single
``Agent``. The model is resolved from config (``EMPORIO_MODEL``), so changing
provider is one environment variable and nothing in this file changes.
"""

from __future__ import annotations

from pydantic_ai import Agent

from .config import MODEL
from .dependencies import AgentDependencies
from .persona import SYSTEM_PROMPT
from .tools import register_tools


def build_agent(model: str | None = None) -> Agent[AgentDependencies, str]:
    agent: Agent[AgentDependencies, str] = Agent(
        model or MODEL,
        deps_type=AgentDependencies,
        system_prompt=SYSTEM_PROMPT,
    )
    register_tools(agent)
    return agent
