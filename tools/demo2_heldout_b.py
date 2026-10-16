"""DEMO-2 second held-out pin (Task AS, 2026-10-16): reserved for one SEARCH confirmation run.

Target: DEMO2_HELDOUT_60_B = 30 multi_turn_base + 30 multi_turn_long_context,
disjoint from every DEMO-1 pin, DEMO2_HELDOUT_60, the W-3 pin and every
entry the pilots use (pilots use DEMO-1 pins only,
docs/amendments/DEMO2_PILOTS_2026-10-16.md).

Eligibility found 2026-10-16:
- multi_turn_base: 0 eligible. The W-3 pin is all 200 multi_turn_base
  entries (d482c621 ran them), so no base entry is disjoint from it. The
  base half is BLOCKED until Zach picks a rule (proposals in the meta file);
  nothing is borrowed from another pin.
- multi_turn_long_context: 133 eligible, but 0 of the 39 entries with a gold
  turn above 18,500 tokens remain (DEMO-1 pins used 36, DEMO2_HELDOUT_60 used
  3). The long half is sampled from the 133 without the jump stratum.

Rule (seed SEED, one random.Random stream): sample 30 from the eligible
long_context ids (file order); write them in file order. This builds
DEMO2_HELDOUT_60_B_LONG30.json now. When the base rule is approved, the full
DEMO2_HELDOUT_60_B.json is base 30 (own seeded draw) followed by these 30
unchanged.

  python tools/demo2_heldout_b.py --data-dir <bfcl_eval 2025.12.17>/bfcl_eval/data
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

from tools import demo2_heldout as h60  # noqa: E402

SEED = 20261016
N_PER_CATEGORY = 30
OUT = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_HELDOUT_60_B_LONG30.json"
HELDOUT_60_META = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_HELDOUT_60.meta.json"
W3_ENTRIES = (
    ROOT
    / "derived"
    / "bfcl_feasibility"
    / "w3_weight_quality"
    / "sealed_1d8db970-4c18-4bcf-824d-d9c141b6eb22"
    / "artifacts"
    / "multi_turn_probe_entries.json"
)
RESERVATION = (
    "reserved for one confirmation run of the final searched DEMO-2 profile vs arm A "
    "(docs/amendments/DEMO2_SEARCH_PHASE_2026-10-16.md); no other use"
)
BASE_RULE_PROPOSALS = [
    "R1 (recommended): 30 multi_turn_base entries from the W-3 pin that are in no DEMO-1 or "
    "DEMO2 pin (140 eligible), seed 20261016; condition: the SEARCH phase never reads W-3 / "
    "d482c621 per-entry outcomes for those 30 ids. Same task distribution as DEMO2_HELDOUT_60; "
    "the leak is per-entry outcomes from a different configuration (2026-09, slo/emission/"
    "bounceback).",
    "R2: 30 multi_turn_miss_param entries (never run in this repo). Clean, but a different task "
    "type from the DEMO2_HELDOUT_60 base half.",
    "R3: 60 multi_turn_long_context entries (133 eligible). Clean, but a different 0/60 mix.",
]


def excluded() -> dict[str, list[str]]:
    out = h60.excluded()
    out["DEMO2_HELDOUT_60"] = list(
        json.loads(HELDOUT_60_META.read_text(encoding="utf-8"))["selected"]
    )
    w3 = json.loads(W3_ENTRIES.read_text(encoding="utf-8-sig"))
    out["W3_multi_turn_base_200"] = [str(e["id"]) for e in w3]
    return out


def select(base_ids: list[str], long_ids: list[str]) -> dict[str, Any]:
    """Pure selection from the two id lists (file order)."""
    drop = {i for ids in excluded().values() for i in ids}
    base_elig = [i for i in base_ids if i not in drop]
    long_elig = [i for i in long_ids if i not in drop]
    largest = h60._largest(h60.ATLAS_LONG)
    jump = [i for i in long_elig if largest[i] > h60.JUMP_N_CTX]
    rng = random.Random(SEED)
    pick = set(rng.sample(long_elig, N_PER_CATEGORY))
    return {
        "base_eligible": len(base_elig),
        "long_eligible": len(long_elig),
        "long_jump_eligible": len(jump),
        "long_jump_category": sum(1 for v in largest.values() if v > h60.JUMP_N_CTX),
        "selected_long": [i for i in long_elig if i in pick],
    }


def build(data_dir: Path) -> dict[str, Any]:
    from tools import h1_context_sizing as hcs

    base = hcs.load_entries("multi_turn_base", data_dir)
    long_ = hcs.load_entries("multi_turn_long_context", data_dir)
    # Loader check: the same data and loader rebuild DEMO2_HELDOUT_60 to its pin.
    sel60 = h60.select([e["id"] for e in base], [e["id"] for e in long_])
    by_id = {e["id"]: e for e in base + long_}
    rebuilt = hcs.entries_bytes([by_id[i] for i in sel60["selected_base"] + sel60["selected_long"]])
    check_sha = hashlib.sha256(rebuilt).hexdigest()
    pinned = json.loads(HELDOUT_60_META.read_text(encoding="utf-8"))["entries_sha256"]
    if check_sha != pinned:
        raise SystemExit(
            f"REFUSED -- loader check: rebuilt DEMO2_HELDOUT_60 {check_sha} != {pinned}"
        )
    sel = select([e["id"] for e in base], [e["id"] for e in long_])
    entries = [by_id[i] for i in sel["selected_long"]]
    payload = hcs.entries_bytes(entries)
    sizes = h60._largest(h60.ATLAS_LONG)
    meta = {
        "kind": "h1_entry_subset",
        "name": "DEMO2_HELDOUT_60_B_LONG30",
        "part_of": "DEMO2_HELDOUT_60_B (long_context half; base half BLOCKED)",
        "categories": ["multi_turn_long_context"],
        "seed": SEED,
        "n": len(entries),
        "rule": __doc__.split("\n\n")[3].strip(),
        "reserved_for": RESERVATION,
        "excluded_pins": excluded(),
        "pilot_entries": "DEMO-1 pins only (already excluded)",
        "data": {
            "bfcl_eval": "2025.12.17",
            "files_sha256": {
                name: hashlib.sha256((data_dir / name).read_bytes()).hexdigest()
                for name in ("BFCL_v4_multi_turn_base.json", "BFCL_v4_multi_turn_long_context.json")
            },
            "check": f"this data rebuilds DEMO2_HELDOUT_60 to its pinned sha256 {pinned}",
        },
        **{k: v for k, v in sel.items() if not k.startswith("selected")},
        "base_half": {
            "status": "BLOCKED: 0 eligible (the W-3 pin is all 200 multi_turn_base entries)",
            "proposed_rules": BASE_RULE_PROPOSALS,
        },
        "long_jump_note": (
            f"0 of the {sel['long_jump_category']} long_context entries with a gold turn above "
            f"{h60.JUMP_N_CTX} remain (DEMO-1 pins 36, DEMO2_HELDOUT_60 3); this half has none"
        ),
        "selected": sel["selected_long"],
        "selected_largest_gold_n_ctx": {i: sizes[i] for i in sel["selected_long"]},
        "entries_sha256": hashlib.sha256(payload).hexdigest(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(payload)
    OUT.with_name(OUT.stem + ".meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    meta = build(args.data_dir)
    print(f"PIN {OUT} n={meta['n']} sha256={meta['entries_sha256']}")
    print(
        f"base eligible {meta['base_eligible']}; long eligible {meta['long_eligible']}, "
        f"jump eligible {meta['long_jump_eligible']} of {meta['long_jump_category']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
