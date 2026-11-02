# Agente Mínimo

Agente de tool use em Python sem framework (loop próprio, ferramentas `read_file`, `write_file` e `run_command`, e ledger de tokens e custo por chamada), construído para demonstrar e inspecionar o funcionamento interno de um harness agêntico contra a API do OpenRouter sem abstrações intermediárias.

## Como rodar

Copie o arquivo de exemplo de ambiente e configure sua chave de API:
```bash
cp .env.example .env
```

Instale as dependências com o `uv`:
```bash
uv sync
```

Execute os testes:
```bash
uv run pytest
```
