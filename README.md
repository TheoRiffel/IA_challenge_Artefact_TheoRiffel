# Empório da Música — Agente de Atendimento

Protótipo de um agente de atendimento por texto para a **Empório da Música**,
uma loja (fictícia) de instrumentos musicais em Campo Grande/MS. O agente atende
dúvidas sobre produtos, preços, estoque e pedidos (dados estruturados) e sobre
políticas da loja — horários, trocas, pagamento, frete (prosa) —, sempre na voz
da loja, e lida graciosamente com pedidos fora de escopo.

> Desafio Técnico — AI Engineer (Artefact).

---

## TL;DR da arquitetura

É um **híbrido**, e a decisão de design mais importante é a *divisão*:

- **Dados estruturados** (produtos, pedidos, promoções) → **function calling**
  sobre uma camada de dados tipada e determinística. **Não são embeddados** —
  preço/estoque/status são consultas exatas, não busca por similaridade. Isso
  elimina a possibilidade de o modelo *alucinar um preço*.
- **Políticas** (PDF, prosa) → **RAG leve por seção**, com embeddings locais
  (BGE-M3) e busca por cosseno + fallback de palavra-chave. Sem banco vetorial:
  com 26 chunks, numpy basta.

Princípio que sustenta tudo: **os números nunca vêm do LLM**. Cada fato é
calculado pela camada de dados e devolvido como objeto Pydantic tipado; o modelo
apenas redige. Detalhes completos em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Como rodar

### 1. Pré-requisitos
- Python 3.10+
- Uma chave de API do provedor escolhido (Anthropic por padrão), **ou** um
  modelo local (ex.: Ollama).

### 2. Instalação

```bash
git clone <seu-repo>
cd emporio-agente

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
# ou, como pacote:  pip install -e .
```

> Na primeira execução, o modelo de embeddings **BGE-M3** (~2 GB) é baixado uma
> vez e os embeddings das políticas ficam cacheados em disco. Execuções
> seguintes não pagam esse custo. Se preferir um download mais leve para
> avaliação, veja a seção *Trocando o modelo de embeddings* abaixo.

### 3. Configuração

```bash
cp .env.example .env
# edite .env e preencha a chave do provedor escolhido
```

`.env` principais variáveis:

```bash
EMPORIO_MODEL=anthropic:claude-sonnet-4-5   # provider:model
ANTHROPIC_API_KEY=...                        # ou OPENAI_API_KEY, etc.
```

### 4. Executar

```bash
python -m emporio_agente.cli
# ou, se instalou como pacote:  emporio
```

Comandos na CLI: `/reset` (limpa o histórico), `/sair`.

### 5. Testes

```bash
pip install -e ".[dev]"
pytest -q
```

Os 27 testes cobrem o **núcleo determinístico** (preços, casos de borda dos
dados, chunking de políticas e evals offline) **sem nenhuma chamada de LLM**.

---

## Trocando o provedor do modelo

A trocabilidade foi um objetivo de design. Mude apenas `EMPORIO_MODEL`:

```bash
EMPORIO_MODEL=anthropic:claude-sonnet-4-5     # Anthropic (padrão)
EMPORIO_MODEL=openai:gpt-4o-mini              # OpenAI
EMPORIO_MODEL=ollama:llama3.1                 # local, via Ollama
```

Nenhuma outra linha do código muda. Isso é viabilizado pela abstração de modelo
do Pydantic AI.

### Trocando o modelo de embeddings

