"""DEMO-2 Task BE predictions (DERIVED, before any run): iso-quality $ for P, and arm A resident.

Writes derived/h1_hybrid/demo2/DEMO2_BE_PREDICTIONS.json, registered by
docs/amendments/DEMO2_ISO_QUALITY_2026-10-21.md.

1. Iso-quality model (random-like escalation, as the research report section 3; SEAM's router
   does not beat matched-rate random escalation, analysis/aq_20261015):
   Q(f) = p + f (q - p); arm A's quality Q* = p_A + f_A (q - p_A);
   arm X reaches Q* with f_X = (Q* - p_X) / (q - p_X) (0 if p_X >= Q*);
   dC_iso = c (f_A - f_X); dQ_iso at A's spend = (1 - f_A) (p_X - p_A).
   Inputs (sealed): p_A = 4/60 per host (XPS 39c1c131 3/30 + 841b84e4 1/14 + 15367c3a 0/15 +
   entry 123 a fail; T2S b90f1d5b 3/30 + 1a634610 1/14 + daa6c026 0/15 + 123 (cddcd9fd) a fail);
   q = 22/30 and c = $0.2968 per all-cloud task (1acc8c58, BASE_30, no caching, no retention);
   f_A = registered A $/task / c (XPS 0.119, T2S 0.052: DEMO2_AMEND_TRUE_DEFAULT_PREDICTIONS).
   P: p_X = 1.4 p_A (conservative, published tier deltas) and 2.0 p_A (optimistic).
   Relative savings do not depend on c, so shared caching/retention leave them unchanged.
2. Arm A re-registered as RESIDENT with warm tool-set prefixes: the registered gold-trajectory
   generator (tools/demo2_bc_predict.py, unchanged imports) with the cold step-0 TTFT edge
   removed (every tool-set prefix is warm before its first entry). The XPS memory limit
   (20,000, cf3555d5) is kept; whether prefix blocks of earlier entries lower it is NOT YET
   MEASURED.
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

from tools import demo2_bc_predict as bc  # noqa: E402
from tools import demo2_predict as d2  # noqa: E402

P_A = 4 / 60
Q_CLOUD = 22 / 30
C_CLOUD = 0.2968
A_REGISTERED = {"XPS": 0.119, "T2S": 0.052}
MULTS = (1.0, 1.4, 2.0)


def iso(p_a: float, p_x: float, q: float, f_a: float, c: float) -> dict[str, float | None]:
    q_star = p_a + f_a * (q - p_a)
    f_x = 0.0 if p_x >= q_star else (q_star - p_x) / (q - p_x)
    return {
        "Q_star": round(q_star, 4),
        "f_A": round(f_a, 4),
        "f_X": round(f_x, 4),
        "C_A": round(f_a * c, 4),
        "C_X_at_Q_star": round(f_x * c, 4),
        "dC_iso_usd": round(c * (f_a - f_x), 4),
        "dC_iso_rel": round(1 - f_x / f_a, 3) if f_a else None,
        "dQ_iso_pp": round(100 * (1 - f_a) * (p_x - p_a), 2),
    }


def resident_a(host: str) -> dict[str, Any]:
    pin = json.loads(d2.PIN_META.read_text(encoding="utf-8"))
    spec = bc.arm_spec(host, "A")
    spec["edge"] = bc.NO
    orig = bc.arm_spec
    try:
        bc.arm_spec = lambda _h, _a: spec  # type: ignore[assignment]
        out = bc.predict(pin["selected"], host, "A")
    finally:
        bc.arm_spec = orig  # type: ignore[assignment]
    return out


def build() -> dict[str, Any]:
    table: dict[str, Any] = {}
    for host, a_usd in A_REGISTERED.items():
        f_a = a_usd / C_CLOUD
        table[host] = {f"p_x={m}xp_A": iso(P_A, m * P_A, Q_CLOUD, f_a, C_CLOUD) for m in MULTS}
    return {
        "id": "DEMO2_BE_PREDICTIONS",
        "status": "registered with docs/amendments/DEMO2_ISO_QUALITY_2026-10-21.md before any run; "
        "DERIVED",
        "generator": "tools/demo2_be_predict.py",
        "runner_must_not_read_this_file": True,
        "inputs": {
            "p_A": P_A,
            "q_cloud": Q_CLOUD,
            "c_cloud_usd": C_CLOUD,
            "A_registered_usd_per_task": A_REGISTERED,
            "sources": "39c1c131, 841b84e4, 15367c3a, b90f1d5b, 1a634610, daa6c026, cddcd9fd "
            "(local passes); 1acc8c58 (cloud pass and cost); DEMO2_AMEND_TRUE_DEFAULT_PREDICTIONS",
        },
        "iso_quality_P": table,
        "A_resident_gold_generator": {h: resident_a(h) for h in ("XPS", "T2S")},
        "odds_judgement": {
            "source": "research report 'Dollar win against the default' section 5, adopted as the "
            "registered judgement (not a measurement)",
            "T2S_P_point_iso_win": "65-75%",
            "T2S_P_ci_excludes_zero_n60": "25-35%",
            "XPS_P_point_iso_win": "55-60%",
            "XPS_P_ci_excludes_zero_n60": "15-20%",
            "T2S_registered_C_raw_usd_win": "<5%",
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    doc = build()
    a.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="ascii")
    for h, t in doc["iso_quality_P"].items():
        for k, v in t.items():
            print(h, k, v)
    for h, p in doc["A_resident_gold_generator"].items():
        print("A_resident", h, {b: p[b]["usd_per_task"] for b in ("lo", "point", "hi")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
