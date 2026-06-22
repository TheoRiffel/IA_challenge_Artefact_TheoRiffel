"""Agent assembly.

Wires the swappable model, the persona, and the typed tools into a single
``Agent``. The model is resolved from config (``EMPORIO_MODEL``), so changing
provider is one environment variable and nothing in this file changes.

If ``EMPORIO_OPENAI_BASE_URL`` is set, the same model string is routed through
that OpenAI-compatible endpoint — the concrete proof that "the provider is a
config value": any local/self-hosted server (vLLM, Ollama, LM Studio,
llama.cpp, TGI, LocalAI, ...) drops in without touching this file.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from . import config
from .config import MODEL
from .dependencies import AgentDependencies
from .persona import SYSTEM_PROMPT
from .tools import register_tools


def _resolve_model(model_id: str) -> str | Model:
    """Resolve ``EMPORIO_MODEL`` to something Pydantic AI accepts.

    Normally this is just the ``"provider:model"`` string. When
    ``EMPORIO_OPENAI_BASE_URL`` is set, build an OpenAI-compatible model that
    points at that endpoint instead, taking the model name from ``model_id``.
    """
    if not config.OPENAI_BASE_URL:
        return model_id

    # Local imports: only paid for when the override is actually in use.
    import os

    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.openai import OpenAIProvider

    model_name = model_id.split(":", 1)[1] if ":" in model_id else model_id
    provider = OpenAIProvider(
        base_url=config.OPENAI_BASE_URL,
        # Local servers usually ignore the key; a placeholder keeps the client happy.
        api_key=os.environ.get("OPENAI_API_KEY") or "not-needed",
    )
    return OpenAIModel(model_name, provider=provider)


def build_agent(model: str | None = None) -> Agent[AgentDependencies, str]:
    agent: Agent[AgentDependencies, str] = Agent(
        _resolve_model(model or MODEL),
        deps_type=AgentDependencies,
        system_prompt=SYSTEM_PROMPT,
    )
    register_tools(agent)
    return agent
