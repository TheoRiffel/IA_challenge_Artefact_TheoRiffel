# Exemplo 2 — Status de pedido cancelado

Demonstra um caso de borda dos dados: um pedido **cancelado não tem rastreio**.
O agente explica o status e o **motivo do cancelamento** (vindo dos `notes` do
pedido) em vez de inventar um código de rastreio — o fato é decidido na camada
de dados, não pelo modelo.

> **Execução real** — gerada em **2026-06-21** com `EMPORIO_MODEL=anthropic:claude-sonnet-4-5`, via:
> `python -m emporio_agente.cli --once "queria rastrear o pedido 17"`
> A resposta abaixo é a saída literal do modelo.

> **Ground truth (camada de dados)** — pedido 17: status **cancelled**, data
> 2026-01-28, pagamento PIX, total R$ 689,00, item Giannini GN-15 Nylon Cedr
> Natural (1un), **sem código de rastreio**, motivo: "Pedido cancelado pelo
> cliente antes do processamento".

---

**Você:** queria rastrear o pedido 17

**Assistente:** Oi! Consultei aqui o pedido **#17** pra você.

Infelizmente esse pedido foi **cancelado** em **28/01/2026**. O motivo foi: pedido cancelado pelo cliente antes do processamento.

Como o pedido foi cancelado, não há código de rastreio disponível.

**Detalhes do pedido:**
- **Produto:** Giannini GN-15 Nylon Cedr Natural
- **Valor:** R$ 689,00
- **Forma de pagamento:** PIX

Se você tiver alguma dúvida sobre o cancelamento ou quiser fazer um novo pedido, estou aqui pra te ajudar! 😊
