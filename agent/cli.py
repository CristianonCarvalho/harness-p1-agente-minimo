import argparse
import json
import sys

from agent.client import OpenRouterClient
from agent.config import load_config


def main(argv: list[str] | None = None, client: OpenRouterClient | None = None) -> int:
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
        resp = cli.chat(messages=[{"role": "user", "content": args.prompt}], model=model)
        content = resp["choices"][0]["message"].get("content", "")
        if content:
            print(content)
        usage = resp.get("usage", {})
        print(json.dumps(usage, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
