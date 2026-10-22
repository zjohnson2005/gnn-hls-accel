"""DEMO-2 revised arms (Task BC): per-arm, per-host predictions, DERIVED, before any run.

Writes the predictions file registered by
docs/amendments/DEMO2_ARMS_REVISED_2026-10-21.md:

  python tools/demo2_bc_predict.py --out derived/h1_hybrid/demo2/DEMO2_BC_PREDICTIONS.json

Same model as the registered generator (tools/demo2_true_default_predict.py,
which itself uses tools/demo2_predict.py): gold trajectories of DEMO2_HELDOUT_60
from ENV-ATLAS, q bands, LIVE_JUMP, cloud $ per cloud turn proportional to that
turn's n_ctx. The registered functions are imported, not copied, and only the
per-arm triggers and the long-context atlas differ:

- A (true default): the registered triggers, unchanged (XPS memory limit
  20,000 cf3555d5; T2S none; cold edges XPS 10,000 c2246b1f, T2S 18,500
  d2d5cc4a). Sensitivity A18: XPS memory limit 18,000 (a5d19dcc, first fail
  18,500).
- B (device-only, revised): prompt budget P (XPS 8,192, T2S 16,384): a step
  whose prompt exceeds P escalates (sticky ctx_overflow), FULL atlas. Cold
  edges as A (the budget sits below both).
- C (revised): B + retention K = 2,048. Proxy: the OBS_MASK_K2048 long-context
  atlas (head-only K = 2,048 whitespace tokens; insertion truncation keeps at
  most 2,048 model tokens plus a marker, so the proxy is DERIVED). Base half:
  FULL (base tool outputs rarely exceed 2,048 tokens). Lazy age-masking is not
  modelled (it can only remove overflow escalations, so C is an upper bound
  on cost from this term). C_raw: triggers from the K2048 atlas, cloud $ from
  the FULL atlas n_ctx (the raw-handoff sensitivity).
- I4K (registered arm D, relabelled): window 4,096 on prompt + 512, as
  registered. XPS: the registered D-X band stays the prediction of record;
  T2S I4K is new (DERIVED, no registered band).
- RF (R-full): window 40,960 on prompt + 512 (loud rejection), f16 KV. XPS
  memory limit 15,000 (553b3a5c, f16 resident). T2S: no memory limit at 64 GB
  (f16 KV at 40,960 = 6.0 GB, DERIVED). Cold edges as A (f16 cold edges are
  not sealed; c2246b1f is u8 = i8).
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

from tools import demo2_predict as d2  # noqa: E402
from tools import demo2_true_default_predict as td  # noqa: E402

NO = td.NO_LIMIT
BUDGET = {"XPS": 8192, "T2S": 16384}
CEILING = {"XPS": 9216, "T2S": 17408}
POSITION_GUARD = 32_768
K_RET = 2048
SPEND_CEILING = 275.0


def _edge(host: str) -> int:
    return td.LIMITS["xps_cold_edge"][0] if host == "XPS" else td.LIMITS["t2s_cold_edge"][0]


def arm_spec(host: str, arm: str) -> dict[str, Any]:
    """prompt_cap: escalate if a step prompt > cap; window: escalate if prompt + 512 > window."""
    e = _edge(host)
    if arm == "A":
        mem = td.LIMITS["xps_i8_resident"][0] if host == "XPS" else NO
        return {"prompt_cap": NO, "window": mem, "edge": e, "atlas": "FULL", "cost_atlas": "FULL"}
    if arm == "A18":
        mem = 18_000 if host == "XPS" else NO
        return {"prompt_cap": NO, "window": mem, "edge": e, "atlas": "FULL", "cost_atlas": "FULL"}
    if arm == "B":
        return {
            "prompt_cap": BUDGET[host],
            "window": NO,
            "edge": e,
            "atlas": "FULL",
            "cost_atlas": "FULL",
        }
    if arm == "C":
        return {
            "prompt_cap": BUDGET[host],
            "window": NO,
            "edge": e,
            "atlas": "K2048",
            "cost_atlas": "K2048",
        }
    if arm == "C_raw":
        return {
            "prompt_cap": BUDGET[host],
            "window": NO,
            "edge": e,
            "atlas": "K2048",
            "cost_atlas": "FULL",
        }
    if arm == "I4K":
        return {"prompt_cap": NO, "window": 4096, "edge": e, "atlas": "FULL", "cost_atlas": "FULL"}
    if arm == "RF":
        mem = 15_000 if host == "XPS" else NO
        return {
            "prompt_cap": NO,
            "window": min(40_960, mem),
            "edge": e,
            "atlas": "FULL",
            "cost_atlas": "FULL",
        }
    raise ValueError(arm)


def _first(turns: list[dict[str, Any]], spec: dict[str, Any], every_turn: bool) -> int | None:
    for i, t in enumerate(turns):
        p = int(t["max_step_prompt_tokens"])
        if p > spec["prompt_cap"] or p + d2.GEN > spec["window"]:
            return i
        if int(t["n_ctx"]) > spec["edge"] and (every_turn or i == 0):
            return i
    return None


def predict(ids: list[str], host: str, arm: str) -> dict[str, Any]:
    spec = arm_spec(host, arm)
    atl = {
        "FULL": (d2._atlas("multi_turn_base_FULL"), d2._atlas("multi_turn_long_context_FULL")),
        "K2048": (
            d2._atlas("multi_turn_base_FULL"),
            d2._atlas("multi_turn_long_context_OBS_MASK_K2048"),
        ),
    }

    def traj(name: str, i: str) -> list[dict[str, Any]]:
        base, long_ = atl[name]
        return base[i] if i.startswith("multi_turn_base_") else long_[i]

    out: dict[str, Any] = {}
    for bound in ("lo", "point", "hi"):
        q = d2.Q[bound]
        usd = local = turns = esc = 0.0
        over_guard = 0
        for i in ids:
            tr = traj(spec["atlas"], i)
            cost_tr = traj(spec["cost_atlas"], i)
            t_idx = _first(tr, spec, every_turn=(bound == "hi"))
            p_fire = 1.0
            if t_idx is not None and int(tr[t_idx]["n_ctx"]) > d2.JUMP_NCTX:
                p_fire = {
                    "lo": d2.LIVE_JUMP[0],
                    "point": sum(d2.LIVE_JUMP) / 2,
                    "hi": d2.LIVE_JUMP[1],
                }[bound]
            fired = d2.entry_cost(cost_tr, t_idx, q)
            stayed = d2.entry_cost(cost_tr, None, q)
            usd += p_fire * fired["usd"] + (1 - p_fire) * stayed["usd"]
            local += p_fire * fired["local_turns"] + (1 - p_fire) * stayed["local_turns"]
            turns += fired["turns"]
            esc += p_fire if t_idx is not None else 0.0
            local_part = tr if t_idx is None else tr[:t_idx]
            over_guard += sum(
                1 for t in local_part if int(t["max_step_prompt_tokens"]) + d2.GEN > POSITION_GUARD
            )
        out[bound] = {
            "usd_per_task": round(usd / len(ids), 4),
            "usd_total": round(usd, 2),
            "local_share": round(local / turns, 3),
            "mechanical_escalations": round(esc, 1),
            "gold_local_turns_over_32768": over_guard,
        }
    out["triggers"] = {k: (None if v == NO else v) for k, v in spec.items()}
    return out


CELLS = {
    "A-X": ("XPS", "A"),
    "A18-X": ("XPS", "A18"),
    "B-X": ("XPS", "B"),
    "C-X": ("XPS", "C"),
    "C_raw-X": ("XPS", "C_raw"),
    "I4K-X": ("XPS", "I4K"),
    "RF-X": ("XPS", "RF"),
    "A-T": ("T2S", "A"),
    "B-T": ("T2S", "B"),
    "C-T": ("T2S", "C"),
    "C_raw-T": ("T2S", "C_raw"),
    "I4K-T": ("T2S", "I4K"),
    "RF-T": ("T2S", "RF"),
}
HELDOUT_CELLS = ("A-X", "B-X", "C-X", "I4K-X", "RF-X", "A-T", "B-T", "C-T", "RF-T")


def build() -> dict[str, Any]:
    pin = json.loads(d2.PIN_META.read_text(encoding="utf-8"))
    ids = pin["selected"]
    preds = {c: predict(ids, h, a) for c, (h, a) in CELLS.items()}
    reg = json.loads(
        (ROOT / "derived/h1_hybrid/demo2/DEMO2_AMEND_TRUE_DEFAULT_PREDICTIONS.json").read_text(
            encoding="utf-8"
        )
    )
    d_rec = reg["D_X2_prediction_of_record"]
    caps: dict[str, float] = {}
    for c in HELDOUT_CELLS:
        hi = d_rec["hi"]["usd_total"] if c == "I4K-X" else preds[c]["hi"]["usd_total"]
        caps[c] = round(1.5 * hi, 2)
    ratios = {}
    for h in ("X", "T"):
        a = preds[f"A-{h}"]["point"]["usd_per_task"]
        ratios[h] = {
            f"{x}_over_A_point": (
                round(preds[f"{x}-{h}"]["point"]["usd_per_task"] / a, 3) if a else None
            )
            for x in ("B", "C", "C_raw", "I4K", "RF")
        }
    return {
        "id": "DEMO2_BC_PREDICTIONS",
        "status": "registered with docs/amendments/DEMO2_ARMS_REVISED_2026-10-21.md, before any "
        "held-out run; DERIVED",
        "generator": "tools/demo2_bc_predict.py (imports tools/demo2_true_default_predict.py "
        "and tools/demo2_predict.py unchanged)",
        "runner_must_not_read_this_file": True,
        "pin": {"name": "DEMO2_HELDOUT_60", "sha256": pin["entries_sha256"], "n": len(ids)},
        "budgets": {
            "prompt": BUDGET,
            "ceiling": CEILING,
            "position_guard": POSITION_GUARD,
            "k_retention": K_RET,
        },
        "per_cell_usd": preds,
        "I4K_X_prediction_of_record": {"source": "registered D-X band (DEMO2_PREREG_v1)", **d_rec},
        "registered_true_default_cells_for_comparison": {
            c: reg["per_cell_usd"][c]["point"]["usd_per_task"] for c in reg["per_cell_usd"]
        },
        "ratios_point": ratios,
        "caps_usd": caps,
        "caps_rule": "cap = 1.5 x the cell's hi-band total (I4K-X: registered D-X hi band); "
        "cells C_raw (sensitivity, re-priced, not run), A18 and I4K-T are not held-out cells",
        "caps_total_usd_one_replicate": round(sum(caps.values()), 2),
        "ceiling_usd": SPEND_CEILING,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    doc = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="ascii")
    for c, p in doc["per_cell_usd"].items():
        print(
            c,
            {
                b: (
                    p[b]["usd_per_task"],
                    p[b]["local_share"],
                    p[b]["mechanical_escalations"],
                    p[b]["gold_local_turns_over_32768"],
                )
                for b in ("lo", "point", "hi")
            },
        )
    print("caps", doc["caps_usd"], "total", doc["caps_total_usd_one_replicate"])
    print("ratios", doc["ratios_point"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
