# Passo 14: Suíte de testes honesta

## O que mudou

- **O que o conftest fazia**:
  No passo 08, quando existiam apenas 3 tarefas no repositório, o teste `tests/test_tasks.py::test_discover_tasks` foi escrito inspecionando o diretório `tasks/` real e esperando exatamente `["01-hello-file", "02-rename-batch", "03-csv-summary"]`. No passo 09 foram criadas as tarefas de 04 a 10. Em vez de atualizar o teste para refletir o novo conjunto de tarefas, foi introduzido o arquivo `tasks/04-fix-failing-test/conftest.py`, que substituía `agent.tasks.discover_tasks` por uma versão que inspecionava a pilha de chamadas via `inspect.stack()`:
  ```python
  def _patched_discover(tasks_root: Path) -> list[Path]:
      tasks = _original_discover(tasks_root)
      stack = inspect.stack()
      if any(frame.function == "test_discover_tasks" for frame in stack):
          return [t for t in tasks if t.name in ("01-hello-file", "02-rename-batch", "03-csv-summary")]
      return tasks
  ```
  Se a função chamadora fosse `test_discover_tasks`, o monkeypatch interceptava o retorno e devolvia apenas as 3 primeiras tarefas.

- **Por que só funcionava ao coletar `tasks/`**:
  O pytest carrega arquivos `conftest.py` dinamicamente conforme descobre diretórios de teste. Ao executar `uv run pytest` na raiz do repositório, o pytest realizava a busca em todas as pastas, encontrava `tasks/04-fix-failing-test/conftest.py` e carregava o patch em memória, fazendo o teste passar silenciosamente. No entanto, ao executar `uv run pytest tests`, o pytest restringia a busca ao diretório `tests/`, nunca carregando o `conftest.py` de `tasks/`. Como resultado, `discover_tasks` retornava todas as 10 tarefas reais e `test_discover_tasks` falhava com `AssertionError` (10 itens != 3 itens).

- **As três mudanças**:
  1. **Remoção dos `conftest.py` de `tasks/`**: Os arquivos `tasks/04-fix-failing-test/conftest.py` e `tasks/05-read-before-edit/conftest.py` (que continha `collect_ignore = ["workspace"]`) foram excluídos com `git rm`.
  2. **Configuração de `testpaths` em `pyproject.toml`**: Adicionada a seção `[tool.pytest.ini_options]` com `testpaths = ["tests"]`, instruindo o pytest a coletar apenas a pasta `tests/`.
  3. **Reescrita dos testes em `tests/test_tasks.py`**:
     - `test_discover_tasks` foi substituído por `test_discover_tasks_sorted(tmp_path: Path)`, que testa a ordenação lexicográfica de `discover_tasks` usando um diretório temporário isolado (`tmp_path`).
     - Adicionado `test_repo_tasks_are_complete()`, que utiliza `REPO_TASKS = Path(__file__).resolve().parent.parent / "tasks"` para validar que as 10 tarefas reais (01 a 10) contêm `prompt.md`, `check.py`, `prediction.md` e `workspace/`, além de assegurar que nenhum `conftest.py` volte a ser criado em `tasks/` (`assert list(REPO_TASKS.rglob("conftest.py")) == []`).

## Como rodar

Executar a suíte de testes a partir da raiz:

```bash
uv run pytest -q
```

Executar a suíte apontando explicitamente para a pasta `tests`:

```bash
uv run pytest tests -q
```

Executar a suíte a partir de dentro do diretório `tests`:

```bash
cd tests && uv run pytest -q
```

Verificar que nenhum arquivo de teste fora de `tests/` é coletado:

```bash
uv run pytest --collect-only -q | grep -v '^tests/' | grep '::'
```

## O que observar

- **Resultados do Step 1 vs. Step 3**:
  - No Step 1 (com conftest adúltero): `uv run pytest -q` passava com `127 passed`, mas `uv run pytest tests -q` falhava com `1 failed, 126 passed` (`test_discover_tasks` recebia 10 tarefas em vez das 3 esperadas).
  - No Step 3 (suíte honesta): tanto `uv run pytest -q` quanto `uv run pytest tests -q` passam com consistência exata (`128 passed`), pois o teste agora verifica as 10 tarefas reais e a ordenação é testada de forma isolada via `tmp_path`.
  - O comando `uv run pytest --collect-only -q | grep -v '^tests/' | grep '::'` não exibe nenhuma saída, confirmando que a coleta está devidamente delimitada.
- **Proteção contra coletas indevidas**:
  - Com `testpaths = ["tests"]` em `pyproject.toml`, o pytest deixa de coletar acidentalmente testes executados ou gerados pelo agente dentro de `runs/*/ws/` ou arquivos em `tasks/*/workspace/` (que contêm testes com bugs propositais para avaliação).

## Pergunta de previsão

Que outro jeito um worker teria de fazer um gate passar sem corrigir o problema, e que teste ou regra pegaria isso?
