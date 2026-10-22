"""DEMO2_CALIB_30: the Task BE calibration pin (frozen before any run it governs).

15 multi_turn_base + 15 multi_turn_long_context entries sampled from DEMO2_CONFIRM_200
(one random.Random(SEED) stream: base first, then long; each written in CONFIRM_200 order).
CONFIRM_200 has 0 overlap with DEMO2_HELDOUT_60 / _B and the DEMO-1 pins, so neither does
this pin. Router score thresholds and the P vs P' rule are fixed on it, never on held-out.

  python tools/demo2_be_pins.py
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEED = 20261022
SRC = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_CONFIRM_200.json"
OUT = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_CALIB_30.json"


def select(ids: list[str]) -> list[str]:
    rng = random.Random(SEED)
    base = [i for i in ids if i.startswith("multi_turn_base_")]
    long_ = [i for i in ids if i.startswith("multi_turn_long_context_")]
    pick = set(rng.sample(base, 15)) | set(rng.sample(long_, 15))
    return [i for i in ids if i in pick]


def main() -> int:
    from tools import h1_context_sizing as hcs

    src = json.loads(SRC.read_text(encoding="utf-8"))
    by_id = {str(e["id"]): e for e in src}
    sel = select([str(e["id"]) for e in src])
    payload = hcs.entries_bytes([by_id[i] for i in sel])
    sha = hashlib.sha256(payload).hexdigest()
    OUT.write_bytes(payload)
    meta = {
        "kind": "h1_entry_subset",
        "name": "DEMO2_CALIB_30",
        "n": len(sel),
        "seed": SEED,
        "source_pin": "DEMO2_CONFIRM_200 sha256 " + hashlib.sha256(SRC.read_bytes()).hexdigest(),
        "rule": __doc__.split("\n\n")[1].strip(),
        "selected": sel,
        "entries_sha256": sha,
    }
    OUT.with_name("DEMO2_CALIB_30.meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    print("DEMO2_CALIB_30", sha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
