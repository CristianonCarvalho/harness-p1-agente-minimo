import sys
from pathlib import Path

if len(sys.argv) < 4:
    sys.exit(1)

ws = Path(sys.argv[1])
final_txt = Path(sys.argv[2])
trace_jsonl = Path(sys.argv[3])

if not final_txt.is_file():
    sys.exit(1)

content = final_txt.read_text(encoding="utf-8")
if "K7-ALFA-29" in content:
    sys.exit(0)

sys.exit(1)
