# P1 — Passo 13: limites por resposta do modelo — Implementation Plan

> **For agentic workers:** execute com `meister orchestrate --plan-file plan-passo-13.json`. É um passo de estudo: mudanças pequenas e legíveis, um teste por correção, sem refatorar além do pedido. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar as três lacunas que a tarefa 10 expôs em `runs/20261103-151638-10-long-chain`: respostas de dezenas de milhares de tokens, centenas de `tool_calls` numa resposta e `finish_reason: "error"` ignorado.

**Architecture:** O cliente passa a mandar `max_tokens` e a repetir a chamada quando o provedor devolve `finish_reason: "error"`. O loop executa no máximo 10 `tool_calls` por resposta, descarta o resto, avisa o modelo e registra o descarte no trace com um evento novo `dropped`.

**Tech Stack:** Python 3.13, `uv`, `httpx`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-11-02-p1-agente-minimo-design.md`; evidência em `docs/report-depois.md`, seção "10-long-chain: repetição degenerada".

## Global Constraints

- Python `>=3.13`; runtime só `httpx`; dev só `pytest`. Nenhuma dependência nova.
- Testes 100% offline: nenhum teste faz requisição de rede real nem grava fora de `tmp_path`.
- `.env` e `runs/` nunca são commitados.
- Mensagens ao usuário e notas em português; identificadores de código em inglês.
- Não editar `meister.config.yaml`, `tasks/`, `docs/arquitetura/` nem `docs/o-que-deu-errado.md`.
- A nota do passo é `docs/steps/13-limites.md` com as seções `## O que mudou`, `## Como rodar`, `## O que observar`, `## Pergunta de previsão`.
- Assinaturas existentes continuam válidas: os novos parâmetros têm valor padrão.

## Review Focus

- Toda `tool_call` que fica na mensagem do assistente tem uma mensagem `role: tool` com o mesmo `tool_call_id`, e nenhuma descartada fica sem resposta; a API rejeita histórico com chamada sem resposta (teste no Step 3).
- Exatamente 10 `tool_calls`: nada é descartado e não há evento `dropped` (teste no Step 3).
- `finish_reason: "error"` em todas as tentativas: `ClientError`, e o loop termina com `reason == "error"`, sem `IndexError` nem laço infinito (teste no Step 2).
- O `agent report` continua lendo traces com o evento `dropped` sem mudar os números (teste no Step 3).
- `max_tokens=None` no cliente: o corpo não leva a chave, para quem quiser desligar o limite (teste no Step 1).

---

### Task 13: Limites por resposta do modelo

**Files:**
- Modify: `agent/client.py`
- Modify: `agent/loop.py`
- Modify: `agent/ledger.py`
- Modify: `tests/test_client.py`
- Modify: `tests/test_robustness.py`
- Create: `docs/steps/13-limites.md`

Cada step é uma correção: escreva o teste, veja falhar com `uv run pytest tests/test_X.py -k nome`, corrija, veja passar. Ao final, rode a suíte inteira.

- [ ] **Step 1: `max_tokens` em toda chamada.** No turno 17 da tarefa 10 uma única resposta teve 56.065 tokens de saída. Em `agent/client.py`, acrescentar ao `__init__` de `OpenRouterClient` o parâmetro `max_tokens: int | None = 4096` (guardado em `self.max_tokens`) e, em `chat`, `payload["max_tokens"] = self.max_tokens` quando não for `None`. Testes em `tests/test_client.py`, no padrão de `test_chat_sends_body_and_auth`:

```python
def test_chat_sends_max_tokens():
    seen = {}

    def h(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "oi"}, "finish_reason": "stop"}], "usage": {}})

    make(h).chat([{"role": "user", "content": "x"}], model="m")
    assert seen["body"]["max_tokens"] == 4096


def test_chat_without_max_tokens():
    seen = {}

    def h(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "oi"}, "finish_reason": "stop"}], "usage": {}})

    OpenRouterClient("k", transport=httpx.MockTransport(h), max_tokens=None).chat([{"role": "user", "content": "x"}], model="m")
    assert "max_tokens" not in seen["body"]
```

- [ ] **Step 2: `finish_reason: "error"` é repetido e, se persistir, vira `ClientError`.** Nos turnos 4 e 14 da tarefa 10 o provedor devolveu HTTP 200 com `finish_reason: "error"`, e o loop seguiu. Em `agent/client.py`, reorganizar `chat` sem mudar o comportamento atual:
  - extrair o laço atual de POST com retry de 429, 5xx e erro de transporte para `_post(self, payload: dict) -> httpx.Response`;
  - extrair a validação que vem depois (status de erro, JSON, `error`, `choices`) para `_parse(self, resp: httpx.Response) -> dict`;
  - em `chat`, um laço de `self.max_retries + 1` tentativas: `data = self._parse(self._post(payload))`; se `data["choices"][0].get("finish_reason") != "error"`, devolve `data`; senão, se ainda houver tentativa, `self.sleep(self.backoff_s * (2 ** attempt))` e repete; esgotadas as tentativas, `raise ClientError("provedor devolveu finish_reason error")`.

Testes em `tests/test_robustness.py`, no padrão de `test_retry_then_success` (cliente com `sleep` falso que registra as esperas):

