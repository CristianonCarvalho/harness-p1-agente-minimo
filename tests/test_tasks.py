import json
from pathlib import Path
import subprocess
import sys
import pytest

from agent.cli import main
from agent.config import Config
from agent.tasks import discover_tasks, prepare, run_check, run_task


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


def call(call_id, name, args):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def test_discover_tasks():
    tasks_root = Path("tasks")
    tasks = discover_tasks(tasks_root)
    names = [t.name for t in tasks]
    assert names == ["01-hello-file", "02-rename-batch", "03-csv-summary"]


def test_discover_tasks_ignores_dir_without_prompt(tmp_path: Path):
    (tmp_path / "01-valid").mkdir()
    (tmp_path / "01-valid" / "prompt.md").write_text("prompt")
    (tmp_path / "02-ignored").mkdir()
    (tmp_path / "02-ignored" / "other.txt").write_text("hello")
    (tmp_path / "some_file.md").write_text("not a dir")

    found = discover_tasks(tmp_path)
    assert [p.name for p in found] == ["01-valid"]


def test_prepare_copies_workspace_and_runs_setup(tmp_path: Path):
    task_dir = tmp_path / "sample-task"
    task_ws = task_dir / "workspace"
    task_ws.mkdir(parents=True)
    (task_ws / "file.txt").write_text("original content")

    # setup.py writes a marker inside <run_dir>
    setup_py = task_dir / "setup.py"
    setup_py.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "run_dir = Path(sys.argv[1])\n"
        "(run_dir / 'setup_done.txt').write_text('ran')\n"
    )

    run_dir = tmp_path / "run_01"
    prepare(task_dir, run_dir)

    assert (run_dir / "ws" / "file.txt").read_text() == "original content"
    assert (run_dir / "setup_done.txt").read_text() == "ran"


def test_run_check_task_01(tmp_path: Path):
    task_dir = Path("tasks/01-hello-file")
    run_dir = tmp_path / "run_01"
    prepare(task_dir, run_dir)

    # Initial workspace has no hello.txt -> False
    assert run_check(task_dir, run_dir) is False

    # Manual solution: exact content
    (run_dir / "ws" / "hello.txt").write_text("Olá, agente!", encoding="utf-8")
    assert run_check(task_dir, run_dir) is True

    # Tolerates final newline
    (run_dir / "ws" / "hello.txt").write_text("Olá, agente!\n", encoding="utf-8")
    assert run_check(task_dir, run_dir) is True

    # Fails if content is wrong
    (run_dir / "ws" / "hello.txt").write_text("Olá agente!", encoding="utf-8")
    assert run_check(task_dir, run_dir) is False


def test_run_check_task_02(tmp_path: Path):
    task_dir = Path("tasks/02-rename-batch")
    run_dir = tmp_path / "run_02"
    prepare(task_dir, run_dir)

    # Initial workspace has .txt files -> False
    assert run_check(task_dir, run_dir) is False

    # Manual solution: delete .txt and create .md with matching content
    ws = run_dir / "ws"
    (ws / "a.md").write_text((ws / "a.txt").read_text(encoding="utf-8"), encoding="utf-8")
    (ws / "b.md").write_text((ws / "b.txt").read_text(encoding="utf-8"), encoding="utf-8")
    (ws / "notas" / "c.md").write_text((ws / "notas" / "c.txt").read_text(encoding="utf-8"), encoding="utf-8")
    (ws / "a.txt").unlink()
    (ws / "b.txt").unlink()
    (ws / "notas" / "c.txt").unlink()

    assert run_check(task_dir, run_dir) is True


def test_run_check_task_03(tmp_path: Path):
    task_dir = Path("tasks/03-csv-summary")
    run_dir = tmp_path / "run_03"
    prepare(task_dir, run_dir)

    # Initial workspace has no resumo.md -> False
    assert run_check(task_dir, run_dir) is False

    # Manual solution: resumo.md with decimal dot
    ws = run_dir / "ws"
    (ws / "resumo.md").write_text(
        "# Resumo de Vendas\n- Norte: 1234.50\n- Sul: 987.00\n- Leste: 2210.25\n",
        encoding="utf-8",
    )
    assert run_check(task_dir, run_dir) is True

    # Manual solution: resumo.md with decimal comma
    (ws / "resumo.md").write_text(
        "Norte: 1234,50; Sul: 987,00; Leste: 2210,25",
        encoding="utf-8",
    )
    assert run_check(task_dir, run_dir) is True


