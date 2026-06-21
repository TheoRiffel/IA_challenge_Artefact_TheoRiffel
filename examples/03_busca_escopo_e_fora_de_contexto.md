# Exemplo 3 — Busca no catálogo + fora de escopo (acessório)

Demonstra dois níveis de tratamento: uma **busca normal** no catálogo (apenas
itens em estoque, melhor preço, dentro do teto pedido) e a **recusa gentil de
um acessório** — a loja só vende instrumentos (políticas 1 e 7.1).

> **Execução real** — gerada em **2026-06-21** com `EMPORIO_MODEL=anthropic:claude-sonnet-4-5`, via:
> `python -m emporio_agente.cli --once "violões até 1000 reais"`
> `python -m emporio_agente.cli --once "vendem cordas de nylon?"`
> As respostas abaixo são a saída literal do modelo (cada `--once` é um turno
> independente).

> **Ground truth (camada de dados)** — `search_products(category="Violões",
> max_price=1000)` retorna 8 itens em estoque, ordenados por melhor preço:
> 408,41 · 436,91 · 521,55 · 550,91 · 569,91 · 654,55 · 664,91 · 711,55.
> (O modelo reagrupou Nylon/Aço para leitura; os 8 itens e valores conferem.)

---

**Você:** violões até 1000 reais

**Assistente:** Opa! Encontrei **8 violões** disponíveis até **R$ 1.000**, todos em estoque. Dá uma olhada nas opções:

**Violões de Nylon:**
1. **Tagima Memphis AC-39 Nylon Natural** – R$ 408,41 (economia de 5% no PIX)
2. **Rozini RC-104 Nylon Estudante** – R$ 436,91 (economia de 5% no PIX)
3. **Yamaha C40 Nylon Natural** – R$ 569,91 (economia de 5% no PIX)
4. **Giannini GN-15 Nylon Cedr Natural** – R$ 654,55 (economia de 5% no PIX)

**Violões de Aço:**
5. **Shelby SN-100 Folk Aço Preto** – R$ 521,55 (economia de 5% no PIX)
6. **Giannini GF-1R Aço Folk Sunburst** – R$ 550,91 (economia de 5% no PIX)
7. **Yamaha F310 Aço Natural** – R$ 664,91 (economia de 5% no PIX)
8. **Tagima Dallas Tuner Aço Natural** – R$ 711,55 (economia de 5% no PIX)

Todos esses valores já são com o desconto de **5% no PIX**. Se você tiver interesse em algum modelo específico ou quiser saber mais detalhes sobre algum deles, é só falar! 😊🎸

Posso te ajudar em mais alguma coisa?

---

**Você:** vendem cordas de nylon?

**Assistente:** Olá! 😊

A Empório da Música trabalha exclusivamente com **instrumentos musicais** e não comercializa acessórios como cordas, palhetas, cabos, cases ou outros itens do tipo.

Mas se você estiver procurando um **violão de nylon** ou qualquer outro instrumento, ficarei feliz em ajudar! Temos várias opções em estoque.

Posso te ajudar com mais alguma coisa?
