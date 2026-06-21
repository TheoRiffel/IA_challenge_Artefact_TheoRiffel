"""Tier 3 — answer-quality harness (opt-in, needs a real model).

Runs the real agent end-to-end (real StoreData + real PolicyRetriever + the
configured model) and checks factual correctness of the reply with deterministic
substring / numeric / regex checks against ground truth from the data layer.
No LLM-as-judge: checks are cheap, reproducible, and explain why they passed.

The checks encode the obligations in ``docs/RESPONSE_CONTRACTS.md`` and protect
the core invariant — facts come from the data layer, never the model — e.g. a
price answer must quote the list AND best price and the PIX-non-cumulative note
when a promo is active; a cancelled order must NOT carry a tracking code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from emporio_agente.dependencies import AgentDependencies
from emporio_agente.session import ChatSession

from . import ground_truth as gt

# A tracking code looks like "BRAB1234567BR" in this dataset.
_TRACKING_RE = re.compile(r"BR[A-Z0-9]{6,}BR")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


# -- Checks: each takes the agent reply and returns (passed, detail) ---------
def _check_price_contract(reply: str) -> tuple[bool, str]:
    # Full price contract (RESPONSE_CONTRACTS.md). Taylor 110e has an ACTIVE
    # promotion, so the non-cumulative-PIX clause is exercised here.
    p = gt.product_by_name("Taylor 110e")
    low = _norm(reply)
    checks = {
        "nome": _norm("Taylor 110e") in low,
        "preço de tabela": any(v.lower() in low for v in gt.price_variants(p.pricing.list_price)),
        "melhor preço": any(v.lower() in low for v in gt.price_variants(p.pricing.best_price)),
        "estoque": any(t in low for t in ("estoque", "unidade", "disponív")),
        "PIX não-cumulativo": any(t in low for t in ("não acumula", "nao acumula", "cumulativ")),
    }
    missing = [k for k, ok in checks.items() if not ok]
    if missing:
        return False, f"resposta de preço incompleta — faltou: {missing}"
    return True, "resposta de preço cobre nome, tabela, melhor preço, estoque e nota PIX"


def _check_cancelled_no_tracking(reply: str) -> tuple[bool, str]:
    o = gt.order(17)
    assert o and o.is_cancelled and o.tracking_code is None  # ground-truth sanity
    ok = _TRACKING_RE.search(reply) is None
    return ok, "cancelled order reply must NOT contain a tracking code"


def _check_delivered_tracking(reply: str) -> tuple[bool, str]:
    code = gt.order(1).tracking_code
    ok = code is not None and code.lower() in _norm(reply)
    return ok, f"delivered order reply must contain tracking code {code!r}"


def _check_violao_budget(reply: str) -> tuple[bool, str]:
    res = gt.search("Violões", max_price=1000.0)
    names = [p.name for p in res.products[:3]]
    low = _norm(reply)
    ok = any(_norm(n) in low for n in names)
    return ok, f"reply must list a real in-budget violão (one of {names})"


def _check_return_window(reply: str) -> tuple[bool, str]:
    low = _norm(reply)
    ok = "7" in low and "dia" in low
    return ok, "return-policy reply must mention the 7-day window"


def _check_accessory_no_price(reply: str) -> tuple[bool, str]:
    # Out-of-scope accessory: the agent must not invent a price for it.
    ok = "r$" not in reply.lower() and _TRACKING_RE.search(reply) is None
    return ok, "out-of-scope accessory reply must not quote a price"


@dataclass
class AnswerCase:
    id: str
    user_message: str
    check: Callable[[str], tuple[bool, str]]


ANSWER_CASES: list[AnswerCase] = [
    AnswerCase("price_taylor", "Quanto custa o Taylor 110e?", _check_price_contract),
    AnswerCase("order_cancelled", "Cadê meu pedido 17?", _check_cancelled_no_tracking),
    AnswerCase("order_delivered", "Qual o status do pedido 1?", _check_delivered_tracking),
    AnswerCase("violao_budget", "Quais violões vocês têm até R$1000?", _check_violao_budget),
    AnswerCase("policy_return", "Posso devolver um produto que comprei?", _check_return_window),
    AnswerCase("oos_strings", "Vocês vendem cordas de violão avulsas?", _check_accessory_no_price),
]


@dataclass
class AnswerResult:
    case: AnswerCase
    reply: str
    passed: bool
    detail: str


def run_answer_quality(cases=ANSWER_CASES) -> list[AnswerResult]:
    """Run each answer case end-to-end against the real model and data layer.

    A fresh session per case keeps cases independent (no carried-over context).
    """
    results: list[AnswerResult] = []
    for case in cases:
        session = ChatSession(deps=AgentDependencies.build())
        reply = session.send_sync(case.user_message)
        passed, detail = case.check(reply)
        results.append(AnswerResult(case, reply, passed, detail))
    return results
