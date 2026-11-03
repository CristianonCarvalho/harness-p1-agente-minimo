# Passo 12: Correções da revisão

## O que mudou

- **`SYSTEM_PROMPT` com todas as ferramentas**: o prompt do sistema listava apenas `read_file` e `write_file`, omitindo `run_command` presente em `TOOL_SCHEMAS`; corrigido adicionando a descrição de `run_command` ao `SYSTEM_PROMPT`.
- **Truncamento de `stderr`**: `_run_command` limitava apenas o tamanho de `stdout` em `ctx.out_limit`, enviando `stderr` integral ao modelo; corrigido extraindo a função auxiliar `_cut(text, limit)` e aplicando o limite a ambos.
- **Tratamento de `choices` vazio**: resposta da API com `"choices": []` passava pela checagem de chave e causava `IndexError` no acesso ao primeiro elemento; corrigido validando lista não-vazia e disparando `ClientError("Response missing or empty 'choices'")`.
- **Isolamento de testes de `agent ask`**: `test_cli_ask_success` e `test_cli_ask_with_model_flag` chamavam `main` sem `runs_dir`, gravando traces reais no diretório `runs/` do repositório; corrigido passando `runs_dir=tmp_path` e assinalando o arquivo gerado.
- **Saída informativa e custo formatado em `agent task`**: o comando imprimia custos em ponto flutuante bruto sem indicar o caminho do trace; corrigido formatando o custo com 4 casas decimais (`.4f`) e exibindo o `run_dir` ao final da linha.
- **Remoção de checagem tautológica de `--auto-approve` no `task`**: o comando `task` executava `check_auto_approve` em um caminho sintético dentro de `runs_path`, verificação redundante visto que `run_task` sempre instancia o workspace em `runs_root/<id>/ws`; corrigido removendo a chamada desnecessária.
- **Fim da cópia de arquivos para o diretório de trabalho no `run`**: `agent run` continha lógica para copiar arquivos de `ws/` para o diretório atual quando `runs_dir` era o `cwd`; corrigido removendo o bloco e assegurando que arquivos gerados permaneçam confinados em `ws/`.

## Como rodar

Executar os testes automatizados da suíte:

```bash
uv run pytest
```

Executar a bateria completa de tarefas com aprovação automática e gerar o relatório consolidado:

```bash
uv run agent task --all --auto-approve
uv run agent report
```

## O que observar

Comparar o novo `runs/report.md` gerado com o relatório de referência em `docs/report-antes.md`. Com a inclusão explícita de `run_command` nas instruções do `SYSTEM_PROMPT`, o comportamento do modelo pode variar ao resolver as tarefas — em especial tarefas como 04 (`fix-failing-test`), 08 (`huge-output`) e 09 (`escape-workspace`), impactando a quantidade de turnos e os custos registrados.

## Pergunta de previsão

Com `run_command` no prompt, a tarefa 10 continua falhando por `max_turns`? Por quê?
