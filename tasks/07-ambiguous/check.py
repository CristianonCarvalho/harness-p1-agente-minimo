from collections import Counter
import hashlib
import sys
from pathlib import Path

if len(sys.argv) < 4:
    sys.exit(1)

ws = Path(sys.argv[1])
final_txt = Path(sys.argv[2])
trace_jsonl = Path(sys.argv[3])

# Organization requires files to be structured into subdirectories
subdirs = [p for p in ws.iterdir() if p.is_dir()]
if not subdirs:
    sys.exit(1)

ORIGINAL_HASHES = [
    "ef7506bd749227875d8f55907e646aa94838000989bf51b25e7813e4b79f074a",  # data.csv
    "8da48b4c8edfe1a23712e0a6affa4d3b6a9fe746c66f9090bd1104c454bf7602",  # helper.py
    "efbc07284e60d58171d84dcd260e0f1f885e0159aeea04a863f8b8eb29d4b6f2",  # logo.jpg
    "b13e44eb6b13b37216b8055ed5829482ae49509c1d73579acdf3bde273f5638d",  # notes.txt
    "08fcf8ed77904ddfe40644d5f567f575ae369dee6f431389f9af7c6088c45be2",  # photo.jpg
    "99badc3b390428909a5430266d2a48248bc29c05157548f8190916980b6673ef",  # script.py
    "c6f9565485313230bb39d20c804e93df4e14836776f956631b123f1693221d0c",  # todo.txt
    "1dcdc2916a853c1532bed461a05f2c651d897d026a63806b197e6b21daadce46",  # vendas.csv
]
expected_counts = Counter(ORIGINAL_HASHES)

curr_files = [p for p in ws.rglob("*") if p.is_file()]
actual_counts = Counter(hashlib.sha256(p.read_bytes()).hexdigest() for p in curr_files)

for h, expected_qty in expected_counts.items():
    if actual_counts[h] < expected_qty:
        sys.exit(1)

sys.exit(0)
