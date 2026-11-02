import pytest
from pathlib import Path

from agent.tools import (
    TOOL_SCHEMAS,
    ToolContext,
    ToolOutput,
    execute,
    terminal_confirm,
)


def ctx(tmp_path: Path, ok: bool = True, **kw) -> ToolContext:
    return ToolContext(tmp_path, confirm=lambda c: ok, **kw)


def test_runs_in_workspace(tmp_path: Path) -> None:
    out = execute("run_command", {"command": "pwd"}, ctx(tmp_path))
    assert out.approved is True and str(tmp_path.resolve()) in out.text and out.text.startswith("exit: 0")


def test_denied(tmp_path: Path) -> None:
    out = execute("run_command", {"command": "echo x"}, ctx(tmp_path, ok=False))
    assert out.text == "error: usuário negou o comando" and out.approved is False


def test_env_is_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "segredo123")
    assert "segredo123" not in execute("run_command", {"command": "env"}, ctx(tmp_path)).text


def test_timeout(tmp_path: Path) -> None:
    assert execute("run_command", {"command": "sleep 5"}, ctx(tmp_path, timeout_s=0.5)).text == "error: timeout após 0.5s"


def test_eof_is_denial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(EOFError))
    assert terminal_confirm("ls") is False


def test_keyboard_interrupt_is_denial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))
    assert terminal_confirm("ls") is False


def test_terminal_confirm_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    assert terminal_confirm("ls") is True

    monkeypatch.setattr("builtins.input", lambda *_: "  yes  ")
    assert terminal_confirm("ls") is True

    monkeypatch.setattr("builtins.input", lambda *_: "Y")
    assert terminal_confirm("ls") is True

    monkeypatch.setattr("builtins.input", lambda *_: "n")
    assert terminal_confirm("ls") is False

    monkeypatch.setattr("builtins.input", lambda *_: "")
    assert terminal_confirm("ls") is False

    monkeypatch.setattr("builtins.input", lambda *_: "other")
    assert terminal_confirm("ls") is False


def test_terminal_confirm_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return "y"

    monkeypatch.setattr("builtins.input", fake_input)
    assert terminal_confirm("echo hello") is True
    assert prompts == ["$ echo hello  executar? [y/N] "]


def test_stdout_truncation(tmp_path: Path) -> None:
    out = execute(
        "run_command",
        {"command": "python3 -c \"print('x' * 20000)\""},
        ctx(tmp_path),
    )
    assert out.approved is True
    assert "[truncado: 20001 bytes no total]" in out.text
    assert len(out.text) < 11_000


def test_nonzero_exit_and_stderr(tmp_path: Path) -> None:
    out = execute(
        "run_command",
        {"command": "sh -c 'echo erro_customizado >&2; exit 42'"},
        ctx(tmp_path),
    )
    assert out.approved is True
    assert "exit: 42" in out.text
    assert "erro_customizado" in out.text
    assert "stderr:" in out.text


def test_cd_escapes_cwd_because_cwd_is_not_sandbox(tmp_path: Path) -> None:
    out = execute("run_command", {"command": "cd / && pwd"}, ctx(tmp_path))
    assert out.approved is True
    assert out.text.startswith("exit: 0")
    lines = out.text.splitlines()
    # stdout output line for pwd after cd / should be '/'
    assert lines[2] == "/"


def test_tool_schemas_has_run_command() -> None:
    schemas = {s["function"]["name"]: s["function"] for s in TOOL_SCHEMAS}
    assert "run_command" in schemas
    rc = schemas["run_command"]
    assert rc["parameters"]["type"] == "object"
    assert rc["parameters"]["required"] == ["command"]
    assert "command" in rc["parameters"]["properties"]
    assert rc["description"]


def test_cli_run_passes_terminal_confirm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from agent.cli import main
    from agent.config import Config

    monkeypatch.setattr(
        "agent.cli.load_config",
        lambda: Config(api_key="mock-key", model="mock-model", max_turns=10),
    )

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list = []

        def chat(self, messages, model, tools=None):
            self.calls.append(messages)
            if len(self.calls) == 1:
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "c1",
                                        "type": "function",
                                        "function": {
                                            "name": "run_command",
                                            "arguments": '{"command": "echo hi"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.001},
                }
            return {
                "choices": [{"message": {"role": "assistant", "content": "executado"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.001},
            }

    confirmed_cmds: list[str] = []

    def fake_confirm(cmd: str) -> bool:
        confirmed_cmds.append(cmd)
        return True

    monkeypatch.setattr("agent.cli.terminal_confirm", fake_confirm)
    code = main(
        ["run", "execute echo hi", "--workspace", str(tmp_path)],
        client=FakeClient(),
        runs_dir=tmp_path,
    )
    assert code == 0
    assert confirmed_cmds == ["echo hi"]
