"""DEMO-1 knob-vs-upgrade table (amendment 2026-10-13c, section 5).

Sealed runs only, via tools/score_demo1_cells.score_cell. Each row is one
pair: the knob's effect next to the upgrade effect. Pairs not yet run are
listed as pending. Pass counts and paired tests are descriptive: passes
were recorded, not predicted.

  python tools/demo1_knob_table.py --out analysis/demo1/KNOB_VS_UPGRADE_20261014b.json

(KNOB_VS_UPGRADE_20261014.json is the earlier version without the retention
rows; committed analysis files are not edited.)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import score_demo1_cells as sdc  # noqa: E402

PAIRS: tuple[dict[str, Any], ...] = (
    {"knob": "placement (XPS GPU -> XPS CPU)", "a": "V1_xps_gpu_4b_u8", "b": "V2_xps_cpu_4b"},
    {
        "knob": "upgrade (XPS GPU -> T2S GPU)",
        "a": "V4_xps_gpu_4b_u8",
        "b": "V4_t2s_gpu_4b_u8_rerun",
    },
    {
        "knob": "upgrade under FULL retention (V3 XPS -> V3 T2S)",
        "a": "V3_xps_gpu_4b_u8",
        "b": "V3_t2s_gpu_4b_u8",
    },
    {
        "knob": "retention on XPS (V3 FULL -> V4 OBS_MASK K=1024)",
        "a": "V3_xps_gpu_4b_u8",
        "b": "V4_xps_gpu_4b_u8",
    },
    {
        "knob": "retention on T2S (V3 FULL -> V4 OBS_MASK K=1024)",
        "a": "V3_t2s_gpu_4b_u8",
        "b": "V4_t2s_gpu_4b_u8_rerun",
    },
)
PENDING = (
    {"knob": "residency (V4 XPS vs V5a)", "status": "not run: V5 addendum rule"},
    {"knob": "KV precision (V5a vs V5b)", "status": "not run: V5 addendum rule"},
)


def exact_binomial_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n)


def pair_row(spec: dict[str, Any]) -> dict[str, Any]:
    a, b = sdc.score_cell(spec["a"]), sdc.score_cell(spec["b"])
    ea = {r["entry_id"]: r for r in a["entries"]}
    eb = {r["entry_id"]: r for r in b["entries"]}
    if set(ea) != set(eb):
        raise SystemExit(f"REFUSED -- {spec['a']} and {spec['b']} differ in entries")
    lost = sorted(i for i in ea if ea[i]["hybrid_pass"] and not eb[i]["hybrid_pass"])
    gained = sorted(i for i in ea if not ea[i]["hybrid_pass"] and eb[i]["hybrid_pass"])
    ma, mb = a["measured"], b["measured"]
    net = mb["n_hybrid_pass"] - ma["n_hybrid_pass"]
    dusd = round(mb["usd"] - ma["usd"], 4)
    return {
        "knob": spec["knob"],
        "a": {"cell": spec["a"], "run_id": a["run_id"], **ma},
        "b": {"cell": spec["b"], "run_id": b["run_id"], **mb},
        "delta": {
            "local_share": round(mb["local_share"] - ma["local_share"], 3),
            "usd_per_task": round(mb["usd_per_task"] - ma["usd_per_task"], 4),
            "usd": dusd,
            "hybrid_passes": net,
        },
        "descriptive_paired_passes": {
            "b_a_pass_b_fail": len(lost),
            "c_a_fail_b_pass": len(gained),
            "both_pass": sum(1 for i in ea if ea[i]["hybrid_pass"] and eb[i]["hybrid_pass"]),
            "p_two_sided_exact": exact_binomial_two_sided(len(lost), len(gained)),
            "lost": lost,
            "gained": gained,
            # $ per recovered pass only when the change costs money and gains passes.
            "usd_per_net_pass": None if net <= 0 or dusd <= 0 else round(dusd / net, 4),
            "usd_per_gained_pass": None
            if not gained or dusd <= 0
            else round(dusd / len(gained), 4),
            "label": "descriptive: passes were recorded, not predicted",
        },
    }


def table() -> dict[str, Any]:
    return {
        "kind": "demo1_knob_vs_upgrade",
        "amendment": "DEMO-1 amendment 2026-10-13c section 5",
        "note": "Placement uses DEMO1_BASE_30; every other row uses DEMO1_PAIRED_15. "
        "Placement is not on the same entries as the others.",
        "rows": [pair_row(p) for p in PAIRS],
        "pending": list(PENDING),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    doc = table()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    for row in doc["rows"]:
        print(
            row["knob"],
            row["delta"],
            row["descriptive_paired_passes"]["b_a_pass_b_fail"],
            row["descriptive_paired_passes"]["c_a_fail_b_pass"],
            row["descriptive_paired_passes"]["p_two_sided_exact"],
            row["descriptive_paired_passes"]["usd_per_net_pass"],
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
