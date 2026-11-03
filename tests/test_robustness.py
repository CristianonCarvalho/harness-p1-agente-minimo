import json
from pathlib import Path
import httpx
import pytest

from agent.client import ClientError, OpenRouterClient
from agent.ledger import Ledger
from agent.loop import run
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


def finish(reason):
    return httpx.Response(200, json={"choices": [{"message": {"content": "x"}, "finish_reason": reason}], "usage": {}})


def test_finish_reason_error_is_retried():
    replies = [finish("error"), finish("stop")]
    slept = []
    c = OpenRouterClient("k", transport=httpx.MockTransport(lambda r: replies.pop(0)), sleep=slept.append)
    r = c.chat([{"role": "user", "content": "x"}], model="m")
    assert r["choices"][0]["finish_reason"] == "stop"
    assert len(slept) == 1


def test_finish_reason_error_exhausted_ends_run(tmp_path: Path):
    count = {"n": 0}

    def h(req):
        count["n"] += 1
        return finish("error")

    c = OpenRouterClient("k", transport=httpx.MockTransport(h), sleep=lambda s: None)
    with pytest.raises(ClientError):
        c.chat([{"role": "user", "content": "x"}], model="m")
    assert count["n"] == 4

    r = run("x", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m")
    assert r.reason == "error"


def test_retry_then_success():
    n = {"i": 0}
    waits = []

    def h(req):
        n["i"] += 1
        return httpx.Response(
            429 if n["i"] < 3 else 200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": {}},
        )

    c = OpenRouterClient("k", transport=httpx.MockTransport(h), sleep=waits.append)
    assert c.chat([], model="m")["choices"][0]["message"]["content"] == "ok"
    assert waits == [1.0, 2.0]


def test_retry_exhausted_raises():
    c = OpenRouterClient(
        "k", transport=httpx.MockTransport(lambda r: httpx.Response(500)), sleep=lambda s: None
    )
    with pytest.raises(ClientError):
        c.chat([], model="m")


def test_no_retry_on_400():
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        return httpx.Response(400, json={})

    c = OpenRouterClient("k", transport=httpx.MockTransport(h), sleep=lambda s: None)
    with pytest.raises(ClientError):
        c.chat([], model="m")
    assert n["i"] == 1


def test_retry_on_timeout_exception():
    n = {"i": 0}
    waits = []

    def h(req):
        n["i"] += 1
        if n["i"] == 1:
            raise httpx.ReadTimeout("read timed out")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}}
        )

    c = OpenRouterClient("k", transport=httpx.MockTransport(h), sleep=waits.append)
    assert c.chat([], model="m")["choices"][0]["message"]["content"] == "ok"
    assert waits == [1.0]


def test_retry_on_transport_error():
    n = {"i": 0}
    waits = []

    def h(req):
        n["i"] += 1
        if n["i"] == 1:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}}
        )

    c = OpenRouterClient("k", transport=httpx.MockTransport(h), sleep=waits.append)
    assert c.chat([], model="m")["choices"][0]["message"]["content"] == "ok"
    assert waits == [1.0]


@pytest.mark.parametrize("raw", ["", "{nao json"])
def test_invalid_arguments_become_error(tmp_path: Path, raw: str):
    bad = {"id": "c1", "type": "function", "function": {"name": "read_file", "arguments": raw}}
    c = FakeClient([msg(tool_calls=[bad]), msg("fim")])
    r = run("x", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m")
    assert c.calls[1][-1]["content"].startswith("error: argumentos inválidos") and r.reason == "no_tool_calls"


def test_cost_cap(tmp_path: Path):  # cada msg custa 0.001
    c = FakeClient([msg(tool_calls=[call(f"c{i}", "read_file", {"path": "x"})]) for i in range(10)])
    assert run("x", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m", cost_cap_usd=0.0025).reason == "cost_cap"


def test_client_error_ends_run(tmp_path: Path):
    class Boom:
        def chat(self, messages, model, tools=None):
            raise ClientError("falhou")

    r = run("x", ToolContext(tmp_path), Boom(), Ledger(tmp_path / "t.jsonl"), "m")
    assert (r.reason, r.final) == ("error", "")
    last = json.loads((tmp_path / "t.jsonl").read_text().splitlines()[-1])
    assert last["t"] == "end" and last["reason"] == "error"


def test_tool_calls_over_limit_are_dropped(tmp_path: Path):
    (tmp_path / "a.txt").write_text("oi")
    many = [call(f"c{i}", "read_file", {"path": "a.txt"}) for i in range(25)]
    c = FakeClient([msg(tool_calls=many), msg("fim")])
    r = run("x", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m")

    assistant = [m for m in r.messages if m["role"] == "assistant"][0]
    tool_msgs = [m for m in r.messages if m["role"] == "tool"]
    assert len(assistant["tool_calls"]) == 10
    assert [m["tool_call_id"] for m in tool_msgs] == [tc["id"] for tc in assistant["tool_calls"]]
    assert "15 chamadas descartadas" in tool_msgs[-1]["content"]

    events = [json.loads(l) for l in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert [e for e in events if e["t"] == "dropped"] == [{"t": "dropped", "turn": 1, "count": 15}]
    assert len([e for e in events if e["t"] == "tool"]) == 10


def test_exactly_limit_is_not_dropped(tmp_path: Path):
    (tmp_path / "a.txt").write_text("oi")
    ten = [call(f"c{i}", "read_file", {"path": "a.txt"}) for i in range(10)]
    c = FakeClient([msg(tool_calls=ten), msg("fim")])
    r = run("x", ToolContext(tmp_path), c, Ledger(tmp_path / "t.jsonl"), "m")
    assert len([m for m in r.messages if m["role"] == "tool"]) == 10
    assert '"dropped"' not in (tmp_path / "t.jsonl").read_text()


def test_report_ignores_dropped_event(tmp_path: Path):
    from agent.report import build_report

    tasks = tmp_path / "tasks" / "01-x"
    tasks.mkdir(parents=True)
    (tasks / "prompt.md").write_text("x")
    run_dir = tmp_path / "runs" / "20260101-000000-01-x"
    run_dir.mkdir(parents=True)
    (run_dir / "trace.jsonl").write_text(
        '{"t": "llm", "turn": 1, "prompt_tokens": 5, "completion_tokens": 2, "cost_usd": 0.001}\n'
        '{"t": "dropped", "turn": 1, "count": 3}\n'
        '{"t": "end", "reason": "no_tool_calls", "turns": 1, "cost_usd": 0.001, "check": "pass"}\n'
    )
    out = build_report(tmp_path / "tasks", tmp_path / "runs")
    assert "| 01-x |" in out and "5/2" in out and "pass" in out
