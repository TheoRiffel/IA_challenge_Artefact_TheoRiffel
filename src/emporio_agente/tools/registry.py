"""Tool definitions.

Four typed tools, each a thin wrapper over the deterministic data/retrieval
layer. They are registered onto an ``Agent`` via ``register_tools`` so the
agent construction stays declarative and the tools stay independently testable.

Design notes:
- Tools return Pydantic models, not strings. The model receives structured
  facts and only phrases them.
- Facts like "discontinued" or "cancelled order has no tracking" are surfaced
  as fields here, not left to prompt instructions.
"""

from __future__ import annotations

from pydantic_ai import RunContext

from ..dependencies import AgentDependencies
from ..models import OrderStatus, PolicyAnswer, Product, ProductSearchResult


def register_tools(agent) -> None:
    """Attach all tools to a Pydantic AI ``Agent[AgentDependencies, str]``."""

    @agent.tool
    def search_products(
        ctx: RunContext[AgentDependencies],
        query: str | None = None,
        category: str | None = None,
        max_price_brl: float | None = None,
    ) -> ProductSearchResult:
        """Busca produtos no catálogo por nome/descrição, categoria e/ou preço
        máximo. Use para perguntas como "violões até R$1000" ou "quais teclados
        vocês têm". Retorna apenas itens em estoque, ordenados pelo melhor preço.

        Categorias válidas: Guitarras, Baixos, Baterias e Percussão, Teclados e
        Pianos, Violões, Instrumentos de Sopro (Madeiras), Instrumentos de Sopro
        (Metais), Cordas Orquestrais, Ukuleles.

        Se o resultado vier com o campo 'disambiguation' preenchido (ex.: o termo
        'cordas' é ambíguo, ou é um acessório que a loja não vende), NÃO assuma:
        peça esclarecimento ao cliente ou explique o escopo.
        """
        return ctx.deps.store.search_products(
            query=query,
            category_name=category,
            max_price=max_price_brl,
            only_in_stock=True,
        )

    @agent.tool
    def get_product_details(
        ctx: RunContext[AgentDependencies],
        product_name: str | None = None,
        product_id: int | None = None,
    ) -> Product | None:
        """Retorna detalhes de UM produto: preço de tabela, preço promocional
        (se houver promoção ATIVA), preço no PIX, melhor preço disponível (com
        a regra de não-cumulatividade já aplicada), estoque e se foi
        descontinuado. Use para "quanto custa o X" ou "tem o modelo Y em
        estoque". Informe product_id quando souber, senão product_name.
        """
        store = ctx.deps.store
        if product_id is not None:
            return store.get_product(product_id)
        if product_name:
            return store.find_product_by_name(product_name)
        return None

    @agent.tool
    def get_order_status(
        ctx: RunContext[AgentDependencies], order_id: int
    ) -> OrderStatus | None:
        """Consulta o status de um pedido pelo número: status atual, data, valor,
        forma de pagamento, código de rastreio e previsão de entrega. Pedidos
        cancelados não têm rastreio — o motivo do cancelamento é retornado.
        Retorna None se o pedido não existir.
        """
        return ctx.deps.store.get_order(order_id)

    @agent.tool
    def search_policies(
        ctx: RunContext[AgentDependencies], question: str
    ) -> PolicyAnswer:
        """Consulta o manual de políticas da loja para responder sobre horários,
        endereço, formas de pagamento e parcelamento, trocas e devoluções,
        frete e entrega, garantia, promoções e dados da empresa. Use sempre que
        a pergunta for sobre uma regra/procedimento, e não sobre um produto ou
        pedido específico.

        Retorna as seções mais relevantes do manual, cada uma com número
        (section_id) e título. Baseie a resposta NO CONTEÚDO dessas seções e
        ancore-a nelas de forma natural (ex.: "Pela nossa política de
        devolução..."); cite o número da seção apenas quando ajudar.
        """
        return ctx.deps.policies.search(question)
