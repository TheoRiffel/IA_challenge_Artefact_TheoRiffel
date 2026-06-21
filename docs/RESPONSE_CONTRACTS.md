# Contratos de resposta

Este documento define as **obrigações factuais** de cada tipo de resposta do
agente. Não é texto de prompt — são **expectativas testáveis**: o que uma
resposta correta *precisa* conter (ou *não pode* conter), independentemente da
redação. A fonte de verdade é sempre a camada de dados determinística
(`StoreData` / motor de preços / retriever); o modelo apenas redige.

A Tier 3 do conjunto de avaliação (`evals/`) verifica estes contratos contra o
ground truth calculado a partir de `StoreData`, com checagens de substring e
numéricas — sem juiz LLM. Ver [`../evals/README.md`](../evals/README.md).

## Resposta de preço (`get_product_details`)

DEVE incluir:
- o **nome do produto**;
- a **disponibilidade em estoque** (em estoque / sem estoque / descontinuado);
- o **preço de tabela** (`list_price`);
- o **melhor preço** (`best_price`);
- quando houver **promoção ativa**, a explicação de que o desconto do **PIX (5%)
  não acumula** com a promoção, deixando claro qual é o melhor preço.

NÃO pode:
- apresentar um preço, desconto ou estoque que não venha da ferramenta;
- prometer uma promoção que não esteja **ativa**.

## Resposta de pedido (`get_order_status`)

DEVE incluir:
- o **rótulo de status** (ex.: Entregue, Cancelado, Enviado);
- o **código de rastreio** *somente quando ele existir*;
- o **motivo do cancelamento** quando o pedido estiver cancelado.

NÃO pode:
- conter um **código de rastreio para um pedido cancelado** (cancelado não tem
  rastreio — o motivo é apresentado no lugar);
- inventar um código de rastreio, data ou valor.

## Resposta de política (`search_policies`)

DEVE:
- estar **ancorada em pelo menos uma seção recuperada** do manual (o conteúdo da
  resposta vem das seções devolvidas pela ferramenta, cada uma com `section_id`
  e `title`).

NÃO pode:
- responder de memória nem inventar uma regra que não esteja no conteúdo
  recuperado.
