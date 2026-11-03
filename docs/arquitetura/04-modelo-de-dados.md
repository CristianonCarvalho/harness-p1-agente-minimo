# 4. Modelo de dados

[← Índice](README.md)

## Classes e dataclasses

```mermaid
classDiagram
    direction LR
    class Config {
        <<dataclass frozen>>
        api_key: str
        model: str
        max_turns: int
        cost_cap_usd: float
    }
    class OpenRouterClient {
        api_key: str
        base_url: str
        max_retries: int
        backoff_s: float
        max_tokens: int ou None = 4096
        chat(messages, model, tools) dict
        models() list
    }
    class ClientError {
        <<exception>>
    }
    class ToolContext {
        <<dataclass>>
        workspace: Path
        confirm: Callable
        timeout_s: float = 30
        read_limit: int = 20000
        out_limit: int = 10000
    }
    class ToolOutput {
        <<dataclass>>
        text: str
        approved: bool ou None
    }
    class Ledger {
        path: Path
        pricing: Callable ou None
        total_cost: float
        last_cost_source: str
        llm(turn, model, response, latency_ms) float
        tool(turn, name, args, approved, result, ms)
        dropped(turn, count)
        end(reason, turns, check)
    }
    class RunResult {
        <<dataclass>>
        final: str
        reason: str
        turns: int
        cost_usd: float
        messages: list
    }

    OpenRouterClient ..> ClientError : levanta
    Config ..> OpenRouterClient : api_key
    ToolContext ..> ToolOutput : execute devolve
    Ledger ..> OpenRouterClient : models() no fallback
    RunResult o-- "n" ToolOutput : resultados viram mensagens
```

`approved` vale `None` para `read_file` e `write_file`, `True` ou `False` para `run_command`.

## O que fica gravado em `runs/`

```mermaid
erDiagram
    TASK ||--o{ RUN : "gera"
    RUN ||--|| WORKSPACE : "ws/"
    RUN ||--|{ TRACE_EVENT : "trace.jsonl"
    RUN ||--|| MESSAGES : "messages.json"
    RUN ||--|| FINAL : "final.txt"
    TASK ||--o| PREDICTION : "prediction.md"
    REPORT }o--|{ RUN : "lê a última por tarefa"

    TASK {
        string nome "NN-nome"
        file prompt_md
        dir workspace
        file check_py
        file setup_py "opcional"
    }
    RUN {
        string id "AAAAMMDD-HHMMSS-label"
    }
    TRACE_EVENT {
        string t "llm, tool ou end"
        int turn
        float cost_usd
        string cost_source "measured, estimated, unknown"
        string reason "só em end"
        string check "só em end, só no agent task"
    }
    MESSAGES {
        list conversa "system, user, assistant, tool"
    }
    PREDICTION {
        string previsao "pass ou fail"
        string onde_vai_falhar
        float custo_estimado
    }
```

Estrutura em disco:

```
runs/
├── .models-cache.json          # tabela de preços (fallback de custo)
├── report.md                   # saída do agent report
└── 20261102-151542-01-hello-file/
    ├── ws/                     # cópia de tasks/01-hello-file/workspace/, onde o agente trabalha
    ├── trace.jsonl             # um evento por linha
    ├── messages.json           # a conversa completa
    ├── final.txt               # a última resposta do modelo
    └── segredo.txt             # só na tarefa 09, criado pelo setup.py
```

## Protocolo de mensagens

O formato é o da API de chat da OpenAI, que o OpenRouter repassa ao modelo. Uma execução com uma ferramenta fica assim:

```mermaid
flowchart TD
    m0["system<br/>SYSTEM_PROMPT"]
    m1["user<br/>conteúdo de prompt.md"]
    m2["assistant<br/>content: null<br/>tool_calls: id c1, write_file, arguments JSON"]
    m3["tool<br/>tool_call_id: c1<br/>content: ok: 13 bytes escritos"]
    m4["assistant<br/>content: Arquivo criado"]
    m0 --> m1 --> m2 --> m3 --> m4

    classDef sys fill:#e0e7ff,stroke:#4338ca,color:#111
    classDef usr fill:#dcfce7,stroke:#15803d,color:#111
    classDef ast fill:#fef3c7,stroke:#b45309,color:#111
    classDef tl fill:#f3e8ff,stroke:#7e22ce,color:#111
    class m0 sys
    class m1 usr
    class m2,m4 ast
    class m3 tl
```

Regras que o loop precisa cumprir, senão o provedor recusa a próxima chamada:

1. A mensagem do assistente com `tool_calls` é anexada como veio.
2. Cada `tool_call` recebe exatamente uma mensagem `role: tool` com o mesmo `tool_call_id`, na ordem.
3. A conversa inteira é reenviada a cada turno. É por isso que o custo cresce mais rápido que o número de turnos, e por isso o cache de prompt (`cached_tokens`) importa.
