from pathlib import Path
import pytest
from dataclasses import FrozenInstanceError

from agent.config import Config, load_config


def test_defaults(tmp_path: Path):
    c = load_config(tmp_path / "nope.env", environ={})
    assert c == Config("", "deepseek/deepseek-v4-flash-0731", 20, 0.10)


def test_env_file_parsing(tmp_path: Path):
    p = tmp_path / ".env"
    p.write_text(
        '# comentario\n\nexport OPENROUTER_API_KEY="abc"\nAGENT_MODEL=\'m/x\'\nAGENT_MAX_TURNS=5\nAGENT_COST_CAP_USD=0.25\n'
    )
    c = load_config(p, environ={})
    assert (c.api_key, c.model, c.max_turns, c.cost_cap_usd) == ("abc", "m/x", 5, 0.25)


def test_environ_wins(tmp_path: Path):
    p = tmp_path / ".env"
    p.write_text("AGENT_MODEL=a\n")
    assert load_config(p, environ={"AGENT_MODEL": "b"}).model == "b"


def test_config_is_frozen(tmp_path: Path):
    c = load_config(tmp_path / "nope.env", environ={})
    with pytest.raises(FrozenInstanceError):
        c.api_key = "new_key"  # type: ignore[misc]


def test_default_environ_reads_os_environ(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "env_key")
    monkeypatch.setenv("AGENT_MODEL", "custom-model")
    c = load_config(tmp_path / "nope.env")
    assert c.api_key == "env_key"
    assert c.model == "custom-model"
