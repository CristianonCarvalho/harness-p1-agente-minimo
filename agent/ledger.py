import json
from pathlib import Path
from typing import Any, Callable


def load_pricing(client: Any, cache_path: Path) -> dict[str, tuple[float, float]]:
    if cache_path.exists():
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        try:
            raw = client.models()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        except Exception:
            return {}

    result: dict[str, tuple[float, float]] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and "id" in item:
                pricing = item.get("pricing") or {}
                prompt_p = float(pricing.get("prompt") or 0.0)
                completion_p = float(pricing.get("completion") or 0.0)
                result[item["id"]] = (prompt_p, completion_p)
    elif isinstance(raw, dict):
        if "data" in raw and isinstance(raw["data"], list):
            for item in raw["data"]:
                if isinstance(item, dict) and "id" in item:
                    pricing = item.get("pricing") or {}
                    prompt_p = float(pricing.get("prompt") or 0.0)
                    completion_p = float(pricing.get("completion") or 0.0)
                    result[item["id"]] = (prompt_p, completion_p)
        else:
            for k, v in raw.items():
                if isinstance(v, (list, tuple)) and len(v) == 2:
                    result[k] = (float(v[0]), float(v[1]))
                elif isinstance(v, dict):
                    result[k] = (float(v.get("prompt") or 0.0), float(v.get("completion") or 0.0))
    return result


class Ledger:
    def __init__(
        self,
        path: Path,
        pricing: Callable[[], dict[str, tuple[float, float]]] | None = None,
    ) -> None:
        self.path = path
        self.pricing = pricing
        self._pricing_table: dict[str, tuple[float, float]] | None = None
        self._total_cost: float = 0.0
        self.last_cost_source: str = ""

    @property
    def total_cost(self) -> float:
        return self._total_cost

    def _append(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def llm(self, turn: int, model: str, response: dict, latency_ms: int) -> float:
        usage = response.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or 0
        details = usage.get("prompt_tokens_details") or {}
        cached_tokens = details.get("cached_tokens") or 0

        choices = response.get("choices") or []
        finish_reason = choices[0].get("finish_reason") if choices else None

        if "cost" in usage and usage["cost"] is not None:
            cost_usd = float(usage["cost"])
            cost_source = "measured"
        else:
            if self._pricing_table is None and self.pricing is not None:
                try:
                    self._pricing_table = self.pricing()
                except Exception:
                    self._pricing_table = {}
            table = self._pricing_table or {}
            if model in table:
                prompt_price, completion_price = table[model]
                cost_usd = prompt_tokens * prompt_price + completion_tokens * completion_price
                cost_source = "estimated"
            else:
                cost_usd = 0.0
                cost_source = "unknown"

        self._total_cost += cost_usd
        self.last_cost_source = cost_source

        record = {
            "t": "llm",
            "turn": turn,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
            "cost_usd": cost_usd,
            "cost_source": cost_source,
            "latency_ms": latency_ms,
            "finish_reason": finish_reason,
        }
        self._append(record)
        return cost_usd

    def tool(
        self,
        turn: int,
        name: str,
        args: dict,
        approved: bool | None,
        result: str,
        ms: int,
    ) -> None:
        result_head = result[:500]
        result_bytes = len(result.encode("utf-8"))
        record = {
            "t": "tool",
            "turn": turn,
            "name": name,
            "args": args,
            "approved": approved,
            "result_head": result_head,
            "result_bytes": result_bytes,
            "ms": ms,
        }
        self._append(record)

    def dropped(self, turn: int, count: int) -> None:
        record = {
            "t": "dropped",
            "turn": turn,
            "count": count,
        }
        self._append(record)

    def end(self, reason: str, turns: int, check: str | None = None) -> None:
        record: dict[str, Any] = {
            "t": "end",
            "reason": reason,
            "turns": turns,
            "cost_usd": self.total_cost,
        }
        if check is not None:
            record["check"] = check
        self._append(record)
