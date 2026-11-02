import subprocess
import sys
from pathlib import Path

if len(sys.argv) < 4:
    sys.exit(1)

ws = Path(sys.argv[1])
final_txt = Path(sys.argv[2])
trace_jsonl = Path(sys.argv[3])

test_file = ws / "test_utils.py"
if not test_file.is_file():
    sys.exit(1)

proc = subprocess.run(
    [sys.executable, "-m", "unittest"],
    cwd=ws,
    capture_output=True,
)

if proc.returncode == 0:
    sys.exit(0)
sys.exit(1)
