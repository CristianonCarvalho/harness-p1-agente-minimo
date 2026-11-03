# 2. Fluxo de execução

[← Índice](README.md)

## `agent task 01` de ponta a ponta

```mermaid
sequenceDiagram
    autonumber
    actor Você
    participant CLI as cli.py
    participant T as tasks.py
    participant R as runs.py
    participant L as loop.py
    participant C as client.py
    participant OR as OpenRouter
    participant TL as tools.py
    participant LG as ledger.py

    Você->>CLI: uv run agent task 01
    CLI->>CLI: load_config() e acha tasks/01-hello-file
    CLI->>T: run_task(task_dir, runs/)
    T->>R: new_run_dir(runs/, "01-hello-file")
    R-->>T: runs/AAAAMMDD-HHMMSS-01-hello-file/
    T->>T: prepare(): copia workspace/ para ws/ e roda setup.py se existir
    T->>R: execute_run(prompt.md, run_dir)
    R->>L: run(prompt, ToolContext(ws), client, Ledger(trace.jsonl))

    loop Até uma condição de parada
        L->>C: chat(messages, model, TOOL_SCHEMAS)
        C->>OR: POST /chat/completions com usage.include
        OR-->>C: choices[0].message + usage
        C-->>L: resposta JSON
        L->>LG: llm(turn, usage, latência)
        alt resposta tem tool_calls
            L->>TL: execute(nome, args, ctx)
            TL-->>L: ToolOutput(text, approved)
            L->>LG: tool(nome, args, resultado)
            L->>L: anexa mensagem role tool com tool_call_id
        else sem tool_calls
            L->>L: final = content, para
        end
    end

    L->>LG: end(reason, turns)
    L-->>R: RunResult
    R->>R: grava messages.json e final.txt
    T->>T: run_check(): python check.py ws final.txt trace.jsonl
    T->>T: reescreve a última linha do trace com check pass ou fail
    T-->>CLI: (run_dir, RunResult, passed)
    CLI-->>Você: pass · turnos · custo
```

## O loop, passo a passo

Este é o coração do projeto (`agent/loop.py`, função `run`).

```mermaid
flowchart TD
    start(["run(prompt)"]) --> init["messages = [system, user]<br/>turns = 0"]
    init --> check_turns{"turns menor<br/>que max_turns?"}
    check_turns -->|não| stop_max(["fim: max_turns"])
    check_turns -->|sim| inc["turns += 1"]
    inc --> chatcall["client.chat(messages, model, TOOL_SCHEMAS)"]
    chatcall -->|ClientError| stop_err(["fim: error<br/>final vazio"])
    chatcall --> log["ledger.llm(...)<br/>anexa a mensagem do assistente"]
    log --> cap{"custo total maior ou<br/>igual a cost_cap_usd?"}
    cap -->|sim| stop_cap(["fim: cost_cap"])
    cap -->|não| has_tc{"mensagem tem<br/>tool_calls?"}
    has_tc -->|não| stop_ok(["fim: no_tool_calls<br/>final = content"])
    has_tc -->|sim| each["para cada tool_call, na ordem"]
    each --> parse{"arguments é<br/>JSON de objeto?"}
    parse -->|não| bad["ToolOutput error: argumentos inválidos"]
    parse -->|sim| exec["tools.execute(name, args, ctx)"]
    bad --> append
    exec --> append["ledger.tool(...)<br/>anexa role tool + tool_call_id"]
    append --> more{"mais tool_calls?"}
    more -->|sim| each
    more -->|não| last{"turns igual<br/>a max_turns?"}
    last -->|sim| stop_max
    last -->|não| check_turns

    classDef fim fill:#e5e7eb,stroke:#374151,color:#111
    class stop_max,stop_err,stop_cap,stop_ok fim
```

Dois detalhes que costumam surpreender:

- O teto de custo é checado **depois** da chamada e **antes** de executar ferramentas. Se ele estoura, as `tool_calls` daquela resposta ficam sem resposta em `messages.json`.
- No fim por `max_turns`, as ferramentas do último turno já rodaram, mas o modelo nunca vê o resultado delas.

## Estados de uma execução

```mermaid
stateDiagram-v2
    [*] --> Preparando: run_task
    Preparando --> ChamandoModelo: messages = system + user
    ChamandoModelo --> ExecutandoFerramentas: tool_calls
    ExecutandoFerramentas --> ChamandoModelo: resultados anexados
    ChamandoModelo --> no_tool_calls: resposta final
    ChamandoModelo --> cost_cap: custo acima do teto
    ChamandoModelo --> error: ClientError após retries
    ExecutandoFerramentas --> max_turns: último turno
    no_tool_calls --> Verificando
    cost_cap --> Verificando
    error --> Verificando
    max_turns --> Verificando
    Verificando --> [*]: check pass ou fail
```

Só no `agent task` existe o estado `Verificando`. No `agent run` a execução termina no motivo do fim.

> **Divergência conhecida (passo 12):** o `SYSTEM_PROMPT` lista só `read_file` e `write_file`. O `run_command` está nos schemas, então o modelo pode usá-lo, mas o prompt não o apresenta.
