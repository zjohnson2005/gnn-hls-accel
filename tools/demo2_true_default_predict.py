"""DEMO-2 true-default redesign: per-arm, per-host predictions from sealed data only.

Task AS, 2026-10-16. Runs nothing. Writes the predictions file that
docs/amendments/DEMO2_AMEND_2026-10-16_TRUE_DEFAULT.md registers by sha256:

  python tools/demo2_true_default_predict.py \\
      --out derived/h1_hybrid/demo2/DEMO2_AMEND_TRUE_DEFAULT_PREDICTIONS.json

Arms (hybrid_full, Qwen3-4B int4, GPU, GenAI 2026.2.1): A true default
(no SchedulerConfig, no KV property, no window, FULL); B device-only tuned
(u4, explicit scheduler, prompt lookup, window, FULL); C = B + OBS_MASK;
D (XPS only) = A + 4096 window.

$ model: tools/demo2_predict.py's registered per-entry model on the ENV-ATLAS
gold trajectories of DEMO2_HELDOUT_60 (same q bands, LIVE_JUMP, cost per
n_ctx), with per-arm mechanical triggers:
- A: no window. Sticky escalation when a step prompt + 512 exceeds the
  memory limit (XPS i8 resident limit 20,000, cf3555d5; u8 = i8 on GPU;
  T2S not binding at 64 GB), or step-0 n_ctx above the cold 10 s edge
  (XPS 10,000 c2246b1f; T2S 18,500 d2d5cc4a). With prefix caching on, the
  lower bound checks the edge on turn 0 only and the upper bound on every
  turn (as the registered RESIDENT profiles).
- B, C: window min(40,960, limit - 10%) on XPS. Point and hi use the sealed
  u4 limit 26,500 (e4a22dac) -> 23,850; lo uses the DERIVED chunk-cap leap
  (P3) -> 36,864. T2S window 40,960. Same edges (u4 cold edges are not
  sealed on either host; c647f0c7's 9,750 is HELD).
- D: window 4096, prefix caching on; prediction of record is the registered
  D-X band (DEMO2_PREREG_v1), carried over; the model value is diagnostic.
Proxy check (sealed DEMO-1 PAIRED_15 cells, FULL -> OBS_MASK K=1024, all
NON_RESIDENT u8 slo_escalate without a window, so KV, scheduler and window
differ from arm A): XPS 71d33f7a+ab88f47f -> a678926e, T2S a4284ab0 -> 30caa847.
Latency: d482c621 slo_escalate local turns (XPS GPU u8 RESIDENT, no
SchedulerConfig: the closest sealed analogue of arm A) and a DERIVED
bandwidth model. Passes: sealed per-category rates with Wilson 95% bands.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import aq_sealed_analyses as aq  # noqa: E402
from tools import demo2_predict as d2  # noqa: E402

PREREG = ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_PREREG_v1.json"
DEMO1 = ROOT / "derived" / "h1_hybrid" / "demo1"
NO_LIMIT = 10**9
SPEND_CEILING = 150.0

LIMITS = {
    "xps_i8_resident": (20_000, "cf3555d5 (u8 = i8 on GPU)"),
    "xps_u4_resident": (26_500, "e4a22dac"),
    "xps_cold_edge": (10_000, "c2246b1f (u8 = i8)"),
    "t2s_cold_edge": (18_500, "d2d5cc4a (u8 = i8)"),
    "model_max": (40_960, "Qwen3-4B max_position_embeddings"),
}
XPS_B_WINDOW = {"lo": 36_864, "point": 23_850, "hi": 23_850}

# Bandwidth model (DERIVED; docs/literature/2026-10-16/TUNED_PROFILE report):
# decode tok/s = BW / (weights + n_ctx * KV bytes per token). Qwen3-4B:
# 36 layers x 8 KV heads x 128 dims x K and V.
WEIGHT_BYTES = 2.353e9
KV_BYTES_PER_TOKEN = {"f16": 147_456, "i8": 73_728, "u4": 36_864}
PROMPT_LOOKUP_DECODE_SPEEDUP = (1.0, 1.3)  # P4 adoption needs >= 1.1; 1.3 = Intel/HF draft figure

ARMS: dict[str, dict[str, Any]] = {
    "A": {"label": "true default", "kv": "i8", "retention": "FULL"},
    "B": {"label": "device-only tuned", "kv": "u4", "retention": "FULL"},
    "C": {"label": "full tuned", "kv": "u4", "retention": "OBS_MASK_K1024"},
    "D": {"label": "ecosystem default (Ollama < 24 GiB tier)", "kv": "i8", "retention": "FULL"},
}
CELLS = {
    "A-X": ("XPS", "A"),
    "B-X": ("XPS", "B"),
    "C-X": ("XPS", "C"),
    "D-X2": ("XPS", "D"),
    "A-T": ("T2S", "A"),
    "B-T": ("T2S", "B"),
    "C-T": ("T2S", "C"),
}
PROXY = {
    "XPS": {"FULL": "XPS_V3", "OBS_MASK_K1024": "XPS_V4"},
    "T2S": {"FULL": "T2S_V3", "OBS_MASK_K1024": "T2S_V4"},
}


def triggers(host: str, arm: str, bound: str) -> dict[str, Any]:
    """Window (sticky overflow), memory limit (generation error) and cold edge."""
    edge = LIMITS["xps_cold_edge"][0] if host == "XPS" else LIMITS["t2s_cold_edge"][0]
    if arm in ("A", "D"):
        window = 4096 if arm == "D" else NO_LIMIT
        mem = LIMITS["xps_i8_resident"][0] if host == "XPS" else NO_LIMIT
    else:
        window = XPS_B_WINDOW[bound] if host == "XPS" else LIMITS["model_max"][0]
        mem = NO_LIMIT  # the window sits below the limit
    return {"window": window, "memory_limit": mem, "edge": edge}


def first_trigger(
    turns: list[dict[str, Any]], trig: dict[str, Any], *, every_turn: bool
) -> int | None:
    cap = min(trig["window"], trig["memory_limit"])
    for i, t in enumerate(turns):
        if int(t["max_step_prompt_tokens"]) + d2.GEN > cap:
            return i
        if int(t["n_ctx"]) > trig["edge"] and (every_turn or i == 0):
            return i
    return None


def predict_cost(ids: list[str], host: str, arm: str) -> dict[str, Any]:
    base = d2._atlas("multi_turn_base_FULL")
    long_name = (
        "multi_turn_long_context_OBS_MASK_K1024"
        if ARMS[arm]["retention"] == "OBS_MASK_K1024"
        else "multi_turn_long_context_FULL"
    )
    long_ = d2._atlas(long_name)
    out: dict[str, Any] = {}
    for bound in ("lo", "point", "hi"):
        q = d2.Q[bound]
        trig = triggers(host, arm, bound)
        usd = local = turns = esc = 0.0
        for i in ids:
            tr = base[i] if i.startswith("multi_turn_base_") else long_[i]
            t_idx = first_trigger(tr, trig, every_turn=(bound == "hi"))
            p_fire = 1.0
            if t_idx is not None and int(tr[t_idx]["n_ctx"]) > d2.JUMP_NCTX:
                p_fire = {
                    "lo": d2.LIVE_JUMP[0],
                    "point": sum(d2.LIVE_JUMP) / 2,
                    "hi": d2.LIVE_JUMP[1],
                }[bound]
            fired = d2.entry_cost(tr, t_idx, q)
            stayed = d2.entry_cost(tr, None, q)
            usd += p_fire * fired["usd"] + (1 - p_fire) * stayed["usd"]
            local += p_fire * fired["local_turns"] + (1 - p_fire) * stayed["local_turns"]
            turns += fired["turns"]
            esc += p_fire if t_idx is not None else 0.0
        out[bound] = {
            "usd_per_task": round(usd / len(ids), 4),
            "usd_total": round(usd, 2),
            "local_share": round(local / turns, 3),
            "mechanical_escalations": round(esc, 1),
            "triggers": {k: (None if v == NO_LIMIT else v) for k, v in trig.items()},
        }
    return out


def _cell_entries(label: str) -> list[dict[str, Any]]:
    cell = aq.DEMO1_CELLS[label]
    return aq.load_entries([aq.H1 / d for d in cell["dirs"]])


def _local_turns(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for e in entries for t in e["turns"] if t.get("placement") == "local"]


def proxy() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for host, pair in PROXY.items():
        rec: dict[str, Any] = {}
        for ret, label in pair.items():
            ents = _cell_entries(label)
            rec[ret] = {
                "cell": label,
                "run_ids": aq._run_ids(aq.DEMO1_CELLS[label]["dirs"]),
                "n": len(ents),
                "usd_per_task": round(
                    sum(e.get("cloud_usd_entry") or 0 for e in ents) / len(ents), 3
                ),
                "hybrid_passes": sum(bool(e.get("hybrid_pass")) for e in ents),
                "escalated_entries": sum(aq.escalated(e) for e in ents),
            }
        full, obs = rec["FULL"]["usd_per_task"], rec["OBS_MASK_K1024"]["usd_per_task"]
        rec["ratio_obs_over_full"] = round(obs / full, 3) if full else None
        out[host] = rec
    out["caveat"] = (
        "proxy cells ran NON_RESIDENT (prefix caching off, bare SchedulerConfig), u8 (= i8), "
        "slo_escalate, no window; arm A runs prefix caching on, i8, hybrid_full, no window"
    )
    return out


def _q(xs: list[float], p: int) -> float:
    return statistics.quantiles(xs, n=100)[p - 1]


def latency() -> dict[str, Any]:
    ents = aq.load_entries([aq.D482 / "slo_escalate"])
    loc = _local_turns(ents)
    ttft = [float(t["ttft_s"]) for t in loc if t.get("ttft_s")]
    gen = [float(t["t_generate"]) for t in loc]
    nctx = [int(t["n_ctx"]) for t in loc]
    dec = [float(t["decode_tok_s"]) for t in loc if t.get("decode_tok_s")]
    nctx50 = statistics.median(nctx)
    dec50 = statistics.median(dec)
    bw = dec50 * (WEIGHT_BYTES + nctx50 * KV_BYTES_PER_TOKEN["i8"])
    decode_share = statistics.median(
        [
            (float(t["t_generate"]) - float(t["ttft_s"])) / float(t["t_generate"])
            for t in loc
            if t.get("ttft_s") and float(t["t_generate"]) > 0
        ]
    )

    def tok_s(kv: str, n: float) -> float:
        return bw / (WEIGHT_BYTES + n * KV_BYTES_PER_TOKEN[kv])

    grid = {
        str(n): {kv: round(tok_s(kv, n), 1) for kv in ("f16", "i8", "u4")}
        for n in (3_500, 12_000, 20_000, 30_000)
    }
    u4_gain = tok_s("u4", nctx50) / tok_s("i8", nctx50)
    lo_pl, hi_pl = PROMPT_LOOKUP_DECODE_SPEEDUP
    # Turn generate time scales as (1 - s) + s / speedup, s = decode share.
    small = 1 - ((1 - decode_share) + decode_share / (u4_gain * lo_pl))
    large = 1 - ((1 - decode_share) + decode_share / (u4_gain * hi_pl))
    v1x = _local_turns(_cell_entries("XPS_V1"))
    v1t = _local_turns(_cell_entries("T2S_V1"))
    ratio = statistics.median([t["decode_tok_s"] for t in v1t if t.get("decode_tok_s")]) / (
        statistics.median([t["decode_tok_s"] for t in v1x if t.get("decode_tok_s")])
    )
    return {
        "source": "d482c621 slo_escalate local turns (XPS GPU u8 = i8, RESIDENT, no SchedulerConfig)",
        "n_local_turns": len(loc),
        "XPS_arm_A": {
            "ttft_s_p50": round(statistics.median(ttft), 3),
            "ttft_s_p90": round(_q(ttft, 90), 3),
            "turn_generate_s_p50": round(statistics.median(gen), 2),
            "turn_generate_s_p90": round(_q(gen, 90), 2),
            "n_ctx_p50": nctx50,
            "decode_tok_s_p50": round(dec50, 2),
            "basis": "MEASURED analogue (d482c621, W-3 base entries, 2026-09)",
        },
        "T2S_arm_A": {
            "turn_generate_s_p50": round(statistics.median(gen) / ratio, 2),
            "basis": "DERIVED: XPS p50 / T2S-over-XPS decode ratio "
            f"{ratio:.3f} (V1 b026f3fd vs f7343708, BASE_30, same config)",
            "ttft": "NOT YET MEASURED (no sealed T2S RESIDENT hybrid cell)",
        },
        "bandwidth_model": {
            "effective_GBps": round(bw / 1e9, 1),
            "basis": "DERIVED: d482c621 decode p50 at n_ctx p50 with i8 KV and "
            f"{WEIGHT_BYTES / 1e9:.3f} GB weights; theoretical peak 119.5 GB/s per "
            "Notebookcheck, unmeasured",
            "decode_tok_s_grid": grid,
        },
        "B_C_vs_A_local_turn_generate_reduction": {
            "lo": round(small, 3),
            "hi": round(large, 3),
            "basis": f"DERIVED: decode share {decode_share:.2f} (d482c621), u4/i8 decode gain "
            f"{u4_gain:.3f} at n_ctx p50, prompt lookup x{lo_pl}..x{hi_pl} on decode",
        },
    }


def _wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, mid - half), 3), round(min(1.0, mid + half), 3)]


def passes(px: dict[str, Any]) -> dict[str, Any]:
    d482 = {p: aq.load_entries([aq.D482 / p]) for p in ("slo_escalate", "full_signal_bounceback")}
    base_rates = {p: sum(bool(e.get("hybrid_pass")) for e in v) / len(v) for p, v in d482.items()}
    out: dict[str, Any] = {
        "base_half_rate": {
            "lo": round(min(base_rates.values()), 3),
            "hi": round(max(base_rates.values()), 3),
            "basis": "d482c621 W-3 200 hybrid pass rate, full_signal_bounceback .. slo_escalate; "
            "same for A, B, C (base entries rarely reach a mechanical trigger)",
        }
    }
    for host in ("XPS", "T2S"):
        for ret in ("FULL", "OBS_MASK_K1024"):
            rec = px[host][ret]
            out[f"{host}_long_half_{ret}"] = {
                "rate": round(rec["hybrid_passes"] / rec["n"], 3),
                "wilson95": _wilson(rec["hybrid_passes"], rec["n"]),
                "basis": f"{rec['cell']} {'+'.join(rec['run_ids'])}: "
                f"{rec['hybrid_passes']}/{rec['n']}",
            }
    return out


def caps(preds: dict[str, Any], d_registered: dict[str, Any]) -> dict[str, Any]:
    raw = {}
    for cell, p in preds.items():
        hi_total = d_registered["hi"]["usd_total"] if cell == "D-X2" else p["hi"]["usd_total"]
        raw[cell] = round(1.5 * hi_total, 2)
    return raw


def build() -> dict[str, Any]:
    pin = json.loads(d2.PIN_META.read_text(encoding="utf-8"))
    ids = pin["selected"]
    preds = {c: predict_cost(ids, h, a) for c, (h, a) in CELLS.items()}
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    d_reg = prereg["predictions"]["per_cell"]["D-X"]
    px = proxy()
    cell_caps = caps(preds, d_reg)
    total = round(sum(cell_caps.values()), 2)
    ratios = {
        host: {
            "C_over_A_point": round(
                preds[f"C-{h}"]["point"]["usd_per_task"] / preds[f"A-{h}"]["point"]["usd_per_task"],
                3,
            )
            if preds[f"A-{h}"]["point"]["usd_per_task"]
            else None,
            "B_over_A_point": round(
                preds[f"B-{h}"]["point"]["usd_per_task"] / preds[f"A-{h}"]["point"]["usd_per_task"],
                3,
            )
            if preds[f"A-{h}"]["point"]["usd_per_task"]
            else None,
            "proxy_obs_over_full": px[host]["ratio_obs_over_full"],
        }
        for host, h in (("XPS", "X"), ("T2S", "T"))
    }

    def _pin(name: str) -> list[str]:
        return json.loads((DEMO1 / f"{name}.meta.json").read_text(encoding="utf-8"))["selected"]

    p7_ids = _pin("DEMO1_BASE_30") + _pin("DEMO1_PAIRED_15")
    pilot = {
        "P7_entries": "DEMO1_BASE_30 + DEMO1_PAIRED_15 (45 entries; DEMO1_LONGCTX_30 holds 36 of "
        "the 39 jump entries and is priced below for the record)",
        "P7_discordance_trigger": "more than 25% of entries discordant (15 of 60 scaled: 12 of 45)",
        "P7_arm_A_per_run": {h: predict_cost(p7_ids, h, "A") for h in ("XPS", "T2S")},
        "P7_rejected_alternative_BASE_30_plus_LONGCTX_30_per_run": {
            h: predict_cost(_pin("DEMO1_BASE_30") + _pin("DEMO1_LONGCTX_30"), h, "A")["point"]
            for h in ("XPS", "T2S")
        },
        "P5_entries": "DEMO1_PAIRED_15, K in {512, 1024, 2048}, arm C settings, both hosts",
    }
    base30 = set(_pin("DEMO1_BASE_30"))
    d482_base = {
        pol: round(
            sum(
                e.get("cloud_usd_entry") or 0
                for e in aq.load_entries([aq.D482 / pol])
                if e["entry_id"] in base30
            ),
            2,
        )
        for pol in aq.D482_POLICIES
    }
    empirical = {
        h: round(max(d482_base.values()) + 15 * px[h]["FULL"]["usd_per_task"], 2)
        for h in ("XPS", "T2S")
    }
    pilot["P7_empirical_per_run_usd"] = {
        **empirical,
        "basis": "sealed costs on the same entries: BASE_30 = max over d482c621 policies "
        f"{d482_base} (XPS, RESIDENT); PAIRED_15 = DEMO-1 V3 FULL cells (XPS 71d33f7a+ab88f47f, "
        "T2S a4284ab0; NON_RESIDENT, so arm A should cost no more). The gold-trajectory model "
        "above over-predicts these jump-selected entries (DEMO-1 lesson).",
    }
    pilot["P7_cap_usd"] = {h: round(1.5 * 2 * empirical[h], 2) for h in ("XPS", "T2S")}
    pilot["P7_cap_rule"] = (
        "1.5 x 2 runs x the empirical per-run estimate; --max-usd stops a run at its cap"
    )
    pilot["P5_estimate_usd"] = {
        "XPS": round(3 * 15 * px["XPS"]["FULL"]["usd_per_task"], 2),
        "T2S": round(3 * 15 * px["T2S"]["FULL"]["usd_per_task"], 2),
        "basis": "upper estimate: 3 runs x 15 entries at the FULL proxy $/task "
        "(OBS_MASK at K <= 2048 costs less in both sealed pairs)",
    }
    return {
        "id": "DEMO2_AMEND_TRUE_DEFAULT_PREDICTIONS",
        "status": "registered with docs/amendments/DEMO2_AMEND_2026-10-16_TRUE_DEFAULT.md, "
        "before any DEMO-2 run",
        "generator": "tools/demo2_true_default_predict.py",
        "runner_must_not_read_this_file": True,
        "pin": {"name": "DEMO2_HELDOUT_60", "sha256": pin["entries_sha256"], "n": len(ids)},
        "limits": {k: {"tokens": v[0], "source": v[1]} for k, v in LIMITS.items()},
        "xps_b_c_window_by_bound": XPS_B_WINDOW,
        "cost_model": "tools/demo2_predict.py registered model (q bands, LIVE_JUMP, "
        "3.20e-6 x 7.11 $ per n_ctx) with per-arm triggers (see generator docstring)",
        "per_cell_usd": preds,
        "D_X2_prediction_of_record": {
            "source": "DEMO2_PREREG_v1 D-X band, carried over unchanged (Task AS: the ~8x "
            "prediction is withdrawn against A and kept against D)",
            **d_reg,
        },
        "ratios": ratios,
        "proxy": px,
        "latency": latency(),
        "memory_derived": {
            "kv_bytes_at_n_ctx_p50_GB": {
                kv: round(3935.5 * KV_BYTES_PER_TOKEN[kv] / 1e9, 3) for kv in ("i8", "u4")
            },
            "kv_bytes_at_40960_GB": {
                kv: round(40_960 * KV_BYTES_PER_TOKEN[kv] / 1e9, 2) for kv in ("i8", "u4")
            },
            "peak_working_set": "NOT YET MEASURED (telemetry added in Task AS part 6)",
        },
        "context_held": {
            "XPS_A": {"tokens": 20_000, "source": "cf3555d5 i8 resident limit"},
            "XPS_B_C": {
                "tokens": [26_500, 40_960],
                "source": "e4a22dac u4 resident limit; 40,960 only if the DERIVED P3 chunk-cap "
                "leap holds",
            },
            "XPS_D": {"tokens": 4096, "source": "window"},
            "T2S_A": {
                "tokens": None,
                "source": "memory not binding at 64 GB; uncapped (no window)",
            },
            "T2S_B_C": {"tokens": 40_960, "source": "window = max_position_embeddings"},
        },
        "passes": passes(px),
        "caps_usd": cell_caps,
        "caps_rule": "cap = 1.5 x the cell's hi-band total (D-X2: registered D-X hi band)",
        "caps_total_usd_one_replicate": total,
        "caps_total_usd_two_replicates": round(2 * total, 2),
        "ceiling_usd": SPEND_CEILING,
        "pilots": pilot,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    doc = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="ascii")
    for cell, p in doc["per_cell_usd"].items():
        print(cell, {b: (p[b]["usd_per_task"], p[b]["mechanical_escalations"]) for b in p})
    print("caps", doc["caps_usd"], "total", doc["caps_total_usd_one_replicate"])
    print("ratios", doc["ratios"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
