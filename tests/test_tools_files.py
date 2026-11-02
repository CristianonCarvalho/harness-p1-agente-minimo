from pathlib import Path
import pytest

from agent.tools import (
    TOOL_SCHEMAS,
    ToolContext,
    ToolOutput,
    execute,
    resolve_inside,
)


def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(workspace=tmp_path)


def test_write_then_read(tmp_path: Path) -> None:
    res_w = execute("write_file", {"path": "a/b.txt", "content": "olá"}, ctx(tmp_path))
    assert res_w.text.startswith("ok: ")
    res_r = execute("read_file", {"path": "a/b.txt"}, ctx(tmp_path))
    assert res_r.text == "olá"


@pytest.mark.parametrize("p", ["../x", "/etc/passwd"])
def test_outside_rejected(tmp_path: Path, p: str) -> None:
    assert execute("read_file", {"path": p}, ctx(tmp_path)).text == "error: caminho fora do workspace"


def test_symlink_outside_rejected(tmp_path: Path) -> None:
    (tmp_path / "ws").mkdir()
    (tmp_path / "s.txt").write_text("x")
    (tmp_path / "ws" / "l").symlink_to(tmp_path / "s.txt")
    assert execute("read_file", {"path": "l"}, ToolContext(tmp_path / "ws")).text.startswith("error:")


def test_truncation(tmp_path: Path) -> None:
    (tmp_path / "big").write_text("x" * 30_000)
    out = execute("read_file", {"path": "big"}, ctx(tmp_path)).text
    assert out.endswith("[truncado: 30000 bytes no total]") and len(out) < 20_100


def test_binary_does_not_crash(tmp_path: Path) -> None:
    (tmp_path / "b").write_bytes(b"\xff\xfe\x00")
    assert not execute("read_file", {"path": "b"}, ctx(tmp_path)).text.startswith("error:")


def test_file_not_found(tmp_path: Path) -> None:
    out = execute("read_file", {"path": "missing.txt"}, ctx(tmp_path)).text
    assert out == "error: arquivo não encontrado: missing.txt"


def test_unknown_tool(tmp_path: Path) -> None:
    out = execute("magic_tool", {}, ctx(tmp_path)).text
    assert out == "error: ferramenta desconhecida: magic_tool"


def test_tool_schemas() -> None:
    assert isinstance(TOOL_SCHEMAS, list)
    schemas = {s["function"]["name"]: s["function"] for s in TOOL_SCHEMAS}
    assert "read_file" in schemas
    assert "write_file" in schemas

    rf = schemas["read_file"]
    assert rf["parameters"]["type"] == "object"
    assert rf["parameters"]["required"] == ["path"]
    assert "path" in rf["parameters"]["properties"]
    assert rf["description"]

    wf = schemas["write_file"]
    assert wf["parameters"]["type"] == "object"
    assert wf["parameters"]["required"] == ["path", "content"]
    assert "path" in wf["parameters"]["properties"]
    assert "content" in wf["parameters"]["properties"]
    assert wf["description"]


def test_write_outside_rejected(tmp_path: Path) -> None:
    out = execute("write_file", {"path": "../fora.txt", "content": "x"}, ctx(tmp_path)).text
    assert out == "error: caminho fora do workspace"


def test_resolve_inside_direct(tmp_path: Path) -> None:
    c = ctx(tmp_path)
    with pytest.raises(ValueError, match="caminho fora do workspace"):
        resolve_inside(c, "../out.txt")

    with pytest.raises(ValueError, match="caminho fora do workspace"):
        resolve_inside(c, "/etc/passwd")

    resolved = resolve_inside(c, "sub/dir/file.txt")
    assert resolved == (tmp_path.resolve() / "sub/dir/file.txt")


def test_custom_read_limit(tmp_path: Path) -> None:
    (tmp_path / "test.txt").write_text("abcdefghijklmnopqrstuvwxyz")
    c = ToolContext(workspace=tmp_path, read_limit=10)
    out = execute("read_file", {"path": "test.txt"}, c).text
    assert out.endswith("[truncado: 26 bytes no total]")
    assert out.startswith("abcdefghij")


def test_missing_args(tmp_path: Path) -> None:
    out = execute("read_file", {}, ctx(tmp_path)).text
    assert out.startswith("error: KeyError:")


def test_symlink_outside_write_rejected(tmp_path: Path) -> None:
    (tmp_path / "ws").mkdir()
    (tmp_path / "outside.txt").write_text("orig")
    (tmp_path / "ws" / "l").symlink_to(tmp_path / "outside.txt")
    out = execute("write_file", {"path": "l", "content": "novo"}, ToolContext(tmp_path / "ws")).text
    assert out == "error: caminho fora do workspace"
    assert (tmp_path / "outside.txt").read_text() == "orig"


def test_read_directory(tmp_path: Path) -> None:
    (tmp_path / "dir").mkdir()
    out = execute("read_file", {"path": "dir"}, ctx(tmp_path)).text
    assert out.startswith("error: IsADirectoryError:")

