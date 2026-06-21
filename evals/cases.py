"""Routing dataset.

Each case pins the tool set the agent *should* end up calling for a given
Portuguese user message. ``expected_tools`` is the empty tuple for messages the
agent must answer WITHOUT any data tool (out-of-scope refusals): the store only
sells instruments, so accessory and off-topic requests get a polite decline,
not a fabricated lookup.

Tool names mirror ``emporio_agente.tools.registry``:
search_products | get_product_details | get_order_status | search_policies
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingCase:
    id: str
    user_message: str
    expected_tools: tuple[str, ...]
    scenario_tag: str


# Real product names / order ids are used so the chosen tool actually resolves
# against the CSV data layer end-to-end (see data/products.csv, data/orders.csv).
CASES: list[RoutingCase] = [
    # --- price of a single product -> get_product_details ------------------
    RoutingCase(
        "price_takamine",
        "Quanto custa o Takamine GD20?",
        ("get_product_details",),
        "price",
    ),
    RoutingCase(
        "price_yamaha",
        "Qual o preço do Yamaha C40?",
        ("get_product_details",),
        "price",
    ),
    # --- catalogue search -> search_products -------------------------------
    RoutingCase(
        "search_violao_budget",
        "Quais violões vocês têm até R$1000?",
        ("search_products",),
        "search",
    ),
    RoutingCase(
        "search_teclados",
        "Quais teclados vocês têm?",
        ("search_products",),
        "search",
    ),
    # --- order status -> get_order_status ----------------------------------
    RoutingCase(
        "order_cancelled",
        "Cadê meu pedido 17?",
        ("get_order_status",),
        "order",
    ),
    RoutingCase(
        "order_delivered",
        "Qual o status do pedido 1?",
        ("get_order_status",),
        "order",
    ),
    # --- policy question -> search_policies --------------------------------
    RoutingCase(
        "policy_return",
        "Posso devolver um produto que comprei?",
        ("search_policies",),
        "policy",
    ),
    RoutingCase(
        "policy_hours",
        "Qual o horário de funcionamento no sábado?",
        ("search_policies",),
        "policy",
    ),
    RoutingCase(
        "policy_payment",
        "Quais as formas de pagamento aceitas?",
        ("search_policies",),
        "policy",
    ),
    # --- out-of-scope accessory -> NO data tool, polite refusal ------------
    RoutingCase(
        "oos_strings",
        "Vocês vendem cordas de violão avulsas?",
        (),
        "out_of_scope_accessory",
    ),
    RoutingCase(
        "oos_cable",
        "Tem cabo P10 para guitarra aí?",
        (),
        "out_of_scope_accessory",
    ),
    # --- fully off-topic -> NO tool, refusal -------------------------------
    RoutingCase(
        "offtopic_weather",
        "Qual a previsão do tempo amanhã em Campo Grande?",
        (),
        "off_topic",
    ),
]
