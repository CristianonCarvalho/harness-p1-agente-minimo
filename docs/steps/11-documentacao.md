# Passo 11: Documentação final

## O que mudou

- **README consolidado e detalhado (`README.md`)**:
  - Apresentação completa dos objetivos do projeto e link para a especificação técnica e roadmap da Fase 1 (`docs/superpowers/specs/2026-11-02-p1-agente-minimo-design.md`).
  - Guia de instalação (`uv sync`) e configuração do ambiente via `.env` (`OPENROUTER_API_KEY`, `AGENT_MODEL`, `AGENT_MAX_TURNS`, `AGENT_COST_CAP_USD`).
  - Documentação de todos os subcomandos da CLI (`ask`, `run`, `task`, `report`) acompanhados de exemplos práticos de invocação.
  - Tabela completa de arquitetura dos módulos (`config`, `client`, `tools`, `ledger`, `loop`, `cli`) e suas interfaces e dependências.
  - Tabela com todas as decisões de projeto fundamentais da especificação e seus respectivos motivos.
  - Seção detalhada sobre os limites conhecidos do harness: `cwd` não é sandbox (`cd /` funciona), os riscos associados ao `--auto-approve`, o uso de `shell=True`, possíveis divergências no custo estimado em relação ao faturado e a variabilidade probabilística entre execuções.
  - Guia metodológico de estudo detalhando o fluxo de inspeção com `git diff step-NN-1 step-NN`, leitura das notas em `docs/steps/`, calibração de hipóteses com `prediction.md` e preenchimento da análise de falhas.
- **Roteiro de análise de falhas e custos (`docs/o-que-deu-errado.md`)**:
  - Template estruturado (sem conteúdo inventado) contendo 5 seções de falhas com os campos: tarefa, trace (`runs/<id>`), o que aconteceu, por que, previ? (s/n) e conserto possível.
  - Seção de consolidação do custo por tarefa para apuração do custo total e médio da suíte.
- Conclusão do ciclo de implementação do P1 sem alterações nos módulos de código em `agent/` ou nos testes unitários em `tests/`.

## Como rodar

Validar a documentação e os links:

```bash
# Inspecionar o README principal:
cat README.md

# Inspecionar o roteiro de falhas:
cat docs/o-que-deu-errado.md
```

Executar os testes offline relevantes do projeto:

```bash
uv run pytest tests/test_report.py
```

Fluxo completo de estudo do projeto com `git diff`:

```bash
# Comparar a evolução entre dois passos quaisquer (ex.: passo 03 e passo 04):
git diff step-03 step-04
```

## O que observar

- **Transparência de Limitações e Riscos**:
  Diferente de frameworks que tentam esconder a complexidade operacional, o README explicita que o harness não fornece sandbox no nível de sistema operacional e que `shell=True` confere amplo poder de execução ao modelo. A segurança em agentes de software requer entender essas fronteiras com precisão.
- **Exercício Metacognitivo de Análise de Falhas**:
  O documento `docs/o-que-deu-errado.md` orienta o autor a não descartar falhas como "erros aleatórios", mas a investigar o trace JSONL em `runs/<id>/trace.jsonl` e o histórico de mensagens em `messages.json` para descobrir a causa-raiz (instrução ambígua, corte de contexto, erro de ferramenta não recuperado, etc.).
- **Independência de Frameworks**:
  A tabela de arquitetura demonstra que um agente autônomo completo com suporte a chamadas de ferramentas, controle de custo e execução de tarefas pode ser implementado de forma enxuta com poucas centenas de linhas de Python padrão e `httpx`.

## Pergunta de previsão

Com a conclusão do P1 (Agente Mínimo), na transição para a Fase 2 do roadmap (memória entre execuções, compactação de contexto e arquiteturas multiagente/subagentes): como os módulos `loop` e `ledger` podem ser estendidos para registrar mensagens e custos de múltiplos agentes trabalhando cooperativamente sem perder a granularidade por chamada?
