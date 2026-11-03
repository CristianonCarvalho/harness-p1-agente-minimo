# P1 — Passo 12: correções da revisão — Implementation Plan

> **For agentic workers:** execute com `meister orchestrate --plan-file plan-passo-12.json`. É um passo de estudo: mudanças pequenas e legíveis, um teste por correção, sem refatorar além do pedido. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir os 7 desvios encontrados na revisão do código da tag `step-11`, cada um com um teste que falha antes e passa depois.

**Architecture:** Mudanças locais em `agent/loop.py`, `agent/tools.py`, `agent/client.py` e `agent/cli.py`, mais ajustes nos testes que dependiam do comportamento errado. Nenhuma interface pública muda de assinatura.

**Tech Stack:** Python 3.13, `uv`, `httpx`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-11-02-p1-agente-minimo-design.md`

## Global Constraints

- Python `>=3.13`; runtime só `httpx`; dev só `pytest`. Nenhuma dependência nova.
- Testes 100% offline: nenhum teste faz requisição de rede real nem grava fora de `tmp_path`.
- `.env` e `runs/` nunca são commitados.
- Mensagens ao usuário e notas em português; identificadores de código em inglês.
- Retornos de ferramenta com erro começam com `error: `.
- Não editar `meister.config.yaml`, `tasks/` nem `docs/arquitetura/`.
- A nota do passo é `docs/steps/12-correcoes.md` com as seções `## O que mudou`, `## Como rodar`, `## O que observar`, `## Pergunta de previsão`.

## Review Focus

- `stderr` enorme de `run_command`: cortado no mesmo limite e com o mesmo aviso `[truncado: N bytes no total]` do `stdout` (teste no Step 2).
- Resposta HTTP 200 com `"choices": []`: `ClientError`, e o loop termina com `reason == "error"` em vez de `IndexError` (teste no Step 3).
- Teste do `ask` que grava em `runs/` do repositório: depois do passo, a suíte não cria nada em `runs/` (teste no Step 4).
- `agent run` sem `--workspace`: nenhum arquivo aparece no diretório atual; tudo fica em `runs/<id>/ws/` (teste no Step 7).
- Saída do `agent task`: mostra o diretório da execução, onde o usuário vai procurar o trace (teste no Step 5).

---

### Task 12: Correções da revisão

**Files:**
- Modify: `agent/loop.py`
- Modify: `agent/tools.py`
- Modify: `agent/client.py`
- Modify: `agent/cli.py`
- Modify: `tests/test_loop.py`
- Modify: `tests/test_tools_shell.py`
- Modify: `tests/test_client.py`
- Modify: `tests/test_tasks.py`
- Modify: `tests/test_report.py`
- Create: `docs/steps/12-correcoes.md`

Cada step é uma correção: escreva o teste, veja falhar com `uv run pytest tests/test_X.py -k nome`, corrija, veja passar. Ao final, rode a suíte inteira.

- [ ] **Step 1: `SYSTEM_PROMPT` apresenta as três ferramentas.** Hoje o prompt cita só `read_file` e `write_file`, embora `run_command` esteja em `TOOL_SCHEMAS`. Teste em `tests/test_loop.py`:

```python
from agent.tools import TOOL_SCHEMAS

def test_system_prompt_lists_every_tool():
    for schema in TOOL_SCHEMAS:
        assert schema["function"]["name"] in SYSTEM_PROMPT
```

Correção em `agent/loop.py`: acrescentar ao `SYSTEM_PROMPT` a linha `- run_command: executa um comando de shell no workspace (o usuário pode negar).`

- [ ] **Step 2: `stderr` cortado como o `stdout`.** Hoje `_run_command` corta só o `stdout` em `ctx.out_limit`; o `stderr` vai inteiro para o modelo. Teste em `tests/test_tools_shell.py` (use o `ToolContext` com `confirm=lambda c: True` e `out_limit=100`, como os testes vizinhos):

```python
def test_stderr_is_truncated(tmp_path):
    ctx = ToolContext(workspace=tmp_path, confirm=lambda c: True, out_limit=100)
    out = execute("run_command", {"command": "python3 -c \"import sys; sys.stderr.write('e' * 5000)\""}, ctx)
    stderr_part = out.text.split("stderr:\n", 1)[1]
    assert "[truncado: 5000 bytes no total]" in stderr_part
    assert len(stderr_part) < 200
```

Correção em `agent/tools.py`: extrair uma função `_cut(text: str, limit: int) -> str` com a lógica de corte que hoje está inline para o `stdout` (encode, corte em bytes, decode com `errors="replace"`, aviso `[truncado: N bytes no total]`) e aplicá-la a `stdout` e `stderr`.

- [ ] **Step 3: `choices` vazio vira `ClientError`.** Hoje o cliente só verifica se a chave `choices` existe; `"choices": []` passa e o loop quebra com `IndexError` em `resp["choices"][0]`. Teste em `tests/test_client.py`, seguindo o padrão de `test_chat_missing_choices_raises`:

