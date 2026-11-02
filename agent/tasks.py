from collections.abc import Callable
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from agent.config import DEFAULT_COST_CAP_USD, DEFAULT_MAX_TURNS, DEFAULT_MODEL
from agent.loop import RunResult
from agent.runs import execute_run, new_run_dir


def discover_tasks(tasks_root: Path) -> list[Path]:
    if not tasks_root.is_dir():
        return []
    tasks = [p for p in tasks_root.iterdir() if p.is_dir() and (p / "prompt.md").is_file()]
    tasks.sort(key=lambda p: p.name)
    return tasks


def prepare(task_dir: Path, run_dir: Path) -> None:
    ws = run_dir / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    task_ws = task_dir / "workspace"
    if task_ws.is_dir():
        shutil.copytree(task_ws, ws, dirs_exist_ok=True)

    setup_py = task_dir / "setup.py"
    if setup_py.is_file():
        subprocess.run(
            [sys.executable, str(setup_py.resolve()), str(run_dir.resolve())],
            cwd=task_dir,
            check=True,
        )


def run_check(task_dir: Path, run_dir: Path) -> bool:
    check_py = task_dir / "check.py"
    if not check_py.is_file():
        return False

    ws = run_dir / "ws"
    final_txt = run_dir / "final.txt"
    trace_jsonl = run_dir / "trace.jsonl"

    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(check_py.resolve()),
                str(ws.resolve()),
                str(final_txt.resolve()),
                str(trace_jsonl.resolve()),
            ],
            cwd=task_dir,
            timeout=60,
            capture_output=True,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        return False


def run_task(
    task_dir: Path,
    runs_root: Path,
    client: Any,
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    cost_cap_usd: float = DEFAULT_COST_CAP_USD,
    confirm: Callable[[str], bool] | None = None,
) -> tuple[Path, RunResult, bool]:
    prompt_file = task_dir / "prompt.md"
    prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else ""

    run_dir = new_run_dir(runs_root, task_dir.name)
    prepare(task_dir, run_dir)

    result = execute_run(
        prompt=prompt,
        run_dir=run_dir,
        client=client,
        model=model,
        max_turns=max_turns,
        cost_cap_usd=cost_cap_usd,
        confirm=confirm,
    )

    passed = run_check(task_dir, run_dir)

    trace_path = run_dir / "trace.jsonl"
    if trace_path.is_file():
        content = trace_path.read_text(encoding="utf-8")
        lines = [line for line in content.splitlines() if line.strip()]
        if lines:
            try:
                last_event = json.loads(lines[-1])
                last_event["check"] = "pass" if passed else "fail"
                lines[-1] = json.dumps(last_event, ensure_ascii=False)
                trace_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            except Exception:
                pass

    return run_dir, result, passed
