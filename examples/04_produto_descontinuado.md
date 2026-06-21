# Exemplo 4 — Produto descontinuado

Demonstra o tratamento de um **produto fora de linha**: o agente informa que foi
descontinuado (fato vindo do campo `status` na camada de dados) e se oferece
para **buscar alternativas** na mesma categoria — sem inventar um modelo
específico que não exista no catálogo.

> **Execução real** — gerada em **2026-06-21** com `EMPORIO_MODEL=anthropic:claude-sonnet-4-5`, via:
> `python -m emporio_agente.cli --once "tem o Shelby SN-7C?"`
> A resposta abaixo é a saída literal do modelo.

> **Ground truth (camada de dados)** — Shelby SN-7C 7 Cordas Nylon Natural
> (id 113): status **discontinued**, categoria Violões.

---

**Você:** tem o Shelby SN-7C?

**Assistente:** Olá! O **Shelby SN-7C** infelizmente foi **descontinuado** pela marca e não está mais disponível no nosso estoque. 😕

Mas se você está procurando um **violão de 7 cordas**, posso buscar outras opções que temos disponíveis para você! Quer que eu veja o que temos em estoque nessa categoria?
