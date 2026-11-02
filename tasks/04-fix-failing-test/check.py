import hashlib
import subprocess
import sys
from pathlib import Path

if len(sys.argv) < 4:
    sys.exit(1)

ws = Path(sys.argv[1])
final_txt = Path(sys.argv[2])
trace_jsonl = Path(sys.argv[3])

test_file = ws / "test_calc.py"
if not test_file.is_file():
    sys.exit(1)

ORIGINAL_HASH = "264d9616854a79ffff07ae5a2ed586ac331d318a80182e712c108dfa95845ec8"
current_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
if current_hash != ORIGINAL_HASH:
    sys.exit(1)

proc = subprocess.run(
    [sys.executable, "-m", "unittest"],
    cwd=ws,
    capture_output=True,
)

if proc.returncode == 0:
    sys.exit(0)
sys.exit(1)
