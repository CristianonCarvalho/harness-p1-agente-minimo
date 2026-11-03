# Passo 13: Limites por resposta do modelo

## O que mudou

- **`max_tokens` em toda chamada ao modelo (`agent/client.py`)**:
  - *Motivação:* No turno 17 da tarefa 10, uma única resposta do modelo produziu 56.065 tokens de saída descontrolados (custando mais de US$ 0.016 apenas naquele turno).
  - *Implementação:* Adicionado o parâmetro `max_tokens: int | None = 4096` ao `__init__` de `OpenRouterClient` (armazenado em `self.max_tokens`). No método `chat`, quando `self.max_tokens` não for `None`, o payload enviado à API inclui `"max_tokens": self.max_tokens`.
- **Repetição e contenção de `finish_reason: "error"` (`agent/client.py`)**:
  - *Motivação:* Nos turnos 4 e 14 da tarefa 10, o provedor devolveu HTTP 200 com `finish_reason: "error"`, e o loop prosseguiu ignorando o problema.
  - *Implementação:* O método `chat` foi reorganizado sem alterar o comportamento existente para outros cenários: a rotina de envio HTTP com retries para 429, 5xx e erros de transporte foi extraída para `_post(self, payload: dict) -> httpx.Response`; a validação do status, JSON, chaves de erro e `choices` foi extraída para `_parse(self, resp: httpx.Response) -> dict`. Em `chat`, um laço de `self.max_retries + 1` tentativas executa `data = self._parse(self._post(payload))`; caso `data["choices"][0].get("finish_reason") != "error"`, devolve `data`; caso contrário, se ainda houver tentativa, espera com backoff exponencial (`self.sleep(self.backoff_s * (2 ** attempt))`) e repete. Esgotadas as tentativas, dispara `ClientError("provedor devolveu finish_reason error")`.
- **Limite de 10 chamadas de ferramenta por resposta (`agent/ledger.py`, `agent/loop.py`)**:
  - *Motivação:* No turno 6 da tarefa 10, uma resposta trouxe 791 chamadas idênticas da mesma ferramenta (`c06.txt`); todas foram executadas e anexadas ao histórico, fazendo o contexto de entrada saltar de ~1 mil para ~39 mil tokens pelos turnos seguintes.
  - *Implementação:*
    - Em `agent/ledger.py`, criado o método `dropped(self, turn: int, count: int) -> None`, que persiste o registro `{"t": "dropped", "turn": turn, "count": count}` no ledger via `_append`.
    - Em `agent/loop.py`, adicionado o parâmetro `max_tool_calls_per_turn: int = 10` à função `run`. Imediatamente após a leitura de `tool_calls`, se `len(tool_calls) > max_tool_calls_per_turn`, calcula-se `dropped = len(tool_calls) - max_tool_calls_per_turn`, trunca-se `tool_calls` para as primeiras 10 chamadas, atualiza-se `assistant_msg["tool_calls"]` (mantendo o histórico consistente) e registra-se `ledger.dropped(turn=turns, count=dropped)`. Após a execução das chamadas mantidas, caso tenha havido descarte, anexa-se ao `content` da última mensagem `role: tool` a linha `\n[harness: {dropped} chamadas descartadas; máximo de {max_tool_calls_per_turn} por resposta]`.

## Como rodar

Executar os testes das unidades modificadas:

```bash
uv run pytest tests/test_robustness.py tests/test_client.py
```

Executar a tarefa 10 com aprovação automática para observar o comportamento com os novos limites:

```bash
uv run agent task 10 --auto-approve
```

## O que observar

- O evento `dropped` no arquivo `trace.jsonl` quando o modelo tentar emitir chamadas excessivas em uma única resposta.
- O `finish_reason: "length"` quando o `max_tokens` cortar uma resposta excessiva (notando que os `arguments` da última `tool_call` cortada pela metade podem se tornar `error: argumentos inválidos`).
- O custo final da tarefa 10 em comparação com os US$ 0.0725 reportados em `docs/report-depois.md`.

## Pergunta de previsão

Com no máximo 10 chamadas por resposta, a tarefa 10 volta a falhar por `max_turns`? Quantos turnos ela precisa no melhor caso?
