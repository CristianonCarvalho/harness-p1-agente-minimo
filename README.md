# Agente Mínimo

Agente de *tool use* em Python sem frameworks (loop próprio, ferramentas `read_file`, `write_file` e `run_command`, e ledger de tokens e custo por chamada), construído para demonstrar e inspecionar o funcionamento interno de um harness agêntico contra a API do OpenRouter sem abstrações intermediárias.

Este repositório corresponde ao **Projeto 1 (P1)** — Fase 1 do roadmap *"Engenharia de Software com Agentes de IA"* (semanas 3–10).

- **Especificação técnica e design do projeto:** [docs/superpowers/specs/2026-11-02-p1-agente-minimo-design.md](docs/superpowers/specs/2026-11-02-p1-agente-minimo-design.md)
- **Roteiro de análise de falhas:** [docs/o-que-deu-errado.md](docs/o-que-deu-errado.md)
- **Notas de estudo passo a passo:** pasta [docs/steps/](docs/steps/)

### Critérios de conclusão da Fase 1

1. Explicar 5 falhas reais do agente, com o trace detalhado de cada uma (ver [docs/o-que-deu-errado.md](docs/o-que-deu-errado.md)).
2. Conhecer e auditar o custo por tarefa.
3. Prever, antes da execução, onde o agente irá falhar em pelo menos metade das tarefas.

---

## Instalação e Configuração

### Pré-requisitos

