"""Deterministic routing stub for the offline (Tier 1) eval.

A real LLM is what *decides* which tool to call, so its routing accuracy can
only be measured with a real model (that is the live tier). To make Tier 1 run
in CI without an API key, we replace the model with a deterministic, rule-based
router that plays the model's role: it reads the latest user message and emits
the tool call(s) a correct agent should make, using simple Portuguese keyword
heuristics.

What this lets Tier 1 prove, honestly:
- the routing dataset, the scoring harness, and the expected/actual comparison
  all work and stay green;
- every expected tool is registered on the agent and executes end-to-end
  against the real data layer without error.

What it does NOT prove: that any particular LLM routes correctly. That is the
job of the live tier, which feeds the *same* dataset through a real model.

The router is intentionally generic (keyword rules, not a per-message lookup
table) so it is not a disguised hard-coding of the expected answers.
"""

from __future__ import annotations

import re

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

_WORD_RE = re.compile(r"[a-zà-ÿ0-9]+", re.IGNORECASE)

# Accessories the store explicitly does NOT sell (ARCHITECTURE.md §3.5).
_ACCESSORY = {
    "corda", "cordas", "palheta", "palhetas", "cabo", "cabos", "pedal",
    "pedais", "case", "cases", "capa", "capas", "amplificador",
    "amplificadores", "fone", "fones", "afinador", "afinadores",
    "encordoamento",
}
_POLICY = {
    "devolver", "devolução", "devolucao", "troca", "trocar", "reembolso",
    "arrependimento", "horário", "horario", "horarios", "sábado", "sabado",
    "domingo", "funcionamento", "pagamento", "pagamentos", "pagar",
    "parcelamento", "parcelar", "parcelas", "frete", "entrega", "prazo",
    "garantia", "política", "politica", "politicas", "cnpj", "endereço",
    "endereco", "boleto",
}
_CATEGORY = {
    "guitarra", "guitarras", "baixo", "baixos", "bateria", "baterias",
    "percussão", "percussao", "teclado", "teclados", "piano", "pianos",
    "violão", "violao", "violões", "violoes", "sopro", "ukulele", "ukuleles",
}
_PRICE_PHRASES = (
    "quanto custa", "qual o preço", "qual o preco", "qual é o preço",
    "preço do", "preço da", "preço de", "preco do", "preco da", "quanto sai",
)
_SEARCH_PHRASES = ("vocês têm", "voces tem", "você tem", "voce tem", "quais")

_REFUSAL = (
    "Desculpe, isso está fora do que a Empório da Música atende. "
    "(resposta de recusa simulada para o eval de roteamento offline)"
)
_ANSWERED = "(resposta final simulada — fatos vêm das tools)"


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD_RE.findall(text)}


def _extract_product(message: str) -> str:
    """Best-effort product-name extraction (only affects whether the offline
    lookup resolves; the recorded tool name is unaffected)."""
    low = message.lower()
    for marker in ("custa o ", "custa a ", "custa ", "preço do ", "preço da ",
                   "preco do ", "preco da ", "preço de "):
        idx = low.find(marker)
        if idx != -1:
            return message[idx + len(marker):].strip(" ?.!")
    return message.strip(" ?.!")


def decide(message: str) -> list[tuple[str, dict]]:
    """Map a user message to the tool call(s) a correct agent should make.

    Returns a list of ``(tool_name, args)``; an empty list means "no data tool"
    (an out-of-scope or off-topic message the agent should simply refuse).
    """
    low = message.lower()
    toks = _tokens(message)

    # 1. Accessories / out of scope: refuse, never look up data.
    if toks & _ACCESSORY:
        return []
    # 2. Order status: the word "pedido" plus an order number.
    if "pedido" in toks:
        num = re.search(r"\d+", message)
        if num:
            return [("get_order_status", {"order_id": int(num.group())})]
    # 3. Policy / procedure questions.
    if toks & _POLICY:
        return [("search_policies", {"question": message})]
    # 4. Price of one product.
    if any(p in low for p in _PRICE_PHRASES) or {"preço", "preco"} & toks:
        return [("get_product_details", {"product_name": _extract_product(message)})]
    # 5. Catalogue search (a category word, or a "do you have / which" phrasing).
    if (toks & _CATEGORY) or any(p in low for p in _SEARCH_PHRASES):
        category = next((c.capitalize() for c in toks & _CATEGORY), None)
        return [("search_products", {"query": None, "category": category})]
    # 6. Nothing matched: treat as off-topic, no tool.
    return []


def _latest_user_text(messages: list[ModelMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    return part.content
    return ""


def _routing_function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    # If we have already issued tool calls this run, the tools have returned;
    # emit a final text answer so the agent loop terminates.
    already_called = any(
        isinstance(p, ToolCallPart)
        for m in messages
        if isinstance(m, ModelResponse)
        for p in m.parts
    )
    if already_called:
        return ModelResponse(parts=[TextPart(content=_ANSWERED)])

    decisions = decide(_latest_user_text(messages))
    if not decisions:
        return ModelResponse(parts=[TextPart(content=_REFUSAL)])
    return ModelResponse(
        parts=[ToolCallPart(tool_name=name, args=args) for name, args in decisions]
    )


def routing_stub_model() -> FunctionModel:
    """A FunctionModel that routes deterministically (no network, no API key)."""
    return FunctionModel(_routing_function, model_name="routing-stub")
