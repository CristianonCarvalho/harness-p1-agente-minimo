from datetime import datetime
import json
from pathlib import Path
import pytest

from agent.cli import main
from agent.config import Config
from agent.loop import SYSTEM_PROMPT, RunResult
from agent.runs import execute_run, new_run_dir, save_result


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


def test_new_run_dir_with_fixed_now(tmp_path: Path):
    now = datetime(2026, 11, 2, 10, 30, 45)
    run_dir = new_run_dir(tmp_path, "run", now=now)
    assert run_dir == tmp_path / "20261102-103045-run"
    assert run_dir.is_dir()
    assert (run_dir / "ws").is_dir()


def test_new_run_dir_repeated_call_same_second(tmp_path: Path):
    now = datetime(2026, 11, 2, 10, 30, 45)
    run_dir1 = new_run_dir(tmp_path, "run", now=now)
    run_dir2 = new_run_dir(tmp_path, "run", now=now)
    run_dir3 = new_run_dir(tmp_path, "run", now=now)

    assert run_dir1.name == "20261102-103045-run"
    assert run_dir2.name == "20261102-103045-run-2"
    assert run_dir3.name == "20261102-103045-run-3"
    assert (run_dir1 / "ws").is_dir()
    assert (run_dir2 / "ws").is_dir()
    assert (run_dir3 / "ws").is_dir()


def test_save_result(tmp_path: Path):
    run_dir = tmp_path / "sample_run"
    result = RunResult(
        final="resposta final",
        reason="no_tool_calls",
        turns=1,
        cost_usd=0.002,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "prompt"},
            {"role": "assistant", "content": "resposta final"},
        ],
    )
    save_result(run_dir, result)

    messages_path = run_dir / "messages.json"
    final_path = run_dir / "final.txt"

    assert messages_path.exists()
    assert final_path.exists()
    assert final_path.read_text(encoding="utf-8") == "resposta final"

    saved_messages = json.loads(messages_path.read_text(encoding="utf-8"))
    assert saved_messages == result.messages
    assert saved_messages[0]["role"] == "system"
    assert saved_messages[0]["content"] == SYSTEM_PROMPT

    raw_json = messages_path.read_text(encoding="utf-8")
    assert "  {\n    \"role\": \"system\"" in raw_json or "  \"role\": \"system\"" in raw_json


def test_execute_run(tmp_path: Path):
    run_dir = new_run_dir(tmp_path, "test")
    client = FakeClient([
        msg(tool_calls=[call("c1", "write_file", {"path": "saida.txt", "content": "conteudo gerado"})]),
        msg("tarefa concluida"),
    ])

    result = execute_run(
        prompt="crie saida.txt",
        run_dir=run_dir,
        client=client,
        model="mock-model",
        max_turns=5,
        cost_cap_usd=0.10,
    )

    assert result.final == "tarefa concluida"
    assert result.reason == "no_tool_calls"
    assert result.turns == 2

    # ws contains the created file
    assert (run_dir / "ws" / "saida.txt").read_text(encoding="utf-8") == "conteudo gerado"

    # trace.jsonl exists and has events
    trace_path = run_dir / "trace.jsonl"
    assert trace_path.exists()
    lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    event_types = [event["t"] for event in lines]
    assert event_types == ["llm", "tool", "llm", "end"]

    # messages.json exists and starts with system prompt in [0]
    messages_path = run_dir / "messages.json"
    assert messages_path.exists()
    saved_messages = json.loads(messages_path.read_text(encoding="utf-8"))
    assert saved_messages[0]["role"] == "system"
    assert saved_messages[0]["content"] == SYSTEM_PROMPT

    # final.txt exists and contains the answer
    final_path = run_dir / "final.txt"
    assert final_path.exists()
    assert final_path.read_text(encoding="utf-8") == "tarefa concluida"


def test_cli_run_uses_runs_by_default(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model", max_turns=10))
    runs_dir = tmp_path / "runs"
    client = FakeClient([
        msg(tool_calls=[call("c1", "write_file", {"path": "isolado.txt", "content": "executado"})]),
        msg("finalizado"),
    ])

    code = main(["run", "crie isolado.txt"], client=client, runs_dir=runs_dir)
    assert code == 0

    captured = capsys.readouterr()
    assert "finalizado" in captured.out

    run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    assert str(run_dir) in captured.out
    assert (run_dir / "ws" / "isolado.txt").read_text() == "executado"
    assert (run_dir / "trace.jsonl").exists()
    assert (run_dir / "messages.json").exists()
    assert (run_dir / "final.txt").read_text() == "finalizado"


def test_cli_run_custom_workspace(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model", max_turns=10))
    runs_dir = tmp_path / "runs"
    custom_ws = tmp_path / "my_workspace"
    custom_ws.mkdir()

    client = FakeClient([
        msg(tool_calls=[call("c1", "write_file", {"path": "custom.txt", "content": "em custom ws"})]),
        msg("feito custom"),
    ])

    code = main(["run", "crie custom.txt", "--workspace", str(custom_ws)], client=client, runs_dir=runs_dir)
    assert code == 0

    captured = capsys.readouterr()
    assert "feito custom" in captured.out

    run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    assert str(run_dir) in captured.out
    assert (custom_ws / "custom.txt").read_text() == "em custom ws"
    assert (run_dir / "trace.jsonl").exists()
    assert (run_dir / "messages.json").exists()
    assert (run_dir / "final.txt").read_text() == "feito custom"
