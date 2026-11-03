# 3. Ferramentas e guardas

[← Índice](README.md)

## Despacho de uma `tool_call`

`tools.execute(name, args, ctx)` nunca levanta exceção para o loop: todo erro vira texto começando com `error: `, que o modelo lê como resultado da ferramenta.

```mermaid
flowchart TD
    in(["execute(name, args, ctx)"]) --> which{"name"}
    which -->|read_file| rf["_read_file"]
    which -->|write_file| wf["_write_file"]
    which -->|run_command| rc["_run_command"]
    which -->|outro| unk["error: ferramenta desconhecida: name"]

    rf --> guard1["resolve_inside(ctx, path)"]
    wf --> guard2["resolve_inside(ctx, path)"]
    guard1 -->|fora| out_err["error: caminho fora do workspace"]
    guard2 -->|fora| out_err
    guard1 -->|dentro| exists{"arquivo existe?"}
    exists -->|não| nf["error: arquivo não encontrado: path"]
    exists -->|sim| size{"maior que 20 KB?"}
    size -->|sim| trunc["20 KB + aviso truncado: N bytes no total"]
    size -->|não| full["conteúdo, decode utf-8 com replace"]
    guard2 -->|dentro| write["cria diretórios e grava<br/>ok: N bytes escritos em path"]

    rc --> shell["ver diagrama do run_command"]

    in -.->|qualquer outra exceção| exc["error: Tipo: mensagem"]

    classDef err fill:#fecaca,stroke:#b91c1c,color:#111
    class unk,out_err,nf,exc err
```

## Guarda de caminho

```mermaid
flowchart LR
    p["path vindo do modelo"] --> join["workspace.resolve() / path"]
    join --> res["Path.resolve()<br/>normaliza .. e segue symlinks"]
    res --> rel{"is_relative_to(workspace)?"}
    rel -->|sim| ok["caminho liberado"]
    rel -->|não| no["ValueError: caminho fora do workspace"]
```

| Entrada | Resultado |
|---|---|
| `notas/a.txt` | liberado |
| `../segredo.txt` | bloqueado (`..` sai do workspace) |
| `/etc/passwd` | bloqueado (absoluto: o `/` descarta o workspace na junção) |
| `link` apontando para fora | bloqueado (`resolve()` segue o symlink) |

Essa guarda vale só para `read_file` e `write_file`. O `run_command` não passa por ela.

## `run_command`

```mermaid
sequenceDiagram
    participant L as loop.py
    participant T as tools._run_command
    actor Você
    participant SH as /bin/sh

    L->>T: execute("run_command", {command})
    T->>Você: $ command  executar? [y/N]
    alt resposta diferente de y, EOF ou Ctrl-C
        Você-->>T: n
        T-->>L: error: usuário negou o comando (approved=False)
    else y
        Você-->>T: y
        T->>SH: subprocess.run(shell=True, cwd=ws, timeout=30s)
        Note over T,SH: env só com PATH, HOME=ws e LANG=C.UTF-8,<br/>sem OPENROUTER_API_KEY
        alt passou de 30s
            SH-->>T: TimeoutExpired
            T-->>L: error: timeout após 30s
        else terminou
            SH-->>T: exit, stdout, stderr
            T->>T: corta stdout em 10 KB
            T-->>L: exit: N, stdout, stderr (approved=True)
        end
    end
```

## O que as guardas protegem, e o que não

```mermaid
flowchart TD
    subgraph Protege["Protegido"]
        a1["Ler ou escrever fora do workspace<br/>com read_file e write_file"]
        a2["Vazar a chave da API<br/>via env ou printenv"]
        a3["Comando que trava o loop"]
        a4["Arquivo grande estourando o contexto"]
        a5["Comando executado sem você ver"]
    end
    subgraph Aberto["Não protegido, de propósito"]
        b1["cd / ou caminho absoluto<br/>dentro do run_command"]
        b2["cat ~/.ssh/... via shell<br/>depois que você aprova"]
        b3["--auto-approve: remove a confirmação"]
        b4["stderr enorme, sem corte"]
    end
    g1["guarda de caminho"] --> a1
    g2["env limpo"] --> a2
    g3["timeout"] --> a3
    g4["corte de saída"] --> a4
    g5["confirmação y/N"] --> a5
    g5 -. "é o único controle real para" .-> b1 & b2
```

O isolamento de verdade (container, `sandbox-exec`) fica para a Fase 4 do roadmap.

> **Divergências conhecidas (passo 12):**
> - o `stderr` não é cortado; a spec pede 10 KB por fluxo;
> - no `agent task --auto-approve`, a checagem recebe `runs/check/ws`, que está sempre dentro de `runs/`, então nunca recusa. O workspace real das tarefas também fica em `runs/`, então o efeito prático é o mesmo, mas a checagem não testa nada.
