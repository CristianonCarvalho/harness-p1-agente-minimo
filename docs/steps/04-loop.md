# Passo 04: Loop agêntico

## O que mudou

- Criação do módulo `agent/loop.py` implementando o loop agêntico sem framework:
  - `SYSTEM_PROMPT: str`: instrução de sistema que orienta o modelo a trabalhar exclusivamente dentro do diretório de workspace atual e lista as ferramentas disponíveis (`read_file`, `write_file`).
  - `@dataclass RunResult`: estrutura que consolida o resultado de uma execução completa com `final: str` (texto final do assistente), `reason: str` (motivo de término: `no_tool_calls` ou `max_turns`), `turns: int` (número de chamadas ao modelo), `cost_usd: float` (custo total acumulado no ledger) e `messages: list[dict]` (histórico completo da conversa).
  - `run(prompt, ctx, client, ledger, model, max_turns=20) -> RunResult`: orquestrador do ciclo agêntico. Inicializa `messages` com `SYSTEM_PROMPT` no índice 0 e a mensagem do usuário no índice 1. A cada turno, invoca `client.chat(messages, model, tools=TOOL_SCHEMAS)`, registra o evento `llm` no `Ledger` com latência medida, anexa a mensagem do assistente intacta (com `tool_calls`) ao histórico, e verifica as condições de parada.
  - Execução sequencial de ferramentas: quando o assistente emite `tool_calls`, o loop despacha cada uma para `tools.execute`, mede a latência em milissegundos, registra o evento `tool` no `Ledger` (com `turn`, `name`, `args`, `approved`, `result_head`, `result_bytes` e `ms`), e anexa a resposta da ferramenta com `role: "tool"`, `tool_call_id` e o texto do resultado.
  - Condições de parada: encerra com `no_tool_calls` quando o modelo responde apenas com texto (convertendo `content: None` em `""` caso ocorra), ou com `max_turns` quando o limite de chamadas é atingido. Ao terminar, emite o evento `end` no `Ledger`.
- Atualização do CLI em `agent/cli.py`:
  - Adicionado o subcomando `run`: `agent run PROMPT [--model M] [--workspace DIR]`.
  - Padrão para `--workspace`: diretório atual (`cwd`).
  - Ao concluir a execução, imprime a resposta textual final do modelo (se houver) e a linha de sumário no formato `turnos: N · custo: US$ X · fim: <reason>`.
- Criação dos testes unitários offline em `tests/test_loop.py` com `FakeClient` roteirizado:
  - Cobertura de ciclo completo com chamada de ferramenta seguida de resposta final.
  - Cobertura de parada por estouro de `max_turns`.
  - Múltiplas `tool_calls` em uma única resposta do modelo gerando mensagens `role: tool` na ordem esperada com seus respectivos `tool_call_id`.
  - Validação de que `messages[0]` contém o `SYSTEM_PROMPT`.
  - Verificação de eventos `llm`, `tool` e `end` gravados no trace JSONL do `Ledger`.
  - Conversão de `content: None` em string vazia na resposta final.
  - Testes do comando CLI `run` com workspace customizado, workspace padrão (`cwd`) e validação de chave de API ausente.

## Como rodar

Para rodar com a API real (smoke test):

```bash
mkdir /tmp/ws && uv run agent run --workspace /tmp/ws "crie hello.txt com 'oi'"
```

Para rodar os testes automatizados da tarefa:

```bash
uv run pytest tests/test_loop.py
```

## O que observar

- **A alternância de papéis na conversa (`messages`)**: A primeira mensagem é `system`, seguida de `user`. Quando o assistente decide invocar uma ferramenta, ele responde com `tool_calls` (muitas vezes com `content: None`). O harness executa a ferramenta e anexa a resposta com `role: tool` referenciando exatamente o `tool_call_id`. Na rodada seguinte, o assistente recebe todo o contexto acumulado e decide se precisa chamar outra ferramenta ou responder textualmente ao usuário.
- **Múltiplas chamadas simultâneas**: O modelo pode emitir mais de uma ferramenta em um único turno (`tool_calls` com múltiplos itens). O harness executa todas na sequência e adiciona as mensagens de retorno na mesma ordem antes de fazer a próxima chamada ao LLM.
- **Rastreabilidade no Ledger**: O trace JSONL reflete todo o ciclo de vida da execução: cada turno de LLM gera um evento `llm`, cada execução de ferramenta gera um evento `tool` com tempo de execução e tamanho do resultado, e a finalização é selada com o evento `end` indicando o motivo e custo consolidado.

## Pergunta de previsão

No próximo passo (Passo 05: Ferramenta `run_command` com guardas), adicionaremos ao harness a capacidade de executar comandos arbitrários no shell do sistema operacional dentro do workspace. Se o modelo tentar rodar um comando que use encadeamento como `cd / && ls`, a guarda de diretório `cwd=workspace` impedirá que o comando liste o diretório raiz do sistema operacional, ou o comando conseguirá escapar do workspace?
