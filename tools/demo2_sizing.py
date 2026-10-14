"""DEMO-2 design sizing (sealed and committed data only; nothing measured).

Per workload and retention arm, from the ENV-ATLAS gold trajectories
(analysis/demo1/atlas): the share of turns that escalate mechanically
under the default control and under a tuned profile, with sticky
escalation (a turn and every later turn of the entry go to cloud once a
trigger fires). Triggers:
- window overflow: any step prompt of the turn plus GEN_HEADROOM tokens
  exceeds the configured window (checked at every step);
- TTFT edge: the step-0 prompt of the turn exceeds the device's sealed
  10 s cold edge (the runner's step-0 rule).
Cloud input tokens per escalated entry: atlas estimate (sum of n_ctx over
cloud turns x CLOUD_TOKENS_PER_LOCAL_NCTX, the DEMO-1 registered factor)
and measured (DEMO-1 ledgers, sum of cloud_tokens_in per escalated entry).
Quality-trigger rates come from the sealed H1-3POLICY run d482c621.

  python tools/demo2_sizing.py --out analysis/demo2/DEMO2_SIZING_20261014.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "analysis" / "demo1" / "atlas"
H1 = ROOT / "derived" / "h1_hybrid"

GEN_HEADROOM = 512  # H1 generation_config max_new_tokens
CLOUD_TOKENS_PER_LOCAL_NCTX = 7.11  # tools/demo1_v5_predict.py (DEMO-1 registered)
MODEL_WINDOW = 40_960  # Qwen3-4B/8B max_position_embeddings (docs/EXPERIMENT_attrib_results.md)
EDGES = {"XPS": (10_000, "c2246b1f"), "T2S": (18_500, "d2d5cc4a")}

PROFILES = {
    # Default control: 4096-token window (Ollama FAQ default), runtime
    # defaults otherwise; the 4096 window binds before either TTFT edge.
    "control_4096": {"window": 4096, "edge": None},
    "tuned_XPS": {"window": MODEL_WINDOW, "edge": EDGES["XPS"][0]},
    "tuned_T2S": {"window": MODEL_WINDOW, "edge": EDGES["T2S"][0]},
}
WORKLOADS = {
    "multi_turn_base": ("FULL", "OBS_MASK_K1024"),
    "multi_turn_long_context": ("FULL", "OBS_MASK_K1024"),
}
MEASURED = {
    "FULL": (
        ("V2 XPS CPU", "slo_escalate_1acc8c58-a637-42a9-ac7a-78267b98f9ed"),
        ("V3 T2S GPU", "slo_escalate_a4284ab0-7bb4-497a-8ff7-cc4d54817dd8"),
    ),
    "OBS_MASK_K1024": (
        ("V4 XPS GPU", "slo_escalate_a678926e-2681-4851-a386-8b7c83e971a3"),
        ("V4 T2S GPU rerun", "slo_escalate_30caa847-d97a-4e4b-aa22-f152b95d08e9"),
    ),
}
QUALITY_RUN = "interleaved_d482c621-4292-4281-b6a1-8635e5eeb6da"


def _trigger(turn: dict[str, Any], window: int, edge: int | None) -> str | None:
    if int(turn["max_step_prompt_tokens"]) + GEN_HEADROOM > window:
        return "window_overflow"
    if edge is not None and int(turn["n_ctx"]) > edge:
        return "ttft_edge"
    return None


def profile_share(entries: list[dict[str, Any]], window: int, edge: int | None) -> dict[str, Any]:
    n_turns = cloud_turns = esc_entries = 0
    reasons: dict[str, int] = {}
    tokens: list[float] = []
    for e in entries:
        turns = e["turns"]
        n_turns += len(turns)
        first = None
        for t in turns:
            r = _trigger(t, window, edge)
            if r is not None:
                first = int(t["turn"])
                reasons[r] = reasons.get(r, 0) + 1
                break
        if first is None:
            continue
        esc_entries += 1
        cloud = [t for t in turns if int(t["turn"]) >= first]
        cloud_turns += len(cloud)
        tokens.append(sum(int(t["n_ctx"]) for t in cloud) * CLOUD_TOKENS_PER_LOCAL_NCTX)
    return {
        "entries": len(entries),
        "turns": n_turns,
        "escalated_entries": esc_entries,
        "entry_share": round(esc_entries / len(entries), 3),
        "cloud_turn_share": round(cloud_turns / n_turns, 3),
        "first_trigger": reasons,
        "cloud_input_tokens_per_escalated_entry_est": {
            "median": round(statistics.median(tokens)) if tokens else None,
            "mean": round(statistics.mean(tokens)) if tokens else None,
        },
    }


def measured_tokens(run: str) -> dict[str, Any]:
    ledger = json.loads((H1 / run / "turn_ledger.json").read_text(encoding="utf-8"))["entries"]
    per = [
        sum(int(t.get("cloud_tokens_in") or 0) for t in e["turns"])
        for e in ledger
        if any(t["placement"] != "local" for t in e["turns"])
    ]
    per = [x for x in per if x > 0]
    return {
        "run_id": run.split("_", 2)[-1],
        "escalated_entries_billed": len(per),
        "median": round(statistics.median(per)) if per else None,
        "mean": round(statistics.mean(per)) if per else None,
    }


def quality_rates() -> dict[str, Any]:
    out: dict[str, Any] = {
        "run_id": QUALITY_RUN.split("_", 1)[1],
        "workload": "multi_turn_base 200",
    }
    for pol in ("emission_escalate", "full_signal_bounceback"):
        ledger = json.loads(
            (H1 / QUALITY_RUN / "policies" / pol / "turn_ledger.json").read_text(encoding="utf-8")
        )["entries"]
        turns = sum(len(e["turns"]) for e in ledger)
        cloud = sum(1 for e in ledger for t in e["turns"] if t["placement"] != "local")
        esc = sum(1 for e in ledger if any(t["placement"] != "local" for t in e["turns"]))
        out[pol] = {
            "entries_with_cloud_turn": esc,
            "entry_share": round(esc / len(ledger), 3),
            "cloud_turn_share": round(cloud / turns, 3),
        }
    return out


def sizing() -> dict[str, Any]:
    work: dict[str, Any] = {}
    for wl, arms in WORKLOADS.items():
        for arm in arms:
            entries = json.loads((ATLAS / f"{wl}_{arm}.json").read_text(encoding="utf-8"))[
                "entries"
            ]
            work[f"{wl}_{arm}"] = {
                name: profile_share(entries, p["window"], p["edge"]) for name, p in PROFILES.items()
            }
    return {
        "kind": "demo2_sizing",
        "basis": "ENV-ATLAS gold trajectories; DEMO-1 ledgers; d482c621. Nothing measured.",
        "gen_headroom_tokens": GEN_HEADROOM,
        "cloud_tokens_per_local_nctx": CLOUD_TOKENS_PER_LOCAL_NCTX,
        "profiles": PROFILES,
        "edges": EDGES,
        "mechanical": work,
        "measured_cloud_input_tokens_per_escalated_entry": {
            arm: {label: measured_tokens(run) for label, run in runs}
            for arm, runs in MEASURED.items()
        },
        "quality_triggers": quality_rates(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    doc = sizing()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    for key, profs in doc["mechanical"].items():
        for name, r in profs.items():
            print(
                f"{key:40s} {name:13s} entries {r['entry_share']:.3f} turns "
                f"{r['cloud_turn_share']:.3f} first {r['first_trigger']} "
                f"tok/esc {r['cloud_input_tokens_per_escalated_entry_est']['median']}"
            )
    print(json.dumps(doc["measured_cloud_input_tokens_per_escalated_entry"]))
    print(json.dumps(doc["quality_triggers"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
