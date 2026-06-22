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

### Modo debug / trace (revisão)

```bash
python -m emporio_agente.cli --debug              # ou EMPORIO_DEBUG=1
python -m emporio_agente.cli --once "..." --debug
```

Com o debug ligado, após cada turno o agente imprime no **stderr** um trace
compacto: a(s) tool(s) selecionada(s) e seus argumentos, um resumo de uma linha
do resultado de cada tool, o modelo usado e a latência (ms). A resposta ao
cliente continua limpa no **stdout**. Desligado por padrão, sem efeito algum
quando não usado.

### 5. Testes

```bash
pip install -e ".[dev]"
pytest -q
```

Os testes cobrem o **núcleo determinístico** (preços, casos de borda dos dados,
chunking de políticas, busca/desambiguação, formatação do trace e evals offline)
**sem nenhuma chamada de LLM**.

---

## Rodar com Docker (sem setup local de Python)

Para avaliar sem instalar Python/venv nem as dependências de ML na máquina:

```bash
cp .env.example .env          # preencha a chave do provedor (ou um modelo local — abaixo)
docker compose build
docker compose run --rm app   # CLI interativa; saia com /sair
```

Use `docker compose run --rm app` (e **não** `up`): a CLI é interativa, então
precisa do TTY anexado e do container encerrando limpo ao digitar `/sair`.

Um único turno (bom para script/demo):

```bash
docker compose run --rm app python -m emporio_agente.cli --once "Quanto custa o Taylor 110e?"
```

Detalhes do que a imagem faz de propósito:

- **Imagem enxuta (~1,7 GB):** instala **torch CPU-only** (não baixa ~2,5 GB de
  libs CUDA). O modelo de embeddings **não** é embutido na imagem.
- **Cache persistente:** o modelo de embeddings e os embeddings calculados são
  baixados **uma vez** para um volume (`emporio-cache`, montado em `/cache` via
  `HF_HOME`); execuções seguintes sobem instantâneas.
- **Embeddings mais leves por padrão:** a imagem usa
  `paraphrase-multilingual-MiniLM-L12-v2` para o primeiro run ser rápido. Para
  qualidade máxima de retrieval, sobreescreva com
  `EMPORIO_EMBEDDING_MODEL=BAAI/bge-m3` no `.env`.
- **Segredos só em runtime:** a chave de API entra via `env_file: .env`, nunca
  é gravada em uma camada da imagem (`.env` está no `.gitignore` **e** no
  `.dockerignore`).

A troca do modelo de chat é por variável de ambiente (no `.env`), tanto para um
provedor hospedado quanto para um modelo local/self-hosted — veja a seção
seguinte.

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

### Rodar com um modelo local / self-hosted (qualquer endpoint OpenAI-compatível)

O modelo de chat é selecionado por `EMPORIO_MODEL` e alcança o provedor por uma
API **compatível com OpenAI**. **Qualquer** servidor que exponha essa API
funciona — basta apontar três coisas:

```bash
EMPORIO_MODEL=qwen2.5:7b                          # o nome/tag servido lá
EMPORIO_OPENAI_BASE_URL=http://localhost:11434/v1 # o endpoint OpenAI-compatível
OPENAI_API_KEY=sk-local                           # placeholder; servidores locais não checam
```

Quando `EMPORIO_OPENAI_BASE_URL` está definido, `build_agent` roteia o mesmo
`EMPORIO_MODEL` por esse endpoint (mudança apenas em `config.py`/`agent.py`);
nada mais no código muda. Como os embeddings já são **locais**, isso faz o
sistema inteiro rodar **sem nenhuma API paga**.

Servidores **comprovadamente compatíveis** (lista ilustrativa, não exaustiva —
*qualquer* servidor OpenAI-compatível serve):

| Servidor | Base URL típica |
|---|---|
| Ollama | `http://localhost:11434/v1` |
| vLLM | `http://localhost:8000/v1` |
| LM Studio | `http://localhost:1234/v1` |
| llama.cpp (`llama-server`) | `http://localhost:8080/v1` |
| text-generation-inference (TGI) | `http://localhost:8080/v1` |
| LocalAI | `http://localhost:8080/v1` |

**Rede no Docker:** um servidor de modelo rodando no **host** é alcançado de
dentro do container por `host.docker.internal` (no Linux, o `compose.yml` já
adiciona `--add-host=host.docker.internal:host-gateway`):

```bash
EMPORIO_OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

Alternativamente, o servidor poderia subir como **outro serviço no mesmo
compose**, alcançado pelo nome do serviço (ex.: `http://ollama:11434/v1`) — fica
como opção, não como o compose padrão deste protótipo, que é de um serviço só.

