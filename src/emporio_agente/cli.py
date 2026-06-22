"""Command-line chat interface.

Run with:  python -m emporio_agente.cli
The focus is a correct agent; the CLI is intentionally minimal.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import unicodedata

from .config import MODEL
from .session import ChatSession
from .trace import format_trace

_BOLD = "\033[1m"
_RESET = "\033[0m"
_BOLD_MD = re.compile(r"(?:\*\*|__)(.+?)(?:\*\*|__)")


def _build_banner() -> str:
    """Build the title box so the borders always line up with the content
    (computed width instead of hand-aligned spaces)."""
    lines = ["Empório da Música — Assistente Virtual", "Sua música começa aqui."]
    pad = 2
    norm = [unicodedata.normalize("NFC", line) for line in lines]
    width = max(len(line) for line in norm) + pad * 2
    top = "╭" + "─" * width + "╮"
    bottom = "╰" + "─" * width + "╯"
    middle = [f"│{' ' * pad}{line}{' ' * (width - pad - len(line))}│" for line in norm]
    box = "\n".join([top, *middle, bottom])

    options = "\n".join([
        "Posso te ajudar a:",
        "  🎸 Encontrar o instrumento ideal",
        "  💰 Consultar preços e condições de pagamento",
        "  📦 Verificar status de pedidos",
        "  ❓ Tirar dúvidas sobre trocas, devoluções, garantias e entregas",
    ])
    examples = "\n".join([
        "Exemplos de perguntas:",
        "  • Quais violões vocês têm até R$ 1.000?",
        "  • Quanto custa o Taylor 110e?",
        "  • Posso devolver um produto que comprei?",
    ])
    return (
        f"{box}\n\n{options}\n\n{examples}\n\n"
        "Digite sua mensagem. Comandos: /reset  /sair\n"
    )


BANNER = _build_banner()


def _format_reply(text: str) -> str:
    """Render markdown bold for display: real bold on a terminal, plain text
    (markers stripped) when piped/redirected so scripts get clean output."""
    if sys.stdout.isatty():
        return _BOLD_MD.sub(rf"{_BOLD}\1{_RESET}", text)
    return _BOLD_MD.sub(r"\1", text)


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


def _debug_enabled(flag: bool) -> bool:
    """Debug on via --debug or EMPORIO_DEBUG (1/true/yes/on)."""
    return flag or os.environ.get("EMPORIO_DEBUG", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _send(session: ChatSession, message: str, debug: bool) -> str:
    """Run one turn, emitting a debug trace to stderr when enabled."""
    start = time.perf_counter()
    reply = session.send_sync(message)
    if debug and session.last_result is not None:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(format_trace(session.last_result, MODEL, elapsed_ms), file=sys.stderr)
    return reply


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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Imprime no stderr um trace (tools, argumentos, modelo, latência) "
        "após cada turno. Também ativável via EMPORIO_DEBUG=1.",
    )
    args = parser.parse_args(argv)
    debug = _debug_enabled(args.debug)

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
            print(_format_reply(_send(session, args.once, debug)))
            return 0
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            print(f"[erro] {exc}", file=sys.stderr)
            return 1

    print(BANNER)

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
            reply = _send(session, user, debug)
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            print(f"[erro] {exc}\n", file=sys.stderr)
            continue
        print(f"\nAssistente: {_format_reply(reply)}\n")


if __name__ == "__main__":
    raise SystemExit(main())
