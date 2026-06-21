"""Command-line chat interface.

Run with:  python -m emporio_agente.cli
The focus is a correct agent; the CLI is intentionally minimal.
"""

from __future__ import annotations

import argparse
import os
import sys

from .config import MODEL
from .session import ChatSession

BANNER = """\
╭──────────────────────────────────────────────╮
│  Empório da Música — Assistente Virtual        │
│  Sua música começa aqui.                       │
╰──────────────────────────────────────────────╯
Digite sua mensagem. Comandos: /reset  /sair
"""


def _credential_hint() -> str | None:
    """Return a friendly message if the selected provider's credential is
    missing, else ``None``. Avoids a cryptic provider error at first call."""
    provider = MODEL.split(":", 1)[0]
    if provider == "ollama":
        if not os.environ.get("OLLAMA_BASE_URL"):
            return (
                "OLLAMA_BASE_URL não está definida — o provedor Ollama precisa do "
                "endereço do servidor (ex.: http://localhost:11434/v1). "
                "Copie .env.example para .env e ajuste, ou rode "
                "`export OLLAMA_BASE_URL=http://localhost:11434/v1`."
            )
        return None
    key_var = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openai-chat": "OPENAI_API_KEY",
        "openai-responses": "OPENAI_API_KEY",
    }.get(provider)
    if key_var and not os.environ.get(key_var):
        return (
            f"A variável {key_var} não está definida para o provedor '{provider}'. "
            "Copie .env.example para .env e preencha a chave, ou rode "
            f"`export {key_var}=...`."
        )
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="emporio",
        description="Agente de atendimento da Empório da Música.",
    )
    parser.add_argument(
        "--once",
        metavar="MENSAGEM",
        help="Executa um único turno com MENSAGEM e sai (modo não interativo).",
    )
    args = parser.parse_args(argv)

    hint = _credential_hint()
    if hint:
        print(f"[config] {hint}", file=sys.stderr)
        return 1

    try:
        session = ChatSession()
    except Exception as exc:  # pragma: no cover - startup diagnostics
        print(f"Falha ao iniciar o agente: {exc}", file=sys.stderr)
        return 1

    # Single-turn mode: print only the reply, so it is easy to script/pipe.
    if args.once is not None:
        try:
            print(session.send_sync(args.once))
            return 0
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            print(f"[erro] {exc}", file=sys.stderr)
            return 1

    print(BANNER)
    print(f"(modelo: {MODEL})\n")

    while True:
        try:
            user = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté logo! 🎵")
            return 0

        if not user:
            continue
        if user in {"/sair", "/quit", "/exit"}:
            print("Até logo! 🎵")
            return 0
        if user == "/reset":
            session.reset()
            print("(conversa reiniciada)\n")
            continue

        try:
            reply = session.send_sync(user)
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            print(f"[erro] {exc}\n", file=sys.stderr)
            continue
        print(f"\nAssistente: {reply}\n")


if __name__ == "__main__":
    raise SystemExit(main())
