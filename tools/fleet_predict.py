"""FLEET-FRONTIER (Task BO): per-tier context capacity through the law, before any fleet result.

Writes derived/fleet/FLEET_PREDICTIONS.json, registered by docs/registrations/FLEET_FRONTIER_2026-10-23.md.

Per installed RAM tier M (GiB, OS-visible assumed M - 0.5 GiB):
- Windows graphics tier S = MIN(0.80 M, MAX(M - 16 GiB, 0.50 M)) (Microsoft "Calculating Graphics
  Memory"; Intel's override can change it, ignored here);
- Qwen3-4B INT4 budget B = S - (W + c0), with W + c0 from the XPS fit (S_XPS assumed 0.50 x 15.5
  GiB until A19 measures it; substitute the measured S_XPS with no refit);
- L_mem = B / (k + a) uncapped and B / k with a bounded step; L_window = 40,960;
- the Ollama default window from its documented tiers (4K below 24 GiB, 32K for 24-48 GiB, 256K
  at 48 GiB and above), with S standing in for VRAM on an iGPU.
Fit-fraction predictions (DERIVED in the award report from lognormal fits) are recorded verbatim;
the registered measurement replaces the lognormals with the TraceLab CDF (tools/fleet_cdf.py).
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

from tools import cc_bl_predict as bl  # noqa: E402
from tools import cc_predict as base  # noqa: E402

GIB = 2**30
TIERS_GIB = (8, 16, 32, 64, 128)
XPS_VISIBLE_GIB = 15.5
FIRMWARE_GIB = 0.5
WINDOW = 40_960


def graphics_tier(m_gib: float) -> float:
    return min(0.80 * m_gib, max(m_gib - 16.0, 0.50 * m_gib))


def ollama_default(s_gib: float) -> int:
    if s_gib < 24:
        return 4_096
    if s_gib < 48:
        return 32_768
    return 262_144


def build() -> dict[str, Any]:
    a, b4 = bl.h_act()
    fixed = graphics_tier(XPS_VISIBLE_GIB) * GIB - b4  # W + c0 on the XPS fit
    k = {"f16": base.K_KV["f16"], "u4": base.K_KV["u4"]}
    tiers = {}
    for m in TIERS_GIB:
        s = graphics_tier(m - FIRMWARE_GIB)
        b = s * GIB - fixed
        tiers[f"{m}GiB"] = {
            "graphics_tier_GiB": round(s, 2),
            "budget_GiB": round(b / GIB, 2),
            "L_mem_uncapped": {p: (max(0, round(b / (k[p] + a))) if b > 0 else 0) for p in k},
            "L_mem_bounded_step": {p: (max(0, round(b / k[p])) if b > 0 else 0) for p in k},
            "L_window": WINDOW,
            "ollama_default_window": ollama_default(s),
        }
    return {
        "id": "FLEET_PREDICTIONS",
        "status": "registered with docs/registrations/FLEET_FRONTIER_2026-10-23.md before any fleet "
        "result; DERIVED; results only after the Nov 6 gate",
        "generator": "tools/fleet_predict.py",
        "inputs": {
            "a_B_per_token": round(a),
            "budget_xps_GiB": round(b4 / GIB, 3),
            "W_plus_c0_GiB": round(fixed / GIB, 3),
            "xps_visible_GiB_assumed": XPS_VISIBLE_GIB,
            "firmware_GiB_assumed": FIRMWARE_GIB,
            "a19_rule": "replace the assumed XPS graphics tier with the A19 SharedSystemMemory; W + c0 "
            "follows, no refit",
        },
        "tiers": tiers,
        "award_report_fit_fractions_verbatim": {
            "steam_mix_defaults": "~0-1.1%",
            "16GB_measured_ceilings_15K_26.5K": "7-17% (Copilot fit), 3-8% (TraceLab-wide), 0% "
            "(TraceLab-tight)",
            "16GB_capped_u4_88K_memory_feasible": "61% / 39% / 24% (past Qwen3-4B's window)",
        },
        "registered_predictions": {
            "defaults_fit_fraction_max": 0.02,
            "tier16_measured_ceiling_fit_fraction_band": [0.0, 0.20],
            "basis": "the award report's ranges, widened to whole bands; scored on the TraceLab CDF",
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    doc = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="ascii")
    print(json.dumps(doc["tiers"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
