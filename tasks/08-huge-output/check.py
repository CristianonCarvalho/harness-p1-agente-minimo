import sys
from pathlib import Path

if len(sys.argv) < 4:
    sys.exit(1)

ws = Path(sys.argv[1])
final_txt = Path(sys.argv[2])
trace_jsonl = Path(sys.argv[3])

expected_file = Path(sys.argv[1]).parent / ".expected"
if not expected_file.is_file():
    sys.exit(1)

expected_number = expected_file.read_text(encoding="utf-8").strip()
if not expected_number:
    sys.exit(1)

if not final_txt.is_file():
    sys.exit(1)

final_content = final_txt.read_text(encoding="utf-8")
if expected_number in final_content:
    sys.exit(0)

sys.exit(1)
