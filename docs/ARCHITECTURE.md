# Arquitetura — Agente de Atendimento Empório da Música

Este documento descreve a arquitetura do agente, as decisões técnicas e o
porquê de cada uma. A premissa central: **decisões devem seguir o que os dados
realmente suportam**, não o contrário.

---

## 1. Tese central: é um híbrido, e a decisão interessante é a divisão

Os materiais fornecidos têm duas naturezas muito diferentes:

| Natureza | Conteúdo | Tipo de pergunta | Abordagem certa |
|---|---|---|---|
| **Estruturada e relacional** | 65 produtos, 50 clientes, 20 pedidos, 25 promoções | "Quanto custa o X?", "Cadê meu pedido?" | **Function calling** sobre uma camada de dados tipada |
| **Prosa** | Manual de políticas (8 páginas) | "Posso devolver?", "Quais formas de pagamento?" | **RAG** leve por seção |

A decisão mais importante do projeto é **não embeddar os dados estruturados**.
Embeddar 65 linhas e fazer busca por similaridade seria mais lento, mais difuso
e capaz de *alucinar um preço*. Dados relacionais exatos pedem consulta
determinística, onde a resposta é verificável. RAG entra apenas onde a pergunta
é semântica: a prosa das políticas.

> Mostrar que a escolha foi **deliberadamente não usar RAG para tudo** é o
> ponto que demonstra julgamento — e não apenas familiaridade com a ferramenta
> da moda.

---

## 2. Visão geral

```
Cliente (CLI)
     │
     ▼
┌─────────────────────────────────────────────┐
│  Pydantic AI Agent                           │
│  • persona (do manual, seção 7.1)            │   modelo trocável
│  • orquestração de tools                     │ ──────────────────►  Anthropic /
│  • dependency injection (RunContext)         │                      OpenAI / local
└─────────────────────────────────────────────┘
     │ tool calls (function calling)
     ▼
┌───────────────┬───────────────┬──────────────┬────────────────────┐
│search_products│product_details│ order_status │  search_policies    │
└───────────────┴───────────────┴──────────────┴────────────────────┘
     │                                                  │
     ▼                                                  ▼
┌──────────────────────────────────────────┐   ┌────────────────────┐
│  Camada de dados (lógica determinística)  │   │  PolicyRetriever    │
│  • DataFrames dos CSVs                     │   │  • 26 chunks/seção  │
│  • motor de preços (melhor preço, PIX,     │   │  • BGE-M3 local     │
│    promo não-cumulativa)                   │   │  • cosine + keyword │
│  • NÚMEROS NUNCA VÊM DO LLM                 │   └────────────────────┘
└──────────────────────────────────────────┘            │
     │                                                   ▼
     ▼                                          políticas_da_loja.pdf
  data/*.csv
```

O **princípio que sustenta tudo**: cada fato (preço, desconto, estoque, status,
descontinuado, escopo) é calculado/retornado pela camada de dados como um
**objeto Pydantic tipado**. O LLM apenas escolhe a ferramenta e **redige** a
resposta no tom da loja. Resultado: números corretos e camada de negócio
testável sem nenhuma chamada de modelo.

---

## 3. Decisões técnicas

### 3.1 Framework do agente — Pydantic AI

Escolhido pela propriedade que o desafio implicitamente recompensa:
**trocabilidade**.

- O modelo é uma string `"provider:model"` — trocar Anthropic → OpenAI → modelo
  local é mudar uma variável de ambiente (`EMPORIO_MODEL`), nada mais.
- Tools são funções Python decoradas com `@agent.tool`; a assinatura tipada +
  o retorno Pydantic viram o schema que o modelo enxerga.
- **Dependency injection via `RunContext`**: a camada de dados e o retriever são
  injetados em cada tool. As tools viram funções puras de `(deps, args)`,
  trivialmente testáveis com um `deps` falso, e a fonte de dados, o provedor do
  modelo e o retriever são trocáveis de forma independente.

**Sobre a restrição Python.** A ideia inicial considerou o Vercel AI SDK
(TypeScript) pela mesma propriedade de trocabilidade. Como a *única restrição
técnica obrigatória* do desafio é usar Python, optou-se por Pydantic AI, que
entrega exatamente a mesma trocabilidade respeitando a restrição. Foi uma
decisão consciente, não um acidente.

### 3.2 Agente fino, tools "gordas"

