import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

from agent.client import OpenRouterClient
from agent.config import load_config
from agent.ledger import Ledger, load_pricing
from agent.runs import execute_run, new_run_dir
from agent.tools import terminal_confirm


def main(
    argv: list[str] | None = None,
    client: OpenRouterClient | None = None,
    runs_dir: Path | None = None,
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
        print(run_dir)

        workspace = Path(args.workspace) if args.workspace is not None else None

        res = execute_run(
            prompt=args.prompt,
            run_dir=run_dir,
            client=cli,
            model=model,
            max_turns=cfg.max_turns,
            cost_cap_usd=cfg.cost_cap_usd,
            confirm=terminal_confirm,
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

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
