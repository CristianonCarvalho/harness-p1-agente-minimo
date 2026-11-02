# Passo 05: Ferramenta `run_command` com guardas

## O que mudou

- Implementação da ferramenta `run_command` em `agent/tools.py`:
  - Adicionado o schema de `run_command` em `TOOL_SCHEMAS` com especificação do parâmetro obrigatório `command: string`.
  - Implementação da função `terminal_confirm(cmd: str) -> bool`: exibe o prompt `$ <comando>  executar? [y/N] `, aceita respostas afirmativas (`y`, `yes`, maiúsculas/minúsculas) e trata `EOFError` e `KeyboardInterrupt` retornando `False` com segurança.
  - Execução via `subprocess.run` com guardas estritas:
    - Confirmação humana prévia via `ctx.confirm(cmd)`: se recusado, retorna `ToolOutput("error: usuário negou o comando", approved=False)`.
    - Isolamento de variáveis de ambiente com `env={"PATH": os.environ.get("PATH", ""), "HOME": str(ws), "LANG": "C.UTF-8"}`: segredos e credenciais como `OPENROUTER_API_KEY` não vazam para o subprocesso.
    - Timeout com `ctx.timeout_s`, capturando `subprocess.TimeoutExpired` e retornando `error: timeout após {ctx.timeout_s:g}s` com `approved=True`.
    - Truncamento do `stdout` quando exceder `ctx.out_limit` bytes, adicionando `\n[truncado: N bytes no total]`.
    - Formatação padronizada: `exit: N\nstdout:\n...\nstderr:\n...` com exit code, saída padrão e saída de erro.
  - Despacho em `execute("run_command", args, ctx)`.
- Atualização do CLI em `agent/cli.py`:
  - No subcomando `run`, instancia `ToolContext(workspace=workspace, confirm=terminal_confirm)`.
- Criação dos testes unitários offline em `tests/test_tools_shell.py`:
  - Execução com sucesso dentro do workspace (`pwd`).
  - Negação de execução pelo usuário (`approved=False`).
  - Isolamento de variáveis de ambiente (`OPENROUTER_API_KEY` não vaza).
  - Timeout com formatação fracionária e inteira (`0.5s`).
  - Tratamento de `EOFError` e `KeyboardInterrupt` como negação.
  - Aceitação de respostas `y`, `yes`, `Y` e recusa de `n`, string vazia ou outras.
  - Formatação exata do prompt de confirmação.
  - Truncamento de `stdout` longo em `out_limit`.
  - Captura de `stderr` e exit code diferente de zero.
  - Comportamento de comandos que usam `cd /` (demonstrando que `cwd` não é sandbox).
  - Validação do schema no `TOOL_SCHEMAS`.
  - Integração do CLI passando `terminal_confirm`.

## Como rodar

Para rodar os testes unitários offline da ferramenta:

```bash
uv run pytest tests/test_tools_shell.py
```

Para rodar o agente interativo com confirmação no terminal:

```bash
uv run agent run "liste os arquivos do diretório atual"
```

## O que observar

- **`cd / && ls` funciona porque `cwd` não é sandbox**: O parâmetro `cwd=ws` no `subprocess.run` apenas define o diretório de trabalho inicial do processo do shell. Comandos encadeados com `cd` (como `cd / && ls`) alteram o diretório de trabalho do subshell e conseguem listar ou inspecionar diretórios fora do workspace. Portanto, `cwd` por si só não funciona como uma sandbox de isolamento (diferente de contêineres ou chroot). É por essa razão que a guarda de confirmação humana interativa (`confirm`) e a limpeza de variáveis de ambiente (`env`) são fundamentais.
- **Isolamento de credenciais**: Como o subprocesso recebe um dicionário de ambiente limpo contendo apenas `PATH`, `HOME` e `LANG`, variáveis sensíveis do processo pai (como chaves de API, senhas ou tokens) não ficam acessíveis a scripts ou binários executados pelo comando.
- **Tratamento gracioso de limites**: Comandos demorados sofrem timeout de acordo com `ctx.timeout_s` sem travar o harness, e comandos que geram volumes massivos de saída têm seu `stdout` truncado de forma transparente para não esgotar o contexto da LLM.

## Pergunta de previsão

Como podemos garantir que o agente não continue executando turnos infinitamente ou consumindo orçamento além do pretendido caso o modelo entre em loop chamando comandos sucessivos, integrando um teto orçamentário (`AGENT_COST_CAP_USD`) diretamente nas verificações de parada do loop?
