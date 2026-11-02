# Passo 00: Base do projeto e config

## O que mudou

- Estrutura base do projeto configurada com `pyproject.toml` utilizando Python `>=3.13`, runtime com `httpx`, dependência de desenvolvimento `pytest` e build via `hatchling` com pacote `agent`.
- Geração do `uv.lock` com `uv sync`.
- Criação do `.gitignore` para ignorar `.env`, `runs/`, `.venv/`, `__pycache__/` e `.pytest_cache/`.
- Criação do `.env.example` com as 4 variáveis padrão: `OPENROUTER_API_KEY`, `AGENT_MODEL`, `AGENT_MAX_TURNS` e `AGENT_COST_CAP_USD`.
- Implementação do módulo `agent/config.py` contendo a dataclass frozen `Config` e a função `load_config(env_path, environ)` com parser próprio sem dependências externas (ignora linhas vazias e comentários `#`, remove prefixo `export `, separa no primeiro `=` e remove aspas das pontas).
- Atualização do `AGENTS.md` com as diretrizes de contexto do projeto.
- Testes unitários 100% offline em `tests/test_config.py` cobrindo valores padrão, parsing do `.env` e prioridade do ambiente sobre o `.env`.

## Como rodar

Sincronize o ambiente e execute os testes da tarefa:
```bash
uv sync
uv run pytest tests/test_config.py
```

## O que observar

- A dataclass `Config` é congelada (`frozen=True`), impedindo alterações acidentais em tempo de execução.
- O parser de `.env` suporta sintaxe comum de shell (`export VAR="val"`) e variáveis com aspas simples ou duplas.
- Variáveis no ambiente (`environ`) têm precedência sobre os valores declarados no arquivo `.env`.
- Se `OPENROUTER_API_KEY` não for informada, o valor padrão é `""`, postergando a validação para os módulos consumidores.

## Pergunta de previsão

Que campos você espera no JSON de resposta do OpenRouter além do texto?
