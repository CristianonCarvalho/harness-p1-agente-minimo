from collections.abc import Callable
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from agent.config import DEFAULT_COST_CAP_USD, DEFAULT_MAX_TURNS, DEFAULT_MODEL
from agent.ledger import Ledger, load_pricing
from agent.loop import RunResult, run
from agent.tools import ToolContext


def new_run_dir(
    runs_root: Path,
    label: str,
    now: datetime | None = None,
) -> Path:
    if now is None:
        now = datetime.now()
    ts = now.strftime("%Y%m%d-%H%M%S")
    base_name = f"{ts}-{label}"
    target_dir = runs_root / base_name

    if target_dir.exists():
        counter = 2
        while (runs_root / f"{base_name}-{counter}").exists():
            counter += 1
        target_dir = runs_root / f"{base_name}-{counter}"

    (target_dir / "ws").mkdir(parents=True, exist_ok=True)
    return target_dir


def save_result(run_dir: Path, result: RunResult) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    messages_path = run_dir / "messages.json"
    messages_path.write_text(
        json.dumps(result.messages, indent=2),
        encoding="utf-8",
    )
    final_path = run_dir / "final.txt"
    final_path.write_text(result.final, encoding="utf-8")


def execute_run(
    prompt: str,
    run_dir: Path,
    client: Any,
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    cost_cap_usd: float = DEFAULT_COST_CAP_USD,
    confirm: Callable[[str], bool] | None = None,
    workspace: Path | None = None,
) -> RunResult:
    ws = workspace if workspace is not None else (run_dir / "ws")
    if confirm is not None:
        ctx = ToolContext(workspace=ws, confirm=confirm)
    else:
        ctx = ToolContext(workspace=ws)

    cache_path = run_dir.parent / ".models-cache.json"
    ledger = Ledger(
        run_dir / "trace.jsonl",
        pricing=lambda: load_pricing(client, cache_path),
    )

    result = run(
        prompt=prompt,
        ctx=ctx,
        client=client,
        ledger=ledger,
        model=model,
        max_turns=max_turns,
        cost_cap_usd=cost_cap_usd,
    )
    save_result(run_dir, result)
    return result
