# Passo 10: Relatório, lote e `--auto-approve`

## O que mudou

- **Módulo de relatório e segurança (`agent/report.py`)**:
  - `read_prediction(task_dir: Path) -> str | None`: lê o arquivo `prediction.md` de uma tarefa e identifica se a previsão declarada foi `"pass"` ou `"fail"`. Retorna `None` se o arquivo não existir, estiver vazio ou se contiver apenas o modelo/template inicial.
  - `latest_run(runs_root: Path, task_name: str) -> Path | None`: seleciona a execução mais recente para uma dada tarefa em `runs_root`, ordenando lexicograficamente pelo nome do diretório (`<timestamp>-<tarefa>`).
  - `check_auto_approve(workspace: Path, runs_root: Path) -> None`: protege o operador de execuções perigosas sem intervenção humana, garantindo que o workspace resolvido esteja estritamente contido dentro da pasta `runs/` resolvida. Levanta `ValueError` se o caminho apontar para fora do diretório de runs ou for a própria raiz de runs.
  - `build_report(tasks_root: Path, runs_root: Path) -> str`: sintetiza os dados em um relatório em Markdown estruturado com:
    - Tabela de cada tarefa com as colunas: `tarefa`, `previsto`, `real`, `acertou?` (`sim`/`não`/`—`), `turnos`, `tokens (in/out)`, `custo US$` e `motivo do fim`.
    - Tarefas sem histórico de execução aparecem com `real: —`.
    - Rodapé estatístico detalhando a taxa de acerto das previsões (`Acerto das previsões: X/Y (Z%)`), lista das tarefas sem previsão, custo médio por tarefa executada, custo total e quantidade de chamadas que utilizaram custo estimado (`estimated`).
- **Extensões na interface de linha de comando (`agent/cli.py`)**:
  - Subcomando `agent report`: compila o relatório das últimas execuções, imprime no terminal e grava em `runs/report.md`.
  - Opção `--all` em `agent task`: orquestra a execução sequencial em lote de todas as tarefas cadastradas na pasta `tasks/`.
  - Flag `--auto-approve` em `agent task` e `agent run`: desativa a confirmação interativa no terminal substituindo a função `confirm` por `lambda c: True`, validada antes com `check_auto_approve`. No comando `run`, caso `--workspace` aponte para um diretório fora de `runs/`, a execução é rejeitada com código de saída 2 e mensagem descritiva de erro.
- **Suíte de testes offline (`tests/test_report.py`)**:
  - 12 testes unitários cobrindo leitura de previsões (`read_prediction`), seleção determinística da execução mais recente (`latest_run`), validações de confinamento de sandbox (`check_auto_approve`), geração do relatório e do rodapé (`build_report`), e os fluxos de CLI (`report`, `task --all --auto-approve`, e rejeição de `--auto-approve` em workspace externo).

## Como rodar

Executar os testes unitários do relatório e comandos em lote:

```bash
uv run pytest tests/test_report.py
```

Fluxo completo de estudo com a API real (requer chave configurada em `.env`):

1. Preencher as hipóteses em `prediction.md` de cada tarefa (ex.: `tasks/01-hello-file/prediction.md` com `previsão: pass`):
```markdown
previsão: pass
onde vai falhar:
custo estimado (US$): 0.002
```

2. Executar a suíte completa de tarefas em lote com auto-aprovação:
```bash
uv run agent task --all --auto-approve
```

3. Gerar e visualizar o relatório consolidado de previsões e custos:
```bash
uv run agent report
cat runs/report.md
```

Testar a guarda de auto-aprovação bloqueando workspace externo:
```bash
uv run agent run "liste os arquivos" --workspace /tmp --auto-approve
# Retorna código 2 com mensagem de erro
```

## O que observar

- **Confronto Hipótese vs. Realidade**:
  O relatório tabula lado a lado o que você esperava (`previsto`) com a aferição automatizada do `check.py` (`real`), evidenciando acertos e surpresas na taxa final de acerto (`Acerto das previsões`).
- **Auditoria de Custos e Estimativas**:
  O rodapé expõe não apenas o custo total e médio, mas destaca quantas linhas do log dependeram de tabela de precificação estimada (`estimated`) por ausência de campo de custo retornado diretamente pelo provedor.
- **Controle de Risco e Sandbox Limitada**:
  A guarda `check_auto_approve` garante que o modo sem intervenção manual (`--auto-approve`) só opere em diretórios isolados dentro de `runs/`. No entanto, como o comando executa via `shell=True`, comandos com caminhos absolutos ainda poderiam interagir com o sistema hospedeiro se não houvesse monitoramento ou confinamento no nível de SO.

## Pergunta de previsão

Para a documentação final e o encerramento do projeto (Passo 11): quais limites fundamentais do harness (como `shell=True`, a falta de container real e a aprovação automática) devem ser destacados no README para orientar quem for estudar o código?
