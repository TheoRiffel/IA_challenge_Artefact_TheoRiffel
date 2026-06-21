"""Optional debug trace of an agent turn (for reviewability).

Reads the tool-call and tool-return parts out of a pydantic_ai run result and
renders a compact, reviewer-friendly summary: which tools ran with what
arguments, a one-line result summary per tool (never the full payload), the
model used, and the turn latency. The CLI prints this to stderr so it never
pollutes the assistant reply on stdout.

No new dependencies — pydantic_ai is already used by the agent.
"""

from __future__ import annotations

import json

from pydantic_ai.messages import ToolCallPart, ToolReturnPart


def _format_args(args) -> str:
    if args is None:
        return ""
    if isinstance(args, str):
        # pydantic_ai may store tool args as a JSON string.
        try:
            args = json.loads(args)
        except (ValueError, TypeError):
            return args.strip()
    if isinstance(args, dict):
        return ", ".join(f"{k}={v!r}" for k, v in args.items() if v is not None)
    return str(args)


def _summarize_result(content) -> str:
    """One-line summary of a tool's return — never the full payload.

    Uses duck typing on the domain models so this module stays decoupled from
    ``models.py``; falls back to a truncated string for anything else.
    """
    if content is None:
        return "—"
    if hasattr(content, "count") and hasattr(content, "products"):
        flag = " [sinal de desambiguação]" if getattr(content, "disambiguation", None) else ""
        return f"{content.count} produto(s){flag}"
    if hasattr(content, "order_id") and hasattr(content, "status"):
        return f"pedido {content.order_id}: {getattr(content, 'status_label_ptbr', content.status)}"
    if hasattr(content, "chunks"):
        return f"{len(content.chunks)} seção(ões) de política"
    if hasattr(content, "name") and hasattr(content, "pricing"):
        return f"{content.name}: melhor preço R$ {content.pricing.best_price:.2f}"
    text = " ".join(str(content).split())
    return text[:100] + ("…" if len(text) > 100 else "")


def format_trace(result, model: str, elapsed_ms: float) -> str:
    """Render a compact trace of one agent turn.

    ``result`` is a pydantic_ai run result — anything exposing
    ``all_messages()`` whose messages carry ``parts``.
    """
    calls: list[tuple[str, str, object]] = []  # (call_id, name, args)
    returns: dict[str, object] = {}
    for msg in result.all_messages():
        for part in getattr(msg, "parts", []):
            if isinstance(part, ToolCallPart):
                calls.append((part.tool_call_id, part.tool_name, part.args))
            elif isinstance(part, ToolReturnPart):
                returns[part.tool_call_id] = part.content

    lines = [
        "[debug] trace da interação",
        f"  modelo:   {model}",
        f"  latência: {elapsed_ms:.0f} ms",
    ]
    if not calls:
        lines.append("  tools:    (nenhuma tool chamada)")
    else:
        lines.append("  tools:")
        for call_id, name, args in calls:
            lines.append(f"    • {name}({_format_args(args)})")
            if call_id in returns:
                lines.append(f"      → {_summarize_result(returns[call_id])}")
    return "\n".join(lines)
