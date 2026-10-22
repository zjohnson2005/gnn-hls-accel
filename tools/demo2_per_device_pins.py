"""Entry pins for the per-device ladder (Task BC addendum 2; frozen before any run).

CONFIRM_200 (R6 and the 2x2): 100 multi_turn_base + 100 multi_turn_long_context
entries that are in none of DEMO2_HELDOUT_60, DEMO2_HELDOUT_60_B and the DEMO-1
pins (DEMO1_BASE_30, DEMO1_LONGCTX_30, DEMO1_LONGCTX_15,
DEMO1_LONGCTX_OBSK1024_15, DEMO1_PAIRED_15). The DEMO-1 pins are the entries
that motivated u4 (P8: BASE_30, LONGCTX_30) and prompt lookup (P4: BASE_30), so
they are out. Rule: one random.Random(SEED) stream; sample 100 eligible base ids,
then 100 eligible long ids; each written in file order, base first.

GROWTH_10 (R5): the 10 DEMO1_LONGCTX_30 entries with the largest step prompt
any T2S arm A local-only run reached (analysis/demo2_pilots/BB/
context_over_limit.json: 1a634610, daa6c026; entry 123 from 8af10211's
87,392-98,165, which cddcd9fd confirmed); ties by entry id. Mechanism rung only
(arm A failure type under KV caps), so motivating entries are allowed.

  PYTHONPATH=<bfcl unpacked> python tools/demo2_per_device_pins.py --data-dir <unpacked>/bfcl_eval/data
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEED = 20261021
OUT_DIR = ROOT / "derived" / "h1_hybrid" / "demo2"
DEMO1 = ROOT / "derived" / "h1_hybrid" / "demo1"
EXCLUDE = (
    DEMO1 / "DEMO1_BASE_30.meta.json",
    DEMO1 / "DEMO1_LONGCTX_30.meta.json",
    DEMO1 / "DEMO1_LONGCTX_15.meta.json",
    DEMO1 / "DEMO1_LONGCTX_OBSK1024_15.meta.json",
    DEMO1 / "DEMO1_PAIRED_15.meta.json",
    OUT_DIR / "DEMO2_HELDOUT_60.meta.json",
    OUT_DIR / "DEMO2_HELDOUT_60_B.meta.json",
)
COL = ROOT / "analysis" / "demo2_pilots" / "BB" / "context_over_limit.json"
T2S_ARM_A_RUNS = ("1a634610", "daa6c026")
E123 = "multi_turn_long_context_123"
E123_MAX = 98_165  # cddcd9fd step 20 (8af10211 reached 89,660 before its watchdog)


def excluded_ids() -> set[str]:
    out: set[str] = set()
    for p in EXCLUDE:
        out.update(json.loads(p.read_text(encoding="utf-8"))["selected"])
    return out


def select_confirm(base_ids: list[str], long_ids: list[str]) -> dict[str, list[str]]:
    drop = excluded_ids()
    rng = random.Random(SEED)
    be = [i for i in base_ids if i not in drop]
    le = [i for i in long_ids if i not in drop]
    bp = set(rng.sample(be, 100))
    lp = set(rng.sample(le, 100))
    return {
        "base_eligible": be,
        "long_eligible": le,
        "selected": [i for i in be if i in bp] + [i for i in le if i in lp],
    }


def select_growth() -> list[tuple[str, int]]:
    pin = json.loads((DEMO1 / "DEMO1_LONGCTX_30.meta.json").read_text(encoding="utf-8"))["selected"]
    doc = json.loads(COL.read_text(encoding="utf-8"))
    best: dict[str, int] = {}
    for r in doc["runs"]:
        if not any(rid in str(r.get("dir")) for rid in T2S_ARM_A_RUNS):
            continue
        for e in r.get("entries") or []:
            best[e["entry_id"]] = max(best.get(e["entry_id"], 0), int(e["max_prompt"]))
    best[E123] = max(best.get(E123, 0), E123_MAX)
    ranked = sorted(((i, best.get(i, 0)) for i in pin), key=lambda x: (-x[1], x[0]))
    return ranked[:10]


def _write(name: str, entries: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    from tools import h1_context_sizing as hcs

    payload = hcs.entries_bytes(entries)
    sha = hashlib.sha256(payload).hexdigest()
    (OUT_DIR / f"{name}.json").write_bytes(payload)
    meta = {**meta, "name": name, "n": len(entries), "entries_sha256": sha}
    (OUT_DIR / f"{name}.meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    return sha


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    from tools import h1_context_sizing as hcs

    base = hcs.load_entries("multi_turn_base", a.data_dir)
    long_ = hcs.load_entries("multi_turn_long_context", a.data_dir)
    by_id = {e["id"]: e for e in base + long_}
    sel = select_confirm([e["id"] for e in base], [e["id"] for e in long_])
    files = {
        n: hashlib.sha256((a.data_dir / n).read_bytes()).hexdigest()
        for n in ("BFCL_v4_multi_turn_base.json", "BFCL_v4_multi_turn_long_context.json")
    }
    common = {
        "kind": "h1_entry_subset",
        "categories": ["multi_turn_base", "multi_turn_long_context"],
        "seed": SEED,
        "data": {"bfcl_eval": "2025.12.17", "files_sha256": files},
        "excluded_pins": [str(p.relative_to(ROOT)) for p in EXCLUDE],
    }
    s1 = _write(
        "DEMO2_CONFIRM_200",
        [by_id[i] for i in sel["selected"]],
        {
            **common,
            "rule": __doc__.split("\n\n")[1].strip(),
            "base_eligible": len(sel["base_eligible"]),
            "long_eligible": len(sel["long_eligible"]),
            "selected": sel["selected"],
        },
    )
    g = select_growth()
    s2 = _write(
        "DEMO2_GROWTH_10",
        [by_id[i] for i, _ in sorted(g, key=lambda x: int(x[0].rsplit("_", 1)[1]))],
        {
            **common,
            "categories": ["multi_turn_long_context"],
            "rule": __doc__.split("\n\n")[2].strip(),
            "selected": sorted((i for i, _ in g), key=lambda x: int(x.rsplit("_", 1)[1])),
            "observed_max_prompt": dict(g),
        },
    )
    print("DEMO2_CONFIRM_200", s1)
    print("DEMO2_GROWTH_10", s2, g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
