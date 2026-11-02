import random
import sys
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit(1)

run_dir = Path(sys.argv[1])
ws = run_dir / "ws"
ws.mkdir(parents=True, exist_ok=True)

rng = random.Random(42)
error_count = 0
lines = []
other_levels = ["INFO", "DEBUG", "WARNING"]

for i in range(50000):
    if rng.random() < 0.03:
        level = "ERROR"
        error_count += 1
        msg = f"2026-11-02 10:00:{i % 60:02d} [{level}] Ocorreu uma falha na requisicao {i}\n"
    else:
        level = rng.choice(other_levels)
        msg = f"2026-11-02 10:00:{i % 60:02d} [{level}] Operacao concluida normalmente no evento {i}\n"
    lines.append(msg)

(ws / "app.log").write_text("".join(lines), encoding="utf-8")
(run_dir / ".expected").write_text(str(error_count), encoding="utf-8")
