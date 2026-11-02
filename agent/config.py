from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"
DEFAULT_MAX_TURNS = 20
DEFAULT_COST_CAP_USD = 0.10


@dataclass(frozen=True)
class Config:
    api_key: str = ""
    model: str = DEFAULT_MODEL
    max_turns: int = DEFAULT_MAX_TURNS
    cost_cap_usd: float = DEFAULT_COST_CAP_USD


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}

    parsed: dict[str, str] = {}
    content = path.read_text(encoding="utf-8")
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        parsed[key] = val
    return parsed


def load_config(
    env_path: Path = Path(".env"),
    environ: Mapping[str, str] | None = None,
) -> Config:
    file_vars = _parse_env_file(env_path)
    env = os.environ if environ is None else environ

    merged = dict(file_vars)
    for k, v in env.items():
        merged[k] = v

    api_key = merged.get("OPENROUTER_API_KEY", "")

    model = merged.get("AGENT_MODEL")
    if not model:
        model = DEFAULT_MODEL

    raw_max_turns = merged.get("AGENT_MAX_TURNS")
    max_turns = int(raw_max_turns) if raw_max_turns is not None and str(raw_max_turns).strip() != "" else DEFAULT_MAX_TURNS

    raw_cost_cap = merged.get("AGENT_COST_CAP_USD")
    cost_cap = float(raw_cost_cap) if raw_cost_cap is not None and str(raw_cost_cap).strip() != "" else DEFAULT_COST_CAP_USD

    return Config(
        api_key=api_key,
        model=model,
        max_turns=max_turns,
        cost_cap_usd=cost_cap,
    )
