"""DEMO-1 V5-CAL plan: the points, the boot estimate and the coverage check.

Not read by the runner (tools/run_warm_kv.py takes its points on the command
line from tools/launch_boot1.ps1 profile v5-cal). Tests check that the
launcher table equals this plan and that every V5 jump step is covered.

Prefix break of the turn-2 history, measured with the pinned Qwen3-4B
tokenizer (OpenVINO/Qwen3-4B-int4-ov b467368d; render as the GenAI
ChatHistory, thinking off):
- user_followup (the sealed WARM-KV path): turn 2 shares the turn-1 prompt
  minus 6 tokens (assistant, newline, empty think block) and adds the raw
  delta plus 11 template tokens.
- assistant_then_user (the H1 / V5 path): shares the turn-1 prompt minus 4
  tokens (empty think block) and adds the reply, the raw delta and 15
  template tokens.

Estimate (boot-4 method, sealed cold medians): base_s = 2 x 13.504825195
(warm-up bound) + per point cold(n_cached) + 3 x cold(n_cached + delta +
32), each cold value from the sealed cold curve at the cell's KV (u8
c2246b1f + 2b3316b6; u4 c647f0c7 + 2b3316b6); estimate_s = ceil(base_s +
752.1359013).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

N_CACHED = (2200, 3320, 4080, 6290, 7380)
DELTA_TOKENS = 8500
V5_PATH_N_CACHED = (4080,)
BREAK_TOKENS = {"user_followup": 6, "assistant_then_user": 4}
TEMPLATE_OVERHEAD = {"user_followup": 11, "assistant_then_user": 15}
WARMUP_BOUND_S = 2 * 13.504825195
CANARY_OVERHEAD_S = 752.1359013
ESTIMATE_PAD_TOKENS = 32
BOOT_CAP_S = 6000

CELLS = (
    {"name": "V5-CAL u8", "kv": "u8", "n_cached": N_CACHED, "path": "user_followup"},
    {"name": "V5-CAL u4", "kv": "u4", "n_cached": N_CACHED, "path": "user_followup"},
    {
        "name": "V5-CAL u8 V5-path",
        "kv": "u8",
        "n_cached": V5_PATH_N_CACHED,
        "path": "assistant_then_user",
    },
)


def cell_estimate_s(kv: str, n_cached: tuple[int, ...]) -> int:
    from tools.demo1_v5_predict import cold_medians, cold_ttft

    medians = cold_medians(kv)
    base = WARMUP_BOUND_S
    for n in n_cached:
        base += cold_ttft(n, medians)["ttft_s"]
        base += 3 * cold_ttft(n + DELTA_TOKENS + ESTIMATE_PAD_TOKENS, medians)["ttft_s"]
    return math.ceil(base + CANARY_OVERHEAD_S)


def planned_points(cell: dict[str, Any]) -> list[dict[str, int]]:
    """(P, D) each point of the cell will measure, from the measured break."""
    path = cell["path"]
    return [
        {
            "P": n - BREAK_TOKENS[path],
            "D": DELTA_TOKENS + TEMPLATE_OVERHEAD[path],
        }
        for n in cell["n_cached"]
    ]


def coverage(predictions_path: Path | None = None) -> dict[str, Any]:
    """Every V5 jump step, at both block bounds, dominated by a planned point."""
    path = predictions_path or ROOT / "analysis" / "demo1" / "V5_PREDICTIONS.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    for cell_name, kv in (
        ("V5a_xps_gpu_4b_RESIDENT_u8", "u8"),
        ("V5b_xps_gpu_4b_RESIDENT_u4", "u4"),
    ):
        pts = [p for c in CELLS if c["kv"] == kv for p in planned_points(c)]
        uncovered = []
        for bound in ("block_low", "block_high"):
            for entry in doc["cells"][cell_name][bound]["entries"]:
                jump = entry["jump_step"]
                if jump is None:
                    continue
                if not any(p["P"] >= jump["P"] and p["D"] >= jump["D"] for p in pts):
                    uncovered.append((bound, entry["entry_id"], jump["P"], jump["D"]))
        out[kv] = {"n_points": len(pts), "uncovered": uncovered}
    return out


def plan() -> dict[str, Any]:
    cells = [
        {
            **c,
            "n_cached": list(c["n_cached"]),
            "estimate_s": cell_estimate_s(c["kv"], c["n_cached"]),
        }
        for c in CELLS
    ]
    return {
        "cells": cells,
        "sum_estimate_s": sum(c["estimate_s"] for c in cells),
        "boot_cap_s": BOOT_CAP_S,
        "coverage": coverage(),
    }


if __name__ == "__main__":
    print(json.dumps(plan(), indent=2))
