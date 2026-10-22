"""DEMO-2 Task BF0 predictions (DERIVED, before any calibration ledger is read): every contrast.

Writes derived/h1_hybrid/demo2/DEMO2_BF0_PREDICTIONS.json, registered by
docs/amendments/DEMO2_PREFREEZE_2026-10-22.md (H5, X6).

Model: the BE iso-quality model (tools/demo2_be_predict.iso, random-like escalation), extended
to any reference arm R:
  Q*_R = p_R + f_R (q - p_R); X reaches Q*_R with f_X = (Q*_R - p_X) / (q - p_X);
  dC_iso = c (f_R - f_X); scored in % as dC_iso_rel = 1 - f_X / f_R.
Inputs are the BE inputs (p_A = 4/60 per host, q = 22/30, c = $0.2968, f_A from the registered
A $/task), plus local-pass multipliers per arm (DERIVED, stated per arm in ARM_PASS):
- B, C, R-full: the same 4B IR and the same triggers; their extra local passes come only from
  turns that A also keeps local, so p = p_A (band 0.75-1.25 x p_A, +-1 of A's 4 passes);
- I-4K: p = 0.5 x p_A (band 0-1.0): half of local turns are above 4,096 tokens (n_ctx p50
  3,936, d482c621), and I-4K counts them as local fails;
- P': Qwen3-4B INT8 vs INT4, p = 1.1 x p_A (band 1.0-1.2; same model, higher precision);
- P: as BE, 1.4 x p_A (band 1.0-2.0; BE registered 1.4 conservative and 2.0 optimistic).
Reference escalation share f_R: f_A for A, B, C, R-full and P (same trigger thresholds; the
model prices only the local pass rate), 48/60 for I-4K (its registered BC escalation count at the
point). In this model dC_iso depends only on p_X vs p_R: same-pass arms predict 0%.
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

ARM_PASS: dict[str, tuple[float, float, float]] = {  # (lo, point, hi) x p_A
    "A": (1.0, 1.0, 1.0),
    "B": (0.75, 1.0, 1.25),
    "C": (0.75, 1.0, 1.25),
    "R-full": (0.75, 1.0, 1.25),
    "I-4K": (0.0, 0.5, 1.0),
    "P'": (1.0, 1.1, 1.2),
    "P": (1.0, 1.4, 2.0),
}
I4K_F = 48 / 60
# (X, reference): X vs A for every arm, plus the approval-2 secondaries (X6).
CONTRASTS: tuple[tuple[str, str], ...] = (
    ("P", "A"),
    ("P'", "A"),
    ("C", "A"),
    ("B", "A"),
    ("I-4K", "A"),
    ("R-full", "A"),
    ("P", "R-full"),
    ("P", "I-4K"),
    ("C", "R-full"),
    ("P", "C"),
    ("C", "I-4K"),
)


def f_ref(arm: str, f_a: float) -> float:
    return I4K_F if arm == "I-4K" else f_a


def contrast(x: str, r: str, f_a: float) -> dict[str, Any]:
    out: dict[str, Any] = {}
    fr = f_ref(r, f_a)
    for k, band in zip(("lo", "point", "hi"), range(3), strict=True):
        px = ARM_PASS[x][band] * be.P_A
        pr = ARM_PASS[r][1] * be.P_A
        out[k] = be.iso(pr, px, be.Q_CLOUD, fr, be.C_CLOUD)
    rel = [out[k]["dC_iso_rel"] for k in ("lo", "point", "hi")]
    out["dC_iso_rel_band_pct"] = [round(100 * min(rel), 1), round(100 * max(rel), 1)]
    out["dC_iso_rel_point_pct"] = round(100 * out["point"]["dC_iso_rel"], 1)
    return out


def build() -> dict[str, Any]:
    table: dict[str, Any] = {}
    for host, a_usd in be.A_REGISTERED.items():
        f_a = a_usd / be.C_CLOUD
        table[host] = {f"{x} vs {r}": contrast(x, r, f_a) for x, r in CONTRASTS}
    return {
        "id": "DEMO2_BF0_PREDICTIONS",
        "status": "registered with docs/amendments/DEMO2_PREFREEZE_2026-10-22.md before any "
        "calibration ledger was read by the author; DERIVED",
        "generator": "tools/demo2_bf0_predict.py",
        "runner_must_not_read_this_file": True,
        "inputs": {
            "be_inputs": "tools/demo2_be_predict.py (P_A, Q_CLOUD, C_CLOUD, A_REGISTERED)",
            "arm_pass_multipliers_lo_point_hi": {k: list(v) for k, v in ARM_PASS.items()},
            "f_ref_I4K": I4K_F,
        },
        "scoring": "HIT if the measured dC_iso_rel (point, %) lies inside dC_iso_rel_band_pct; "
        "a measured -inf (X does not reach Q*) is a MISS unless the band's lower end is -inf",
        "contrasts": table,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    doc = build()
    a.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="ascii")
    for h, t in doc["contrasts"].items():
        for k, v in t.items():
            print(h, k, v["dC_iso_rel_point_pct"], v["dC_iso_rel_band_pct"],
                  v["point"]["dC_iso_usd"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
