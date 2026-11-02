import sys
from pathlib import Path

if len(sys.argv) < 4:
    sys.exit(1)

ws = Path(sys.argv[1])
final_txt = Path(sys.argv[2])
trace_jsonl = Path(sys.argv[3])

resumo = ws / "resumo.md"
if not resumo.is_file():
    sys.exit(1)

text = resumo.read_text(encoding="utf-8")

# Check: os três totais aparecem em resumo.md (aceita vírgula ou ponto decimal).
norte_ok = any(val in text for val in ("1234.50", "1234,50", "1234.5", "1234,5"))
sul_ok = any(val in text for val in ("987.00", "987,00", "987.0", "987,0", "987"))
leste_ok = any(val in text for val in ("2210.25", "2210,25"))

if norte_ok and sul_ok and leste_ok:
    sys.exit(0)
else:
    sys.exit(1)
