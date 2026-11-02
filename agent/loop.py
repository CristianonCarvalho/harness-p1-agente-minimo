from dataclasses import dataclass
import json
import time
from typing import Any

from agent.client import ClientError
from agent.ledger import Ledger
from agent.tools import TOOL_SCHEMAS, ToolContext, ToolOutput, execute

SYSTEM_PROMPT = """Você é um assistente autônomo que executa tarefas trabalhando exclusivamente dentro do diretório atual (workspace).
Você tem acesso às seguintes ferramentas:
- read_file: lê o conteúdo de um arquivo dentro do workspace.
- write_file: escreve conteúdo em um arquivo dentro do workspace.

Use as ferramentas necessárias para inspecionar, criar ou modificar arquivos e conclua a tarefa respondendo de forma clara e objetiva."""


@dataclass
class RunResult:
    final: str
    reason: str
    turns: int
    cost_usd: float
    messages: list[dict]


def run(
    prompt: str,
    ctx: ToolContext,
    client: Any,
    ledger: Ledger,
    model: str,
    max_turns: int = 20,
    cost_cap_usd: float = 0.10,
) -> RunResult:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    turns = 0
    reason = "max_turns"
    final = ""

    while turns < max_turns:
        turns += 1

        start_time = time.perf_counter()
        try:
            resp = client.chat(messages, model, tools=TOOL_SCHEMAS)
        except ClientError:
            reason = "error"
            final = ""
            break
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        ledger.llm(turn=turns, model=model, response=resp, latency_ms=latency_ms)

        choice = resp["choices"][0]
        assistant_msg = choice["message"]
        messages.append(assistant_msg)

        if ledger.total_cost >= cost_cap_usd:
            reason = "cost_cap"
            content = assistant_msg.get("content")
            final = "" if content is None else str(content)
            break

        tool_calls = assistant_msg.get("tool_calls")
        if not tool_calls:
            reason = "no_tool_calls"
            content = assistant_msg.get("content")
            final = "" if content is None else str(content)
            break

        for tc in tool_calls:
            call_id = tc.get("id", "")
            func = tc.get("function") or {}
            name = func.get("name", "")
            raw_args = func.get("arguments", "{}")

            invalid_args_err: str | None = None
            if isinstance(raw_args, str):
                try:
                    parsed = json.loads(raw_args)
                    if isinstance(parsed, dict):
                        args = parsed
                    else:
                        args = {}
                        invalid_args_err = f"error: argumentos inválidos: esperado objeto JSON, obteve {type(parsed).__name__}"
                except Exception as exc:
                    args = {}
                    invalid_args_err = f"error: argumentos inválidos: {exc}"
            elif isinstance(raw_args, dict):
                args = raw_args
            else:
                args = {}
                invalid_args_err = f"error: argumentos inválidos: tipo inesperado {type(raw_args).__name__}"

            start_tool = time.perf_counter()
            if invalid_args_err is not None:
                out = ToolOutput(text=invalid_args_err, approved=None)
            else:
                out = execute(name, args, ctx)
            tool_ms = int((time.perf_counter() - start_tool) * 1000)

            ledger.tool(
                turn=turns,
                name=name,
                args=args,
                approved=out.approved,
                result=out.text,
                ms=tool_ms,
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": out.text,
                }
            )

        if turns >= max_turns:
            reason = "max_turns"
            content = assistant_msg.get("content")
            final = "" if content is None else str(content)
            break

    ledger.end(reason=reason, turns=turns)
    return RunResult(
        final=final,
        reason=reason,
        turns=turns,
        cost_usd=ledger.total_cost,
        messages=messages,
    )
