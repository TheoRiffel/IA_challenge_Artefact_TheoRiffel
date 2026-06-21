# Exemplo 1 — Preço com promoção ativa (cenário não trivial)

Demonstra o caso de borda mais importante: um produto com **promoção ativa**,
onde a regra de **não-cumulatividade do PIX** (política 6.2) decide o melhor
preço. Os valores vêm do motor de preços determinístico, não do modelo.

> **Execução real** — gerada em **2026-06-21** com `EMPORIO_MODEL=anthropic:claude-sonnet-4-5`, via:
> `python -m emporio_agente.cli --once "quanto custa o Taylor 110e?"`
> A resposta abaixo é a saída literal do modelo.

> **Ground truth (camada de dados)** — Taylor 110e Dreadnought Natural (id 94):
> tabela R$ 5.999,00 · promoção ativa "Desconto Exclusivo" 8% → R$ 5.519,08 ·
> PIX R$ 5.699,05 · **melhor preço R$ 5.519,08** (promo vence; PIX não acumula) ·
> 4 unidades em estoque.

---

**Você:** quanto custa o Taylor 110e?

**Assistente:** Opa! O **Taylor 110e Dreadnought Natural** está disponível aqui na loja! 🎸

Esse violão é top: tampo sólido em Sitka Spruce, eletrônica ES2 da Taylor — ideal pra quem quer um som amplificado de alta fidelidade no palco.

**Preço:**
- **De:** R$ 5.999,00
- **Por:** R$ 5.519,08 **(8% OFF)** na promoção **Desconto Exclusivo**

💡 *Lembrando que o desconto do PIX (5%) não acumula com a promoção, então o melhor preço é o promocional mesmo: **R$ 5.519,08**.*

Temos **4 unidades** em estoque!

Posso te ajudar com mais alguma coisa? 😊