def test_run_task(tmp_path: Path):
    task_dir = Path("tasks/01-hello-file")
    runs_root = tmp_path / "runs"

    client = FakeClient([
        msg(tool_calls=[call("c1", "write_file", {"path": "hello.txt", "content": "Olá, agente!"})]),
        msg("Arquivo criado com sucesso."),
    ])

    run_dir, result, passed = run_task(
        task_dir=task_dir,
        runs_root=runs_root,
        client=client,
        model="test-model",
        max_turns=5,
        cost_cap_usd=0.10,
    )

    assert passed is True
    assert result.turns == 2
    assert (run_dir / "ws" / "hello.txt").read_text(encoding="utf-8") == "Olá, agente!"

    # Trace last line has "check": "pass"
    trace_path = run_dir / "trace.jsonl"
    assert trace_path.exists()
    lines = [json.loads(l) for l in trace_path.read_text(encoding="utf-8").splitlines()]
    last_event = lines[-1]
    assert last_event["t"] == "end"
    assert last_event["check"] == "pass"


def test_cli_task_prefix(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model", max_turns=10))
    runs_dir = tmp_path / "runs"

    client = FakeClient([
        msg(tool_calls=[call("c1", "write_file", {"path": "hello.txt", "content": "Olá, agente!"})]),
        msg("concluido"),
    ])

    code = main(["task", "01"], client=client, runs_dir=runs_dir)
    assert code == 0

    out = capsys.readouterr().out
    assert "pass · turnos: 2 · custo: US$ 0.0020 · " in out
    created = [d for d in runs_dir.iterdir() if d.is_dir()]
    assert len(created) == 1
    assert str(created[0]) in out


def test_cli_task_full_name(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model", max_turns=10))
    runs_dir = tmp_path / "runs"

    client = FakeClient([
        msg("não fiz nada"),
    ])

    code = main(["task", "01-hello-file"], client=client, runs_dir=runs_dir)
    assert code == 0

    out = capsys.readouterr().out
    assert "fail · turnos: 1" in out


def test_cli_task_not_found(capsys, monkeypatch):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model"))
    code = main(["task", "99"])
    assert code != 0
    assert "tarefa '99' não encontrada" in capsys.readouterr().out


def test_run_task_failing(tmp_path: Path):
    task_dir = Path("tasks/01-hello-file")
    runs_root = tmp_path / "runs"

    client = FakeClient([
        msg("Não criei nenhum arquivo."),
    ])

    run_dir, result, passed = run_task(
        task_dir=task_dir,
        runs_root=runs_root,
        client=client,
        model="test-model",
        max_turns=5,
        cost_cap_usd=0.10,
    )

    assert passed is False
    assert result.turns == 1

    trace_path = run_dir / "trace.jsonl"
    assert trace_path.exists()
    lines = [json.loads(l) for l in trace_path.read_text(encoding="utf-8").splitlines()]
    last_event = lines[-1]
    assert last_event["t"] == "end"
    assert last_event["check"] == "fail"


def test_prepare_no_workspace(tmp_path: Path):
    task_dir = tmp_path / "no-ws-task"
    task_dir.mkdir()
    run_dir = tmp_path / "run_no_ws"
    prepare(task_dir, run_dir)
    assert (run_dir / "ws").is_dir()


def test_run_check_missing_check_file(tmp_path: Path):
    task_dir = tmp_path / "empty-task"
    task_dir.mkdir()
    run_dir = tmp_path / "run"
    assert run_check(task_dir, run_dir) is False


def test_cli_task_no_api_key(capsys, monkeypatch):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="", model="mock-model"))
    code = main(["task", "01"])
    assert code == 2
    assert "defina OPENROUTER_API_KEY no .env" in capsys.readouterr().out


def test_cli_task_numeric_single_digit(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model"))
    runs_dir = tmp_path / "runs"
    client = FakeClient([
        msg(tool_calls=[call("c1", "write_file", {"path": "hello.txt", "content": "Olá, agente!"})]),
        msg("feito"),
    ])
    code = main(["task", "1"], client=client, runs_dir=runs_dir)
    assert code == 0
    assert "pass" in capsys.readouterr().out

