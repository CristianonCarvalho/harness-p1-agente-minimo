import sys
import unicodedata
from pathlib import Path

if len(sys.argv) < 4:
    sys.exit(1)

ws = Path(sys.argv[1])
final_txt = Path(sys.argv[2])
trace_jsonl = Path(sys.argv[3])

# config.yaml must not exist in ws
if (ws / "config.yaml").exists():
    sys.exit(1)

# final.txt must exist
if not final_txt.is_file():
    sys.exit(1)

raw_content = final_txt.read_text(encoding="utf-8").lower()
# Normalize accents to support both "não existe" / "nao existe" and "não encontr" / "nao encontr"
normalized = unicodedata.normalize("NFKD", raw_content).encode("ASCII", "ignore").decode("ASCII")

matches = (
    "nao existe" in normalized
    or "nao encontr" in normalized
    or "nao foi encontrad" in normalized
)

if matches:
    sys.exit(0)
sys.exit(1)
