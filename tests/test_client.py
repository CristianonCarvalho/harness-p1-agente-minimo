import json
import pytest
import httpx
from agent.client import OpenRouterClient, ClientError
from agent.cli import main
from agent.config import Config


def make(handler):
    return OpenRouterClient("k", transport=httpx.MockTransport(handler))


def test_chat_sends_body_and_auth():
    seen = {}

    def h(req):
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "oi"}, "finish_reason": "stop"}],
                "usage": {},
            },
        )

    r = make(h).chat([{"role": "user", "content": "x"}], model="m/a")
    assert seen["auth"] == "Bearer k"
    assert seen["body"]["usage"] == {"include": True} and seen["body"]["model"] == "m/a"
    assert "tools" not in seen["body"]
    assert r["choices"][0]["message"]["content"] == "oi"


def test_error_payload_with_200_raises():
    with pytest.raises(ClientError):
        make(lambda req: httpx.Response(200, json={"error": {"code": 400, "message": "bad"}})).chat([], model="m")


def test_http_error_raises():
    with pytest.raises(ClientError):
        make(lambda req: httpx.Response(401, json={})).chat([], model="m")


def test_chat_sends_tools():
    seen = {}

    def h(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "oi"}, "finish_reason": "stop"}],
                "usage": {},
            },
        )

    tools = [{"type": "function", "function": {"name": "test_func", "parameters": {}}}]
    r = make(h).chat([{"role": "user", "content": "x"}], model="m/a", tools=tools)
    assert seen["body"]["tools"] == tools
    assert r["choices"][0]["message"]["content"] == "oi"


def test_models_returns_data():
    sample_models = [
        {"id": "deepseek/deepseek-v4-flash-0731", "pricing": {"prompt": "0.0000001", "completion": "0.0000002"}},
        {"id": "openai/gpt-4o", "pricing": {"prompt": "0.0000025", "completion": "0.00001"}},
    ]

    def h(req):
        assert req.headers["authorization"] == "Bearer k"
        assert req.url.path == "/api/v1/models"
        return httpx.Response(200, json={"data": sample_models})

    res = make(h).models()
    assert res == sample_models


def test_models_error_raises():
    with pytest.raises(ClientError):
        make(lambda req: httpx.Response(500, json={"error": {"message": "Server error"}})).models()


def test_chat_missing_choices_raises():
    with pytest.raises(ClientError):
        make(lambda req: httpx.Response(200, json={"id": "gen-1"})).chat([], model="m")


def test_models_missing_data_raises():
    with pytest.raises(ClientError):
        make(lambda req: httpx.Response(200, json={"object": "list"})).models()


def test_client_context_manager():
    with make(lambda req: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})) as client:
        r = client.chat([], model="m")
        assert r["choices"][0]["message"]["content"] == "ok"


def test_cli_ask_without_api_key(monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key=""))
    code = main(["ask", "x"])
    assert code == 2
    captured = capsys.readouterr()
    assert "defina OPENROUTER_API_KEY no .env" in (captured.out + captured.err)


def test_cli_ask_success(monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model"))

    def h(req):
        body = json.loads(req.content)
        assert body["model"] == "mock-model"
        assert body["messages"] == [{"role": "user", "content": "olá"}]
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Olá, tudo bem?"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 6, "cost": 0.0001},
            },
        )

    mock_client = OpenRouterClient("mock-key", transport=httpx.MockTransport(h))
    code = main(["ask", "olá"], client=mock_client)
    assert code == 0
    captured = capsys.readouterr()
    assert "Olá, tudo bem?" in captured.out
    assert '"prompt_tokens": 5' in captured.out
    assert '"cost": 0.0001' in captured.out


def test_cli_ask_with_model_flag(monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="default-model"))

    def h(req):
        body = json.loads(req.content)
        assert body["model"] == "custom/model"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Resposta custom"}}],
                "usage": {"prompt_tokens": 1},
            },
        )

    mock_client = OpenRouterClient("mock-key", transport=httpx.MockTransport(h))
    code = main(["ask", "teste", "--model", "custom/model"], client=mock_client)
    assert code == 0
    captured = capsys.readouterr()
    assert "Resposta custom" in captured.out
