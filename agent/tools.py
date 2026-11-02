from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolContext:
    workspace: Path
    confirm: Callable[[str], bool] = lambda cmd: False
    timeout_s: float = 30.0
    read_limit: int = 20_000
    out_limit: int = 10_000

    def __post_init__(self) -> None:
        if not isinstance(self.workspace, Path):
            self.workspace = Path(self.workspace)


@dataclass
class ToolOutput:
    text: str
    approved: bool | None = None


TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lê o conteúdo de um arquivo dentro do workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Caminho do arquivo relativo ao workspace.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Escreve conteúdo em um arquivo dentro do workspace, criando diretórios se necessário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Caminho do arquivo relativo ao workspace.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Conteúdo a ser escrito no arquivo.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
]


def resolve_inside(ctx: ToolContext, path: str) -> Path:
    ws = ctx.workspace.resolve()
    target = (ws / path).resolve()
    if not target.is_relative_to(ws):
        raise ValueError("caminho fora do workspace")
    return target


def _read_file(args: dict, ctx: ToolContext) -> ToolOutput:
    path = args["path"]
    target = resolve_inside(ctx, path)
    if not target.exists():
        return ToolOutput(f"error: arquivo não encontrado: {path}")

    raw = target.read_bytes()
    if len(raw) > ctx.read_limit:
        truncated = raw[: ctx.read_limit].decode("utf-8", errors="replace")
        return ToolOutput(f"{truncated}\n[truncado: {len(raw)} bytes no total]")
    return ToolOutput(raw.decode("utf-8", errors="replace"))


def _write_file(args: dict, ctx: ToolContext) -> ToolOutput:
    path = args["path"]
    content = args["content"]
    target = resolve_inside(ctx, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    target.write_bytes(data)
    return ToolOutput(f"ok: {len(data)} bytes escritos em {path}")


def execute(name: str, args: dict, ctx: ToolContext) -> ToolOutput:
    try:
        if name == "read_file":
            return _read_file(args, ctx)
        elif name == "write_file":
            return _write_file(args, ctx)
        else:
            return ToolOutput(f"error: ferramenta desconhecida: {name}")
    except ValueError as e:
        if str(e) == "caminho fora do workspace":
            return ToolOutput("error: caminho fora do workspace")
        return ToolOutput(f"error: {type(e).__name__}: {e}")
    except Exception as e:
        return ToolOutput(f"error: {type(e).__name__}: {e}")
