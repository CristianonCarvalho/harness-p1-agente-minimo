import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

from agent.client import OpenRouterClient
from agent.config import load_config
from agent.ledger import Ledger, load_pricing


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

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
