# 5. Custo e ledger

[← Índice](README.md)

## De onde vem o custo de cada chamada

`Ledger.llm()` decide a origem do número e a registra em `cost_source`, para você sempre saber se o custo é medido ou estimado.

```mermaid
flowchart TD
    r(["resposta do OpenRouter"]) --> u{"usage.cost<br/>existe e não é null?"}
    u -->|sim| m["custo = usage.cost<br/>cost_source: measured"]
    u -->|não| loaded{"tabela de preços<br/>já carregada?"}
    loaded -->|não| load["pricing() = load_pricing(client, cache)<br/>uma vez por Ledger"]
    load --> loaded2["tabela em memória"]
    loaded -->|sim| loaded2
    loaded2 --> has{"modelo está<br/>na tabela?"}
    has -->|sim| e["custo = prompt_tokens × preço_prompt<br/>+ completion_tokens × preço_completion<br/>cost_source: estimated"]
    has -->|não| z["custo = 0<br/>cost_source: unknown"]
    m & e & z --> sum["total_cost += custo<br/>grava linha llm no trace.jsonl"]
```

O `"usage": {"include": true}` em toda requisição é o que pede ao OpenRouter para devolver `usage.cost`.

## Cache da tabela de preços

```mermaid
sequenceDiagram
    participant LG as Ledger
    participant LP as load_pricing
    participant FS as runs/.models-cache.json
    participant C as OpenRouterClient
    participant OR as OpenRouter

    LG->>LP: só quando falta usage.cost
    LP->>FS: existe?
    alt cache existe
        FS-->>LP: lista de modelos
    else sem cache
        LP->>C: models()
        C->>OR: GET /api/v1/models
        OR-->>C: data com pricing por modelo
        C-->>LP: lista
        LP->>FS: grava cache
    end
    LP-->>LG: dict modelo para preço_prompt, preço_completion
    Note over LP: falha ao buscar devolve dict vazio,<br/>e o custo vira unknown
```

O cache nunca expira. Se os preços mudarem, apague `runs/.models-cache.json`.

## Eventos do trace

```mermaid
flowchart LR
    subgraph turno1["Turno 1"]
        l1["llm<br/>tokens, custo, latência,<br/>finish_reason: tool_calls"] --> t1["tool<br/>write_file, approved: null,<br/>result_head, ms"]
    end
    subgraph turno2["Turno 2"]
        l2["llm<br/>finish_reason: stop"]
    end
    e["end<br/>reason, turns, cost_usd total,<br/>check: pass"]
    turno1 --> turno2 --> e
```

| Evento | Campos |
|---|---|
| `llm` | `turn`, `model`, `prompt_tokens`, `completion_tokens`, `cached_tokens`, `cost_usd`, `cost_source`, `latency_ms`, `finish_reason` |
| `tool` | `turn`, `name`, `args`, `approved`, `result_head` (500 caracteres), `result_bytes`, `ms` |
| `end` | `reason`, `turns`, `cost_usd` (total), `check` (só no `agent task`) |

O `check` é acrescentado depois: `run_task` roda o `check.py` e reescreve a última linha do trace.

## Por que o custo cresce

A cada turno a conversa inteira é reenviada, então `prompt_tokens` cresce turno a turno mesmo quando o modelo escreve pouco (valores ilustrativos):

```
turno 1: system + user                                  → ~400 tokens de entrada
turno 2: system + user + assistant + tool               → ~550
turno 3: ... + assistant + tool                         → ~700
```

O custo de uma tarefa é aproximadamente quadrático no número de turnos. O `cached_tokens` mostra quanto desse prefixo repetido o provedor cobrou com desconto.
