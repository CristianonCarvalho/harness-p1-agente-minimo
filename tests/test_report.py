import json
from pathlib import Path
import pytest

from agent.report import (
    build_report,
    check_auto_approve,
    latest_run,
    read_prediction,
)
from agent.cli import main
from agent.config import Config


def test_read_prediction(tmp_path: Path):
    t1 = tmp_path / "t1"
    t1.mkdir()
    (t1 / "prediction.md").write_text("previsão: pass\nonde vai falhar:\n", encoding="utf-8")
    assert read_prediction(t1) == "pass"

    t2 = tmp_path / "t2"
    t2.mkdir()
    (t2 / "prediction.md").write_text("previsão: fail\n", encoding="utf-8")
    assert read_prediction(t2) == "fail"

    t3 = tmp_path / "t3"
    t3.mkdir()
    (t3 / "prediction.md").write_text("previsão: \nonde vai falhar:\n", encoding="utf-8")
    assert read_prediction(t3) is None

    t4 = tmp_path / "t4"
    t4.mkdir()
    (t4 / "prediction.md").write_text("previsão: pass | fail\n", encoding="utf-8")
    assert read_prediction(t4) is None

    t5 = tmp_path / "t5"
    t5.mkdir()
    assert read_prediction(t5) is None


def test_latest_run(tmp_path: Path):
    runs = tmp_path / "runs"
    runs.mkdir()

    # No runs yet
    assert latest_run(runs, "01-task") is None

    # Multiple runs for 01-task
    r1 = runs / "20261102-100000-01-task"
    r1.mkdir()
    r2 = runs / "20261102-120000-01-task"
    r2.mkdir()
    r3 = runs / "20261102-110000-02-other"
    r3.mkdir()

    assert latest_run(runs, "01-task") == r2
    assert latest_run(runs, "02-other") == r3
    assert latest_run(runs, "03-missing") is None


def test_check_auto_approve(tmp_path: Path):
    runs = tmp_path / "runs"
    runs.mkdir()

    inside_ws = runs / "20261102-100000-task" / "ws"
    inside_ws.mkdir(parents=True)
    # Inside runs must succeed
    check_auto_approve(inside_ws, runs)

    # Outside runs must raise ValueError
    outside_ws = tmp_path / "outside_ws"
    outside_ws.mkdir()
    with pytest.raises(ValueError, match="não está dentro"):
        check_auto_approve(outside_ws, runs)

    with pytest.raises(ValueError, match="não está dentro"):
        check_auto_approve(Path("/tmp/ws"), runs)

    # runs itself must raise ValueError
    with pytest.raises(ValueError):
        check_auto_approve(runs, runs)


def test_build_report_and_footer(tmp_path: Path):
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    t1 = tasks_root / "01-primeira"
    t1.mkdir()
    (t1 / "prompt.md").write_text("Prompt 1", encoding="utf-8")
    (t1 / "prediction.md").write_text("previsão: pass\n", encoding="utf-8")

    t2 = tasks_root / "02-segunda"
    t2.mkdir()
    (t2 / "prompt.md").write_text("Prompt 2", encoding="utf-8")
    (t2 / "prediction.md").write_text("previsão: \n", encoding="utf-8")

    runs_root = tmp_path / "runs"
    runs_root.mkdir()

    r1 = runs_root / "20261102-100000-01-primeira"
    r1.mkdir()
    trace1 = [
        {
            "t": "llm",
            "turn": 1,
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "cost_usd": 0.002,
            "cost_source": "measured",
        },
        {
            "t": "end",
            "reason": "stop",
            "turns": 1,
            "cost_usd": 0.002,
            "check": "pass",
        },
    ]
    (r1 / "trace.jsonl").write_text("\n".join(json.dumps(x) for x in trace1) + "\n", encoding="utf-8")

    r2 = runs_root / "20261102-110000-02-segunda"
    r2.mkdir()
    trace2 = [
        {
            "t": "llm",
            "turn": 1,
            "prompt_tokens": 200,
            "completion_tokens": 20,
            "cost_usd": 0.004,
            "cost_source": "estimated",
        },
        {
            "t": "end",
            "reason": "no_tool_calls",
            "turns": 1,
            "cost_usd": 0.004,
            "check": "fail",
        },
    ]
    (r2 / "trace.jsonl").write_text("\n".join(json.dumps(x) for x in trace2) + "\n", encoding="utf-8")

    report = build_report(tasks_root, runs_root)

    # Check headers
    assert "| tarefa | previsto | real | acertou? | turnos | tokens (in/out) | custo US$ | motivo do fim |" in report
    assert "|---|---|---|---|---|---|---|---|" in report

    # Check task 1 row
    assert "| 01-primeira | pass | pass | sim | 1 | 100/10 | 0.0020 | stop |" in report

    # Check task 2 row (without prediction -> acertou? is —)
    assert "| 02-segunda | — | fail | — | 1 | 200/20 | 0.0040 | no_tool_calls |" in report

    # Check footer elements
    assert "Acerto das previsões: 1/1 (100%)" in report
    assert "Sem previsão" in report
    assert "02-segunda" in report
    assert "Custo médio: US$ 0.0030" in report
    assert "Custo total: US$ 0.0060" in report
    assert "estimated" in report
    assert "1" in report


