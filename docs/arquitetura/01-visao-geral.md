# 1. Visão geral

[← Índice](README.md)

## Contexto

O agente é uma CLI local. Ela conversa com um único serviço externo (o OpenRouter) e age só sobre o disco local, dentro de um workspace descartável.

```mermaid
flowchart LR
    U(["Você no terminal"])
    subgraph Local["Máquina local"]
        CLI["agent CLI<br/>ask · run · task · report"]
        ENV[".env<br/>OPENROUTER_API_KEY, AGENT_*"]
        TASKS["tasks/NN-nome/<br/>prompt, workspace, check, prediction"]
        RUNS["runs/&lt;id&gt;/<br/>ws, trace, messages, final"]
        SH["Shell do sistema<br/>subprocess"]
    end
    OR[("OpenRouter<br/>/chat/completions<br/>/models")]
    LLM[("Modelo<br/>deepseek-v4-flash por padrão")]

    U -->|comando| CLI
    U -->|"y/N para cada comando"| CLI
    ENV -->|config| CLI
    TASKS -->|copia workspace| RUNS
    CLI -->|lê e escreve| RUNS
    CLI -->|run_command| SH
    SH -->|cwd = runs/id/ws| RUNS
    CLI <-->|HTTPS + Bearer| OR
    OR <--> LLM
```

## Dependências entre módulos

Cada seta é um `import`. O `loop` não importa o cliente concreto: recebe qualquer objeto com `.chat()`, e por isso os testes usam um cliente falso.

```mermaid
flowchart TD
    cli["cli.py<br/>comandos e argumentos"]
    report["report.py<br/>tabela e acerto"]
    tasks["tasks.py<br/>prepare, check, run_task"]
    runs["runs.py<br/>run_dir, execute_run"]
    loop["loop.py<br/>o loop agêntico"]
    tools["tools.py<br/>schemas, execute, guardas"]
    ledger["ledger.py<br/>trace e custo"]
    client["client.py<br/>HTTP OpenRouter"]
    config["config.py<br/>.env e defaults"]

    cli --> client & config & ledger & report & runs & tasks & tools
    report --> tasks
    tasks --> runs & loop & config
    runs --> loop & ledger & tools & config
    loop --> tools & ledger
    loop -.->|"só ClientError"| client
    ledger -.->|"duck typing: .models()"| client

    classDef core fill:#fde68a,stroke:#b45309,color:#111
    class loop,tools core
```

O núcleo do estudo (amarelo) são `loop.py` e `tools.py`: juntos têm cerca de 300 linhas.

## Dependências externas

```mermaid
flowchart LR
    subgraph Runtime
        httpx["httpx"]
    end
    subgraph Dev
        pytest["pytest"]
    end
    subgraph Stdlib["Biblioteca padrão"]
        std["subprocess · json · pathlib<br/>argparse · shutil · dataclasses"]
    end
    subgraph Proibidos["Fora do projeto, de propósito"]
        sdk["SDK openai / anthropic"]
        dotenv["python-dotenv"]
        fw["LangChain e afins"]
    end
    agent(["pacote agent"]) --> httpx & Stdlib
    tests(["tests/"]) --> pytest
    agent -.-x Proibidos
```

| Módulo | Linhas | Responsabilidade |
|---|---|---|
| `config.py` | 70 | Lê `.env` (parser próprio) e o ambiente; o ambiente vence |
| `client.py` | 148 | `chat()` e `models()`; retry em 429, 5xx e falha de rede |
| `tools.py` | 170 | 3 ferramentas, schemas e guardas |
| `loop.py` | 136 | Chama o modelo, executa `tool_calls`, decide quando parar |
| `ledger.py` | 141 | Grava eventos em JSONL e soma o custo |
| `runs.py` | 77 | Cria `runs/<id>/` e salva `messages.json` e `final.txt` |
| `tasks.py` | 105 | Descobre, prepara e verifica tarefas |
| `report.py` | 185 | Compara previsão e resultado |
| `cli.py` | 209 | Liga tudo atrás de `argparse` |
