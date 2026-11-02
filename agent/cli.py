import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

from agent.client import OpenRouterClient
from agent.config import load_config
from agent.ledger import Ledger, load_pricing
from agent.report import build_report, check_auto_approve
from agent.runs import execute_run, new_run_dir
from agent.tasks import discover_tasks, run_task
from agent.tools import terminal_confirm


def main(
    argv: list[str] | None = None,
    client: OpenRouterClient | None = None,
    runs_dir: Path | None = None,
    tasks_dir: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Minimal agent CLI")
    subparsers = parser.add_subparsers(dest="command")

    ask_parser = subparsers.add_parser("ask", help="Send a prompt to the model")
    ask_parser.add_argument("prompt", help="Prompt text")
    ask_parser.add_argument("--model", "-m", default=None, help="Model name")

    run_parser = subparsers.add_parser("run", help="Run agent loop with tools")
    run_parser.add_argument("prompt", help="Prompt text")
    run_parser.add_argument("--model", "-m", default=None, help="Model name")
    run_parser.add_argument("--workspace", "-w", default=None, help="Workspace directory")
    run_parser.add_argument("--auto-approve", action="store_true", help="Auto approve commands")

    task_parser = subparsers.add_parser("task", help="Run a task")
    task_parser.add_argument("task", nargs="?", default=None, help="Task name or prefix")
    task_parser.add_argument("--all", "-a", action="store_true", help="Run all tasks")
    task_parser.add_argument("--auto-approve", action="store_true", help="Auto approve commands")
    task_parser.add_argument("--model", "-m", default=None, help="Model name")

    report_parser = subparsers.add_parser("report", help="Generate task report")

    args = parser.parse_args(argv)

    if args.command == "ask":
        cfg = load_config()
        if not cfg.api_key:
            print("defina OPENROUTER_API_KEY no .env")
            return 2

        model = args.model if args.model is not None else cfg.model
        cli = client if client is not None else OpenRouterClient(api_key=cfg.api_key)

        runs_path = runs_dir if runs_dir is not None else Path("runs")
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        ledger_path = runs_path / f"ask-{ts}.jsonl"
        cache_path = runs_path / ".models-cache.json"

        ledger = Ledger(ledger_path, pricing=lambda: load_pricing(cli, cache_path))

        start_time = time.perf_counter()
        resp = cli.chat(messages=[{"role": "user", "content": args.prompt}], model=model)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        cost = ledger.llm(turn=1, model=model, response=resp, latency_ms=latency_ms)

        content = resp["choices"][0]["message"].get("content", "")
        if content:
            print(content)
        usage = resp.get("usage", {})
        print(json.dumps(usage, indent=2))
        print(f"custo: US$ {cost} ({ledger.last_cost_source})")
        return 0

    if args.command == "run":
        cfg = load_config()
        if not cfg.api_key and client is None:
            print("defina OPENROUTER_API_KEY no .env")
            return 2

        model = args.model if args.model is not None else cfg.model
        cli = client if client is not None else OpenRouterClient(api_key=cfg.api_key)

        runs_path = runs_dir if runs_dir is not None else Path("runs")
        run_dir = new_run_dir(runs_path, "run")

        workspace = Path(args.workspace) if args.workspace is not None else None
        target_ws = workspace if workspace is not None else (run_dir / "ws")

        if args.auto_approve:
            try:
                check_auto_approve(target_ws, runs_path)
            except ValueError as err:
                print(f"erro: {err}")
                return 2
            confirm = lambda c: True
        else:
            confirm = terminal_confirm

        print(run_dir)

        res = execute_run(
            prompt=args.prompt,
            run_dir=run_dir,
            client=cli,
            model=model,
            max_turns=cfg.max_turns,
            cost_cap_usd=cfg.cost_cap_usd,
            confirm=confirm,
            workspace=workspace,
        )

        if runs_dir is not None and Path.cwd().resolve() == runs_dir.resolve():
            ws = run_dir / "ws"
            if ws.is_dir():
                for item in ws.iterdir():
                    dest = Path.cwd() / item.name
                    if not dest.exists() and item.is_file():
                        dest.write_bytes(item.read_bytes())

        if res.final:
            print(res.final)
        print(f"turnos: {res.turns} · custo: US$ {res.cost_usd} · fim: {res.reason}")
        return 0

    if args.command == "task":
        if not args.all and not args.task:
            task_parser.print_help()
            return 1

        cfg = load_config()
        if not cfg.api_key and client is None:
            print("defina OPENROUTER_API_KEY no .env")
            return 2

        model = args.model if args.model is not None else cfg.model
        cli = client if client is not None else OpenRouterClient(api_key=cfg.api_key)

        tasks_root = tasks_dir if tasks_dir is not None else Path("tasks")
        available_tasks = discover_tasks(tasks_root)
        runs_path = runs_dir if runs_dir is not None else Path("runs")

        if args.auto_approve:
            check_auto_approve(runs_path / "check" / "ws", runs_path)
            confirm = lambda c: True
        else:
            confirm = terminal_confirm

        if args.all:
            for task_dir in available_tasks:
                run_dir, res, passed = run_task(
                    task_dir=task_dir,
                    runs_root=runs_path,
                    client=cli,
                    model=model,
                    max_turns=cfg.max_turns,
                    cost_cap_usd=cfg.cost_cap_usd,
                    confirm=confirm,
                )
                status = "pass" if passed else "fail"
                print(f"{task_dir.name}: {status} · turnos: {res.turns} · custo: US$ {res.cost_usd}")
            return 0

        target = args.task
        matched_task: Path | None = None
        for t in available_tasks:
            if t.name == target or t.name.startswith(target):
                matched_task = t
                break
            if target.isdigit() and t.name.startswith(f"{int(target):02d}"):
                matched_task = t
                break

        if matched_task is None:
            print(f"tarefa '{target}' não encontrada")
            return 1

        run_dir, res, passed = run_task(
            task_dir=matched_task,
            runs_root=runs_path,
            client=cli,
            model=model,
            max_turns=cfg.max_turns,
            cost_cap_usd=cfg.cost_cap_usd,
            confirm=confirm,
        )

        status = "pass" if passed else "fail"
        print(f"{status} · turnos: {res.turns} · custo: US$ {res.cost_usd}")
        return 0

    if args.command == "report":
        tasks_root = tasks_dir if tasks_dir is not None else Path("tasks")
        runs_path = runs_dir if runs_dir is not None else Path("runs")

        report_md = build_report(tasks_root, runs_path)
        print(report_md, end="" if report_md.endswith("\n") else "\n")

        runs_path.mkdir(parents=True, exist_ok=True)
        (runs_path / "report.md").write_text(report_md, encoding="utf-8")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