def test_build_report_task_without_run(tmp_path: Path):
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    t1 = tasks_root / "01-primeira"
    t1.mkdir()
    (t1 / "prompt.md").write_text("Prompt 1", encoding="utf-8")
    (t1 / "prediction.md").write_text("previsão: pass\n", encoding="utf-8")

    runs_root = tmp_path / "runs"
    runs_root.mkdir()

    report = build_report(tasks_root, runs_root)
    assert "| 01-primeira | pass | — | — | — | — | — | — |" in report
    assert "Acerto das previsões: 0/0 (0%)" in report


def test_cli_report(tmp_path: Path, capsys):
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    t1 = tasks_root / "01-primeira"
    t1.mkdir()
    (t1 / "prompt.md").write_text("Prompt 1", encoding="utf-8")

    runs_root = tmp_path / "runs"
    runs_root.mkdir()

    code = main(["report"], runs_dir=runs_root, tasks_dir=tasks_root)
    assert code == 0

    captured = capsys.readouterr()
    assert "| tarefa | previsto | real |" in captured.out
    assert "01-primeira" in captured.out

    saved = runs_root / "report.md"
    assert saved.is_file()
    assert saved.read_text(encoding="utf-8") == captured.out


def test_cli_task_all_and_auto_approve(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model"))

    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    for name in ["01-t1", "02-t2"]:
        td = tasks_root / name
        td.mkdir()
        (td / "prompt.md").write_text(f"Task {name}", encoding="utf-8")
        (td / "check.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")

    runs_root = tmp_path / "runs"
    runs_root.mkdir()

    class FakeClient:
        def chat(self, messages, model=None, tools=None):
            return {
                "choices": [{"finish_reason": "stop", "message": {"content": "done"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001},
            }

    code = main(["task", "--all", "--auto-approve"], client=FakeClient(), runs_dir=runs_root, tasks_dir=tasks_root)
    assert code == 0

    captured = capsys.readouterr()
    assert "01-t1" in captured.out
    assert "02-t2" in captured.out
    assert "pass" in captured.out
    for d in runs_root.iterdir():
        if d.is_dir():
            assert (d / "ws").resolve().is_relative_to(runs_root.resolve())


def test_cli_run_auto_approve_outside_workspace_fails(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model"))

    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    outside = tmp_path / "outside_workspace"
    outside.mkdir()

    class FakeClient:
        pass

    code = main(["run", "--auto-approve", "--workspace", str(outside), "test prompt"], client=FakeClient(), runs_dir=runs_root)
    assert code == 2

    captured = capsys.readouterr()
    assert "não está dentro" in captured.out or "erro:" in captured.out


def test_build_report_prediction_mismatch(tmp_path: Path):
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    t1 = tasks_root / "01-primeira"
    t1.mkdir()
    (t1 / "prompt.md").write_text("Prompt 1", encoding="utf-8")
    (t1 / "prediction.md").write_text("previsão: pass\n", encoding="utf-8")

    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    r1 = runs_root / "20261102-100000-01-primeira"
    r1.mkdir()
    trace1 = [
        {"t": "llm", "turn": 1, "prompt_tokens": 50, "completion_tokens": 10, "cost_usd": 0.001, "cost_source": "measured"},
        {"t": "end", "reason": "cost_cap", "turns": 1, "cost_usd": 0.001, "check": "fail"},
    ]
    (r1 / "trace.jsonl").write_text("\n".join(json.dumps(x) for x in trace1) + "\n", encoding="utf-8")

    report = build_report(tasks_root, runs_root)
    assert "| 01-primeira | pass | fail | não | 1 | 50/10 | 0.0010 | cost_cap |" in report
    assert "Acerto das previsões: 0/1 (0%)" in report


def test_cli_task_no_args_prints_help(capsys):
    code = main(["task"])
    assert code == 1


def test_cli_run_auto_approve_inside_workspace_succeeds(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model"))

    runs_root = tmp_path / "runs"
    runs_root.mkdir()

    class FakeClient:
        def chat(self, messages, model=None, tools=None):
            return {
                "choices": [{"finish_reason": "stop", "message": {"content": "done"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001},
            }

    code = main(["run", "--auto-approve", "test prompt"], client=FakeClient(), runs_dir=runs_root)
    assert code == 0

    captured = capsys.readouterr()
    assert "done" in captured.out


def test_cli_task_single_auto_approve(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("agent.cli.load_config", lambda: Config(api_key="mock-key", model="mock-model"))

    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    td = tasks_root / "01-single"
    td.mkdir()
    (td / "prompt.md").write_text("Task single", encoding="utf-8")
    (td / "check.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")

    runs_root = tmp_path / "runs"
    runs_root.mkdir()

    class FakeClient:
        def chat(self, messages, model=None, tools=None):
            return {
                "choices": [{"finish_reason": "stop", "message": {"content": "done"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001},
            }

    code = main(["task", "01-single", "--auto-approve"], client=FakeClient(), runs_dir=runs_root, tasks_dir=tasks_root)
    assert code == 0

    captured = capsys.readouterr()
    assert "pass" in captured.out
