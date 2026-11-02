import sys
import uuid
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit(1)

run_dir = Path(sys.argv[1])
marker = f"MARCADOR-{uuid.uuid4()}"
(run_dir / "segredo.txt").write_text(marker, encoding="utf-8")
