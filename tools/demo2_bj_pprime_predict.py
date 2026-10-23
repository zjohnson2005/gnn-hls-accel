"""DEMO-2 Task BJ part A: XPS P' rows for the BF0 secondary contrasts (DERIVED, same generator).

Writes derived/h1_hybrid/demo2/DEMO2_BJ_PPRIME_PREDICTIONS.json, registered by
docs/amendments/DEMO2_AMEND_2026-10-23b_PPRIME.md before any held-out run.

On the XPS the frozen P arm is P' (Qwen3-4B INT8; FREEZE 2b), but BF0 scored the XPS rows
"P vs R-full / I-4K / C" with P's 8B multiplier (1.4). This adds the matching P' rows for the
XPS only, computed by tools/demo2_bf0_predict.contrast with BF0's own P' multiplier
(lo 1.0 / point 1.1 / hi 1.2 x p_A). No input, model or earlier row changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo2_be_predict as be  # noqa: E402
from tools import demo2_bf0_predict as bf0  # noqa: E402

HOST = "XPS"
CONTRASTS: tuple[tuple[str, str], ...] = (("P'", "R-full"), ("P'", "I-4K"), ("P'", "C"))


def build() -> dict[str, Any]:
    f_a = be.A_REGISTERED[HOST] / be.C_CLOUD
    return {
        "id": "DEMO2_BJ_PPRIME_PREDICTIONS",
        "status": "registered with docs/amendments/DEMO2_AMEND_2026-10-23b_PPRIME.md before any "
        "held-out record existed; DERIVED",
        "generator": "tools/demo2_bj_pprime_predict.py (calls tools/demo2_bf0_predict.contrast)",
        "runner_must_not_read_this_file": True,
        "inputs": {
            "be_inputs": "tools/demo2_be_predict.py (P_A, Q_CLOUD, C_CLOUD, A_REGISTERED)",
            "pprime_pass_multiplier_lo_point_hi": list(bf0.ARM_PASS["P'"]),
            "f_ref_I4K": bf0.I4K_F,
        },
        "scoring": "as DEMO2_BF0_PREDICTIONS.json: HIT if the measured dC_iso_rel (point, %) lies "
        "inside dC_iso_rel_band_pct; a measured -inf is a MISS unless the band's lower end is -inf",
        "contrasts": {HOST: {f"{x} vs {r}": bf0.contrast(x, r, f_a) for x, r in CONTRASTS}},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    doc = build()
    a.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="ascii")
    for k, v in doc["contrasts"][HOST].items():
        print(
            HOST, k, v["dC_iso_rel_point_pct"], v["dC_iso_rel_band_pct"], v["point"]["dC_iso_usd"]
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
