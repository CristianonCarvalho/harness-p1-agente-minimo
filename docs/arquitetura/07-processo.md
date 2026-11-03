# 7. Processo

[← Índice](README.md)

## Onde o P1 está no roadmap

```mermaid
timeline
    title Roadmap de 12 meses
    Fase 0 : Linha de base
    Fase 1 : Fundamentos de LLM : P1 agente mínimo
    Fase 2 : Contexto e harness : P2 MCP server de legislação
    Fase 3 : Evals : P3 suíte de evals do P2
    Fase 4 : Segurança e CI/CD : P4 agente abre PR, gates decidem
    Fase 5 : Especialização na RFB : P5 kit de adoção
    Fase 6 : Consolidação : artigo ou TCC
```

## Da ideia ao código

```mermaid
flowchart LR
    a["Roadmap<br/>claude.ai"] --> b["Brainstorming<br/>decisões uma a uma"]
    b --> c["Spec<br/>docs/superpowers/specs/"]
    c --> d["Plano de 12 tarefas<br/>docs/superpowers/plans/"]
    d --> e["plan.json<br/>meister plan import"]
    e --> f["meister orchestrate"]
    f --> g["main + tags step-00 a step-11"]
    g --> h["Revisão<br/>117 testes, 7 desvios"]
    h --> i["Passo 12<br/>correções"]
```

## Como o Meister executou cada passo

```mermaid
sequenceDiagram
    participant O as meister orchestrate
    participant J as Jev (roteador)
    participant W1 as tier_1 / 1b / 1c<br/>copilot e codex
    participant W2 as tier_2<br/>agy, Gemini 3.8 Flash
    participant G as Gate
    participant I as worktree de integração

    loop para cada tarefa, em sequência
        O->>O: cria worktree isolado da tarefa
        O->>J: classifica a tarefa
        J-->>O: começa pelo tier_1
        O->>W1: executa
        W1-->>O: sai com código 1 em menos de 10s
        Note over O,W1: nesta execução, copilot e codex falharam<br/>ao abrir em todas as 12 tarefas
        O->>W2: escala para o tier_2
        W2-->>O: implementação + testes + commit
        O->>G: confere escopo dos arquivos e roda a suíte
        G-->>O: aprovado
        O->>I: merge da tarefa
    end
    O->>O: atualiza main com a integração
```

Cada tarefa levou de 5 a 23 minutos no `tier_2`, cerca de 2 horas no total.

## Histórico git

```mermaid
gitGraph
    commit id: "spec"
    commit id: "plano"
    commit id: "meister init"
    branch integracao
    commit id: "base" tag: "step-00"
    commit id: "cliente" tag: "step-01"
    commit id: "ledger" tag: "step-02"
    commit id: "ferramentas" tag: "step-03"
    commit id: "loop" tag: "step-04"
    commit id: "shell" tag: "step-05"
    commit id: "robustez" tag: "step-06"
    commit id: "runs" tag: "step-07"
    commit id: "tarefas 1-3" tag: "step-08"
    commit id: "tarefas 4-10" tag: "step-09"
    commit id: "relatorio" tag: "step-10"
    commit id: "readme" tag: "step-11"
    checkout main
    merge integracao
```

Simplificação: na prática, cada passo veio de um worktree próprio e entrou na integração com um merge.

## Como estudar cada passo

```mermaid
flowchart TD
    a["Ler docs/steps/NN-nome.md"] --> b["Responder a pergunta de previsão<br/>do passo anterior"]
    b --> c["git diff step-NN-1 step-NN"]
    c --> d["Rodar os testes do passo<br/>uv run pytest tests/test_X.py"]
    d --> e["Smoke test com a API<br/>comando da nota"]
    e --> f{"Acertou a previsão?"}
    f -->|sim| g["Próximo passo"]
    f -->|não| h["Anotar por quê<br/>candidato a falha explicada"]
    h --> g
```

## O ciclo de medição do P1

```mermaid
journey
    title Do palpite à falha explicada
    section Antes de rodar
      Ler prompt e workspace de cada tarefa: 4: Você
      Preencher prediction.md: 3: Você
    section Rodar
      agent task --all --auto-approve: 5: Agente
      agent report: 5: Agente
    section Depois
      Comparar previsto e real: 3: Você
      Abrir messages.json das surpresas: 2: Você
      Escrever as 5 falhas explicadas: 2: Você
```

As notas de 1 a 5 indicam o esforço esperado: quanto menor, mais trabalho. A parte difícil, e a que vale o projeto, é a última seção.
