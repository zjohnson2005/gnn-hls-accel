"""DEMO-2 prereg: profiles, selection rule, cells, predictions, caps.

Sealed and committed data only; runs nothing. Writes DEMO2_PREREG_v1.json,
committed with its sha256 before any DEMO-2 run (task AL, 2026-10-14):

  python tools/demo2_predict.py --out derived/h1_hybrid/demo2/DEMO2_PREREG_v1.json

Prediction model (per held-out entry, gold trajectories from ENV-ATLAS):
- mechanical, sticky: the first turn whose max step prompt + 512 exceeds the
  window, or whose step-0 n_ctx exceeds the cold 10 s edge. With RESIDENT the
  runner's step-0 check after turn 0 sees a warm delta (V5 addendum, runner
  trigger), so the lower bound checks the edge on turn 0 only and the upper
  bound on every turn;
- live conditioning (DEMO-1 lesson: gold over-predicts the large call): a
  mechanical trigger on a turn whose gold n_ctx exceeds 10,000 fires live with
  probability LIVE_JUMP (lower 5/15, V3 T2S a4284ab0; upper 1.0, gold);
- quality, one-turn bounce: each remaining local turn bounces with
  probability q (lower 0.0625, point 0.125, upper 0.25; R2c turn share 0.125
  in d482c621, x0.5..x2);
- cloud $ per cloud turn = 3.20e-6 x 7.11 x n_ctx (DEMO-1 registered cost
  model, d482c621).
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

ATLAS = ROOT / "analysis" / "demo1" / "atlas"
PIN_META = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_HELDOUT_60.meta.json"
USD_PER_NCTX = 3.20e-6 * 7.11
GEN = 512
JUMP_NCTX = 10_000
LIVE_JUMP = (5 / 15, 1.0)  # a4284ab0 live 5/15 of gold-jump entries escalated; gold 1.0
Q = {"lo": 0.0625, "point": 0.125, "hi": 0.25}
SPEND_CEILING = 150.0

PROFILES: dict[str, dict[str, Any]] = {
    "control": {
        "placement": "gpu_only (Zach 2026-10-14)",
        "context_window": 4096,
        "kv": "runtime default: no KV_CACHE_PRECISION passed (--kv default, delta_n arm "
        "gpu_only); readback 'dynamic' on XPS and T2S (2026-10-14); the load refuses any "
        "other readback",
        "prefix_caching": "off: NON_RESIDENT passes SchedulerConfig(enable_prefix_caching="
        "False); the SchedulerConfig default read back as false on both hosts",
        "residency": "NON_RESIDENT",
        "retention": "FULL",
        "weights": "Qwen3-4B int4 (configs/models/Qwen3-4B-int4-ov.yaml)",
        "policy": "hybrid_full",
        "edge": None,
        "resident": False,
        "long_atlas": "multi_turn_long_context_FULL",
    },
    "tuned_XPS": {
        "placement": "gpu_only",
        "context_window": 40_960,
        "kv": "u4 (largest sealed RESIDENT limit 26,500, e4a22dac)",
        "prefix_caching": "not passed (RESIDENT keeps the session's chat history; "
        "SchedulerConfig default false)",
        "residency": "RESIDENT (turn-boundary D median 50.5 <= 400)",
        "retention": "OBS_MASK K=1024 on the whole pin (long_context needs it; base is "
        "identical under FULL and K=1024 in ENV-ATLAS)",
        "weights": "Qwen3-4B int4 (int8 decodes 30-34% slower, 180dfbb9)",
        "policy": "hybrid_full",
        "edge": (9_750, "c647f0c7 u4 cold curve: largest n with TTFT <= 10 s"),
        "resident": True,
        "long_atlas": "multi_turn_long_context_OBS_MASK_K1024",
    },
    "tuned_T2S": {
        "placement": "gpu_only",
        "context_window": 40_960,
        "kv": "u8 (only sealed T2S precision, d2d5cc4a)",
        "prefix_caching": "not passed (RESIDENT keeps the session's chat history; "
        "SchedulerConfig default false)",
        "residency": "RESIDENT (turn-boundary D median 50.5 <= 400)",
        "retention": "OBS_MASK K=1024 on the whole pin (as tuned_XPS)",
        "weights": "Qwen3-4B int4",
        "policy": "hybrid_full",
        "edge": (18_500, "d2d5cc4a u8 cold limit"),
        "resident": True,
        "long_atlas": "multi_turn_long_context_OBS_MASK_K1024",
    },
}
CELLS = {
    "D-X": ("XPS", "control"),
    "T-X": ("XPS", "tuned_XPS"),
    "D-T": ("T2S", "control"),
    "T-T": ("T2S", "tuned_T2S"),
}
PIN_FLAG = "-Entries derived\\h1_hybrid\\demo2\\DEMO2_HELDOUT_60.json"
FLAGS = {
    "control": "-Policy hybrid_full -Placement gpu_only -Kv default -Residency NON_RESIDENT "
    "-ContextWindow 4096",
    "tuned_XPS": "-Policy hybrid_full -Placement gpu_only -Kv u4 -Residency RESIDENT "
    "-ObsMaskK 1024 -ContextWindow 40960",
    "tuned_T2S": "-Policy hybrid_full -Placement gpu_only -Kv u8 -Residency RESIDENT "
    "-ObsMaskK 1024 -ContextWindow 40960",
}
READBACKS = {
    "date": "2026-10-14",
    "tool": "tools/demo2_readback.ps1 (no properties passed)",
    "XPS": {
        "gpu": "Intel(R) Graphics",
        "openvino": "2026.2.1",
        "openvino_genai": "2026.2.1",
        "KV_CACHE_PRECISION_before_load": "dynamic",
        "KV_CACHE_PRECISION_after_load": "dynamic",
        "KEY_VALUE_CACHE_PRECISION": "not supported",
        "SchedulerConfig_default_enable_prefix_caching": False,
    },
    "T2S": {
        "gpu": "Intel(R) Arc(TM) B390",
        "openvino": "2026.2.1",
        "openvino_genai": "2026.2.1",
        "KV_CACHE_PRECISION_before_load": "dynamic",
        "KV_CACHE_PRECISION_after_load": "dynamic",
        "KEY_VALUE_CACHE_PRECISION": "not supported",
        "SchedulerConfig_default_enable_prefix_caching": False,
    },
}


def _atlas(name: str) -> dict[str, list[dict[str, Any]]]:
    doc = json.loads((ATLAS / f"{name}.json").read_text(encoding="utf-8"))
    return {r["entry_id"]: r["turns"] for r in doc["entries"]}


def _first_trigger(
    turns: list[dict[str, Any]], prof: dict[str, Any], *, every_turn: bool
) -> int | None:
    window = int(prof["context_window"])
    edge = prof["edge"][0] if prof["edge"] else None
    for i, t in enumerate(turns):
        if int(t["max_step_prompt_tokens"]) + GEN > window:
            return i
        if edge is not None and int(t["n_ctx"]) > edge and (every_turn or i == 0):
            return i
    return None


def entry_cost(turns: list[dict[str, Any]], trigger: int | None, q: float) -> dict[str, float]:
    if trigger is None:
        local = turns
        mech_usd = 0.0
    else:
        local = turns[:trigger]
        mech_usd = sum(int(t["n_ctx"]) for t in turns[trigger:]) * USD_PER_NCTX
    bounce_usd = q * sum(int(t["n_ctx"]) for t in local) * USD_PER_NCTX
    local_turns = len(local) * (1 - q)
    return {"usd": mech_usd + bounce_usd, "local_turns": local_turns, "turns": len(turns)}


def predict_cell(ids: list[str], prof: dict[str, Any]) -> dict[str, Any]:
    base = _atlas("multi_turn_base_FULL")
    long_ = _atlas(prof["long_atlas"])
    out: dict[str, Any] = {}
    for bound, q in (("lo", Q["lo"]), ("point", Q["point"]), ("hi", Q["hi"])):
        usd = local = turns = esc = 0.0
        for i in ids:
            tr = base[i] if i.startswith("multi_turn_base_") else long_[i]
            trig = _first_trigger(tr, prof, every_turn=(bound == "hi" or not prof["resident"]))
            p_fire = 1.0
            if trig is not None and int(tr[trig]["n_ctx"]) > JUMP_NCTX:
                p_fire = {"lo": LIVE_JUMP[0], "point": sum(LIVE_JUMP) / 2, "hi": LIVE_JUMP[1]}[
                    bound
                ]
            fired = entry_cost(tr, trig, q)
            stayed = entry_cost(tr, None, q)
            usd += p_fire * fired["usd"] + (1 - p_fire) * stayed["usd"]
            local += p_fire * fired["local_turns"] + (1 - p_fire) * stayed["local_turns"]
            turns += fired["turns"]
            esc += p_fire if trig is not None else 0.0
        out[bound] = {
            "usd_per_task": round(usd / len(ids), 4),
            "usd_total": round(usd, 2),
            "local_share": round(local / turns, 3),
            "mechanical_escalations": round(esc, 1),
        }
    return out


def caps(preds: dict[str, Any]) -> dict[str, float]:
    raw = {c: 1.5 * p["hi"]["usd_total"] for c, p in preds.items()}
    total = sum(raw.values())
    scale = min(1.0, SPEND_CEILING / total) if total else 1.0
    return {c: round(v * scale, 2) for c, v in raw.items()}


def draft() -> dict[str, Any]:
    pin = json.loads(PIN_META.read_text(encoding="utf-8"))
    ids = pin["selected"]
    preds = {c: predict_cell(ids, PROFILES[p]) for c, (_h, p) in CELLS.items()}
    cell_caps = caps(preds)
    profiles = {
        k: {kk: vv for kk, vv in v.items() if kk not in ("resident", "long_atlas")}
        for k, v in PROFILES.items()
    }
    return {
        "id": "DEMO2_PREREG_v1",
        "status": "REGISTERED 2026-10-14 (task AL), before any DEMO-2 run",
        "readbacks": READBACKS,
        "runner_must_not_read_this_file": True,
        "design": "docs/amendments/DEMO2_DESIGN_2026-10-14.md",
        "decisions_zach_2026_10_14": [
            "(1) control placement GPU",
            "(2) n = 60 (30 base + 30 long_context held-out pin), non-inferiority margin 0.15 on "
            "paired pass rate; report point estimate and CI; claim stated as 'within 15 points'",
            "(3) DEMO-2 spend ceiling $150 for the main 2x2 only; ablations decided after the "
            "2x2's measured cost",
            "(4) TTFT/decode trigger at step 0 only (as DEMO-1); window overflow checked before "
            "every local generate",
            "(5) build now",
            "(6) T2S Windows Update pause pending Rithwik",
        ],
        "pin": {
            "name": "DEMO2_HELDOUT_60",
            "path": "derived/h1_hybrid/demo2/DEMO2_HELDOUT_60.json",
            "sha256": pin["entries_sha256"],
            "seed": pin["seed"],
            "long_jump_note": (
                f"{pin['long_jump_selected']} of 30 long_context entries have a gold turn above "
                f"18,500 (category {pin['long_jump_category_share']}; DEMO-1 pins used 36 of 39)"
            ),
        },
        "policy": {
            "name": "hybrid_full",
            "mechanical_sticky": [
                "ctx_overflow: step prompt + max_new_tokens > window, before every local generate",
                "step-0 ttft_s > 10 or decode_tok_s < 6",
                "local generation_error",
            ],
            "quality_one_turn_bounce": [
                "no_parseable_tool_call",
                "tool_exec_error",
                "n_steps >= 5",
            ],
            "order": "mechanical first; every escalation row records trigger_class",
        },
        "profiles": profiles,
        "selection_rule_frozen": [
            "placement GPU: XPS cold limit 21.4x CPU (c2246b1f 10,000 vs 7f232f86 468); NPU "
            "excluded (only citable NPU-INT8 limit 1984, 9acabbf7)",
            "weights int4 (180dfbb9)",
            "window = max_position_embeddings 40,960",
            "KV = largest sealed RESIDENT limit on the device: XPS u4 (e4a22dac 26,500 > "
            "cf3555d5 20,000 > 553b3a5c 15,000); T2S u8 (only sealed, d2d5cc4a)",
            "retention OBS_MASK K=1024 where the category has observations above K "
            "(long_context), else FULL",
            "RESIDENT if turn-boundary D <= 400 (sealed small-D points 72776603, 1587d2f4, "
            "dd2b0779); DEMO-1 D median 50.5, so RESIDENT",
            "uses sealed limits only; no held-out entry",
        ],
        "cells": {
            c: {
                "host": h,
                "profile": p,
                "cap_usd": cell_caps[c],
                "launch_flags": f"{'-T2S ' if h == 'T2S' else ''}{FLAGS[p]} {PIN_FLAG} "
                f"-MaxUsd {cell_caps[c]}",
            }
            for c, (h, p) in CELLS.items()
        },
        "run_order": ["D-X", "T-X", "D-T", "T-T"],
        "ablations": "DEFERRED: decided after the 2x2's measured cost (Zach 2026-10-14)",
        "predictions": {
            "model": __doc__.split("\n\n")[2],
            "per_cell": preds,
            "registered_bands": "[lo, hi] per quantity; point is the band's centre estimate",
        },
        "tests": {
            "primary": (
                "per host: $/task tuned vs default, paired by entry; one-sided Wilcoxon "
                "signed-rank (tuned < default), alpha 0.05; bootstrap 95% CI of the mean "
                "difference (10,000 resamples, seed 20261014)"
            ),
            "non_inferiority": (
                "paired hybrid pass rate, tuned - default; lower bound of the one-sided 95% CI "
                "(Newcombe paired score interval) must exceed -0.15; report point estimate and CI; "
                "claim worded 'within 15 points'"
            ),
            "win": "primary significant AND non-inferiority holds, per host",
            "secondary": [
                "local share",
                "TTA per turn",
                "cloud input tokens per task",
                "trigger counts by class",
            ],
        },
        "spend": {
            "ceiling_usd": SPEND_CEILING,
            "caps_sum_usd": round(sum(cell_caps.values()), 2),
            "rule": "cap = 1.5 x the cell's hi-band total, scaled to sum to <= $150",
        },
        "rehearsal_oct17": [
            "both hosts: git pull --ff-only to the prereg commit; tools/demo2_readback.ps1 "
            "results recorded in the prereg before this point",
            "XPS: fixture dry-run: python tools/run_h1_hybrid.py --policy hybrid_full --fixture "
            "<stub> --context-window 4096 --max-usd 1 --no-seal --out <tmp>",
            "XPS and T2S: launch_h1.ps1 -Policy hybrid_full -ContextWindow 4096 -MaxUsd 1 "
            "-Entries derived/h1_hybrid/demo2/DEMO2_HELDOUT_60.json -EntryCount 2 -DryRun, "
            "then the same via tools/spawn_detached.ps1 until REHEARSAL_COMPLETE",
            "tuned profile smoke on each host (-Kv u4 on XPS / u8 on T2S, -Residency RESIDENT, "
            "-ObsMaskK 1024 on long_context entries, -ContextWindow 40960), 2 entries, $1 cap",
            "check: plan.json context_window, trigger_class on escalation rows, seal MATCH",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    doc = draft()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    for c, p in doc["predictions"]["per_cell"].items():
        print(c, p, "cap", doc["cells"][c]["cap_usd"])
    print("caps sum", doc["spend"]["caps_sum_usd"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