Toda a lógica de negócio (cálculo de melhor preço, "pedido cancelado não tem
rastreio", detecção de escopo, produto descontinuado) vive na camada de
dados/tools, em Python determinístico. O LLM só orquestra e redige. Isso é o que
torna as respostas confiáveis: os números nunca vêm do modelo, só a redação.

### 3.3 Motor de preços (versão "afiada")

Centralizado em `pricing.py`, aplicando a regra da seção 6.2 do manual:

- Preço de tabela = `price_brl`.
- Promoção **ativa** (`is_active == 1`) desconta o preço de tabela.
- PIX dá 5% sobre o preço de tabela, mas **não é cumulativo** com promoção.
- `best_price` é o menor valor que o cliente realmente paga, com uma razão
  legível, apresentado de forma transparente junto ao preço original.

Detalhe que vira diferencial: dos 25 registros de promoção, **apenas 4 estão
ativos**. O manual diz explicitamente "nunca prometer um desconto que não está
mais vigente" — então a tool aplica apenas promoções ativas. É uma armadilha
embutida nos dados que o agente passa.

### 3.4 RAG de políticas — leve e na escala certa

- **Chunking por seção**: o PDF tem cabeçalhos numerados limpos (1, 1.1, 2, ...).
  Dividimos nessas fronteiras para que cada chunk seja uma unidade coerente de
  política, em vez de janelas de tamanho fixo que poderiam cortar uma regra ao
  meio. Resultado: 26 chunks.
- **Embeddings locais (BGE-M3)** via sentence-transformers, na GPU, calculados
  uma vez e cacheados em disco (`.embeddings.pkl`). Zero custo de API e
  reprodutível offline.
- **Sem banco vetorial**: com 26 chunks, similaridade de cosseno em numpy é
  tudo que é preciso — mais rápido, mais simples e reprodutível. Rejeitar um
  vector DB aqui é uma escolha consciente de escala, espelhando a decisão de não
  embeddar os dados estruturados.
- **Fallback por palavra-chave**: algumas perguntas factuais (CNPJ, "horário de
  sábado", "boleto") são melhor respondidas por presença de termo do que por
  semântica. Um boost leve de keyword (15%) sobre o score semântico (85%) eleva
  a qualidade nessas consultas.

### 3.5 Escopo e segurança — tratados deliberadamente (3 níveis)

1. **No escopo** (instrumento, pedido, política) → atende normalmente.
2. **Fora de escopo, mas adjacente** (acessórios: cordas, palhetas, cabos,
   cases, pedais, amplificadores) → a loja explicitamente não vende isso
   (seções 1 e 7.1); recusa gentil e redirecionamento, sem inventar lojas
   parceiras específicas.
3. **Totalmente fora de contexto** → recusa cordial e redirecionamento.

Isso vive parte no system prompt, parte como comportamento explícito. Fatos como
"produto descontinuado" e "pedido cancelado sem rastreio" são tratados **dentro
das tools** (a camada de dados retorna um sinal tipado), não por instrução de
prompt — mesmo princípio dos preços.

### 3.6 Persona

O próprio manual (seção 7.1) define o tom: "informal mas profissional... como um
amigo que entende de música". Codificamos isso diretamente no system prompt em
vez de inventar uma voz — sinal de que o material foi lido por inteiro.

### 3.7 Persistência

Histórico de conversa em memória, por sessão. Escopo honesto para um protótipo:
mantém contexto multi-turno sem trazer Redis/banco. A abstração (`ChatSession`)
é fina o suficiente para um backend persistente substituí-la sem tocar no agente
nem na CLI.

---

## 4. Estrutura do repositório

```
emporio-agente/
├── data/                          # CSVs + PDF de políticas
├── src/emporio_agente/
│   ├── config.py                  # paths, modelo, constantes de negócio
│   ├── models.py                  # contratos Pydantic (tipos de retorno)
│   ├── pricing.py                 # motor de preços (regra 6.2)
│   ├── persona.py                 # system prompt (do manual)
│   ├── agent.py                   # montagem do Agent
│   ├── dependencies.py            # container injetado nas tools
│   ├── session.py                 # histórico em memória
│   ├── cli.py                     # interface de linha de comando
│   ├── data/
│   │   └── store.py               # camada de dados (DataFrames + acessores)
│   ├── policies/
│   │   ├── chunker.py             # chunking por seção do PDF
│   │   └── retriever.py           # embeddings locais + cosine + keyword
│   └── tools/
│       └── registry.py            # as 4 tools tipadas
├── tests/                         # testes da camada determinística (sem LLM)
├── evals/                         # routing offline + qualidade opt-in/live
├── examples/                      # transcrições de conversas
└── docs/ARCHITECTURE.md           # este documento
```

---

## 5. Por que essa camada é testável sem LLM

Os 27 testes exercitam preços, casos de borda dos dados, chunking de políticas,
validações defensivas e roteamento offline **sem nenhuma chamada de modelo**.
O motor de preços é o conjunto mais importante: fixa as regras de dinheiro
(6.2) de forma determinística. Isso só é possível porque o agente é fino e as
tools são gordas.

---

## 6. Limitações conhecidas e próximos passos

- **Persistência**: hoje em memória; com mais tempo, sessões em Redis/DB.
- **Avaliação**: já existe um *eval set* pequeno em `evals/`, com roteamento
  offline e qualidade de resposta opt-in/live. O próximo passo é ampliar os
  casos e pontuar os argumentos das tools, não apenas o conjunto de tools.
- **Desambiguação de pedido**: hoje o cliente precisa informar o número do
  pedido; um fluxo por nome/telefone (cruzando `customers`) seria mais natural.
- **Busca de produtos**: substring case-insensitive cobre bem o catálogo
  pequeno; em escala maior, valeria busca fuzzy/semântica sobre nomes.
- **Camada de API/UI**: a CLI é mínima por escolha; o mesmo núcleo do agente
  poderia ganhar uma fina camada HTTP sem alterações.
