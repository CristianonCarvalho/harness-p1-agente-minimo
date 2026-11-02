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
