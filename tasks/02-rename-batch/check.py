import sys
from pathlib import Path

if len(sys.argv) < 4:
    sys.exit(1)

ws = Path(sys.argv[1])
final_txt = Path(sys.argv[2])
trace_jsonl = Path(sys.argv[3])

# Check: nenhum .txt; os .md com o mesmo conteúdo.
txt_files = list(ws.rglob("*.txt"))
if txt_files:
    sys.exit(1)

expected = {
    ws / "a.md": "Arquivo A\n",
    ws / "b.md": "Arquivo B\n",
    ws / "notas" / "c.md": "Arquivo C em notas\n",
}

for path, expected_content in expected.items():
    if not path.is_file():
        sys.exit(1)
    if path.read_text(encoding="utf-8") != expected_content:
        sys.exit(1)

sys.exit(0)
