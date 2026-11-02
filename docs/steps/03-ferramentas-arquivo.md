# Passo 03: Ferramentas de arquivo

## O que mudou

- Criação do módulo `agent/tools.py` com os contratos das ferramentas de arquivo e do harness:
  - `@dataclass ToolContext`: encapsula o contexto de execução de ferramentas, incluindo `workspace` (convertido para `Path`), função de confirmação `confirm`, `timeout_s` (padrão 30.0s), `read_limit` (padrão 20.000 bytes) e `out_limit` (padrão 10.000 bytes).
  - `@dataclass ToolOutput`: estrutura padronizada para o retorno das ferramentas com `text: str` e status de aprovação opcional `approved: bool | None = None`.
  - `TOOL_SCHEMAS`: lista de especificações no formato JSON Schema / OpenAI function calling contendo as definições de `read_file` (com `path` obrigatório) e `write_file` (com `path` e `content` obrigatórios).
  - `resolve_inside(ctx, path)`: função de guarda que resolve caminhos canônicos com `Path.resolve()` e verifica se o destino está contido em `ctx.workspace.resolve()` via `is_relative_to`. Lança `ValueError("caminho fora do workspace")` para tentativas de path traversal (`../`), caminhos absolutos fora do workspace ou symlinks apontando para fora.
  - `execute(name, args, ctx)`: despachante de ferramentas com tratamento resiliente de erros. Captura qualquer exceção e devolve `ToolOutput(f"error: {type(e).__name__}: {e}")`, exceto para `ValueError` da guarda de caminho, que devolve exatamente `ToolOutput("error: caminho fora do workspace")`. Tratamento específico para ferramentas inexistentes (`error: ferramenta desconhecida: <nome>`).
  - Implementação de `read_file`: valida se o arquivo existe (retornando `error: arquivo não encontrado: <path>`), lê bytes em modo binário e decodifica com tolerância (`errors="replace"` para evitar quebras com arquivos binários), truncando em `ctx.read_limit` com o sufixo `[truncado: N bytes no total]` caso o arquivo exceda o limite.
  - Implementação de `write_file`: cria diretórios intermediários automaticamente (`target.parent.mkdir(parents=True, exist_ok=True)`), grava o conteúdo em UTF-8 e retorna `ok: N bytes escritos em <path>`.
- Criação dos testes unitários offline em `tests/test_tools_files.py` cobrindo escrita e leitura, bloqueio de paths externos e symlinks externos, truncamento de arquivos longos, arquivos binários, arquivos inexistentes, ferramentas desconhecidas e validação dos schemas.

## Como rodar

Como as ferramentas são consumidas pelo loop agêntico (a ser implementado no passo 04), a verificação direta é feita por meio dos testes unitários offline:

```bash
uv run pytest tests/test_tools_files.py
```

## O que observar

- **O JSON Schema das ferramentas (`TOOL_SCHEMAS`)**: O modelo LLM não vê o código Python das ferramentas nem sabe como elas são executadas internamente. Ele recebe unicamente os campos `name`, `description` e `parameters` (especificando propriedades, tipos e campos `required`). Uma descrição clara e precisa é fundamental para que o modelo decida quando e como chamar cada ferramenta.
- **A guarda de caminho e symlinks**: A utilização de `Path.resolve()` em conjunto com `is_relative_to()` impede que o modelo (ou um comando malicioso) escape do diretório de trabalho, mesmo usando symlinks apontando para fora do workspace ou truques como `../` e caminhos absolutos como `/etc/passwd`.
- **Tolerância a binários e limite de leitura**: Arquivos binários são decodificados usando `errors="replace"`, garantindo que o agente não sofra um crash de `UnicodeDecodeError`. Além disso, o corte de leitura em 20 KB com indicação do total de bytes impede que o modelo estoure seu limite de contexto ou gaste tokens desnecessariamente lendo arquivos gigantes.

## Pergunta de previsão

No loop agêntico (Passo 04), quando o modelo decide chamar uma ferramenta através do campo `tool_calls` na sua resposta, de que forma o resultado retornado pela execução dessa ferramenta deve ser devolvido ao modelo na conversa do chat?
