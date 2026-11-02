import json
from pathlib import Path
import pytest
import httpx

from agent.client import OpenRouterClient
from agent.config import Config
from agent.ledger import Ledger, load_pricing
from agent.cli import main


RESP = {
    "choices": [{"finish_reason": "stop", "message": {}}],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 10,
        "cost": 0.002,
        "prompt_tokens_details": {"cached_tokens": 80},
    },
}


def lines(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]


def test_measured_cost(tmp_path: Path):
    lg = Ledger(tmp_path / "t.jsonl")
    assert lg.llm(1, "m", RESP, 50) == 0.002
    e = lines(tmp_path / "t.jsonl")[0]
    assert e["t"] == "llm" and e["cost_source"] == "measured" and e["cached_tokens"] == 80
    assert e["prompt_tokens"] == 100 and e["finish_reason"] == "stop" and e["latency_ms"] == 50
    assert e["cost_usd"] == 0.002 and e["turn"] == 1 and e["model"] == "m"


def test_estimated_cost(tmp_path: Path):
    r = {**RESP, "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
    lg = Ledger(tmp_path / "t.jsonl", pricing=lambda: {"m": (0.001, 0.01)})
    assert lg.llm(1, "m", r, 5) == pytest.approx(0.2)
    e = lines(tmp_path / "t.jsonl")[0]
    assert e["cost_source"] == "estimated"
    assert e["cost_usd"] == pytest.approx(0.2)


def test_total_cost_accumulates(tmp_path: Path):
    lg = Ledger(tmp_path / "t.jsonl", pricing=lambda: {"m": (0.001, 0.01)})
    cost1 = lg.llm(1, "m", RESP, 50)  # measured: 0.002
    r2 = {**RESP, "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
    cost2 = lg.llm(2, "m", r2, 5)     # estimated: 0.2
    assert lg.total_cost == pytest.approx(cost1 + cost2)


def test_unknown_cost_source_when_model_missing(tmp_path: Path):
    r = {**RESP, "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
    lg = Ledger(tmp_path / "t.jsonl", pricing=lambda: {"other": (0.001, 0.01)})
    assert lg.llm(1, "missing_model", r, 10) == 0.0
    e = lines(tmp_path / "t.jsonl")[0]
    assert e["cost_source"] == "unknown"
    assert e["cost_usd"] == 0.0


def test_lazy_pricing_loading(tmp_path: Path):
    def failing_pricing():
        raise AssertionError("pricing should not be called when usage.cost is present")

    lg = Ledger(tmp_path / "t.jsonl", pricing=failing_pricing)
    # With measured cost, failing_pricing must NOT be called
    assert lg.llm(1, "m", RESP, 50) == 0.002

    # Without measured cost, pricing is called
    called = []
    lg2 = Ledger(tmp_path / "t2.jsonl", pricing=lambda: called.append(True) or {"m": (0.001, 0.01)})
    r_no_cost = {**RESP, "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    lg2.llm(1, "m", r_no_cost, 10)
    assert len(called) == 1


def test_tool_event(tmp_path: Path):
    lg = Ledger(tmp_path / "t.jsonl")
    long_result = "x" * 600
    lg.tool(
        turn=2,
        name="run_command",
        args={"command": "ls -la"},
        approved=True,
        result=long_result,
        ms=120,
    )
    e = lines(tmp_path / "t.jsonl")[0]
    assert e["t"] == "tool"
    assert e["turn"] == 2
    assert e["name"] == "run_command"
    assert e["args"] == {"command": "ls -la"}
    assert e["approved"] is True
    assert e["result_head"] == "x" * 500
    assert len(e["result_head"]) == 500
    assert e["result_bytes"] == 600
    assert e["ms"] == 120


def test_end_event(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    lg = Ledger(p)
    lg.llm(1, "m", RESP, 50)

    # End with check
    lg.end(reason="no_tool_calls", turns=1, check="pass")
    records = lines(p)
    assert len(records) == 2
    end_entry = records[1]
    assert end_entry["t"] == "end"
    assert end_entry["reason"] == "no_tool_calls"
    assert end_entry["turns"] == 1
    assert end_entry["cost_usd"] == 0.002
    assert end_entry["check"] == "pass"

    # End without check omits check key
    p2 = tmp_path / "t2.jsonl"
    lg2 = Ledger(p2)
    lg2.end(reason="max_turns", turns=5)
    e2 = lines(p2)[0]
    assert e2["t"] == "end"
    assert e2["reason"] == "max_turns"
    assert e2["turns"] == 5
    assert e2["cost_usd"] == 0.0
    assert "check" not in e2


def test_cached_tokens_default_zero(tmp_path: Path):
    r = {
        "choices": [{"finish_reason": "stop", "message": {}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10, "cost": 0.001},
    }
    lg = Ledger(tmp_path / "t.jsonl")
    lg.llm(1, "m", r, 20)
    e = lines(tmp_path / "t.jsonl")[0]
    assert e["cached_tokens"] == 0


def test_load_pricing_uses_cache_without_calling_client(tmp_path: Path):
    cache_path = tmp_path / ".models-cache.json"
    cache_path.write_text(
        json.dumps([
            {
                "id": "model-cached",
                "pricing": {"prompt": "0.000002", "completion": "0.000008"},
            }
        ]),
        encoding="utf-8",
    )

    class FailingClient:
        def models(self):
            raise AssertionError("client.models() must not be called when cache exists")

    pricing = load_pricing(FailingClient(), cache_path)
    assert pricing == {"model-cached": (0.000002, 0.000008)}


def test_load_pricing_fetches_and_saves_cache_when_missing(tmp_path: Path):
    cache_path = tmp_path / "sub" / ".models-cache.json"
    assert not cache_path.exists()

    class FakeClient:
        def __init__(self):
            self.called = False

        def models(self):
            self.called = True
            return [
                {
                    "id": "model-a",
                    "pricing": {"prompt": "0.000001", "completion": "0.000005"},
                }
            ]

    cli = FakeClient()
    pricing = load_pricing(cli, cache_path)
    assert cli.called is True
    assert pricing == {"model-a": (0.000001, 0.000005)}
    assert cache_path.is_file()
    saved = json.loads(cache_path.read_text(encoding="utf-8"))
    assert saved[0]["id"] == "model-a"


def test_cli_ask_records_trace_and_prints_cost(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model"))

    def h(req):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Olá!"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0005},
            },
        )

    mock_client = OpenRouterClient("mock-key", transport=httpx.MockTransport(h))
    code = main(["ask", "olá"], client=mock_client, runs_dir=tmp_path)
    assert code == 0

    captured = capsys.readouterr()
    assert "Olá!" in captured.out
    assert "custo: US$ 0.0005 (measured)" in captured.out

    jsonl_files = list(tmp_path.glob("ask-*.jsonl"))
    assert len(jsonl_files) == 1
    events = lines(jsonl_files[0])
    assert len(events) == 1
    assert events[0]["t"] == "llm"
    assert events[0]["cost_usd"] == 0.0005
    assert events[0]["cost_source"] == "measured"


def test_cli_ask_estimated_cost(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model"))
    cache_path = tmp_path / ".models-cache.json"
    cache_path.write_text(
        json.dumps([{"id": "mock-model", "pricing": {"prompt": "0.00001", "completion": "0.00002"}}]),
        encoding="utf-8",
    )

    def h(req):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Olá estimado!"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

    mock_client = OpenRouterClient("mock-key", transport=httpx.MockTransport(h))
    code = main(["ask", "olá"], client=mock_client, runs_dir=tmp_path)
    assert code == 0

    captured = capsys.readouterr()
    assert "Olá estimado!" in captured.out
    # 100 * 0.00001 + 50 * 0.00002 = 0.001 + 0.001 = 0.002
    assert "custo: US$ 0.002 (estimated)" in captured.out

    jsonl_files = list(tmp_path.glob("ask-*.jsonl"))
    events = lines(jsonl_files[0])
    assert events[0]["cost_source"] == "estimated"
    assert events[0]["cost_usd"] == pytest.approx(0.002)


def test_tool_unicode_result_bytes(tmp_path: Path):
    lg = Ledger(tmp_path / "t.jsonl")
    result = "é" * 100  # 100 chars, 200 bytes in UTF-8
    lg.tool(turn=1, name="read_file", args={"path": "f.txt"}, approved=None, result=result, ms=5)
    e = lines(tmp_path / "t.jsonl")[0]
    assert e["result_head"] == result
    assert e["result_bytes"] == 200
    assert e["approved"] is None


def test_load_pricing_handles_dict_data_and_client_error(tmp_path: Path):
    cache_path = tmp_path / "dict_cache.json"
    cache_path.write_text(
        json.dumps({"data": [{"id": "m1", "pricing": {"prompt": "0.05", "completion": "0.10"}}]}),
        encoding="utf-8",
    )
    p = load_pricing(None, cache_path)
    assert p == {"m1": (0.05, 0.10)}

    class ExplodingClient:
        def models(self):
            raise RuntimeError("API error")

    missing_cache = tmp_path / "missing.json"
    assert load_pricing(ExplodingClient(), missing_cache) == {}

