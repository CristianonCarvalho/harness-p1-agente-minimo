import json
from pathlib import Path
import pytest

from agent.cli import main
from agent.config import Config
from agent.ledger import Ledger
from agent.loop import SYSTEM_PROMPT, RunResult, run
from agent.tools import ToolContext


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, model, tools=None):
        self.calls.append([dict(m) for m in messages])
        return self.replies.pop(0)


def msg(content=None, tool_calls=None):
    m = {"role": "assistant", "content": content}
    if tool_calls:
        m["tool_calls"] = tool_calls
    return {
        "choices": [{"message": m, "finish_reason": "tool_calls" if tool_calls else "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.001},
    }


def call(id, name, args):
    return {
        "id": id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def test_tool_then_answer(tmp_path: Path):
    c = FakeClient([msg(tool_calls=[call("c1", "write_file", {"path": "h.txt", "content": "oi"})]), msg("feito")])
    r = run("crie", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m")
    assert (r.final, r.reason, r.turns) == ("feito", "no_tool_calls", 2)
    assert (tmp_path / "h.txt").read_text() == "oi"
    tool_msg = c.calls[1][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c1"


def test_max_turns(tmp_path: Path):
    c = FakeClient([msg(tool_calls=[call(f"c{i}", "read_file", {"path": "x"})]) for i in range(5)])
    r = run("x", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m", max_turns=3)
    assert (r.reason, r.turns) == ("max_turns", 3)


def test_multiple_tool_calls_in_one_response(tmp_path: Path):
    c = FakeClient([
        msg(tool_calls=[
            call("c1", "write_file", {"path": "a.txt", "content": "ola"}),
            call("c2", "write_file", {"path": "b.txt", "content": "mundo"}),
        ]),
        msg("feito tudo"),
    ])
    r = run("crie dois arquivos", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m")
    assert (r.final, r.reason, r.turns) == ("feito tudo", "no_tool_calls", 2)
    assert (tmp_path / "a.txt").read_text() == "ola"
    assert (tmp_path / "b.txt").read_text() == "mundo"

    call_msgs = c.calls[1]
    assert call_msgs[-2]["role"] == "tool" and call_msgs[-2]["tool_call_id"] == "c1"
    assert call_msgs[-1]["role"] == "tool" and call_msgs[-1]["tool_call_id"] == "c2"


def test_messages_starts_with_system_prompt(tmp_path: Path):
    c = FakeClient([msg("resposta direta")])
    r = run("ola", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m")
    assert r.messages[0]["role"] == "system"
    assert r.messages[0]["content"] == SYSTEM_PROMPT
    assert c.calls[0][0]["role"] == "system"
    assert c.calls[0][0]["content"] == SYSTEM_PROMPT
    assert r.messages[1]["role"] == "user"
    assert r.messages[1]["content"] == "ola"


def test_trace_has_llm_tool_and_end_events(tmp_path: Path):
    ledger_path = tmp_path / "trace.jsonl"
    c = FakeClient([msg(tool_calls=[call("c1", "write_file", {"path": "out.txt", "content": "ok"})]), msg("fim")])
    r = run("escreva", ToolContext(tmp_path), c, Ledger(ledger_path), "m")
    assert r.reason == "no_tool_calls"
    assert r.cost_usd == pytest.approx(0.002)

    lines = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    event_types = [entry["t"] for entry in lines]
    assert event_types == ["llm", "tool", "llm", "end"]
    assert lines[1]["name"] == "write_file"
    assert lines[3]["reason"] == "no_tool_calls"
    assert lines[3]["turns"] == 2
    assert lines[3]["cost_usd"] == pytest.approx(0.002)


def test_content_none_becomes_empty_string(tmp_path: Path):
    c = FakeClient([msg(content=None)])
    r = run("vazio", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m")
    assert r.final == ""
    assert r.reason == "no_tool_calls"


def test_cli_run_command(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model", max_turns=10))
    c = FakeClient([
        msg(tool_calls=[call("c1", "write_file", {"path": "hello.txt", "content": "oi"})]),
        msg("arquivo criado"),
    ])
    code = main(["run", "crie hello.txt com 'oi'", "--workspace", str(tmp_path)], client=c, runs_dir=tmp_path)
    assert code == 0
    captured = capsys.readouterr()
    assert "arquivo criado" in captured.out
    assert "turnos: 2 · custo: US$ 0.002 · fim: no_tool_calls" in captured.out
    assert (tmp_path / "hello.txt").read_text() == "oi"


def test_cli_run_missing_api_key_exits_2(monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key=""))
    code = main(["run", "prompt"])
    assert code == 2
    captured = capsys.readouterr()
    assert "defina OPENROUTER_API_KEY no .env" in captured.out


def test_cli_run_default_workspace(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model", max_turns=10))
    monkeypatch.chdir(tmp_path)
    c = FakeClient([
        msg(tool_calls=[call("c1", "write_file", {"path": "default_ws.txt", "content": "teste"})]),
        msg("criado no cwd"),
    ])
    code = main(["run", "crie default_ws.txt"], client=c, runs_dir=tmp_path)
    assert code == 0
    assert (tmp_path / "default_ws.txt").read_text() == "teste"
