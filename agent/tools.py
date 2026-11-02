from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess


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


def terminal_confirm(cmd: str) -> bool:
    try:
        ans = input(f"$ {cmd}  executar? [y/N] ").strip().lower()
        return ans in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


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
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Executa um comando no shell do sistema operacional dentro do workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Comando shell a ser executado.",
                    },
                },
                "required": ["command"],
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


def _run_command(args: dict, ctx: ToolContext) -> ToolOutput:
    cmd = args["command"]
    if not ctx.confirm(cmd):
        return ToolOutput("error: usuário negou o comando", approved=False)

    ws = ctx.workspace.resolve()
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=ws,
            env={"PATH": os.environ.get("PATH", ""), "HOME": str(ws), "LANG": "C.UTF-8"},
            capture_output=True,
            text=True,
            errors="replace",
            timeout=ctx.timeout_s,
        )
    except subprocess.TimeoutExpired:
        return ToolOutput(f"error: timeout após {ctx.timeout_s:g}s", approved=True)

    stdout = proc.stdout
    raw_stdout = stdout.encode("utf-8")
    if len(raw_stdout) > ctx.out_limit:
        truncated = raw_stdout[: ctx.out_limit].decode("utf-8", errors="replace")
        stdout = f"{truncated}\n[truncado: {len(raw_stdout)} bytes no total]"

    text = f"exit: {proc.returncode}\nstdout:\n{stdout}\nstderr:\n{proc.stderr}"
    return ToolOutput(text, approved=True)


def execute(name: str, args: dict, ctx: ToolContext) -> ToolOutput:
    try:
        if name == "read_file":
            return _read_file(args, ctx)
        elif name == "write_file":
            return _write_file(args, ctx)
        elif name == "run_command":
            return _run_command(args, ctx)
        else:
            return ToolOutput(f"error: ferramenta desconhecida: {name}")
    except ValueError as e:
        if str(e) == "caminho fora do workspace":
            return ToolOutput("error: caminho fora do workspace")
        return ToolOutput(f"error: {type(e).__name__}: {e}")
    except Exception as e:
        return ToolOutput(f"error: {type(e).__name__}: {e}")
