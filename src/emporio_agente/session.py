"""Conversation session.

In-memory per-session history. This is honest scope for a prototype: it keeps
multi-turn context within a run without pulling in Redis or a database. The
abstraction is deliberately thin so a persistent backend could replace it
without touching the agent or CLI.
"""

from __future__ import annotations

from pydantic_ai.messages import ModelMessage

from .agent import build_agent
from .dependencies import AgentDependencies


class ChatSession:
    """Holds message history and runs turns against the agent."""

    def __init__(self, deps: AgentDependencies | None = None, model: str | None = None):
        self.agent = build_agent(model)
        self.deps = deps or AgentDependencies.build()
        self.history: list[ModelMessage] = []
        # Raw result of the most recent turn, exposed for the debug trace.
        self.last_result = None

    async def send(self, user_message: str) -> str:
        result = await self.agent.run(
            user_message, deps=self.deps, message_history=self.history
        )
        self.history = result.all_messages()
        self.last_result = result
        return result.output

    def send_sync(self, user_message: str) -> str:
        result = self.agent.run_sync(
            user_message, deps=self.deps, message_history=self.history
        )
        self.history = result.all_messages()
        self.last_result = result
        return result.output

    def reset(self) -> None:
        self.history = []
        self.last_result = None
