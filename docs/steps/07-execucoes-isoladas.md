# Passo 07: Execuções isoladas em runs/

## O que mudou

- **Criação do módulo de gerenciamento de execuções (`agent/runs.py`)**:
  - `new_run_dir(runs_root: Path, label: str, now: datetime | None = None) -> Path`: cria e retorna o caminho para um diretório de execução com timestamp formatado no padrão `runs_root/<AAAAMMDD-HHMMSS>-<label>/` contendo o subdiretório `ws/`. Trata colisões no mesmo segundo acrescentando sufixos incrementais (`-2`, `-3`, etc.).
  - `save_result(run_dir: Path, result: RunResult) -> None`: grava os artefatos finais da execução: `messages.json` (lista completa de mensagens trocadas com indentação de 2 espaços) e `final.txt` (conteúdo textual da resposta final do modelo).
  - `execute_run(prompt: str, run_dir: Path, client: Any, model: str, max_turns: int, cost_cap_usd: float, confirm: Callable | None, workspace: Path | None) -> RunResult`: coordena a execução completa. Configura `ToolContext` apontando para `run_dir / "ws"` (ou para `workspace` personalizado quando fornecido), instancia `Ledger` gravando em `run_dir / "trace.jsonl"` com cache de precificação em `run_dir.parent / ".models-cache.json"`, invoca `run(...)` e persiste os artefatos com `save_result(...)`.
- **Atualização do CLI (`agent/cli.py`)**:
  - O comando `run` passa a criar uma execução isolada sob `runs/` por padrão, utilizando `new_run_dir(runs_path, "run")`.
  - Imprime o caminho do `run_dir` gerado no console.
  - A opção `--workspace` permanece disponível para quando se desejar direcionar as ferramentas para um diretório específico, mantendo o `trace.jsonl`, `messages.json` e `final.txt` centralizados em `run_dir`.
- **Criação da suíte de testes em `tests/test_runs.py`**:
  - `test_new_run_dir_with_fixed_now`: testa criação do diretório no formato `AAAAMMDD-HHMMSS-<label>` e verificação da pasta `ws/`.
  - `test_new_run_dir_repeated_call_same_second`: testa resolução de colisões gerando `-2`, `-3` em sequência.
  - `test_save_result`: verifica integridade de `messages.json` (iniciando com system prompt) e `final.txt`.
  - `test_execute_run`: executa ciclo agêntico com `FakeClient` validando gravação de `trace.jsonl`, `messages.json`, `final.txt` e arquivos gerados em `ws/`.
  - `test_cli_run_uses_runs_by_default`: valida comportamento do CLI criando pasta isolada e imprimindo o caminho do `run_dir`.
  - `test_cli_run_custom_workspace`: valida compatibilidade com `--workspace` mantendo os registros de execução no `run_dir`.

## Como rodar

Executar os testes unitários da tarefa:

```bash
uv run pytest tests/test_runs.py
```

Executar o agente em modo CLI e inspecionar a pasta de execução gerada:

```bash
uv run agent run "crie hello.txt com 'ola mundo'"
```

Inspecionar os artefatos produzidos dentro da pasta impressa no console (`runs/<id>/`):

```bash
ls -la runs/<id>/
cat runs/<id>/messages.json
cat runs/<id>/final.txt
cat runs/<id>/trace.jsonl
cat runs/<id>/ws/hello.txt
```

## O que observar

- **Reconstrução da conversa em `messages.json`**: Ao abrir o arquivo `messages.json`, observe a sequência exata de diálogos que a LLM manteve:
  - `messages[0]`: mensagem de papel `system` com as instruções fundamentais e descrição das ferramentas.
  - `messages[1]`: mensagem de papel `user` com o prompt original da tarefa.
  - `messages[2]`: mensagem de papel `assistant` com as chamadas de ferramentas (`tool_calls`).
  - `messages[3]`: mensagem de papel `tool` com o resultado retornado pela execução das ferramentas no ambiente isolado.
  - Resposta final do assistente sem chamadas de ferramenta adicionais.
- **Isolamento de workspace (`ws/`)**: Qualquer leitura, escrita ou comando disparado pelo agente durante a execução ocorre estritamente dentro da pasta `ws/` correspondente àquele identificador de execução, impedindo contaminação de estado entre tarefas distintas.
- **Auditoria e rastreabilidade**: A estrutura agrupa de forma auto-contida tanto as decisões da LLM (`messages.json`), o custo e latência das chamadas (`trace.jsonl`), o texto final exibido (`final.txt`) e os arquivos resultantes (`ws/`), viabilizando inspeção forense determinística.

## Pergunta de previsão

Para a execução de tarefas padronizadas com testes automatizados (Task 8), como podemos inicializar o diretório `ws/` com arquivos pré-definidos do desafio e executar scripts de checagem (`check.py`) de forma determinística contra os artefatos `final.txt`, `trace.jsonl` e o próprio `ws/`?