```python
def finish(reason):
    return httpx.Response(200, json={"choices": [{"message": {"content": "x"}, "finish_reason": reason}], "usage": {}})


def test_finish_reason_error_is_retried():
    replies = [finish("error"), finish("stop")]
    slept = []
    c = OpenRouterClient("k", transport=httpx.MockTransport(lambda r: replies.pop(0)), sleep=slept.append)
    r = c.chat([{"role": "user", "content": "x"}], model="m")
    assert r["choices"][0]["finish_reason"] == "stop"
    assert len(slept) == 1


def test_finish_reason_error_exhausted_ends_run(tmp_path: Path):
    count = {"n": 0}

    def h(req):
        count["n"] += 1
        return finish("error")

    c = OpenRouterClient("k", transport=httpx.MockTransport(h), sleep=lambda s: None)
    with pytest.raises(ClientError):
        c.chat([{"role": "user", "content": "x"}], model="m")
    assert count["n"] == 4

    r = run("x", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m")
    assert r.reason == "error"
```

- [ ] **Step 3: no máximo 10 `tool_calls` por resposta.** No turno 6 da tarefa 10 uma resposta trouxe 791 chamadas idênticas; todas foram executadas e anexadas ao histórico. Mudanças:
  - `agent/ledger.py`: método `dropped(self, turn: int, count: int) -> None`, que grava `{"t": "dropped", "turn": turn, "count": count}` pelo `_append`, como os outros eventos.
  - `agent/loop.py`: novo parâmetro `max_tool_calls_per_turn: int = 10` em `run`. Logo depois de ler `tool_calls`, se `len(tool_calls) > max_tool_calls_per_turn`: `dropped = len(tool_calls) - max_tool_calls_per_turn`, `tool_calls = tool_calls[:max_tool_calls_per_turn]`, `assistant_msg["tool_calls"] = tool_calls` (a mensagem já está em `messages`, então o histórico fica coerente) e `ledger.dropped(turn=turns, count=dropped)`. Depois do laço que executa as chamadas, se houve descarte, acrescentar ao `content` da última mensagem `role: tool` a linha `\n[harness: {dropped} chamadas descartadas; máximo de {max_tool_calls_per_turn} por resposta]`.

Testes em `tests/test_robustness.py`, com o `FakeClient`, `msg` e `call` do arquivo:

```python
def test_tool_calls_over_limit_are_dropped(tmp_path: Path):
    (tmp_path / "a.txt").write_text("oi")
    many = [call(f"c{i}", "read_file", {"path": "a.txt"}) for i in range(25)]
    c = FakeClient([msg(tool_calls=many), msg("fim")])
    r = run("x", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m")

    assistant = [m for m in r.messages if m["role"] == "assistant"][0]
    tool_msgs = [m for m in r.messages if m["role"] == "tool"]
    assert len(assistant["tool_calls"]) == 10
    assert [m["tool_call_id"] for m in tool_msgs] == [tc["id"] for tc in assistant["tool_calls"]]
    assert "15 chamadas descartadas" in tool_msgs[-1]["content"]

    events = [json.loads(l) for l in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert [e for e in events if e["t"] == "dropped"] == [{"t": "dropped", "turn": 1, "count": 15}]
    assert len([e for e in events if e["t"] == "tool"]) == 10


def test_exactly_limit_is_not_dropped(tmp_path: Path):
    (tmp_path / "a.txt").write_text("oi")
    ten = [call(f"c{i}", "read_file", {"path": "a.txt"}) for i in range(10)]
    c = FakeClient([msg(tool_calls=ten), msg("fim")])
    r = run("x", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m")
    assert len([m for m in r.messages if m["role"] == "tool"]) == 10
    assert '"dropped"' not in (tmp_path / "t.jsonl").read_text()
```

E um teste de que o relatório ignora o evento novo, também em `tests/test_robustness.py`:

```python
def test_report_ignores_dropped_event(tmp_path: Path):
    from agent.report import build_report

    tasks = tmp_path / "tasks" / "01-x"
    tasks.mkdir(parents=True)
    (tasks / "prompt.md").write_text("x")
    run_dir = tmp_path / "runs" / "20260101-000000-01-x"
    run_dir.mkdir(parents=True)
    (run_dir / "trace.jsonl").write_text(
        '{"t": "llm", "turn": 1, "prompt_tokens": 5, "completion_tokens": 2, "cost_usd": 0.001}\n'
        '{"t": "dropped", "turn": 1, "count": 3}\n'
        '{"t": "end", "reason": "no_tool_calls", "turns": 1, "cost_usd": 0.001, "check": "pass"}\n'
    )
    out = build_report(tmp_path / "tasks", tmp_path / "runs")
    assert "| 01-x |" in out and "5/2" in out and "pass" in out
```

Se `build_report` exigir outros arquivos na pasta da tarefa ou outro formato de nome de execução, ajuste o teste ao que `discover_tasks` e `latest_run` esperam (veja `tests/test_report.py`), mantendo as três linhas do trace.

- [ ] **Step 4: suíte, nota e commit.** Rode `uv run pytest` (suíte inteira) → PASS. Escreva `docs/steps/13-limites.md`: em "O que mudou", as três mudanças com o turno do trace da tarefa 10 que motivou cada uma; em "Como rodar", `uv run pytest tests/test_robustness.py tests/test_client.py` e `uv run agent task 10 --auto-approve`; em "O que observar", o evento `dropped` no `trace.jsonl`, o `finish_reason: "length"` quando o `max_tokens` corta uma resposta (o `arguments` da última `tool_call` pode vir cortado e virar `error: argumentos inválidos`), e o custo da tarefa 10 comparado com os US$ 0.0725 de `docs/report-depois.md`; em "Pergunta de previsão", "Com no máximo 10 chamadas por resposta, a tarefa 10 volta a falhar por `max_turns`? Quantos turnos ela precisa no melhor caso?". Commit `fix(step-13): limites por resposta do modelo`.
