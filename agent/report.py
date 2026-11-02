import json
from pathlib import Path
import re
from typing import Any

from agent.tasks import discover_tasks


def read_prediction(task_dir: Path) -> str | None:
    pred_file = task_dir / "prediction.md"
    if not pred_file.is_file():
        return None
    try:
        content = pred_file.read_text(encoding="utf-8")
    except OSError:
        return None

    for line in content.splitlines():
        line = line.strip()
        lower = line.lower()
        if lower.startswith("previsão:") or lower.startswith("previsao:"):
            parts = line.split(":", 1)
            val = parts[1].strip().lower()
            if "pass" in val and "fail" in val:
                return None
            if val == "pass" or val.startswith("pass"):
                return "pass"
            if val == "fail" or val.startswith("fail"):
                return "fail"
            return None

    stripped = content.strip().lower()
    if stripped == "pass":
        return "pass"
    if stripped == "fail":
        return "fail"
    return None


def latest_run(runs_root: Path, task_name: str) -> Path | None:
    if not runs_root.is_dir():
        return None

    matching: list[Path] = []
    pattern = re.compile(rf"(^|[-_]){re.escape(task_name)}(-\d+)?$")
    for d in runs_root.iterdir():
        if not d.is_dir():
            continue
        if d.name == task_name or pattern.search(d.name):
            matching.append(d)

    if not matching:
        prefix_pattern = re.compile(rf"[-_]{re.escape(task_name)}[-_]")
        for d in runs_root.iterdir():
            if d.is_dir() and prefix_pattern.search(d.name):
                matching.append(d)

    if not matching:
        return None

    return max(matching, key=lambda p: p.name)


def check_auto_approve(workspace: Path, runs_root: Path) -> None:
    resolved_ws = workspace.resolve()
    resolved_runs = runs_root.resolve()
    if resolved_ws == resolved_runs or not resolved_ws.is_relative_to(resolved_runs):
        raise ValueError(
            f"workspace '{workspace}' não está dentro de '{runs_root}' para auto-aprovação"
        )


def build_report(tasks_root: Path, runs_root: Path) -> str:
    tasks = discover_tasks(tasks_root)

    rows: list[str] = []
    total_evaluated = 0
    correct_predictions = 0
    unpredicted: list[str] = []
    total_cost = 0.0
    total_estimated_lines = 0
    executed_count = 0

    for task_dir in tasks:
        task_name = task_dir.name
        pred = read_prediction(task_dir)
        previsto_str = pred if pred is not None else "—"

        run_dir = latest_run(runs_root, task_name)
        trace_path = run_dir / "trace.jsonl" if run_dir else None

        real_str = "—"
        turnos_str = "—"
        tokens_str = "—"
        custo_str = "—"
        motivo_str = "—"
        acertou_str = "—"

        if trace_path and trace_path.is_file():
            executed_count += 1
            turns = 0
            reason = "—"
            check_val = None
            tokens_in = 0
            tokens_out = 0
            cost_usd = 0.0
            found_end = False

            try:
                for line in trace_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    event: dict[str, Any] = json.loads(line)
                    t = event.get("t")
                    if t == "llm":
                        tokens_in += int(event.get("prompt_tokens") or 0)
                        tokens_out += int(event.get("completion_tokens") or 0)
                        if event.get("cost_source") == "estimated":
                            total_estimated_lines += 1
                        if not found_end:
                            cost_usd += float(event.get("cost_usd") or 0.0)
                        t_turn = int(event.get("turn") or 0)
                        if t_turn > turns:
                            turns = t_turn
                    elif t == "end":
                        found_end = True
                        turns = int(event.get("turns") or turns)
                        reason = str(event.get("reason") or "—")
                        if "check" in event:
                            check_val = str(event["check"])
                        if "cost_usd" in event:
                            cost_usd = float(event["cost_usd"] or 0.0)
            except Exception:
                pass

            if check_val in ("pass", "fail"):
                real_str = check_val

            turnos_str = str(turns)
            tokens_str = f"{tokens_in}/{tokens_out}"
            custo_str = f"{cost_usd:.4f}"
            motivo_str = reason
            total_cost += cost_usd

        if pred is not None:
            if real_str in ("pass", "fail"):
                total_evaluated += 1
                if pred == real_str:
                    acertou_str = "sim"
                    correct_predictions += 1
                else:
                    acertou_str = "não"
            else:
                acertou_str = "—"
        else:
            unpredicted.append(task_name)
            acertou_str = "—"

        rows.append(
            f"| {task_name} | {previsto_str} | {real_str} | {acertou_str} | {turnos_str} | {tokens_str} | {custo_str} | {motivo_str} |"
        )

    if total_evaluated > 0:
        pct = (correct_predictions / total_evaluated) * 100
        acerto_str = f"Acerto das previsões: {correct_predictions}/{total_evaluated} ({pct:.0f}%)"
    else:
        acerto_str = "Acerto das previsões: 0/0 (0%)"

    sem_prev_list = ", ".join(unpredicted) if unpredicted else "nenhuma"
    avg_cost = (total_cost / executed_count) if executed_count > 0 else 0.0

    lines = [
        "| tarefa | previsto | real | acertou? | turnos | tokens (in/out) | custo US$ | motivo do fim |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "## Rodapé",
        "",
        f"- {acerto_str}",
        f"- Sem previsão: {sem_prev_list}",
        f"- Custo médio: US$ {avg_cost:.4f}",
        f"- Custo total: US$ {total_cost:.4f}",
        f"- Linhas com custo estimado (estimated): {total_estimated_lines}",
    ]
    return "\n".join(lines) + "\n"
