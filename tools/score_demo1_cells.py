"""Score sealed DEMO-1 cells against DEMO_PREREG_v2 and tabulate live vs gold.

Reads sealed H1 run dirs and the committed atlas only. Opens the prereg (this
is a scorer, not a runner). Prereg v2 states each prediction as a band
[low, high]; a measured value inside the band (inclusive) is MATCH, else MISS.

  python tools/score_demo1_cells.py --out analysis/demo1/SCORE_XPS_20261013.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "derived" / "h1_hybrid" / "demo1" / "DEMO_PREREG_v2.json"
ATLAS = ROOT / "analysis" / "demo1" / "atlas"
# Gold escalation edge per config: the sealed cold limit in DEMO_PREREG_v2
# envelopes (xps c2246b1f 10,000; t2s d2d5cc4a 18,500; xps cpu 7f232f86 468).
EDGES = {"xps_gpu_4b_u8": 10_000, "t2s_gpu_4b_u8": 18_500, "xps_cpu_4b": 468}

CELLS = {
    "V1_xps_gpu_4b_u8": {
        "cell": "V1",
        "config": "xps_gpu_4b_u8",
        "run": "slo_escalate_f7343708-a4a5-4984-93e5-ce5412a6c981",
        "atlas": "multi_turn_base_FULL",
    },
    "V4_xps_gpu_4b_u8": {
        "cell": "V4",
        "config": "xps_gpu_4b_u8",
        "run": "slo_escalate_a678926e-2681-4851-a386-8b7c83e971a3",
        "atlas": "multi_turn_long_context_OBS_MASK_K1024",
    },
    "V2_xps_cpu_4b": {
        "cell": "V2",
        "config": "xps_cpu_4b",
        "run": "slo_escalate_1acc8c58-a637-42a9-ac7a-78267b98f9ed",
        "atlas": "multi_turn_base_FULL",
    },
    "V1_t2s_gpu_4b_u8": {
        "cell": "V1",
        "config": "t2s_gpu_4b_u8",
        "run": "slo_escalate_b026f3fd-004e-4419-91bd-80c79f94e0f1",
        "atlas": "multi_turn_base_FULL",
    },
    "V4_t2s_gpu_4b_u8": {
        "cell": "V4",
        "config": "t2s_gpu_4b_u8",
        "run": "slo_escalate_f7de976b-4cad-471f-abd3-c2ff7a0b439b",
        "atlas": "multi_turn_long_context_OBS_MASK_K1024",
    },
    # V4 T2S rerun (approved 2026-10-14): same cell; f7de976b's only cloud
    # turn was dead, so its cloud cost was not measured.
    "V4_t2s_gpu_4b_u8_rerun": {
        "cell": "V4",
        "config": "t2s_gpu_4b_u8",
        "run": "slo_escalate_30caa847-d97a-4e4b-aa22-f152b95d08e9",
        "atlas": "multi_turn_long_context_OBS_MASK_K1024",
    },
    # V3 XPS in two chunks of DEMO1_PAIRED_15 (V3a [0:8], V3b [8:15]), one cell.
    "V3_xps_gpu_4b_u8": {
        "cell": "V3",
        "config": "xps_gpu_4b_u8",
        "runs": (
            "slo_escalate_71d33f7a-96dd-4e48-ba04-79810a3d4dc8",
            "slo_escalate_ab88f47f-3067-4d79-bf1e-ce533ed41fd2",
        ),
        "atlas": "multi_turn_long_context_FULL",
    },
    "V3_t2s_gpu_4b_u8": {
        "cell": "V3",
        "config": "t2s_gpu_4b_u8",
        "run": "slo_escalate_a4284ab0-7bb4-497a-8ff7-cc4d54817dd8",
        "atlas": "multi_turn_long_context_FULL",
    },
}
GROUPS = {
    "xps": ("V1_xps_gpu_4b_u8", "V4_xps_gpu_4b_u8"),
    "t2s": ("V1_t2s_gpu_4b_u8", "V4_t2s_gpu_4b_u8", "V3_t2s_gpu_4b_u8"),
    "v4_pair": ("V4_xps_gpu_4b_u8", "V4_t2s_gpu_4b_u8_rerun"),
    "v1v2_xps": ("V1_xps_gpu_4b_u8", "V2_xps_cpu_4b"),
    "v3_pair": ("V3_xps_gpu_4b_u8", "V3_t2s_gpu_4b_u8"),
}


def _band(value: float, band: list[float]) -> str:
    return "MATCH" if band[0] <= value <= band[1] else "MISS"


def _called(turn: dict[str, Any], name: str | None) -> bool:
    if not name:
        return False
    return any(
        str(call).startswith(name + "(")
        for step in turn.get("decoded_steps") or []
        for call in step
    )


def _ledger(run_dirs: Path | list[Path]) -> list[dict[str, Any]]:
    """Ledger entries of one run, or of a cell run in chunks (in chunk order)."""
    dirs = [run_dirs] if isinstance(run_dirs, Path) else list(run_dirs)
    out: list[dict[str, Any]] = []
    for d in dirs:
        out += json.loads((d / "turn_ledger.json").read_text(encoding="utf-8"))["entries"]
    return out


def entry_table(run_dir: Path | list[Path], atlas: str, edge: int = 10_000) -> list[dict[str, Any]]:
    ledger = _ledger(run_dir)
    gold = {
        r["entry_id"]: r
        for r in json.loads((ATLAS / f"{atlas}.json").read_text(encoding="utf-8"))["entries"]
    }
    rows = []
    for e in ledger:
        g = gold[e["entry_id"]]["turns"]
        gold_nctx = [t["n_ctx"] for t in g]
        jump = next((i for i, n in enumerate(gold_nctx) if n > edge), None)
        jump_call = g[jump - 1]["max_observation_call"] if jump else None
        live_turns = e["turns"]
        local_turns = [t for t in live_turns if t["placement"] == "local"]
        esc = next((t for t in live_turns if t["escalated"]), None)
        made_call = None
        if jump is not None and jump - 1 < len(live_turns):
            prior = live_turns[jump - 1]
            made_call = _called(prior, jump_call) if prior["placement"] == "local" else None
        rows.append(
            {
                "entry_id": e["entry_id"],
                "live_nctx_local_max": max((t["n_ctx"] for t in local_turns), default=None),
                "live_nctx_per_turn": [t["n_ctx"] for t in live_turns],
                "gold_nctx_per_turn": gold_nctx,
                "gold_max_nctx": max(gold_nctx),
                "gold_jump_turn": jump,
                "gold_jump_call": jump_call,
                "live_made_jump_call_locally": made_call,
                "escalated_turn": None if esc is None else esc["turn"],
                "escalate_reason": None if esc is None else esc["escalate_reason"],
                "escalation_nctx": None if esc is None else esc["n_ctx"],
                "escalation_ttft_s": None if esc is None else esc["ttft_s"],
                "usd": round(float(e["cloud_usd_entry"]), 4),
                "hybrid_pass": e["hybrid_pass"],
                "local_pass": e["local_pass"],
                "trajectory_pass": e["trajectory_pass"],
            }
        )
    return rows


def score_cell(key: str) -> dict[str, Any]:
    spec = CELLS[key]
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    pred = prereg["cells"][spec["cell"]]["configs"][spec["config"]]["prediction"]
    runs = list(spec["runs"]) if "runs" in spec else [spec["run"]]
    run_dirs = [ROOT / "derived" / "h1_hybrid" / r for r in runs]
    summaries = [json.loads((d / "summary.json").read_text(encoding="utf-8")) for d in run_dirs]
    rows = entry_table(run_dirs, spec["atlas"], EDGES[spec["config"]])
    ledger = _ledger(run_dirs)
    n_turns = sum(len(e["turns"]) for e in ledger)
    local = sum(1 for e in ledger for t in e["turns"] if t["placement"] == "local")
    n = len(ledger)
    usd = sum(float(x["running_usd"]) for x in summaries)
    measured = {
        "local_share": round(local / n_turns, 3),
        "usd": round(usd, 4),
        "usd_per_task": round(usd / n, 4),
        "escalations_ttft": sum(1 for r in rows if r["escalated_turn"] is not None),
        "n_entries": n,
        "n_turns": n_turns,
        "n_hybrid_pass": sum(x["quality"]["hybrid"]["n_hybrid_pass"] for x in summaries),
        "n_local_pass": sum(x["quality"]["local_probe"]["n_local_pass"] for x in summaries),
    }
    verdict = {
        "local_share": _band(measured["local_share"], pred["local_share"]),
        "usd_per_task": _band(measured["usd_per_task"], pred["usd_per_task"]),
        "escalations_ttft": _band(measured["escalations_ttft"], pred["escalations_ttft"]),
    }
    reached = [r for r in rows if r["gold_jump_turn"] is not None]
    return {
        "run_id": "+".join(runs),
        "gold_edge_tokens": EDGES[spec["config"]],
        "prediction": {k: pred[k] for k in ("local_share", "usd_per_task", "escalations_ttft")},
        "measured": measured,
        "verdict": verdict,
        "entries_with_gold_jump": len(reached),
        "gold_jump_entries_not_escalated": [
            r["entry_id"] for r in reached if r["escalated_turn"] is None
        ],
        "entries": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--group", choices=tuple(GROUPS), default="xps")
    args = parser.parse_args(argv)
    doc = {"kind": "demo1_cell_scores", "rule": __doc__.split("\n\n")[1], "cells": {}}
    for key in GROUPS[args.group]:
        doc["cells"][key] = score_cell(key)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    for key, c in doc["cells"].items():
        print(
            key,
            c["measured"],
            c["verdict"],
            "not escalated despite gold jump:",
            c["gold_jump_entries_not_escalated"],
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
