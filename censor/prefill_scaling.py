"""Prefill scaling measurement (Item H) and Item B re-run under fitted exponent.

NO EXTERNAL ANCHOR exists for prefill at 115K — that is why this is a finding
rather than a validation. Absolute rates measured on Lunar Lake iGPU / CPU with
a 0.5B model do NOT transfer; only the scaling exponent is claimed, and the
result is marked EXTRAPOLATED with distance stated.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from censor.kv_math import MODEL_SPECS
from censor.latency_ratio import HIT_RATES
from censor.prefill_bounds import (
    EMPIRICAL_LC,
    PP512_ANCHOR_LEN,
    SCALING_MODELS,
    prefill_rate_at,
)
from censor.prelim_phase1 import _v, hw_configs, load_params

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "characterization" / "v2"

DEPTHS_REQUESTED = (512, 2048, 8192, 32768, 65536)


def parse_bench_json(path: Path) -> list[dict[str, Any]]:
    """Parse llama-bench -o json output into per-depth rows."""
    if not path.is_file() or path.stat().st_size == 0:
        return []
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Sometimes PowerShell wraps or the file contains multiple JSON values.
        return []
    if isinstance(data, dict):
        data = [data]
    rows: list[dict[str, Any]] = []
    for r in data:
        # llama-bench json fields: n_prompt, avg_ts (tok/s), ... 
        n_prompt = int(r.get("n_prompt") or r.get("pp") or 0)
        n_gen = int(r.get("n_gen") or r.get("tg") or 0)
        if n_gen > 0 and n_prompt == 0:
            continue  # decode-only row
        ts = r.get("avg_ts")
        if ts is None:
            ts = r.get("tokens_per_second")
        alloc_ok = True
        err = r.get("error") or r.get("err")
        if err:
            alloc_ok = False
        rows.append({
            "depth": n_prompt,
            "n_gen": n_gen,
            "tok_per_sec": float(ts) if ts is not None else float("nan"),
            "alloc_ok": alloc_ok,
            "backend": r.get("backend") or r.get("n_gpu_layers"),
            "model": r.get("model_filename") or r.get("model"),
            "raw": {k: v for k, v in r.items() if k != "samples_ns"},
        })
    return rows


def fit_exponent(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Fit R(L) = R0 * (L0/L)^alpha on successful depth points (log-log).

    Returns alpha with a crude leave-one-out CI. alpha=0 => flat; alpha=1 =>
    inverse-linear (attention-theoretic-like once attention dominates);
    alpha=2 => inverse-quadratic.
    """
    pts = [
        (r["depth"], r["tok_per_sec"])
        for r in rows
        if r["alloc_ok"] and r["depth"] > 0 and r["tok_per_sec"] == r["tok_per_sec"] and r["tok_per_sec"] > 0
    ]
    pts.sort()
    if len(pts) < 2:
        return {
            "alpha": float("nan"),
            "alpha_lo": float("nan"),
            "alpha_hi": float("nan"),
            "r0_at_512": float("nan"),
            "n_points": len(pts),
            "r_squared": float("nan"),
            "note": "insufficient successful depth points to fit",
        }

    xs = [math.log(d) for d, _ in pts]
    ys = [math.log(r) for _, r in pts]
    n = len(xs)
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    sxx = sum((x - xbar) ** 2 for x in xs)
    sxy = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
    # log R = log R0_ref - alpha * log L  => slope = -alpha
    slope = sxy / sxx if sxx > 0 else 0.0
    alpha = -slope
    intercept = ybar - slope * xbar  # log R at log-space origin; use to get R(512)
    r0_512 = math.exp(intercept + slope * math.log(512.0))

    ss_tot = sum((y - ybar) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    # Leave-one-out alphas for a crude CI.
    alphas = []
    for i in range(n):
        xs2 = xs[:i] + xs[i + 1:]
        ys2 = ys[:i] + ys[i + 1:]
        if len(xs2) < 2:
            continue
        xb = sum(xs2) / len(xs2)
        yb = sum(ys2) / len(ys2)
        sxx2 = sum((x - xb) ** 2 for x in xs2)
        sxy2 = sum((x - xb) * (y - yb) for x, y in zip(xs2, ys2))
        if sxx2 > 0:
            alphas.append(-(sxy2 / sxx2))
    alphas.sort()
    return {
        "alpha": alpha,
        "alpha_lo": alphas[0] if alphas else alpha,
        "alpha_hi": alphas[-1] if alphas else alpha,
        "r0_at_512": r0_512,
        "n_points": n,
        "r_squared": r2,
        "depths_used": [d for d, _ in pts],
        "rates_used": [r for _, r in pts],
        "note": (
            "Power-law fit on cold-prefill tok/s vs prompt length. "
            "Absolute rate is Lunar Lake / 0.5B and does NOT transfer; "
            "only alpha is claimed."
        ),
    }


def discriminate_models(rows: list[dict[str, Any]], fit: dict[str, Any]) -> dict[str, Any]:
    """Which of the three Phase-2 scaling models does the data support?"""
    by_d = {r["depth"]: r for r in rows if r["alloc_ok"] and r["tok_per_sec"] == r["tok_per_sec"]}
    if 512 not in by_d:
        return {"verdict": "INCONCLUSIVE", "reason": "no pp512 measurement"}

    r512 = by_d[512]["tok_per_sec"]
    spec = MODEL_SPECS["llama31_8b"]  # architecture class for theoretic curve shape
    # Compare measured ratio R(L)/R(512) to each model at available depths.
    errors: dict[str, list[float]] = {m: [] for m in SCALING_MODELS}
    for d, r in by_d.items():
        if d == 512:
            continue
        measured_ratio = r["tok_per_sec"] / r512
        for m in SCALING_MODELS:
            pred = prefill_rate_at(r512, m, float(d), spec) / r512
            errors[m].append(abs(math.log(max(measured_ratio, 1e-12)) - math.log(max(pred, 1e-12))))

    mean_err = {m: (sum(v) / len(v) if v else float("inf")) for m, v in errors.items()}
    best = min(mean_err, key=mean_err.get)
    # Exclusion: a model whose mean log-error is >2x the best is excluded.
    excluded = [m for m, e in mean_err.items() if e > 2.0 * mean_err[best] and m != best]

    # Also use alpha as a coarse discriminator.
    alpha = fit.get("alpha", float("nan"))
    alpha_vote = "inconclusive"
    if alpha == alpha:
        if abs(alpha) < 0.25:
            alpha_vote = "optimistic_flat"
        elif 0.6 <= alpha <= 1.4:
            alpha_vote = "linear_attention_theoretic"
        elif alpha > 1.6:
            alpha_vote = "quadratic_pessimistic"

    # Prefer the alpha vote when it is decisive; ratio-error against an 8B
    # theoretic curve on 0.5B measurements is itself a cross-architecture
    # extrapolation and can mis-rank.
    if alpha == alpha and abs(alpha) < 0.25:
        verdict = "optimistic_flat"
        note_extra = (
            f" alpha={alpha:.3f}<0.25 overrides ratio-error winner ({best}); "
            "shallow power-law on this hardware looks closer to flat."
        )
    elif alpha == alpha and alpha > 1.6:
        verdict = "quadratic_pessimistic"
        note_extra = f" alpha={alpha:.3f}>1.6 overrides ratio-error winner ({best})."
    else:
        verdict = best
        note_extra = ""

    return {
        "best_by_ratio_error": best,
        "mean_log_error": mean_err,
        "excluded": excluded,
        "alpha": alpha,
        "alpha_vote": alpha_vote,
        "verdict": verdict,
        "supported": verdict,
        "note": (
            f"Primary verdict={verdict}; ratio-error winner={best}; "
            f"alpha={alpha:.3f} votes {alpha_vote}. "
            f"Excluded (log-error >2x best): {excluded or 'none'}."
            + note_extra
        ),
    }


def rate_at_fitted(pp512: float, L: float, fit: dict[str, Any]) -> float:
    """R(L) = R(512) * (512/L)^alpha, using the measured alpha."""
    alpha = fit["alpha"]
    if alpha != alpha:  # NaN
        return float("nan")
    return pp512 * (PP512_ANCHOR_LEN / L) ** alpha


def itemB_rerun(fit: dict[str, Any]) -> list[dict[str, Any]]:
    """Re-run the 45-combination latency table under the fitted exponent.

    Replaces the 3-model bracket with a single fitted scaling law, but still
    sweeps hit rate and hardware. Marked EXTRAPOLATED.
    """
    from censor.latency_ratio import HIT_RATES as HR

    p = load_params()
    context_floor = float(_v(p["workload"]["context_floor"]))
    delta = float(_v(p["local_runtime"]["local_kv_persistence"]["delta_tokens_per_turn"]))
    out_tokens = float(_v(p["workload"]["tokens_per_step"]["output_tokens_median"]))
    ttft_s = float(_v(p["cloud"]["ttft_ms"])) / 1000.0
    cloud_tps = float(_v(p["cloud"]["output_tok_per_sec"]["pure_decode"]))
    rtt_s = float(_v(p["cloud"]["rtt_ms"])) / 1000.0
    t_cloud = ttft_s + out_tokens / cloud_tps + rtt_s

    rows: list[dict[str, Any]] = []
    alpha = fit.get("alpha", float("nan"))
    for hw in hw_configs(p):
        pp512 = float(hw.prefill_tok_per_sec_pp512)
        decode = float(hw.decode_tok_per_sec)
        decode_s = out_tokens / decode
        rate = rate_at_fitted(pp512, context_floor, fit)
        if rate != rate or rate <= 0:
            continue
        t_hit = delta / rate + decode_s
        t_miss = context_floor / rate + decode_s
        for h in HR:
            t_exp = h * t_hit + (1.0 - h) * t_miss
            ratio = t_exp / t_cloud
            e_star = 1.0 - ratio
            rows.append({
                "hw_config": hw.name,
                "scaling": "fitted_power_law",
                "alpha": alpha,
                "alpha_lo": fit.get("alpha_lo"),
                "alpha_hi": fit.get("alpha_hi"),
                "prefill_rate_at_context_floor": rate,
                "hit_rate_h": h,
                "T_local_expected_s": t_exp,
                "T_cloud_s": t_cloud,
                "ratio_local_over_cloud": ratio,
                "max_tolerable_escalation_rate_e_star": e_star,
                "verdict": (
                    "DEAD_ON_LATENCY_regardless_of_escalation_rate"
                    if ratio >= 1.0
                    else "local_first_wins_only_if_escalation_below_e_star"
                ),
                "regime": "EXTRAPOLATED",
                "extrapolation_distance": (
                    f"exponent fitted to depths {fit.get('depths_used')} on "
                    f"Lunar Lake + Qwen2.5-0.5B; absolute rate from published "
                    f"pp512 on target hw; applied at context_floor={context_floor:.0f} "
                    f"({context_floor / max(fit.get('depths_used') or [1]):.1f}x beyond "
                    f"deepest measured depth)"
                ),
            })
    return rows


def analyze_or_stub(bench_path: Path | None = None) -> dict[str, Any]:
    path = bench_path or (OUT / "prefill_bench_raw.json")
    rows = parse_bench_json(path)
    # Also accept a hand-written CSV fallback.
    csv_path = OUT / "prefill_scaling.csv"
    if not rows and csv_path.is_file():
        import csv
        with csv_path.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows.append({
                    "depth": int(float(r["depth"])),
                    "tok_per_sec": float(r["tok_per_sec"]) if r.get("tok_per_sec") else float("nan"),
                    "alloc_ok": str(r.get("alloc_ok", "True")).lower() in {"1", "true", "yes"},
                    "n_gen": 0,
                })

    fit = fit_exponent(rows) if rows else {
        "alpha": float("nan"), "n_points": 0,
        "note": "bench not yet available",
    }
    disc = discriminate_models(rows, fit) if rows else {"verdict": "PENDING"}
    return {"rows": rows, "fit": fit, "discrimination": disc}