- Python `>= 3.13`
- [`uv`](https://docs.astral.sh/uv/) para gerenciamento de ambiente e dependências

### 1. Clonar e sincronizar dependências

```bash
uv sync
```

O projeto utiliza runtime estritamente minimalista com `httpx` e ferramentas de desenvolvimento com `pytest`. Não são utilizados SDKs de fornecedores (`openai`, `anthropic`), `python-dotenv` ou frameworks de agentes (`langchain`, `crewai`, etc.).

### 2. Configurar variáveis de ambiente

Copie o arquivo de exemplo `.env.example`:

```bash
cp .env.example .env
```

Edite o arquivo `.env` para adicionar sua chave de API do OpenRouter:

```dotenv
OPENROUTER_API_KEY=sk-or-v1-sua-chave-aqui
```

> **Recomendação:** Utilize uma chave dedicada do OpenRouter separada de ambientes de produção, preferencialmente configurada com limite de gastos/crédito.

As variáveis configuráveis suportadas são:

| Variável | Padrão | Descrição |
|---|---|---|
| `OPENROUTER_API_KEY` | `""` | Chave de autenticação na API do OpenRouter |
| `AGENT_MODEL` | `deepseek/deepseek-v4-flash-0731` | Modelo LLM padrão para geração e chamadas |
| `AGENT_MAX_TURNS` | `20` | Teto máximo de turnos (chamadas à LLM) por execução |
| `AGENT_COST_CAP_USD` | `0.10` | Teto financeiro máximo em dólares por execução |

---

## Comandos

O pacote disponibiliza o ponto de entrada `agent` via `uv run agent <comando>`:

### 1. `agent ask`
Envia um prompt simples para o modelo (turno único, sem ferramentas). Exibe no terminal o texto da resposta, o bloco JSON completo de `usage` retornado pela API e o custo total calculado pelo ledger.

```bash
uv run agent ask "Explique em uma frase o que é um token em LLMs."
```

### 2. `agent run`
Inicia o loop agêntico completo com as 3 ferramentas (`read_file`, `write_file`, `run_command`). Cria um diretório de execução isolado em `runs/<timestamp>-run/ws/` (a menos que `--workspace` seja informado) e solicita confirmação interativa antes de executar comandos no shell.

```bash
uv run agent run "Crie um arquivo notas.txt com 3 tópicos sobre testes de software."
```

Opções adicionais:
- `--workspace, -w <caminho>`: define um diretório de trabalho específico.
- `--model, -m <modelo>`: substitui temporariamente o modelo padrão.
- `--auto-approve`: dispensa confirmação interativa no shell (permitido apenas para workspaces situados dentro de `runs/`).

### 3. `agent task`
Executa uma tarefa automatizada da pasta `tasks/`. O harness prepara um workspace descartável em `runs/<timestamp>-<tarefa>/ws/`, executa o loop do agente até a conclusão e valida o resultado executando o verificador `check.py` da tarefa.

```bash
# Executa uma tarefa específica por número ou prefixo:
uv run agent task 01

# Executa todas as tarefas disponíveis em lote com aprovação automática de comandos:
uv run agent task --all --auto-approve
```

### 4. `agent report`
Lê a última execução de cada tarefa presente em `runs/`, compara o resultado real com a previsão preenchida em `prediction.md`, calcula a taxa de acerto das previsões, totaliza os custos da suíte e gera uma tabela Markdown no terminal e no arquivo `runs/report.md`.

```bash
uv run agent report
```

---

## Arquitetura

O agente é estruturado em módulos desacoplados, pequenos e diretamente testáveis:

| Módulo | Faz | Interface | Depende de |
|---|---|---|---|
| `config` | Carrega `.env` (formato `CHAVE=valor`, sem aspas especiais) sem sobrescrever o ambiente | `load_config() -> Config` com `api_key`, `model`, `max_turns`, `cost_cap_usd` | — |
| `client` | Uma chamada ao OpenRouter | `chat(messages, tools, model) -> dict` (o JSON da resposta) | `httpx`, `config` |
| `tools` | Executa uma ferramenta dentro de um workspace | `TOOL_SCHEMAS: list[dict]`; `execute(name, args, ctx) -> str` | — |
| `ledger` | Registra eventos e soma o custo | `Ledger(path)`; `.llm(...)`, `.tool(...)`, `.end(...)`; `.total_cost` | `client` (só para a tabela de preços do fallback) |
| `loop` | Orquestra modelo e ferramentas até uma condição de parada | `run(prompt, ctx, client, ledger) -> RunResult` | `tools`, `ledger`, um objeto com `.chat()` |
| `cli` | Prepara o workspace e chama o loop; roda o check; gera o relatório | comandos `agent ...` | todos |

### Estrutura de Diretórios

```
projeto01/
  agent/        # Módulos do harness, cliente HTTP, ferramentas e CLI
  tasks/        # Tarefas avaliativas (01 a 10) com workspace, check.py e prediction.md
  runs/         # Traces JSONL, mensagens e workspaces de execução (ignorado no git)
  tests/        # Testes automatizados 100% offline (pytest)
  docs/steps/   # Notas explicativas de cada etapa de implementação
```

---

## Decisões de Projeto

| Tema | Decisão | Motivo |
|---|---|---|
| Provedor | OpenRouter | Uma chave para vários modelos; facilita comparar falhas entre modelos |
| Cliente | HTTP puro com `httpx` | Mostra o JSON exato de ida e volta; é o "sem framework" levado a sério |
| Modelo padrão | `deepseek/deepseek-v4-flash-0731` | Barato; trocável por `AGENT_MODEL` ou `--model` |
| Ferramentas | `read_file`, `write_file`, `run_command` | O shell deixa o agente realista e expõe os limites das guardas |
| Sandbox | Sem container; guardas no harness (confirmação, env limpo, timeout, corte de saída, `cwd` fixo) | Suficiente para estudo local; o container fica para a Fase 4 |
| Estrutura | Pacote com módulos pequenos, crescendo um passo por commit | O `git diff` entre tags isola cada conceito; o P2 e o P3 reaproveitam `client` e `ledger` |
| Ambiente | Python 3.13, `uv`, dependências `httpx` e `pytest` (dev) | Mínimo necessário |
| Segredos | `.env` local, no `.gitignore` desde o passo 00, lido por um parser próprio | O repositório é público |

---

## Limites Conhecidos

Este harness foi desenhado para estudo e inspeção de protocolos agênticos. Como projeto didático, possui limites intencionais que expõem os desafios de segurança e confiabilidade em sistemas autônomos:

1. **`cwd` não é sandbox (`cd /` funciona):**
   O `cwd` inicial do processo executado por `run_command` aponta para o diretório de workspace isolado (`runs/<id>/ws`). Contudo, o sistema operacional não impõe isolamento de filesystem no nível de kernel (como containers Linux, `chroot` ou sandboxes de SO). Comandos passados para o shell podem utilizar `cd /` ou caminhos absolutos (`cat /etc/passwd`, leitura de diretórios de usuário), conseguindo ler ou modificar arquivos fora do workspace.
2. **`--auto-approve` remove o único controle real:**
   A intervenção humana interativa (confirmação manual antes de cada comando shell) é a defesa primária contra danos acidentais ou comandos destrutivos. A flag `--auto-approve` desativa a confirmação interativa. Embora exista uma trava que restringe seu uso a diretórios dentro de `runs/`, qualquer comando gerado pelo modelo que seja executado nessa pasta ainda pode emitir chamadas de rede ou interações com o sistema hospedeiro.
3. **`shell=True`:**
   A execução de comandos via shell padrão interpreta metacaracteres, expansão de variáveis, encadeamento de comandos (`&&`, `;`, `|`), pipes e redirecionamentos. Isso possibilita injeções arbitrárias caso comandos venham de entradas não sanitizadas ou o modelo gere sequências maliciosas ou imprevistas.
4. **Custo estimado pode divergir:**
   Quando a API do OpenRouter não inclui o campo `usage.cost` na resposta, o harness estima o custo com base em uma tabela de preços mantida em cache (`runs/.models-cache.json`). Se os preços forem atualizados pelo provedor ou a tarifação real diferir da tabela, o custo calculado apresentará discrepâncias em relação à fatura real cobrada.
5. **Variação entre execuções:**
   Grandes modelos de linguagem são probabilísticos. O mesmo prompt executado em momentos distintos pode levar a caminhos de raciocínio diferentes, chamadas de ferramentas em ordens variadas ou mesmo falhas intermitentes sob condições idênticas.

---

## Como Estudar

O projeto foi construído incrementalmente para permitir o estudo detalhado de cada componente isolado:

1. **Inspecione o delta de código entre passos com `git diff`:**
   Cada etapa possui uma tag Git correspondente (`step-00` até `step-11`). Você pode visualizar exatamente o que mudou de um conceito para o outro:
   ```bash
   git diff step-03 step-04
   ```
2. **Leia as notas de estudo em `docs/steps/`:**
   Cada passo possui uma nota em `docs/steps/NN-nome.md` dividida em quatro partes essenciais:
   - *O que mudou:* os arquivos implementados e a teoria por trás da alteração;
   - *Como rodar:* comandos para testar e validar o comportamento;
   - *O que observar:* detalhes nas mensagens JSON, nos traces do ledger e no fluxo de controle;
   - *Pergunta de previsão:* um exercício de reflexão para tentar prever o próximo desafio antes de inspecionar a solução.
3. **Pratique a calibração de previsões:**
   Antes de rodar qualquer tarefa, preencha o arquivo `prediction.md` da tarefa com sua hipótese (`pass` ou `fail`), o motivo esperado e o custo estimado. Depois de rodar com `agent task`, gere o relatório com `agent report` para confrontar sua previsão com a realidade.
4. **Documente falhas reais:**
   Utilize o roteiro em `docs/o-que-deu-errado.md` para registrar e dissecar 5 falhas reais ocorridas durante seus testes práticos.
