# Passo 01: Cliente HTTP do OpenRouter

## O que mudou

- Criação da exceção `ClientError` em `agent/client.py` para encapsular falhas de requisição HTTP e erros retornados pela API.
- Implementação de `OpenRouterClient` em `agent/client.py` com suporte a autenticação via Bearer Token, configuração de `base_url`, `timeout_s` e injeção de `transport` (permitindo testes 100% offline via `httpx.MockTransport`).
- Adição do método `chat(messages, model, tools=None)` que envia requisições `POST /chat/completions` sempre incluindo `"usage": {"include": true}` no corpo, repassando `tools` quando fornecido e tratando erros de payload (mesmo em respostas HTTP 200).
- Adição do método `models()` que envia `GET /models` e retorna a lista de modelos (`json["data"]`).
- Implementação da interface de linha de comando em `agent/cli.py` com o subcomando `ask PROMPT [--model M]`, que valida a existência de `OPENROUTER_API_KEY`, executa a chamada via `OpenRouterClient` e imprime a resposta do modelo seguida pelo `usage` formatado em JSON.
- Criação dos testes unitários offline em `tests/test_client.py` cobrindo autenticação, estrutura do payload, envio opcional de ferramentas, listagem de modelos, tratamento de erros HTTP e de payload, e execução do comando `agent ask`.

## Como rodar

Execute o subcomando `ask` com a variável configurada no `.env`:
```bash
uv run agent ask "Diga oi"
```

Para rodar os testes da tarefa:
```bash
uv run pytest tests/test_client.py
```

## O que observar

- A requisição para `/chat/completions` sempre inclui `"usage": {"include": true}`, garantindo que o OpenRouter retorne métricas de consumo de tokens (`prompt_tokens`, `completion_tokens`) e custo estimado (`cost`).
- Se a variável `OPENROUTER_API_KEY` estiver vazia ou não configurada no `.env`, o comando `agent ask` encerra imediatamente com código de saída 2 e exibe a mensagem de orientação.
- Se o OpenRouter responder com HTTP 200 contendo um objeto `error` e sem `choices`, o cliente levanta `ClientError` com a mensagem apropriada em vez de falhar silenciosamente ou com `KeyError`.

## Pergunta de previsão

Quando o OpenRouter não incluir o campo `cost` no objeto `usage`, como podemos calcular o custo em dólares de cada chamada?