> Duas ressalvas honestas: **(a)** modelos locais pequenos costumam ser mais
> fracos em seleção de tools e em seguir persona/escopo do que um modelo
> hospedado forte — isso é limitação **do modelo**, não do sistema (a Tier 3 dos
> evals torna a diferença visível); **(b)** os embeddings são locais de qualquer
> forma, então operar **ponta a ponta sem API paga** sempre foi suportado.

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
| Embeddings | **BGE-M3 local (GPU ou CPU)** | Totalmente local (zero API), reprodutível offline, forte em PT-BR. Só o modelo de chat precisa de chave → dá pra rodar sem nenhuma API paga. |
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

Esse argumento de trocabilidade não fica no discurso: o suporte a **qualquer
endpoint OpenAI-compatível** (vLLM, Ollama, LM Studio, llama.cpp, TGI,
LocalAI...) via `EMPORIO_OPENAI_BASE_URL` e a imagem **Docker** que sobe com um
comando são a prova concreta de que *"o provedor é um valor de configuração"* —
hospedado ou local, sem mudar código. Detalhes em
[*Rodar com um modelo local / self-hosted*](#rodar-com-um-modelo-local--self-hosted)
e [*Rodar com Docker*](#rodar-com-docker-sem-setup-local-de-python).

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
- **Escopo**: a loja só vende instrumentos; pedidos de acessórios (palhetas,
  pedais, cabos...) são recusados com gentileza.
- **Busca por nome tolerante a erros** → uma camada de busca
  (`data/search.py`) normaliza acentos/caixa, mapeia sinônimos de categoria
  ("sax" → "Instrumentos de Sopro (Madeiras)") e faz *fuzzy matching* de nomes
  de produto com `rapidfuzz` (ex.: "takamine gd" encontra o modelo certo mesmo
  com a grafia parcial).
- **"Cordas" é ambíguo e tratado como tal** → pode ser a categoria "Cordas
  Orquestrais" (violinos, violas, violoncelos) ou cordas avulsas de reposição
  (acessório fora de escopo). Em vez de adivinhar, a camada de dados sinaliza a
  ambiguidade e o agente pede esclarecimento.

Veja [`examples/`](examples/) para transcrições reais cobrindo esses cenários.

As obrigações factuais de cada tipo de resposta (o que uma resposta correta
precisa conter, e o que não pode conter) estão formalizadas como contratos
testáveis em [`docs/RESPONSE_CONTRACTS.md`](docs/RESPONSE_CONTRACTS.md).

---

## Avaliação

Três tiers, do mais barato/determinístico ao mais caro. Detalhes em
[`evals/README.md`](evals/README.md); as obrigações verificadas estão em
[`docs/RESPONSE_CONTRACTS.md`](docs/RESPONSE_CONTRACTS.md).

```bash
pytest tests/ -q            # Tier 1 — núcleo determinístico
python -m evals.run         # Tier 1 + Tier 2 (offline, sem chave)
python -m evals.run --live  # + Tier 3 (qualidade de resposta, requer chave de API)
```

| Tier | O que mede | Score |
|---|---|---|
| **1 — Núcleo determinístico** | pricing, dados, chunking, validação, busca/desambiguação, trace (pytest) | **42/42** |
| **2 — Roteamento de tools** | tool correta por mensagem (offline) | **12/12** |
| **3 — Qualidade de resposta** | contratos vs. ground truth do `StoreData` (live) | **6/6** |

> Tier 1 e 2 rodam offline, sem chave — os números acima são reais (medidos com
> `python -m evals.run`). A Tier 3 é opt-in e depende de um modelo real: o
> `6/6` acima foi medido com `anthropic:claude-sonnet-4-5` via
> `python -m evals.run --live`; o resultado varia conforme o modelo configurado
> (um 7B local, por exemplo, falha vários contratos).

---

## Limitações conhecidas e próximos passos

- **Persistência** apenas em memória; com mais tempo, sessões em Redis/DB.
- **Avaliação**: já há um conjunto pequeno em `evals/` para roteamento offline e
  qualidade de resposta opt-in com modelo real; o próximo passo seria ampliar
  os casos e pontuar também os argumentos das tools.
- **Desambiguação de pedido** exige o número do pedido; um fluxo por
  nome/telefone (cruzando `customers`) seria mais natural.
- **Busca de produtos** já tolera acentos/caixa, sinônimos de categoria e erros
  de grafia (fuzzy via `rapidfuzz`, em `data/search.py`); em catálogos muito
  maiores, busca semântica por embeddings sobre os nomes seria o próximo passo.
- **Escalabilidade**: A medida que os documentos sobre a política da empresa aumentarem,
  o sistema atual armazenado em memório provavelmente falharia. A solução seria migrar para uma
  base vetorial dos embeddings. 

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
