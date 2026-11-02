# Passo 02: Ledger de tokens e custo

## O que mudou

- Implementação do módulo `agent/ledger.py` contendo a função `load_pricing` e a classe `Ledger`.
- `load_pricing(client, cache_path)`: obtém a tabela de preços de modelos consultando `client.models()` e armazenando em cache local (`runs/.models-cache.json`) ou lendo do cache caso já exista, mapeando cada modelo para `(preço_prompt, preço_completion)`.
- `Ledger(path, pricing)`: gerencia a persistência de eventos em formato JSONL, suportando os seguintes registros:
  - `llm`: registra chamada com métricas de tokens (`prompt_tokens`, `completion_tokens`, `cached_tokens`), latência em milissegundos, `finish_reason` e custo em dólares (`cost_usd`). Se `usage.cost` estiver presente, registra como medido (`cost_source: "measured"`); caso ausente, calcula o custo estimado via `pricing()` (`cost_source: "estimated"`), ou `0.0` com `cost_source: "unknown"` se o modelo não constar na tabela de preços. O carregamento de `pricing` é preguiçoso (lazy loading).
  - `tool`: registra a execução de ferramentas com argumentos, status de aprovação (`approved`), primeiros 500 caracteres do resultado (`result_head`), tamanho total em bytes (`result_bytes`) e duração (`ms`).
  - `end`: finaliza o trace registrando o motivo de término (`reason`), total de turnos, custo total acumulado (`cost_usd`) e verificação opcional (`check`).
  - Propriedade `total_cost`: calcula a soma acumulada de custo de todas as chamadas `llm`.
- Atualização de `agent/cli.py`: o comando `agent ask` passa a registrar cada execução em `runs/ask-<AAAAMMDD-HHMMSS>.jsonl` e a imprimir o custo da chamada formatado como `custo: US$ X (measured|estimated)`.
- Criação dos testes unitários offline em `tests/test_ledger.py` cobrindo custo medido, estimado e desconhecido, acúmulo de custo total, carregamento preguiçoso de preços, cache de modelos, eventos de ferramentas e finalização, e integração com o CLI `ask`.

## Como rodar

Faça uma pergunta via CLI com a chave do OpenRouter configurada:
```bash
uv run agent ask "Diga oi"
```

Repita a mesma pergunta logo em seguida para observar o cache de prompt tokens:
```bash
uv run agent ask "Diga oi"
```

Para rodar os testes da tarefa:
```bash
uv run pytest tests/test_ledger.py
```

## O que observar

- A criação do arquivo de trace em `runs/ask-<AAAAMMDD-HHMMSS>.jsonl` a cada chamada do `agent ask`, contendo a linha do evento `llm` com todos os campos estruturados.
- Ao rodar a mesma pergunta duas vezes seguidas no mesmo modelo, observe o campo `cached_tokens` no trace JSONL: provedores que suportam prompt caching retornam tokens em cache com custo reduzido.
- Se a resposta trouxer `usage.cost`, a fonte será `cost_source: "measured"`. Caso contrário, os preços são obtidos via `runs/.models-cache.json` e a fonte será `cost_source: "estimated"`.
- A saída do terminal exibe o custo no formato `custo: US$ X (measured|estimated)` após o detalhamento do `usage`.

## Pergunta de previsão

Como garantir que ferramentas que realizam leitura e escrita de arquivos (`read_file` e `write_file`) não consigam acessar nem modificar arquivos fora do diretório de workspace permitido (por exemplo, bloqueando caminhos com `../` ou caminhos absolutos como `/etc/passwd`)?
