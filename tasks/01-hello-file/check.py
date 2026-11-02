import sys
from pathlib import Path

if len(sys.argv) < 4:
    sys.exit(1)

ws = Path(sys.argv[1])
final_txt = Path(sys.argv[2])
trace_jsonl = Path(sys.argv[3])

hello_file = ws / "hello.txt"
if not hello_file.is_file():
    sys.exit(1)

content = hello_file.read_text(encoding="utf-8")
if content in ("Olá, agente!", "Olá, agente!\n", "Olá, agente!\r\n"):
    sys.exit(0)
else:
    sys.exit(1)
