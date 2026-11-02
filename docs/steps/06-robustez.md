# Passo 06: Robustez — retry, argumentos inválidos e teto de custo

## O que mudou

- **Mecanismo de retry com backoff exponencial no `OpenRouterClient` (`agent/client.py`)**:
  - Novos parâmetros no construtor: `max_retries: int = 3`, `backoff_s: float = 1.0` e `sleep: Callable[[float], None] = time.sleep`.
  - Política de repetição para falhas transitórias: códigos HTTP 429 (rate limit) e 5xx (erros internos do servidor OpenRouter/provedores), além de exceções de rede (`httpx.TimeoutException` e `httpx.TransportError`).
  - Intervalo de espera exponencial: `backoff_s * 2**tentativa` (ex: 1.0s, 2.0s, 4.0s para tentativas 0, 1 e 2).
  - Erros não transitórios do cliente (como 400 Bad Request, 401 Unauthorized) não acionam repetição e lançam `ClientError` imediatamente.
  - Ao esgotar as `max_retries`, levanta `ClientError` com os detalhes da resposta ou exceção subjacente.
- **Tratamento tolerante a falhas de argumentos de ferramentas (`agent/loop.py`)**:
  - Validação do campo `function.arguments` retornado pelo modelo na chamada de ferramentas.
  - Caso o argumento não seja um JSON válido (ex: `""`, `"{nao json"`) ou não seja um objeto (`dict`), em vez de quebrar a execução do Python com `json.JSONDecodeError`, captura a falha e gera uma resposta de ferramenta padronizada iniciando com `error: argumentos inválidos: ...`.
  - O loop anexa esse retorno como uma mensagem `role: "tool"` normal para que o modelo possa interpretar a falha e tentar se auto-corrigir no turno seguinte.
- **Teto orçamentário de custo (`cost_cap_usd`) no ciclo agêntico (`agent/loop.py`)**:
  - Adicionado o parâmetro `cost_cap_usd: float = 0.10` na função `run(...)`.
  - A verificação do teto é realizada imediatamente após cada resposta do modelo e registro no `ledger` (`ledger.total_cost >= cost_cap_usd`), **antes** da execução de qualquer ferramenta daquele turno.
  - Caso o teto seja atingido ou ultrapassado, o loop encerra imediatamente com `reason = "cost_cap"` e as ferramentas solicitadas não são executadas, prevenindo gastos excessivos acidentais.
- **Tratamento de falhas irrecuperáveis do cliente (`ClientError`) no loop (`agent/loop.py`)**:
  - O loop envolve a chamada a `client.chat(...)` em bloco `try/except ClientError`.
  - Caso o cliente falhe definitivamente (mesmo após retries esgotados), o loop finaliza ordenadamente com `reason = "error"`, `RunResult.final = ""` e emite o registro `end` no `Ledger` com `reason: "error"`.
- **Criação da suíte de testes em `tests/test_robustness.py`**:
  - `test_retry_then_success`: valida que respostas 429 repetem com backoff exato de `[1.0, 2.0]` antes de retornar com sucesso no status 200.
  - `test_retry_exhausted_raises`: valida que erro 500 continuado esgota as tentativas e lança `ClientError`.
  - `test_no_retry_on_400`: confirma que status 400 não gera repetições.
  - `test_retry_on_timeout_exception` e `test_retry_on_transport_error`: validam resiliência a timeouts e erros de conexão de transporte.
  - `test_invalid_arguments_become_error`: confirma que JSONs truncados ou inválidos são convertidos em respostas de erro para a LLM sem interromper a execução do agente.
  - `test_cost_cap`: assegura que o loop é interrompido com `reason = "cost_cap"` assim que o teto financeiro é excedido, antes de executar as ferramentas pendentes.
  - `test_client_error_ends_run`: valida encerramento com `reason = "error"`, `final = ""` e registro no `Ledger`.

## Como rodar

Para executar a suíte de testes de robustez e os testes relacionados de cliente e loop:

```bash
uv run pytest tests/test_robustness.py tests/test_loop.py tests/test_client.py
```

Para rodar o agente com o CLI passando um teto orçamentário personalizado (definido via variável de ambiente `AGENT_COST_CAP_USD`):

```bash
AGENT_COST_CAP_USD=0.05 uv run agent run "liste os arquivos do diretório atual"
```

## O que observar

- **Resiliência a instabilidades de rede sem travamento indefinido**: O cliente trata erros transitórios com recuo exponencial injetável (facilitando testes unitários sem sleeps reais via `sleep=waits.append`), assegurando tolerância a picos de carga ou throttles momentâneos da API da OpenRouter.
- **Interrupção prévia ao consumo de recursos**: Ao checar `ledger.total_cost >= cost_cap_usd` antes de executar ferramentas, evitamos que o agente gaste tempo ou execute comandos destrutivos quando o orçamento já tiver estourado.
- **Auto-recuperação de erros sintáticos**: LLMs frequentemente truncam JSONs quando atingem limite de tokens ou alucinam sintaxe inválida. Tratar o erro como retorno de ferramenta com `error: argumentos inválidos` permite que a LLM receba o feedback e reescreva a chamada de ferramenta de forma estruturada.

## Pergunta de previsão

Como podemos introduzir um sistema de verificação pós-execução (por exemplo, executar uma suíte de testes ou checagem de conformidade após o modelo indicar que terminou) para validar se o objetivo foi de fato alcançado antes de marcar o resultado da tarefa como concluído?
