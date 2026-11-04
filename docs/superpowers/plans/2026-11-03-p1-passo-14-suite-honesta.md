# P1 — Passo 14: suíte de testes honesta — Implementation Plan

> **For agentic workers:** execute com `meister orchestrate --plan-file plan-passo-14.json`. É um passo de estudo: mudanças pequenas e legíveis. Não contorne um teste que falha: corrija o código ou o teste, e explique na nota. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remover o `conftest.py` que, desde o passo 09, troca `agent.tasks.discover_tasks` em tempo de execução para fazer passar um teste desatualizado, e deixar a suíte com o mesmo resultado em `uv run pytest` e `uv run pytest tests`.

**Architecture:** O pytest passa a coletar só `tests/` (`testpaths`). Os dois `conftest.py` de `tasks/` saem. O teste de descoberta passa a usar `tmp_path`, e um teste novo confere as 10 tarefas reais e proíbe `conftest.py` dentro de `tasks/`.

**Tech Stack:** Python 3.13, `uv`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-11-02-p1-agente-minimo-design.md`

## Global Constraints

- Python `>=3.13`; runtime só `httpx`; dev só `pytest`. Nenhuma dependência nova.
- Testes 100% offline: nenhum teste faz requisição de rede real nem grava fora de `tmp_path`.
- `.env` e `runs/` nunca são commitados.
- Mensagens ao usuário e notas em português; identificadores de código em inglês.
- Não editar `agent/`, `meister.config.yaml`, `docs/arquitetura/`, `docs/o-que-deu-errado.md` nem nenhum arquivo de `tasks/` além dos dois `conftest.py` removidos. Os `prediction.md` são do autor.
- Nenhum teste pode depender do diretório atual: caminhos do repositório são montados a partir de `Path(__file__)`.
- A nota do passo é `docs/steps/14-suite-honesta.md` com as seções `## O que mudou`, `## Como rodar`, `## O que observar`, `## Pergunta de previsão`.

## Review Focus

- `uv run pytest` e `uv run pytest tests` coletam e passam exatamente os mesmos testes (verificação no Step 3).
- `uv run pytest` na raiz não coleta nada de `tasks/*/workspace/` nem de `runs/*/ws/`, que têm testes que falham de propósito ou foram escritos pelo agente (verificação no Step 3).
- Rodar a suíte de outro diretório (`cd tests && uv run pytest`) não muda o resultado (teste no Step 2).
- Uma tarefa nova sem `check.py` ou sem `prediction.md` quebra a suíte (teste no Step 2).
- Um `conftest.py` reaparecendo em `tasks/` quebra a suíte (teste no Step 2).

---

### Task 14: Suíte de testes honesta

**Files:**
- Delete: `tasks/04-fix-failing-test/conftest.py`
- Delete: `tasks/05-read-before-edit/conftest.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_tasks.py`
- Create: `docs/steps/14-suite-honesta.md`

Contexto: `tests/test_tasks.py::test_discover_tasks` foi escrito no passo 08, quando havia 3 tarefas, e lê o `tasks/` real. No passo 09 vieram as tarefas 04 a 10; em vez de atualizar o teste, `tasks/04-fix-failing-test/conftest.py` passou a substituir `agent.tasks.discover_tasks` por uma versão que inspeciona a pilha e, se encontra uma função chamada `test_discover_tasks`, devolve só as 3 primeiras tarefas. Esse conftest só carrega quando o pytest coleta `tasks/`; por isso `uv run pytest` passa e `uv run pytest tests` falha com `1 failed`.

- [ ] **Step 1: reproduzir.** Rode `uv run pytest tests -q` e confirme `1 failed` em `test_discover_tasks`. Rode `uv run pytest -q` e confirme que passa. Anote os dois resultados para a nota.

- [ ] **Step 2: corrigir.**
  - Apague `tasks/04-fix-failing-test/conftest.py` e `tasks/05-read-before-edit/conftest.py` (`git rm`).
  - Em `pyproject.toml`, acrescente no fim:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

  - Em `tests/test_tasks.py`, substitua `test_discover_tasks` por estes dois testes (mantenha `test_discover_tasks_ignores_dir_without_prompt` como está):

```python
def test_discover_tasks_sorted(tmp_path: Path):
    for name in ("03-c", "01-a", "02-b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "prompt.md").write_text("x")
    assert [t.name for t in discover_tasks(tmp_path)] == ["01-a", "02-b", "03-c"]


REPO_TASKS = Path(__file__).resolve().parent.parent / "tasks"


def test_repo_tasks_are_complete():
    names = [t.name for t in discover_tasks(REPO_TASKS)]
    assert names == [
        "01-hello-file",
        "02-rename-batch",
        "03-csv-summary",
        "04-fix-failing-test",
        "05-read-before-edit",
        "06-missing-file",
        "07-ambiguous",
        "08-huge-output",
        "09-escape-workspace",
        "10-long-chain",
    ]
    for name in names:
        task = REPO_TASKS / name
        for required in ("prompt.md", "check.py", "prediction.md"):
            assert (task / required).is_file(), f"{name} sem {required}"
        assert (task / "workspace").is_dir(), f"{name} sem workspace/"
    assert list(REPO_TASKS.rglob("conftest.py")) == []
```

- [ ] **Step 3: verificar.** Todos devem passar e dar o mesmo número:
  - `uv run pytest -q`
  - `uv run pytest tests -q`
  - `cd tests && uv run pytest -q`
  - `uv run pytest --collect-only -q | grep -v '^tests/' | grep '::'` não deve imprimir nada.

- [ ] **Step 4: nota e commit.** Escreva `docs/steps/14-suite-honesta.md`: em "O que mudou", o que o conftest fazia (com o trecho que inspeciona a pilha), por que só funcionava ao coletar `tasks/`, e as três mudanças; em "Como rodar", os comandos do Step 3; em "O que observar", os resultados do Step 1 contra os do Step 3, e que `testpaths` também deixa de coletar os testes que o agente escreve em `runs/*/ws/`; em "Pergunta de previsão", "Que outro jeito um worker teria de fazer um gate passar sem corrigir o problema, e que teste ou regra pegaria isso?". Commit `fix(step-14): suíte de testes honesta`.
