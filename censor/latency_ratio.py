"""Characterization cell 2c: local/cloud per-turn LATENCY ratio.

Phase 1 measured cost only. Local can win on cost and lose on latency, and this
cell had never been on any measurement list. Derivable today from the Phase-2
prefill bracket plus existing decode rates -- no hardware.

AMENDMENT (Item A consequence). T_local is a MIXTURE, not a point. Under
`persists`, prefill is delta-sized on a cache HIT and context_floor-sized on a
MISS, and the miss path is ~700x the hit path:

    T_local_expected = h*T_local(delta) + (1-h)*T_local(context_floor)

Both the prefill scaling model and h are carried as brackets. Never a midpoint.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from censor.kv_math import MODEL_SPECS
from censor.prefill_bounds import SCALING_MODELS, prefill_rate_at
from censor.prelim_phase1 import _v, hw_configs, load_params

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "characterization"
OUT.mkdir(parents=True, exist_ok=True)

# h = 1.0 is the pure `persists` endpoint; h = 0.0 is the pure `recomputes`
# endpoint. Both are ENDPOINTS of the bracket, not midpoints.
HIT_RATES: tuple[float, ...] = (0.0, 0.5, 0.8, 0.95, 1.0)


def run() -> dict[str, Any]:
    p = load_params()
    spec = MODEL_SPECS["llama31_8b"]  # all three hw configs run the 7-8B class

    context_floor = float(_v(p["workload"]["context_floor"]))
    delta = float(_v(p["local_runtime"]["local_kv_persistence"]["delta_tokens_per_turn"]))
    out_tokens = float(_v(p["workload"]["tokens_per_step"]["output_tokens_median"]))

    ttft_s = float(_v(p["cloud"]["ttft_ms"])) / 1000.0
    ttft_lo = float(_v(p["cloud"]["ttft_ms"], "lo")) / 1000.0
    ttft_hi = float(_v(p["cloud"]["ttft_ms"], "hi")) / 1000.0
    cloud_tps = float(_v(p["cloud"]["output_tok_per_sec"]["pure_decode"]))
    rtt_s = float(_v(p["cloud"]["rtt_ms"])) / 1000.0

    # B2: cloud per-turn latency. Prefill time is inside TTFT (trace-derived),
    # so it is not added separately.
    t_cloud = ttft_s + out_tokens / cloud_tps + rtt_s
    t_cloud_fast = ttft_lo + out_tokens / float(_v(p["cloud"]["output_tok_per_sec"]["pure_decode"], "hi")) + \
        float(_v(p["cloud"]["rtt_ms"], "lo")) / 1000.0
    t_cloud_slow = ttft_hi + out_tokens / float(_v(p["cloud"]["output_tok_per_sec"]["pure_decode"], "lo")) + \
        float(_v(p["cloud"]["rtt_ms"], "hi")) / 1000.0

    rows: list[dict[str, Any]] = []
    for hw in hw_configs(p):
        pp512 = float(hw.prefill_tok_per_sec_pp512)
        decode = float(hw.decode_tok_per_sec)
        decode_s = out_tokens / decode
        for model in SCALING_MODELS:
            # Degradation is a function of RESIDENT context, which is
            # context_floor on both paths -- the hit path prefills fewer tokens,
            # it does not prefill them against a shorter context.
            rate = prefill_rate_at(pp512, model, context_floor, spec)
            t_hit = delta / rate + decode_s
            t_miss = context_floor / rate + decode_s
            for h in HIT_RATES:
                t_exp = h * t_hit + (1.0 - h) * t_miss
                ratio = t_exp / t_cloud
                e_star = 1.0 - ratio
                if ratio >= 1.0:
                    verdict = "DEAD_ON_LATENCY_regardless_of_escalation_rate"
                elif e_star >= 0.5:
                    verdict = "local_first_wins_with_wide_margin"
                else:
                    verdict = "local_first_wins_only_if_escalation_below_e_star"
                rows.append({
                    "hw_config": hw.name,
                    "prefill_scaling_model": model,
                    "prefill_rate_at_context_floor_tok_per_sec": rate,
                    "decode_tok_per_sec": decode,
                    "hit_rate_h": h,
                    "h_label": (
                        "pure_recomputes_endpoint" if h == 0.0
                        else "pure_persists_endpoint" if h == 1.0
                        else "mixture"
                    ),
                    "T_local_hit_s": t_hit,
                    "T_local_miss_s": t_miss,
                    "T_local_expected_s": t_exp,
                    "T_cloud_s": t_cloud,
                    "T_cloud_fast_s": t_cloud_fast,
                    "T_cloud_slow_s": t_cloud_slow,
                    "ratio_local_over_cloud": ratio,
                    "max_tolerable_escalation_rate_e_star": e_star,
                    "e_star_vs_slow_cloud": 1.0 - t_exp / t_cloud_slow,
                    "e_star_vs_fast_cloud": 1.0 - t_exp / t_cloud_fast,
                    "verdict": verdict,
                    "prefill_tokens_hit": delta,
                    "prefill_tokens_miss": context_floor,
                    "output_tokens": out_tokens,
                    "confidence": "estimated",
                    "source": (
                        "T_local from censor/prefill_bounds.py scaling models over the "
                        "published pp512 rate in study_params (confidence: published) and "
                        "published decode rates; h swept, NOT measured (study_params "
                        "local_runtime.prompt_cache_hit_rate_local, confidence: guess). "
                        "T_cloud from study_params cloud.ttft_ms + output_tok_per_sec."
                        "pure_decode + rtt_ms (TraceLab-derived, confidence: published "
                        "except rtt estimated)."
                    ),
                })

    _write_csv(OUT / "latency_ratio.csv", rows)
    return {
        "rows": rows,
        "t_cloud": t_cloud,
        "t_cloud_fast": t_cloud_fast,
        "t_cloud_slow": t_cloud_slow,
        "context_floor": context_floor,
        "delta": delta,
        "out_tokens": out_tokens,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    r = run()
    print(f"T_cloud = {r['t_cloud']:.3f} s  (fast {r['t_cloud_fast']:.3f} / slow {r['t_cloud_slow']:.3f})")
    print(f"delta={r['delta']:.0f} tok  context_floor={r['context_floor']:.0f} tok  out={r['out_tokens']:.0f} tok")
    print()
    hdr = f"{'hw':<22}{'scaling':<28}{'h':>6}{'T_local':>11}{'ratio':>9}{'e*':>9}  verdict"
    print(hdr)
    for row in r["rows"]:
        print(
            f"{row['hw_config']:<22}{row['prefill_scaling_model']:<28}"
            f"{row['hit_rate_h']:>6.2f}{row['T_local_expected_s']:>11.3f}"
            f"{row['ratio_local_over_cloud']:>9.3f}"
            f"{row['max_tolerable_escalation_rate_e_star']:>9.3f}  "
            f"{'DEAD' if row['ratio_local_over_cloud'] >= 1.0 else 'ok'}"
        )
    dead = [x for x in r["rows"] if x["ratio_local_over_cloud"] >= 1.0]
    print(f"\nDEAD-on-latency combinations: {len(dead)} / {len(r['rows'])}")
    print(f"Wrote {OUT / 'latency_ratio.csv'}")


if __name__ == "__main__":
    main()