```bash
# Mais leve/rápido (bom o suficiente para 26 chunks):
EMPORIO_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

---

## Decisões técnicas (resumo)

| Decisão | Escolha | Por quê |
|---|---|---|
| Framework do agente | **Pydantic AI** | Trocabilidade de modelo (1 var de ambiente), tools tipadas, dependency injection. Respeita a restrição "Python". |
| Abordagem | **Function calling + RAG (híbrido)** | Dados exatos → tools determinísticas; prosa → retrieval. Não embeddar dados estruturados evita alucinar números. |
| Modelo de preços | **Versão "afiada"** | Aplica promoção ativa + regra de não-cumulatividade do PIX (seção 6.2), apresentando preço original e desconto. |
| Embeddings | **BGE-M3 local (GPU)** | Sem custo de API, reprodutível offline, forte em PT-BR. |
| Vector store | **Nenhum (numpy)** | 26 chunks não justificam um banco vetorial; cosseno em memória é mais simples e rápido. |
| Interface | **CLI** | O foco é o agente correto, não a UI. |
| Persistência | **Em memória, por sessão** | Escopo honesto de protótipo; abstração fina permite trocar por backend persistente. |
| Persona | **Do próprio manual (7.1)** | "Informal mas profissional, como um amigo que entende de música." |

Justificativas completas em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Decisões e alternativas rejeitadas

Tão importante quanto o que foi escolhido é o que foi **deliberadamente
descartado**:

| Alternativa considerada | Por que NÃO foi escolhida |
|---|---|
| **RAG sobre os CSVs** | Dados exatos pedem consulta determinística; embeddar 65 linhas pode alucinar um preço. |
| **Banco vetorial para ~26 chunks** | Cosseno em numpy é mais simples e rápido nessa escala. |
| **SQL agent** (texto → SQL) | Com 6 padrões de consulta, tools tipadas são mais seguras e testáveis que geração de SQL. |
| **Vercel AI SDK como implementação principal** | A única restrição obrigatória é Python; Pydantic AI entrega a mesma trocabilidade respeitando-a. |

Também foi considerada — e **deliberadamente adiada** — uma camada de *runtime
port* (um `AgentRuntime` genérico por cima do Pydantic AI) para abstrair o
framework do agente. Com uma única implementação concreta hoje, isso seria
generalidade especulativa: a costura natural já está em `agent.py`
(`build_agent`), e este README documenta **onde** ela ficaria em vez de manter
uma abstração vazia.

---

## Comportamentos que valem destacar

Casos de borda presentes nos dados e tratados de forma deliberada:

- **Apenas 4 das 25 promoções estão ativas** → a tool aplica somente promoções
  ativas e nunca promete desconto vencido.
- **PIX (5%) não acumula com promoção** → o motor de preços decide o melhor
  preço corretamente e o apresenta junto ao preço original.
- **Produto descontinuado** (Shelby SN-7C, id 113) → informa que saiu de linha e
  sugere similares.
- **Pedidos cancelados não têm rastreio** → o agente explica o status e o motivo
  em vez de inventar um código.
- **Escopo**: a loja só vende instrumentos; pedidos de acessórios (cordas,
  pedais, cabos...) são recusados com gentileza.

Veja [`examples/`](examples/) para transcrições reais cobrindo esses cenários.

As obrigações factuais de cada tipo de resposta (o que uma resposta correta
precisa conter, e o que não pode conter) estão formalizadas como contratos
testáveis em [`docs/RESPONSE_CONTRACTS.md`](docs/RESPONSE_CONTRACTS.md).

---

## Limitações conhecidas e próximos passos

- **Persistência** apenas em memória; com mais tempo, sessões em Redis/DB.
- **Avaliação**: já há um conjunto pequeno em `evals/` para roteamento offline e
  qualidade de resposta opt-in com modelo real; o próximo passo seria ampliar
  os casos e pontuar também os argumentos das tools.
- **Desambiguação de pedido** exige o número do pedido; um fluxo por
  nome/telefone (cruzando `customers`) seria mais natural.
- **Busca de produtos** é por substring; em catálogos maiores, busca
  fuzzy/semântica sobre nomes ajudaria.

---

## Uso de assistentes de IA

Este projeto foi desenvolvido com auxílio de **Claude** (Anthropic):

- **Discussão de arquitetura**: o desenho da solução (híbrido, divisão
  dados-estruturados vs. prosa, decisão de não usar vector DB, regra de preço
  afiada) foi debatido e refinado em conversa antes de qualquer código — a
  intenção foi *entender a solução*, não gerar código às cegas.
- **Implementação assistida com Claude Code**: scaffolding do repositório,
  camada de dados, motor de preços, chunker/retriever e testes foram escritos
  com assistência, sempre validados contra os dados reais (ex.: o chunker foi
  iterado depois de inspecionar a extração real do pypdf, que cola cabeçalhos no
  corpo).
- **Revisão**: as decisões e trade-offs foram revisados criticamente — preferindo
  resultados honestos e verificáveis a afirmações exageradas.

O workflow priorizou raciocínio explícito e verificação empírica a cada passo.
