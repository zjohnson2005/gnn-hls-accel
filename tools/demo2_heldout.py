"""DEMO-2 held-out pin DEMO2_HELDOUT_60 (task AI; frozen before any DEMO-2 run).

30 multi_turn_base + 30 multi_turn_long_context entries that are in no
DEMO-1 pin (DEMO1_BASE_30, DEMO1_LONGCTX_30, DEMO1_LONGCTX_15,
DEMO1_LONGCTX_OBSK1024_15, DEMO1_PAIRED_15). The tuned-profile selection rule
uses sealed limits only, so it uses no entries.

Rule (seed SEED, one random.Random stream in this order):
1. base: sample 30 from the eligible base ids (file order);
2. long_context: strata by the largest gold turn n_ctx in
   analysis/demo1/atlas/multi_turn_long_context_FULL.json above 18,500;
   k = min(jump ids eligible, round(30 x jump share of the whole category))
   (the design's "match the category" where the pool allows); sample k jump
   ids, then 30 - k others.
Entries are written base first, then long_context, each in file order.

  PYTHONPATH=<bfcl-eval 2025.12.17 --no-deps target> \\
    python tools/demo2_heldout.py --data-dir <target>/bfcl_eval/data
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

SEED = 20261014
N_PER_CATEGORY = 30
JUMP_N_CTX = 18_500
OUT = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_HELDOUT_60.json"
DEMO1 = ROOT / "derived" / "h1_hybrid" / "demo1"
EXCLUDE_PINS = (
    "DEMO1_BASE_30",
    "DEMO1_LONGCTX_30",
    "DEMO1_LONGCTX_15",
    "DEMO1_LONGCTX_OBSK1024_15",
    "DEMO1_PAIRED_15",
)
ATLAS_LONG = ROOT / "analysis" / "demo1" / "atlas" / "multi_turn_long_context_FULL.json"
ATLAS_BASE = ROOT / "analysis" / "demo1" / "atlas" / "multi_turn_base_FULL.json"


def excluded() -> dict[str, list[str]]:
    return {
        name: list(
            json.loads((DEMO1 / f"{name}.meta.json").read_text(encoding="utf-8"))["selected"]
        )
        for name in EXCLUDE_PINS
    }


def _largest(atlas: Path) -> dict[str, int]:
    doc = json.loads(atlas.read_text(encoding="utf-8"))
    return {r["entry_id"]: max(t["n_ctx"] for t in r["turns"]) for r in doc["entries"]}


def select(base_ids: list[str], long_ids: list[str]) -> dict[str, Any]:
    """Selection from the two id lists (file order). Pure; no file writes."""
    drop = {i for ids in excluded().values() for i in ids}
    rng = random.Random(SEED)
    base_elig = [i for i in base_ids if i not in drop]
    base_pick = set(rng.sample(base_elig, N_PER_CATEGORY))
    largest = _largest(ATLAS_LONG)
    long_elig = [i for i in long_ids if i not in drop]
    jump = [i for i in long_elig if largest[i] > JUMP_N_CTX]
    other = [i for i in long_elig if largest[i] <= JUMP_N_CTX]
    category_share = sum(1 for v in largest.values() if v > JUMP_N_CTX) / len(largest)
    k = min(len(jump), round(N_PER_CATEGORY * category_share))
    long_pick = set(rng.sample(jump, k)) | set(rng.sample(other, N_PER_CATEGORY - k))
    return {
        "base_eligible": len(base_elig),
        "long_eligible": len(long_elig),
        "long_jump_eligible": len(jump),
        "long_jump_selected": k,
        "long_jump_category_share": round(category_share, 4),
        "long_jump_target": round(N_PER_CATEGORY * category_share),
        "selected_base": [i for i in base_elig if i in base_pick],
        "selected_long": [i for i in long_elig if i in long_pick],
    }


def build(data_dir: Path) -> dict[str, Any]:
    from tools import h1_context_sizing as hcs

    base = hcs.load_entries("multi_turn_base", data_dir)
    long_ = hcs.load_entries("multi_turn_long_context", data_dir)
    sel = select([e["id"] for e in base], [e["id"] for e in long_])
    by_id = {e["id"]: e for e in base + long_}
    entries = [by_id[i] for i in sel["selected_base"] + sel["selected_long"]]
    payload = hcs.entries_bytes(entries)
    sizes = {**_largest(ATLAS_BASE), **_largest(ATLAS_LONG)}
    meta = {
        "kind": "h1_entry_subset",
        "name": "DEMO2_HELDOUT_60",
        "categories": ["multi_turn_base", "multi_turn_long_context"],
        "seed": SEED,
        "n": len(entries),
        "rule": __doc__.split("\n\n")[2].strip(),
        "excluded_pins": excluded(),
        "selection_rule_entries_used": [],
        "data": {
            "bfcl_eval": "2025.12.17",
            "files_sha256": {
                name: hashlib.sha256((data_dir / name).read_bytes()).hexdigest()
                for name in ("BFCL_v4_multi_turn_base.json", "BFCL_v4_multi_turn_long_context.json")
            },
            "check": "this data rebuilds DEMO1_BASE_30 and DEMO1_PAIRED_15 to their pinned sha256",
        },
        **{k: v for k, v in sel.items() if not k.startswith("selected")},
        "selected": sel["selected_base"] + sel["selected_long"],
        "selected_largest_gold_n_ctx": {
            i: sizes[i] for i in sel["selected_base"] + sel["selected_long"]
        },
        "entries_sha256": hashlib.sha256(payload).hexdigest(),
        "note": (
            "d482c621 (H1-3POLICY) ran all 200 multi_turn_base entries; it set trigger rates "
            "in the design, not the selection rule or this pin."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(payload)
    OUT.with_name(OUT.stem + ".meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    meta = build(args.data_dir)
    print(f"PIN {OUT} n={meta['n']} sha256={meta['entries_sha256']}")
    print(
        f"base eligible {meta['base_eligible']}; long eligible {meta['long_eligible']}, "
        f"jump {meta['long_jump_eligible']} -> {meta['long_jump_selected']} selected"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
