"""Command-line chat interface.

Run with:  python -m emporio_agente.cli
The focus is a correct agent; the CLI is intentionally minimal.
"""

from __future__ import annotations

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


def main() -> int:
    print(BANNER)
    print(f"(modelo: {MODEL})\n")
    try:
        session = ChatSession()
    except Exception as exc:  # pragma: no cover - startup diagnostics
        print(f"Falha ao iniciar o agente: {exc}", file=sys.stderr)
        return 1

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
