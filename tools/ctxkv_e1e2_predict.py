"""CTXKV-E1E2 predictions (DERIVED, before any E1/E2 run): context provisioning and KV capacity.

Writes derived/ctxkv/CTXKV_E1E2_PREDICTIONS.json, registered by
docs/registrations/CTXKV_E1E2_2026-10-23.md ("REG"). Separate from DEMO-2. Mac, no model, $0.

Inputs. None of them has a sealed run in this repo; each is labelled by its source:
- PILOT (Rithwik, AMD Ryzen AI Max+ 395, qwen3:14b, Ollama, n = 150 short tool tasks; reported
  to Zach, no run_id here; exploratory): share wrong by num_ctx 40,960 11.3%, 16,384 12.7%,
  8,192 35.3%, 4,096 42.0% (4,096 with instruction protection 30.0%); 40-step qwen3:14b
  sessions 214.8 min (f16 KV) vs 75.4 min (q8_0 KV).
- ASSUMED: cloud pass q on short tasks 0.95 (sweep 0.90 / 0.95 / 0.98; q is measured by the
  shared cloud-only log); paired discordance between equal-quality arms 8% (5% sensitivity).
- LITERATURE: Qwen3-8B geometry 36 layers, 8 KV heads, head_dim 128 (Hugging Face config; the
  same geometry as our Qwen3-4B, kv_geometry 1fd81d2a); Qwen3-14B 40 / 8 / 128; ggml q8_0 =
  34 bytes per 32 elements; Ollama default num_ctx by VRAM: < 24 GiB 4,096, 24-48 GiB 32,768,
  >= 48 GiB 262,144 clamped to the model's trained 40,960 (docs.ollama.com/context-length).
- E2 cost inputs (replaceable defaults, REG section E2.4): $2,000 box, 3-year straight line,
  120 W wall, $0.16/kWh, 160 active h/month.
- MEASURED here (XPS, OpenVINO, Qwen3-4B): resident limits f16 / u8 / u4 15,000 / 20,000 /
  26,500 (553b3a5c, cf3555d5, e4a22dac); T2S u4/i8 decode at 12,000 1.082 (0a55c316 vs
  29209e26).

E1 model: random-order escalation (the DEMO-2 identity). An arm with local pass p needs the
share f(Q) = (Q - p) / (q - p) escalated to reach Q (0 if p >= Q; unreachable if q < Q).
Per simulated run (n tasks): nested local passes (the larger window passes every task the
smaller one passes), independent cloud passes; f from the sample means; Delta escalations per
1,000 = 1000 (f_A - f_X); paired bootstrap (B draws, same indices) 95% percentile CI. Reported:
analytic point, 2.5-97.5 percentiles of the simulated point, and power = share of runs whose CI
lower end is > 0.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

SEED = 20261023
NSIM = 400
BOOT = 2000
N_CONFIRM = 200
Q_CLOUD = 0.95
Q_SWEEP = (0.90, 0.95, 0.98)
TARGETS = (0.85, 0.90)
DISC = 0.08
DISC_SENS = 0.05
# PILOT local pass (1 - share wrong) by window, qwen3:14b on AMD (Rithwik, n = 150).
PILOT_PASS = {4096: 0.580, 8192: 0.647, 16384: 0.873, 40960: 0.887}
PILOT_PASS_4096_PROTECTED = 0.700
GEOM = {"qwen3:8b": (36, 8, 128), "qwen3:14b": (40, 8, 128)}  # layers, kv heads, head_dim
KV_BYTES = {"f16": 2.0, "q8_0": 34 / 32}
# E2 PILOT session minutes and cost defaults.
T_R_MIN = 214.8
T_X1_MIN = 75.4
BOX_USD = 2000.0
LIFE_Y = 3.0
WATTS = 120.0
USD_KWH = 0.16
ACTIVE_H_MONTH = 160.0
# XPS resident-session limits (OpenVINO, Qwen3-4B): 553b3a5c, cf3555d5, e4a22dac.
XPS_LIMITS = {"f16": 15000, "u8": 20000, "u4": 26500}
T2S_U4_OVER_I8_12K = 1.082  # 0a55c316 / 29209e26
# Cloud price inputs (REG E1.5): Sonnet 5.5 list per MTok as given in the research report
# (Anthropic pricing page, Oct 2026), NOT YET in configs/pricing/anthropic.yaml.
PRICE = {"input": 2.00, "write_5m": 2.50, "read": 0.10, "output": 10.00}


def f_need(p: float, q: float, target: float) -> float:
    if p >= target:
        return 0.0
    if q <= target:
        return math.inf
    return (target - p) / (q - p)


def kv_gib(model: str, tokens: int, dtype: str) -> float:
    layers, heads, dim = GEOM[model]
    return 2 * layers * heads * dim * KV_BYTES[dtype] * tokens / 2**30


def _f_vec(local: np.ndarray, cloud: np.ndarray, target: float) -> np.ndarray:
    p = local.mean(axis=-1)
    q = cloud.mean(axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        f = np.where(p >= target, 0.0, (target - p) / (q - p))
    return np.where((p < target) & (q <= target), np.inf, f)


def sim_delta(
    p_a: float,
    p_x: float,
    target: float,
    *,
    n: int,
    rng: np.random.Generator,
    q: float = Q_CLOUD,
    nested: bool = True,
    disc: float = DISC,
) -> dict[str, Any]:
    pts: list[float] = []
    lo_pos = 0
    for _ in range(NSIM):
        u = rng.random(n)
        if nested:
            la, lx = u < p_a, u < p_x
        else:
            la = u < p_a
            keep = rng.random(n) >= disc
            lx = np.where(keep, la, rng.random(n) < p_x)
        cl = rng.random(n) < q
        d0 = 1000 * (_f_vec(la, cl, target) - _f_vec(lx, cl, target))
        pts.append(float(d0))
        idx = rng.integers(0, n, size=(BOOT, n))
        with np.errstate(invalid="ignore"):
            db = 1000 * (_f_vec(la[idx], cl[idx], target) - _f_vec(lx[idx], cl[idx], target))
        # unreachable target: A only -> +inf (> 0); both -> nan, counted as not > 0
        db = np.nan_to_num(db, nan=-1e9, posinf=1e9, neginf=-1e9)
        if np.quantile(db, 0.025) > 0:
            lo_pos += 1
    arr = np.array(pts)
    fin = arr[np.isfinite(arr)]
    return {
        "analytic_point": round(1000 * (f_need(p_a, q, target) - f_need(p_x, q, target)), 1),
        "sim_p025": round(float(np.quantile(fin, 0.025)), 1) if fin.size else None,
        "sim_p975": round(float(np.quantile(fin, 0.975)), 1) if fin.size else None,
        "power_ci_excludes_0": round(lo_pos / NSIM, 3),
        "n": n,
    }


def mcnemar_power(p_a: float, p_x: float, n: int, rng: np.random.Generator) -> float:
    from scipy.stats import binomtest  # type: ignore[import-untyped]

    hits = 0
    for _ in range(NSIM):
        u = rng.random(n)
        b = int(((u < p_x) & ~(u < p_a)).sum())
        c = int(((u < p_a) & ~(u < p_x)).sum())
        if b + c and binomtest(min(b, c), b + c, 0.5).pvalue < 0.05 and b > c:
            hits += 1
    return round(hits / NSIM, 3)


def noninf_power(n: int, disc: float, rng: np.random.Generator, margin: float = -0.05) -> float:
    """Paired binary, true difference 0, Wald lower one-sided 95% bound > margin."""
    hits = 0
    for _ in range(4 * NSIM):
        k = rng.multinomial(n, [disc / 2, disc / 2, 1 - disc])
        b, c = int(k[0]), int(k[1])
        d = (b - c) / n
        se = math.sqrt(max((b + c) - (b - c) ** 2 / n, 0.0)) / n
        if d - 1.645 * se > margin:
            hits += 1
    return round(hits / (4 * NSIM), 3)


def e2_cost(t_min: float, p_complete: float = 1.0) -> dict[str, float]:
    amort_full = BOX_USD / (LIFE_Y * 8760)
    amort_active = BOX_USD / (LIFE_Y * 12 * ACTIVE_H_MONTH)
    energy = WATTS / 1000 * USD_KWH
    h = t_min / 60 / p_complete
    return {
        "usd_per_session_active_hour_basis": round((amort_active + energy) * h, 3),
        "usd_per_session_full_utilization": round((amort_full + energy) * h, 3),
        "sessions_per_machine_day": round(1440 / t_min, 2),
    }


def e1_block(rng: np.random.Generator) -> dict[str, Any]:
    out: dict[str, Any] = {"primary_order": "XPS, then AMD (fixed sequence; REG E1.6)"}
    p_a = PILOT_PASS[4096]
    for x_win in (16384, 40960):
        p_x = PILOT_PASS[x_win]
        key = f"X_window_{x_win}"
        out[key] = {
            "p_A_4096": p_a,
            "p_X": p_x,
            "mcnemar_X_vs_A_power_n200": mcnemar_power(p_a, p_x, N_CONFIRM, rng),
            "delta_escalations_per_1000": {
                f"Q_t={t}": sim_delta(p_a, p_x, t, n=N_CONFIRM, rng=rng) for t in TARGETS
            },
        }
    out["relative_saving_at_Qt_0.95q"] = {
        f"q={q}": round(1 - f_need(PILOT_PASS[40960], q, 0.95 * q) / f_need(p_a, q, 0.95 * q), 3)
        for q in Q_SWEEP
    }
    out["X_vs_R_AMD_128GB"] = {
        "statement": "about zero: X (largest fitting window, q8_0 KV + FA) and R (40,960, f16) "
        "both run 40,960 on 128 GB; pilot 16,384 vs 40,960 12.7% vs 11.3% wrong (p ~ 0.72)",
        "delta_escalations_per_1000": {
            f"Q_t={t}": sim_delta(
                PILOT_PASS[40960], PILOT_PASS[40960], t, n=N_CONFIRM, rng=rng, nested=False
            )
            for t in TARGETS
        },
    }
    fits: dict[str, Any] = {}
    for m in GEOM:
        fits[m] = {
            f"{dt}@{w}": round(kv_gib(m, w, dt), 2)
            for dt in ("f16", "q8_0")
            for w in (4096, 16384, 40960)
        }
    out["kv_cache_gib"] = fits
    out["secondaries"] = {
        "wrong_answer_rate": {
            "A_4096": round(1 - p_a, 3),
            "X": [round(1 - PILOT_PASS[40960], 3), round(1 - PILOT_PASS[16384], 3)],
            "source": "PILOT (n = 150, qwen3:14b, AMD)",
        },
        "silent_failure_rate": {
            "A_4096": "every failure silent (PILOT: Ollama truncates without an error)",
            "X": "overflow failures loud BY CONSTRUCTION (client token count refuses and "
            "escalates); X's in-window wrong answers stay silent and are counted",
        },
    }
    out["XPS_R_fit"] = {
        "statement": "R (qwen3:8b, f16 KV, 40,960) needs about 5 GB weights + 5.6 GiB KV against "
        "the XPS's default GPU share (about 8 GB, report figure, to be measured by the fit sweep): "
        "predicted NOT to fit; if so R is recorded 'does not fit' and X vs R is not tested on "
        "the XPS",
        "kv_f16_40960_gib": round(kv_gib("qwen3:8b", 40960, "f16"), 2),
        "kv_q8_0_40960_gib": round(kv_gib("qwen3:8b", 40960, "q8_0"), 2),
    }
    out["dollars"] = {
        "formula": "dUSD per 1,000 = dEscalations x c_esc; c_esc = replayed per-entry cost of the "
        "escalated tasks from the shared cloud-only log (cache-aware, PF 1 formula with read "
        "multiplier 0.05 on 5.5-tier models)",
        "prior_c_esc_usd": [0.01, 0.03],
        "prior_dUSD_per_1000_at_Qt_0.85": [
            round(0.01 * 1000 * (f_need(p_a, Q_CLOUD, 0.85) - 0), 1),
            round(0.03 * 1000 * (f_need(p_a, Q_CLOUD, 0.85) - 0), 1),
        ],
        "cache_hit_sweep_input_multiplier": {
            str(h): round((1 - h) + 0.05 * h, 4) for h in (0.55, 0.70, 0.90, 0.95)
        },
        "price_sheet_per_mtok_list": PRICE,
        "price_sheet_minus_50pct": {k: v / 2 for k, v in PRICE.items()},
    }
    out["odds_judgement"] = {
        "source": "research report 'Win cost where device defaults break' (registered judgement, "
        "not a measurement)",
        "X_beats_A_on_local_pass": "85-90%",
        "cost_endpoint_excludes_0_at_Qt_0.85": "about 85%",
        "meaningful_win_over_R_on_AMD": "under 10%",
    }
    return out


def e2_block(rng: np.random.Generator) -> dict[str, Any]:
    r, x1 = e2_cost(T_R_MIN), e2_cost(T_X1_MIN)
    return {
        "cost_formula": "usd_per_session = (BOX_USD / (LIFE_Y x 12 x ACTIVE_H_MONTH) + WATTS/1000 "
        "x USD_KWH) x t_session_h / p_complete (active-hour basis); full-utilization basis uses "
        "LIFE_Y x 8760 h",
        "cost_inputs_defaults": {
            "box_usd": BOX_USD,
            "life_years": LIFE_Y,
            "wall_watts": WATTS,
            "usd_per_kwh": USD_KWH,
            "active_h_per_month": ACTIVE_H_MONTH,
            "replace_with": "measured wall power and duty cycle, actual purchase price",
        },
        "AMD_R_pilot": r,
        "AMD_X1_pilot": x1,
        "AMD_X1_over_R_session_ratio": {
            "point": round(T_R_MIN / T_X1_MIN, 2),
            "band": [2.0, 3.7],
            "band_derivation": "upper = point x 1.3 = 3.70; lower = 2.0, the report's replication "
            "criterion (wider than point / 1.3 = 2.19)",
        },
        "attribution_X0": {
            "statistic": "s = ln(t_R / t_X0) / ln(t_R / t_X1) (share of the X1 gain that FA alone gives)",
            "prediction": "s >= 0.5 (FA / memory fit carries most of it)",
            "odds_judgement": "65-75% (report: 25-35% that KV precision carries it)",
        },
        "cross_device": {
            "XPS_u4_over_i8_sessions_per_day_at_4_concurrent": {
                "point": round(XPS_LIMITS["u4"] / XPS_LIMITS["u8"], 3),
                "band": [1.0, 1.5],
                "derivation": "capacity bound by the resident limit: u4 26,500 / u8 20,000 "
                "(e4a22dac / cf3555d5; u8 is the measured 8-bit proxy for the i8 default); band: 1.0 if memory does not bind at the chosen "
                "contexts, 1.5 = one extra 8,192-token session in 20,000 vs 26,500",
            },
            "T2S_u4_over_i8_sessions_per_day": {
                "point": T2S_U4_OVER_I8_12K,
                "band": [0.9, 1.2],
                "derivation": "64 GB never binds; decode-rate gain only, 1.082 at 12,000 "
                "(0a55c316 / 29209e26)",
            },
            "pattern": "large on 16 GB (XPS) and 128 GB (AMD, f16 at 40,960 x sessions), near-null "
            "(<= 1.2x) on the 64 GB T2S",
        },
        "accuracy_noninferiority": {
            "margin_points": -5,
            "test": "paired, one-sided 95% lower bound of (X - R) pass rate > -0.05",
            "power_n200_disc_0.08": noninf_power(200, DISC, rng),
            "power_n300_disc_0.08": noninf_power(300, DISC, rng),
            "power_n200_disc_0.05": noninf_power(200, DISC_SENS, rng),
            "prediction": "X1 within about 1 point of R (literature: W8A8KV8 within ~1 point, "
            "arXiv 2504.04823); X2 (q4_0 KV) gets its own test",
        },
    }


def build() -> dict[str, Any]:
    rng = np.random.default_rng(SEED)
    return {
        "id": "CTXKV_E1E2_PREDICTIONS",
        "status": "registered with docs/registrations/CTXKV_E1E2_2026-10-23.md before any E1/E2 "
        "run; DERIVED from PILOT / ASSUMED / LITERATURE inputs (labelled)",
        "generator": "tools/ctxkv_e1e2_predict.py",
        "runner_must_not_read_this_file": True,
        "inputs": {
            "pilot_pass_by_window_qwen3_14b_AMD": {str(k): v for k, v in PILOT_PASS.items()},
            "pilot_pass_4096_protected": PILOT_PASS_4096_PROTECTED,
            "pilot_session_min": {"R_f16": T_R_MIN, "X1_q8_0": T_X1_MIN},
            "q_cloud_assumed": Q_CLOUD,
            "discordance_assumed": DISC,
            "n_confirm": N_CONFIRM,
            "nsim": NSIM,
            "boot": BOOT,
            "seed": SEED,
        },
        "E1": e1_block(rng),
        "E2": e2_block(rng),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    doc = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, allow_nan=False) + "\n", encoding="ascii")
    print(json.dumps({"E1": doc["E1"], "E2": doc["E2"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
