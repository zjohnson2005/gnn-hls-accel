"""DEMO-1 groundwork from committed data only: ENV-ATLAS, SLO-SENS, cell predictions.

No model, no device, no API. Inputs:
- analysis/demo1/atlas/*.json      offline sizing (tools/h1_context_sizing.py)
- corpus/normalized/trajectories.jsonl   SWE trajectories (context_len_before)
- sealed probe medians of the limit runs and the CAP-4 curves
- derived/h1_hybrid/demo1/*.meta.json    the subset pins

SLO-SENS method: the edge at target S for a config is the n where cold
prefill equals S, by log-log linear interpolation between the two adjacent
sealed probe medians that bracket S within one sealed run. The config's
limit run is used first; if it does not bracket S, the CAP-4 run of the same
platform, model and KV (XPS 4B u8 2b3316b6; T2S 4B u8 65e33de8). No
extrapolation: an unbracketed S is reported as a bound.

Predictions (for the draft prereg; written only where --predictions-out
points): slo_escalate routing under NON_RESIDENT. A turn escalates when its
n_ctx exceeds the config's sealed limit (TTFT > 10 s); the entry then stays on
cloud. Cloud $ = 3.20e-6 x 7.11 x n_ctx per cloud turn (d482c621: $3.20 per M
input, r^2 0.996; 7.11 cloud input tokens per local n_ctx).

Usage: python tools/demo1_atlas.py --out analysis/demo1/DEMO1_ATLAS.json \\
          [--predictions-out <scratch>/predictions.json]
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.h1_context_sizing import ENVELOPE_EDGES, envelope_bands  # noqa: E402

ATLAS_DIR = ROOT / "analysis" / "demo1" / "atlas"
PIN_DIR = ROOT / "derived" / "h1_hybrid" / "demo1"
SWE = ROOT / "corpus" / "normalized" / "trajectories.jsonl"
BEST_CONSUMER_LIMIT = 18_500
USD_PER_INPUT_TOKEN = 3.20e-6
CLOUD_TOKENS_PER_LOCAL_NCTX = 7.11
LIVE_FACTOR_P90 = 1.083
TARGETS_S = (5.0, 10.0, 20.0)

# Sealed cold limits: (last passing rung, first failing rung, run).
CONFIGS: dict[str, dict[str, Any]] = {
    "xps_cpu_4b": {"limit": 468, "fail": 687, "run": "7f232f86", "arm": "A", "curve": None},
    "xps_gpu_4b_u8": {
        "limit": 10_000,
        "fail": 10_250,
        "run": "c2246b1f",
        "arm": "gpu_only_u8",
        "curve": "2b3316b6",
    },
    "t2s_gpu_8b_u8": {
        "limit": 16_437,
        "fail": 16_625,
        "run": "56c116a6",
        "arm": "gpu_only_u8",
        "curve": None,
    },
    "t2s_gpu_4b_u8": {
        "limit": 18_500,
        "fail": 18_687,
        "run": "d2d5cc4a",
        "arm": "gpu_only_u8",
        "curve": "65e33de8",
    },
}


def probe_medians(run: str, arm: str) -> dict[int, float]:
    """Median prefill_s per n from a sealed run's probes.ndjson."""
    (run_dir,) = (ROOT / "derived").glob(f"*/sealed_{run}*")
    by: dict[int, list[float]] = defaultdict(list)
    for line in (run_dir / "probes.ndjson").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("arm_id") == arm and row.get("prefill_s") and row.get("n_tokens"):
            by[int(row["n_tokens"])].append(float(row["prefill_s"]))
    return {n: statistics.median(v) for n, v in sorted(by.items())}


def edge_at(medians: dict[int, float], target: float) -> dict[str, Any] | None:
    """n where prefill == target, log-log between bracketing medians; None if unbracketed."""
    points = sorted(medians.items())
    for (n0, t0), (n1, t1) in itertools.pairwise(points):
        if t0 <= target <= t1 and t1 > t0:
            slope = math.log(t1 / t0) / math.log(n1 / n0)
            n = n0 * (target / t0) ** (1.0 / slope)
            return {"n": round(n), "between": [n0, n1], "prefill_s": [round(t0, 2), round(t1, 2)]}
    return None


