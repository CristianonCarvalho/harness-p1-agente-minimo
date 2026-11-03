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

## `agent task --all` de ponta a ponta, por classe

Cada participante é um módulo (função) ou uma instância de classe, com o arquivo e a linha onde está. Os dois `loop` do diagrama são os dois laços do código: o de fora percorre as tarefas e o de dentro percorre os turnos com o modelo.

```mermaid
sequenceDiagram
    autonumber
    actor Você
    participant CLI as cli.main<br/>cli.py:17
    participant RP as report<br/>build_report
    participant TK as tasks<br/>discover_tasks / run_task
    participant RN as runs<br/>new_run_dir / execute_run
    participant LP as loop.run<br/>loop.py
    participant LG as Ledger<br/>(uma por tarefa)
    participant OC as OpenRouterClient<br/>(um para o lote)
    participant TL as tools.execute<br/>+ ToolContext

    Você->>CLI: uv run agent task --all --auto-approve
    CLI->>CLI: load_config() devolve Config
    CLI->>OC: OpenRouterClient(api_key)
    CLI->>TK: discover_tasks(tasks/)  cli.py:141
    TK-->>CLI: [01-hello-file, 02-rename-batch, ..., 10-long-chain]
    Note over CLI: --auto-approve: confirm = sempre y<br/>(o ws de cada tarefa já fica em runs/)

    loop for task_dir in available_tasks  (cli.py:151, 10 voltas)
        CLI->>TK: run_task(task_dir, runs/, client, ...)  tasks.py:65
        TK->>RN: new_run_dir(runs/, nome)
        RN-->>TK: runs/AAAAMMDD-HHMMSS-NN-nome/
        TK->>TK: prepare(): copia workspace/, roda setup.py
        TK->>RN: execute_run(prompt.md, run_dir, client)
        RN->>TL: ToolContext(ws, confirm)
        RN->>LG: Ledger(run_dir/trace.jsonl, pricing)
        RN->>LP: run(prompt, ctx, client, ledger, model)

        loop while turns < max_turns  (loop.py, até 20 voltas)
            LP->>OC: chat(messages, model, TOOL_SCHEMAS)
            OC-->>LP: resposta JSON
            LP->>LG: llm(turn, model, resposta, latência)
            opt resposta com tool_calls
                opt mais de 10 tool_calls
                    LP->>LG: dropped(turn, excedentes)
                end
                LP->>TL: execute(nome, args, ctx)
                TL-->>LP: ToolOutput(text, approved)
                LP->>LG: tool(turn, nome, args, approved, text, ms)
            end
            Note over LP: para em no_tool_calls, cost_cap,<br/>max_turns ou error
        end

        LP->>LG: end(reason, turns)
        LP-->>RN: RunResult
        RN->>RN: save_result(): messages.json, final.txt
        RN-->>TK: RunResult
        TK->>TK: run_check(): python check.py
        TK->>TK: grava check no fim do trace.jsonl
        TK-->>CLI: (run_dir, RunResult, passed)
        CLI-->>Você: NN-nome: pass · turnos · custo
    end

    Você->>CLI: uv run agent report
    CLI->>RP: build_report(tasks/, runs/)
    RP-->>CLI: tabela Markdown
    CLI-->>Você: tabela + runs/report.md
```

O que muda e o que se repete a cada tarefa:

| Objeto | Quantos no lote | Por quê |
|---|---|---|
| `Config` | 1 | Lida uma vez no início |
| `OpenRouterClient` | 1 | A mesma conexão HTTP serve todas as tarefas |
| `ToolContext` | 10 | Cada tarefa tem o seu `ws/` |
| `Ledger` | 10 | Cada tarefa tem o seu `trace.jsonl` e o seu teto de custo |
| `RunResult` | 10 | Um por execução do loop |

Uma falha do modelo numa tarefa não interrompe o lote: o `run_task` devolve `passed=False` e o laço segue. Já uma exceção no `setup.py` de uma tarefa interrompe o lote, porque o `prepare` usa `check=True` e ninguém captura o erro.

## O loop, passo a passo

Este é o coração do projeto (`agent/loop.py`, função `run`).

```mermaid
flowchart TD
    start(["run(prompt)"]) --> init["messages = [system, user]<br/>turns = 0"]
    init --> check_turns{"turns menor<br/>que max_turns?"}
    check_turns -->|não| stop_max(["fim: max_turns"])
    check_turns -->|sim| inc["turns += 1"]
    inc --> chatcall["client.chat(messages, model, TOOL_SCHEMAS)"]
    chatcall -->|"ClientError<br/>(HTTP ou finish_reason error<br/>após retries)"| stop_err(["fim: error<br/>final vazio"])
    chatcall --> log["ledger.llm(...)<br/>anexa a mensagem do assistente"]
    log --> cap{"custo total maior ou<br/>igual a cost_cap_usd?"}
    cap -->|sim| stop_cap(["fim: cost_cap"])
    cap -->|não| has_tc{"mensagem tem<br/>tool_calls?"}
    has_tc -->|não| stop_ok(["fim: no_tool_calls<br/>final = content"])
    has_tc -->|sim| limit{"mais de 10<br/>tool_calls?"}
    limit -->|sim| drop["mantém as 10 primeiras<br/>ledger.dropped(...)"]
    limit -->|não| each["para cada tool_call, na ordem"]
    drop --> each
    each --> parse{"arguments é<br/>JSON de objeto?"}
    parse -->|não| bad["ToolOutput error: argumentos inválidos"]
    parse -->|sim| exec["tools.execute(name, args, ctx)"]
    bad --> append
    exec --> append["ledger.tool(...)<br/>anexa role tool + tool_call_id"]
    append --> more{"mais tool_calls?"}
    more -->|sim| each
    more -->|não| warn["se descartou: aviso no fim<br/>da última mensagem role tool"]
    warn --> last{"turns igual<br/>a max_turns?"}
    last -->|sim| stop_max
    last -->|não| check_turns

    classDef fim fill:#e5e7eb,stroke:#374151,color:#111
    class stop_max,stop_err,stop_cap,stop_ok fim
```

Dois detalhes que costumam surpreender:

- O teto de custo é checado **depois** da chamada e **antes** de executar ferramentas. Se ele estoura, as `tool_calls` daquela resposta ficam sem resposta em `messages.json`.
- No fim por `max_turns`, as ferramentas do último turno já rodaram, mas o modelo nunca vê o resultado delas.
- Quando uma resposta traz mais de 10 `tool_calls`, as excedentes são removidas da própria mensagem do assistente antes de executar, para que toda chamada no histórico tenha a sua resposta `role: tool`. O modelo só fica sabendo do corte pelo aviso `[harness: N chamadas descartadas ...]`.

## Estados de uma execução

```mermaid
stateDiagram-v2
    [*] --> Preparando: run_task
    Preparando --> ChamandoModelo: messages = system + user
    ChamandoModelo --> ExecutandoFerramentas: tool_calls
    ExecutandoFerramentas --> ChamandoModelo: resultados anexados
    ChamandoModelo --> no_tool_calls: resposta final
    ChamandoModelo --> cost_cap: custo acima do teto
    ChamandoModelo --> error: ClientError após retries<br/>(HTTP ou finish_reason error)
    ExecutandoFerramentas --> max_turns: último turno
    no_tool_calls --> Verificando
    cost_cap --> Verificando
    error --> Verificando
    max_turns --> Verificando
    Verificando --> [*]: check pass ou fail
```

Só no `agent task` existe o estado `Verificando`. No `agent run` a execução termina no motivo do fim.
