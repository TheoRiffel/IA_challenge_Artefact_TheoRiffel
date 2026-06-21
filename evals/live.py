"""Live-model availability check for the opt-in answer-quality tier.

The answer tier needs a real model. We decide whether it can run by inspecting
the configured provider (``EMPORIO_MODEL``) and whether its credential / endpoint
is present — and, for a local endpoint, whether it is actually reachable. When
it is not, the tier is skipped rather than failed, so CI without secrets stays
green.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

from emporio_agente.config import MODEL


def _reachable(url: str | None, timeout: float = 0.5) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def live_model_available() -> tuple[bool, str]:
    """Return ``(available, reason)`` for the configured ``EMPORIO_MODEL``."""
    provider = MODEL.split(":", 1)[0]

    if provider == "ollama":
        url = os.getenv("OLLAMA_BASE_URL")
        if not url:
            return False, "OLLAMA_BASE_URL not set"
        if not _reachable(url):
            return False, f"Ollama endpoint unreachable at {url}"
        return True, f"ollama via {url}"

    if provider in ("openai", "openai-chat", "openai-responses"):
        if os.getenv("OPENAI_API_KEY") or _reachable(os.getenv("OPENAI_BASE_URL")):
            return True, "openai-compatible endpoint configured"
        return False, "OPENAI_API_KEY / OPENAI_BASE_URL not set"

    if provider == "anthropic":
        if os.getenv("ANTHROPIC_API_KEY"):
            return True, "ANTHROPIC_API_KEY set"
        return False, "ANTHROPIC_API_KEY not set"

    # Unknown provider: best-effort — require *some* credential to be present.
    if any(k.endswith("_API_KEY") and v for k, v in os.environ.items()):
        return True, f"provider '{provider}' with an API key present"
    return False, f"no credential detected for provider '{provider}'"