def slo_edges() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, cfg in CONFIGS.items():
        limit_run = probe_medians(cfg["run"], cfg["arm"])
        curve = probe_medians(cfg["curve"], cfg["arm"]) if cfg["curve"] else None
        per: dict[str, Any] = {}
        for target in TARGETS_S:
            got = edge_at(limit_run, target)
            source = cfg["run"]
            if got is None and curve is not None:
                got = edge_at(curve, target)
                source = cfg["curve"]
            if got is not None:
                per[f"{target:g}s"] = {**got, "source": source, "bound": None}
                continue
            pool = {**limit_run, **(curve or {})}
            lo_n, lo_t = min(pool.items())
            hi_n, hi_t = max(pool.items())
            if target < lo_t:
                bound = f"< {lo_n} ({lo_t:.2f} s at {lo_n})"
            else:
                bound = f"> {hi_n} ({hi_t:.2f} s at {hi_n})"
            per[f"{target:g}s"] = {"n": None, "source": None, "bound": bound}
        per["sealed_limit"] = {"limit": cfg["limit"], "first_fail": cfg["fail"], "run": cfg["run"]}
        out[name] = per
    return out


def load_sizing(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def swe_rows() -> list[dict[str, Any]]:
    rows = []
    for line in SWE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        turns = [{"n_ctx": t["context_len_before"]} for t in doc["turns"]]
        rows.append(
            {
                "entry_id": doc["trajectory_id"],
                "turns": turns,
                "max_n_ctx": max(t["n_ctx"] for t in turns),
            }
        )
    return rows


def bands_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_turn = [t["n_ctx"] for r in rows for t in r["turns"]]
    per_entry = [r["max_n_ctx"] for r in rows]
    return envelope_bands(per_turn, per_entry)


def in_band_share(rows: list[dict[str, Any]], lo: float, hi: float) -> dict[str, Any]:
    per_turn = [t["n_ctx"] for r in rows for t in r["turns"]]
    turns = sum(lo < n <= hi for n in per_turn)
    entries = sum(any(lo < t["n_ctx"] <= hi for t in r["turns"]) for r in rows)
    return {
        "turn_share": round(turns / len(per_turn), 4),
        "entries_with_a_turn": entries,
        "entry_share": round(entries / len(rows), 4),
    }


def atlas() -> dict[str, Any]:
    workloads: dict[str, Any] = {}
    for path in sorted(ATLAS_DIR.glob("*.json")):
        doc = load_sizing(path)
        workloads[path.stem] = {
            "source": f"analysis/demo1/atlas/{path.name}",
            "category": doc["category"],
            "retention_arm": doc.get("retention_arm", "FULL"),
            "obs_mask_k": doc.get("obs_mask_k"),
            "n_entries": doc["summary"]["n_entries"],
            "n_turns": doc["summary"]["n_turns"],
            "turn_n_ctx": doc["summary"]["turn_n_ctx"],
            "max_shown_observation_tokens": max(
                t.get("max_shown_observation_tokens", 0) for r in doc["entries"] for t in r["turns"]
            ),
            "envelope_bands": doc["summary"]["envelope_bands"],
        }
    swe = swe_rows()
    workloads["swe_trajectories"] = {
        "source": "corpus/normalized/trajectories.jsonl (context_len_before; logging model's tokens, not Qwen)",
        "category": "swe (replay only)",
        "retention_arm": "FULL",
        "n_entries": len(swe),
        "n_turns": sum(len(r["turns"]) for r in swe),
        "envelope_bands": bands_for(swe),
    }
    return workloads


def rows_for(stem: str) -> list[dict[str, Any]]:
    if stem == "swe_trajectories":
        return swe_rows()
    return load_sizing(ATLAS_DIR / f"{stem}.json")["entries"]


def slo_sens(edges: dict[str, Any], workloads: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for target in TARGETS_S:
        key = f"{target:g}s"
        xps = edges["xps_gpu_4b_u8"][key]
        best = edges["t2s_gpu_4b_u8"][key]
        if xps["n"] is None or best["n"] is None:
            out[key] = {"band": None, "note": f"edge unresolved: xps {xps}, t2s4b {best}"}
            continue
        band = (xps["n"], best["n"])
        out[key] = {
            "band": list(band),
            "shares": {w: in_band_share(rows_for(w), *band) for w in workloads},
        }
    return out


# ---------------------------------------------------------------- predictions


def route_entry(turns: list[int], limit: float) -> int:
    """Index of the first turn over the limit (slo_escalate is sticky); len if none."""
    for i, n in enumerate(turns):
        if n > limit:
            return i
    return len(turns)


def predict_cell(entries: dict[str, list[int]], config: str | None) -> dict[str, Any]:
    """Local share, $/task, spend split and trigger mix, as bands."""

    def run(scale: float, limit: float) -> dict[str, Any]:
        local = turns = escal = stay = 0
        usd = lat = ctx = 0.0
        for ctx_list in entries.values():
            sized = [n * scale for n in ctx_list]
            first = 0 if config is None else route_entry(sized, limit)
            turns += len(sized)
            local += first
            if first < len(sized) and config is not None:
                escal += 1
                stay += len(sized) - first - 1
            for n in sized[first:]:
                cost = n * CLOUD_TOKENS_PER_LOCAL_NCTX * USD_PER_INPUT_TOKEN
                usd += cost
                if n > BEST_CONSUMER_LIMIT:
                    ctx += cost
                else:
                    lat += cost
        return {
            "local_share": round(local / turns, 3),
            "usd": round(usd, 2),
            "usd_per_task": round(usd / len(entries), 3),
            "split_usd": {"capability": 0.0, "latency": round(lat, 2), "context": round(ctx, 2)},
            "escalations_ttft": escal,
            "stay_cloud_turns": stay,
        }

    if config is None:
        lo = run(1.0, 0)
        hi = run(LIVE_FACTOR_P90, 0)
        return {"low": lo, "high": hi}
    cfg = CONFIGS[config]
    # Fewest cloud turns: gold sizes, edge at the first failing rung.
    low = run(1.0, cfg["fail"])
    # Most cloud turns: live factor p90, edge at the last passing rung.
    high = run(LIVE_FACTOR_P90, cfg["limit"])
    return {"low": low, "high": high}


def pin_entries(pin: str, sizing_stem: str) -> dict[str, list[int]]:
    meta = json.loads((PIN_DIR / f"{pin}.meta.json").read_text(encoding="utf-8"))
    rows = {r["entry_id"]: r for r in rows_for(sizing_stem)}
    return {i: [t["n_ctx"] for t in rows[i]["turns"]] for i in meta["selected"]}


CELLS = {
    "V1": ("DEMO1_BASE_30", "multi_turn_base_FULL", ("xps_gpu_4b_u8", "t2s_gpu_4b_u8")),
    "V2": ("DEMO1_BASE_30", "multi_turn_base_FULL", ("xps_cpu_4b",)),
    # V3 and V4 share DEMO1_PAIRED_15 (docs/DEMO1_DESIGN.md, pairing).
    "V3": ("DEMO1_PAIRED_15", "multi_turn_long_context_FULL", ("xps_gpu_4b_u8", "t2s_gpu_4b_u8")),
    "V4": (
        "DEMO1_PAIRED_15",
        "multi_turn_long_context_OBS_MASK_K1024",
        ("xps_gpu_4b_u8", "t2s_gpu_4b_u8"),
    ),
}
SWEPT_K = (256, 512, 1024, 1536, 2048, 4096, 8192, 16384)


def v4_at_every_k() -> dict[str, Any]:
    """V4 predictions on DEMO1_PAIRED_15 at every swept K (K rule sensitivity)."""
    out: dict[str, Any] = {}
    for k in SWEPT_K:
        entries = pin_entries("DEMO1_PAIRED_15", f"multi_turn_long_context_OBS_MASK_K{k}")
        out[str(k)] = {
            "all_cloud_reference": predict_cell(entries, None),
            "configs": {c: predict_cell(entries, c) for c in ("xps_gpu_4b_u8", "t2s_gpu_4b_u8")},
        }
    return out


def predictions() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cell, (pin, stem, configs) in CELLS.items():
        entries = pin_entries(pin, stem)
        out[cell] = {
            "pin": pin,
            "sizing": stem,
            "n": len(entries),
            "all_cloud_reference": predict_cell(entries, None),
            "configs": {c: predict_cell(entries, c) for c in configs},
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--predictions-out", type=Path, default=None)
    args = parser.parse_args(argv)
    workloads = atlas()
    edges = slo_edges()
    sens_workloads = [
        "multi_turn_base_FULL",
        "multi_turn_long_context_FULL",
        "multi_turn_long_context_OBS_MASK_K1024",
        "swe_trajectories",
    ]
    doc = {
        "kind": "demo1_atlas",
        "measurement": False,
        "envelope_edges": list(ENVELOPE_EDGES),
        "atlas": workloads,
        "slo_sens": {"edges": edges, "in_band": slo_sens(edges, sens_workloads)},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.predictions_out is not None:
        args.predictions_out.parent.mkdir(parents=True, exist_ok=True)
        doc_pred = {"cells": predictions(), "v4_at_every_k": v4_at_every_k()}
        args.predictions_out.write_text(
            json.dumps(doc_pred, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(f"ATLAS {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
