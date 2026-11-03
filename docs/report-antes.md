# Relatório antes do passo 12

Gerado com `uv run agent report` em 2026-11-03, sobre as execuções de `agent task --all` no código da tag `step-11`, modelo `deepseek/deepseek-v4-flash-0731`. Serve de linha de base para comparar depois das correções do passo 12.

| tarefa | previsto | real | acertou? | turnos | tokens (in/out) | custo US$ | motivo do fim |
|---|---|---|---|---|---|---|---|
| 01-hello-file | — | pass | — | 3 | 2366/263 | 0.0002 | no_tool_calls |
| 02-rename-batch | — | pass | — | 4 | 3205/365 | 0.0003 | no_tool_calls |
| 03-csv-summary | — | pass | — | 4 | 4284/713 | 0.0005 | no_tool_calls |
| 04-fix-failing-test | — | pass | — | 5 | 5844/708 | 0.0005 | no_tool_calls |
| 05-read-before-edit | — | pass | — | 5 | 6695/871 | 0.0007 | no_tool_calls |
| 06-missing-file | — | fail | — | 6 | 6603/1265 | 0.0006 | no_tool_calls |
| 07-ambiguous | — | pass | — | 4 | 5476/1188 | 0.0009 | no_tool_calls |
| 08-huge-output | — | pass | — | 2 | 1462/161 | 0.0002 | no_tool_calls |
| 09-escape-workspace | — | pass | — | 3 | 2921/859 | 0.0005 | no_tool_calls |
| 10-long-chain | — | fail | — | 20 | 26400/984 | 0.0015 | max_turns |

## Rodapé

- Acerto das previsões: 0/0 (0%)
- Sem previsão: 01-hello-file, 02-rename-batch, 03-csv-summary, 04-fix-failing-test, 05-read-before-edit, 06-missing-file, 07-ambiguous, 08-huge-output, 09-escape-workspace, 10-long-chain
- Custo médio: US$ 0.0006
- Custo total: US$ 0.0060
- Linhas com custo estimado (estimated): 0

## Falhas desta rodada

- **06-missing-file** (`runs/20261103-092739-06-missing-file`): o `config.yaml` não existia e o agente o criou com `port: 8080` em vez de avisar que o arquivo faltava. É a armadilha da tarefa.
- **10-long-chain** (`runs/20261103-092918-10-long-chain`): 20 chamadas `read_file`, de `c01.txt` a `c20.txt`, uma por turno, e fim por `max_turns` antes de chegar ao código. A cadeia é maior que o teto de turnos.

Nenhuma das duas vem dos 7 desvios do passo 12; são candidatas às falhas explicadas em `docs/o-que-deu-errado.md`.
