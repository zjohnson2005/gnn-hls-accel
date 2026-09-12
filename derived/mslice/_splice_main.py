"""Splice new main()+helpers into affinity_matrix.py after the last pre-main def."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "seam" / "tools" / "affinity_matrix.py"
NEW_TAIL = ROOT / "derived" / "mslice" / "_affinity_matrix_main_tail.py"

text = TARGET.read_text(encoding="utf-8")
idx = text.index("def main(argv:")
prefix = text[:idx]
tail = NEW_TAIL.read_text(encoding="utf-8")
if not tail.startswith("def main"):
    raise SystemExit("tail must start with def main")
TARGET.write_text(prefix + tail, encoding="utf-8", newline="\n")
print(f"wrote {TARGET} bytes={TARGET.stat().st_size}")
print(f"prefix chars={len(prefix)} tail chars={len(tail)}")