```python
def test_chat_empty_choices_raises():
    client = OpenRouterClient("k", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": []})))
    with pytest.raises(ClientError):
        client.chat([{"role": "user", "content": "x"}], model="m")
```

Correção em `agent/client.py`: trocar `if "choices" not in data:` por `if not isinstance(data.get("choices"), list) or not data["choices"]:` e a mensagem para `"Response missing or empty 'choices'"`. Se o teste existente de `choices` ausente conferir a mensagem, ajuste-o.

- [ ] **Step 4: testes do `ask` não gravam em `runs/` do repositório.** Hoje `test_cli_ask_success` e `test_cli_ask_with_model_flag` chamam `main([...], client=...)` sem `runs_dir`, e o ledger vai para `runs/ask-*.jsonl` real. Em `tests/test_client.py`, acrescentar `tmp_path` aos dois testes, passar `runs_dir=tmp_path` e conferir:

```python
    assert len(list(tmp_path.glob("ask-*.jsonl"))) == 1
```

Não há mudança em `agent/`; o `main` já aceita `runs_dir`.

- [ ] **Step 5: saída do `agent task` mostra o diretório e arredonda o custo.** Hoje imprime `pass · turnos: 2 · custo: US$ 0.000202440000002` e não diz onde está o trace. Em `agent/cli.py`, nas duas impressões do comando `task` (lote e tarefa única), usar o custo com 4 casas e o `run_dir` no fim:

```python
print(f"{task_dir.name}: {status} · turnos: {res.turns} · custo: US$ {res.cost_usd:.4f} · {run_dir}")
print(f"{status} · turnos: {res.turns} · custo: US$ {res.cost_usd:.4f} · {run_dir}")
```

A saída do `agent run` não muda. Em `tests/test_tasks.py`, onde hoje há `assert "pass · turnos: 2 · custo: US$ 0.002" in out`, trocar por `"pass · turnos: 2 · custo: US$ 0.0020 · "` e acrescentar uma checagem de que o caminho do único diretório criado em `runs_dir` aparece em `out`.

- [ ] **Step 6: remover a checagem tautológica do `--auto-approve` no `agent task`.** Hoje o comando `task` chama `check_auto_approve(runs_path / "check" / "ws", runs_path)`, que sempre passa: o caminho é montado dentro de `runs_path`. A garantia real é que `run_task` sempre cria o workspace em `runs_root/<id>/ws`. Em `agent/cli.py`, remover essa chamada e deixar um comentário de uma linha: `# no task o ws é sempre runs/<id>/ws (run_task), então o auto-approve já fica restrito a runs/`. Em `tests/test_report.py`, em `test_cli_task_all_and_auto_approve`, acrescentar a checagem que pina a garantia:

```python
    for d in runs_root.iterdir():
        if d.is_dir():
            assert (d / "ws").resolve().is_relative_to(runs_root.resolve())
```

`check_auto_approve` continua existindo e sendo usado pelo `agent run`.

- [ ] **Step 7: `agent run` não copia arquivos para o diretório atual.** Hoje há um bloco em `agent/cli.py` que, quando `runs_dir` é o `cwd`, copia os arquivos de `ws/` para o `cwd`; existe só para satisfazer `test_cli_run_default_workspace`. Remover o bloco inteiro (`if runs_dir is not None and Path.cwd().resolve() == runs_dir.resolve(): ...`). Em `tests/test_loop.py`, reescrever o teste para pinar o comportamento certo:

```python
def test_cli_run_default_workspace(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model", max_turns=10))
    monkeypatch.chdir(tmp_path)
    runs_dir = tmp_path / "runs"
    c = FakeClient([
        msg(tool_calls=[call("c1", "write_file", {"path": "default_ws.txt", "content": "teste"})]),
        msg("criado no ws"),
    ])
    code = main(["run", "crie default_ws.txt"], client=c, runs_dir=runs_dir)
    assert code == 0
    assert not (tmp_path / "default_ws.txt").exists()
    created = list(runs_dir.glob("*/ws/default_ws.txt"))
    assert len(created) == 1 and created[0].read_text() == "teste"
```

- [ ] **Step 8: suíte, nota e commit.** Rode `uv run pytest` (suíte inteira) → PASS, e confira com `git status` que nada foi criado em `runs/` pelos testes. Escreva `docs/steps/12-correcoes.md`: em "O que mudou", uma linha por correção (o desvio e a correção); em "Como rodar", `uv run pytest` e `uv run agent task --all --auto-approve` seguido de `uv run agent report`; em "O que observar", comparar o novo `runs/report.md` com `docs/report-antes.md` (o modelo passa a ver `run_command` no prompt, o que pode mudar turnos e custo das tarefas 04, 08 e 09); em "Pergunta de previsão", "Com `run_command` no prompt, a tarefa 10 continua falhando por `max_turns`? Por quê?". Commit `fix(step-12): correções da revisão`.
