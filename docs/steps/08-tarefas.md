# Passo 08: Formato de tarefa, `agent task` e tarefas 01–03

## O que mudou

- **Módulo de gerenciamento de tarefas (`agent/tasks.py`)**:
  - `discover_tasks(tasks_root: Path) -> list[Path]`: descobre todos os diretórios dentro de `tasks_root` que possuem um arquivo `prompt.md`, retornando-os ordenados pelo nome.
  - `prepare(task_dir: Path, run_dir: Path) -> None`: inicializa o ambiente isolado de execução copiando a pasta `workspace/` da tarefa para `run_dir/ws/` (se existir) e executando `python setup.py <run_dir>` caso um script de setup esteja presente.
  - `run_check(task_dir: Path, run_dir: Path) -> bool`: executa de forma determinística `python check.py <ws> <final.txt> <trace.jsonl>` com `cwd=task_dir` e timeout de 60 segundos. Retorna `True` se o processo sair com código 0 e `False` em caso de erro, código diferente de zero ou timeout.
  - `run_task(...) -> tuple[Path, RunResult, bool]`: coordena a execução completa da tarefa no diretório `run_dir`, executa o loop do agente (`execute_run`), avalia a solução com `run_check` e atualiza a última linha do arquivo `trace.jsonl` (evento `end`) registrando `"check": "pass"` ou `"check": "fail"`.
- **Implementação das tarefas 01 a 03 em `tasks/`**:
  - `tasks/01-hello-file/`: solicita a criação de `hello.txt` com o conteúdo exato `Olá, agente!` (tolerando quebra de linha final). O `check.py` valida o conteúdo estrito sem dependências externas.
  - `tasks/02-rename-batch/`: inicializa workspace com `a.txt`, `b.txt` e `notas/c.txt`. Solicita renomear todos os `.txt` para `.md` (inclusive subpastas). O `check.py` assegura que nenhum `.txt` permaneça e que os novos arquivos `.md` possuam o conteúdo original idêntico.
  - `tasks/03-csv-summary/`: inicializa workspace com `vendas.csv` (30 registros distribuídos entre Norte, Sul e Leste, somando respectivamente 1234.50, 987.00 e 2210.25). O `check.py` verifica se todos os três valores aparecem em `resumo.md` aceitando vírgula ou ponto como separador decimal.
  - Todas as tarefas possuem `prediction.md` com os campos `previsão:`, `onde vai falhar:` e `custo estimado (US$):`.
- **Suporte ao comando `task` no CLI (`agent/cli.py`)**:
  - Comando `agent task NN [--model M]` aceitando prefixos como `01` ou nomes completos como `01-hello-file`.
  - Executa o agente isoladamente na pasta `runs/`, submete o resultado ao `check.py` e exibe o status (`pass`/`fail`), o número de turnos e o custo apurado.
- **Testes unitários offline (`tests/test_tasks.py`)**:
  - Validação da descoberta de tarefas, preparação de workspace e execução de `setup.py`.
  - Validação dos scripts `check.py` para as tarefas 01, 02 e 03 (verificando que falham no estado inicial e passam com as soluções esperadas).
  - Testes do fluxo de `run_task` e comandos CLI com clientes simulados.

## Como rodar

Executar os testes unitários da tarefa:

```bash
uv run pytest tests/test_tasks.py
```

Executar uma tarefa específica pelo CLI (requer chave configurada em `.env`):

```bash
uv run agent task 01
uv run agent task 02
uv run agent task 03
```

Inspecionar a execução gerada em `runs/`:

```bash
cat runs/<id>-01-hello-file/trace.jsonl | tail -n 1
cat runs/<id>-01-hello-file/final.txt
ls -la runs/<id>-01-hello-file/ws/
```

## O que observar

- **Linha de encerramento (`end`) no trace**:
  Ao abrir o arquivo `trace.jsonl` de uma execução de tarefa, observe que o evento `end` agora possui o atributo `check`:
  ```json
  {"t": "end", "reason": "no_tool_calls", "turns": 2, "cost_usd": 0.002, "check": "pass"}
  ```
- **Isolamento e reprodutibilidade**:
  Cada execução de tarefa cria sua própria pasta descartável em `runs/<timestamp>-<tarefa>/`, clonando os arquivos originais a partir de `tasks/<tarefa>/workspace/`. O workspace original da tarefa nunca é modificado pela execução do agente.
- **Validação determinística com `check.py`**:
  O script de checagem recebe como argumentos o workspace trabalhado (`ws/`), a resposta textual final (`final.txt`) e o log estruturado (`trace.jsonl`). A validação é completamente offline e independente do modelo utilizado.

## Pergunta de previsão

Para o próximo passo (Task 9: Tarefas armadilha 04–10), ao expor o agente a testes com falhas de compilação/teste, arquivos inexistentes, comandos ambíguos ou tentativas de fuga do workspace, que tipos de comportamento defensivo e limites nas ferramentas esperamos que os scripts de `check.py` precisem verificar?
