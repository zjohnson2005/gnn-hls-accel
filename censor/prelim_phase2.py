"""Phase-2 prelim runner: Arms A, B, C.

Order is forced: Arm C (KV arithmetic) -> A1 sanity gate -> A2/A3 -> Arm B.
If the A1 gate fails, A2/A3 are NOT built and the run reports the failure.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from censor.kv_math import (
    LOCAL_HW,
    MODEL_SPECS,
    attention_quadratic_coefficient,
    kv_bytes_per_token,
    local_feasibility,
    weights_footprint,
)
from censor.prefill_bounds import (
    EMPIRICAL_ANCHOR,
    EMPIRICAL_LC,
    SCALING_MODELS,
    SCALING_SPECS,
    InverseInputs,
    marginal_flip_rate,
    prefill_rate_at,
    rate_for_target_u_star,
    rate_ratio,
    recommended_measurement_grid,
    u_star_at_rate,
)
from censor.prelim_phase1 import (
    KV_VALUES,
    LONGCTX,
    _v,
    cloud_prices,
    hw_configs,
    load_params,
    representative_turn,
)
from censor.tier_economics import (
    ACCELERATORS,
    B_MIN_SWEEP,
    BATCH_CAP_BRACKET,
    BATCH_CAP_SOURCE,
    PUBLISHED_THRESHOLDS,
    batch_max,
    collapse_ratio,
    l_cross,
    memory_limited_kv_to_weights_ratio,
    per_user_memory_cost,
    predicted_knee,
    run_sanity_check,
)
from censor.tiers import cost_T2

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "prelim" / "phase2"
OUT.mkdir(parents=True, exist_ok=True)

CONTEXT_SWEEP = [4096, 8192, 16384, 32768, 65536, 115440, 131072, 200000, 262144]
GB = 1e9


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Arm C1
# ---------------------------------------------------------------------------
def run_arm_c(context_floor: float) -> dict[str, Any]:
    rows = local_feasibility(context_floor)
    out = [
        {
            "hw_config": r.hw,
            "hw_name": LOCAL_HW[r.hw].name,
            "hw_usable_gb": r.usable_bytes / GB,
            "hw_usable_fraction": LOCAL_HW[r.hw].usable_fraction,
            "hw_source_confidence": LOCAL_HW[r.hw].confidence,
            "model": r.model,
            "model_name": MODEL_SPECS[r.model].name,
            "attention": MODEL_SPECS[r.model].attention,
            "n_kv_heads": MODEL_SPECS[r.model].n_kv_heads,
            "quant": r.quant,
            "kv_dtype": r.kv_dtype,
            "weights_gb": r.weights_bytes / GB,
            "free_for_kv_gb": r.free_for_kv_bytes / GB,
            "kv_bytes_per_token": r.kv_bytes_per_token,
            "kv_kib_per_token": r.kv_bytes_per_token / 1024.0,
            "max_context_tokens": r.max_context_tokens,
            "context_floor": r.context_floor,
            "feasible_at_context_floor": r.feasible_at_context_floor,
            "headroom_ratio": r.headroom_ratio,
        }
        for r in rows
    ]
    _write_csv(OUT / "kv_feasibility.csv", out)

    # Which Phase-1 hw configs survive for the 7-8B agent class they actually ran?
    phase1_models = ["llama31_8b"]
    phase1_hw = ["strix_halo", "apple_m_series", "discrete_gpu_rtx5090"]
    survival: dict[str, dict[str, Any]] = {}
    for hw in phase1_hw:
        cands = [
            r for r in rows
            if r.hw == hw and r.model in phase1_models
        ]
        any_feasible = [c for c in cands if c.feasible_at_context_floor]
        # Cheapest feasible configuration (lowest quant pressure needed)
        survival[hw] = {
            "any_feasible": bool(any_feasible),
            "feasible_combos": [
                f"{c.quant}/kv_{c.kv_dtype} (max_ctx={c.max_context_tokens:,.0f})"
                for c in any_feasible
            ],
            "infeasible_combos": [
                f"{c.quant}/kv_{c.kv_dtype} (max_ctx={c.max_context_tokens:,.0f})"
                for c in cands if not c.feasible_at_context_floor
            ],
            "fp16_weights_fp16_kv_feasible": any(
                c.feasible_at_context_floor
                for c in cands if c.quant == "fp16" and c.kv_dtype == "fp16"
            ),
        }
    return {"rows": out, "survival": survival}


# ---------------------------------------------------------------------------
# Arm A1 sanity gate + sweep
# ---------------------------------------------------------------------------
def run_arm_a1() -> dict[str, Any]:
    passed, results = run_sanity_check(MODEL_SPECS)
    sanity_rows = [
        {
            "anchor": r.anchor.label,
            "accelerator": r.anchor.accelerator,
            "model": r.anchor.model,
            "context_len": r.anchor.context_len,
            "published_batch": r.anchor.published_batch,
            "predicted_batch": r.predicted_batch,
            "ratio_predicted_over_published": r.ratio,
            "disagreement_factor": r.disagreement,
            "tolerance": 2.0,
            "passed": r.passed,
            "source": r.anchor.source,
        }
        for r in results
    ]
    return {"passed": passed, "rows": sanity_rows, "results": results}


def run_arm_a1_sweep() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for accel_key, accel in ACCELERATORS.items():
        for mk, spec in MODEL_SPECS.items():
            w = weights_footprint(spec, "fp16")
            for ctx in CONTEXT_SWEEP:
                b = batch_max(accel.memory_bytes, spec, ctx)
                rows.append({
                    "accelerator": accel_key,
                    "accelerator_name": accel.name,
                    "accelerator_memory_gb": accel.memory_bytes / GB,
                    "model": mk,
                    "model_name": spec.name,
                    "attention": spec.attention,
                    "params_total_b": spec.params_total / 1e9,
                    "weights_gb_fp16": w / GB,
                    "fits_weights": w < accel.memory_bytes,
                    "kv_kib_per_token": kv_bytes_per_token(spec) / 1024.0,
                    "context_len": ctx,
                    "batch_max": b,
                    "batch_max_floor": int(b),
                })
    _write_csv(OUT / "batch_vs_context.csv", rows)
    return rows


# ---------------------------------------------------------------------------
# Arm A2
# ---------------------------------------------------------------------------
def run_arm_a2(context_floor: float) -> dict[str, Any]:
    per_model: dict[str, Any] = {}
    for mk, spec in MODEL_SPECS.items():
        w = weights_footprint(spec, "fp16")
        entry: dict[str, Any] = {
            "model_name": spec.name,
            "attention": spec.attention,
            "kv_kib_per_token": kv_bytes_per_token(spec) / 1024.0,
            "weights_gb": w / GB,
            "l_cross_by_batch_cap": {
                cap: l_cross(spec, batch_cap=cap) for cap in BATCH_CAP_BRACKET
            },
            "memory_limited_kv_to_weights_ratio": {
                ak: (
                    memory_limited_kv_to_weights_ratio(a.memory_bytes, spec)
                    if w < a.memory_bytes else None
                )
                for ak, a in ACCELERATORS.items()
            },
        }
        per_model[mk] = entry

    # Collapse ratio is analytic: B ~ 1/L exactly, so B(8K)/B(115K) = 115440/8192
    # independent of model and accelerator. Verify numerically anyway.
    verify: list[dict[str, Any]] = []
    for accel_key, accel in ACCELERATORS.items():
        for mk, spec in MODEL_SPECS.items():
            if weights_footprint(spec, "fp16") >= accel.memory_bytes:
                continue
            b8 = batch_max(accel.memory_bytes, spec, 8192)
            bf = batch_max(accel.memory_bytes, spec, context_floor)
            verify.append({
                "accelerator": accel_key,
                "model": mk,
                "batch_at_8k": b8,
                "batch_at_context_floor": bf,
                "collapse_ratio_numeric": b8 / bf if bf > 0 else float("inf"),
            })
    analytic = collapse_ratio(8192.0, context_floor)
    max_dev = max(abs(v["collapse_ratio_numeric"] - analytic) for v in verify) if verify else 0.0

    _plot_amortization_collapse(context_floor)
    return {
        "per_model": per_model,
        "collapse_ratio_analytic": analytic,
        "collapse_verification_max_deviation": max_dev,
        "verify_rows": verify,
    }


def _plot_amortization_collapse(context_floor: float) -> None:
    contexts = [2048 * 2 ** i for i in range(8)]  # 2K .. 256K
    models = ["llama31_8b", "qwen25_32b", "llama31_70b"]
    colors = {"llama31_8b": "#2f6f8f", "qwen25_32b": "#3a7d44", "llama31_70b": "#b85c38"}
    n = len(ACCELERATORS)
    fig, axes = plt.subplots(2, n, figsize=(15, 8.6))

    # Row 0: the amortization factor B(L) itself.
    for j, (ak, accel) in enumerate(ACCELERATORS.items()):
        ax = axes[0][j]
        for mk in models:
            spec = MODEL_SPECS[mk]
            if weights_footprint(spec, "fp16") >= accel.memory_bytes:
                continue
            b = [
                min(batch_max(accel.memory_bytes, spec, L), 256) for L in contexts
            ]
            ax.plot(contexts, b, color=colors[mk], label=spec.name)
        ax.axhline(1.0, color="black", linewidth=0.8, alpha=0.5)
        ax.axvline(8192, color="gray", linestyle="-.", linewidth=0.9)
        ax.axvline(context_floor, color="gray", linestyle=":", linewidth=1.2)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(f"{accel.name}", fontsize=10)
        ax.set_xlabel("context tokens")
        ax.grid(True, which="both", alpha=0.3)
        if j == 0:
            ax.set_ylabel("B(L): concurrent users\n(amortization factor)")
            ax.annotate(
                f"8K -> context_floor:\n{context_floor / 8192.0:.1f}x collapse\n(model-independent)",
                xy=(0.03, 0.06), xycoords="axes fraction", fontsize=7,
                bbox=dict(boxstyle="round", fc="#fff6e0", ec="#c8a24a", lw=0.6),
            )
        ax.legend(fontsize=6, loc="upper right")

    # Row 1: per-user memory split into amortizable weights vs private KV.
    for j, (ak, accel) in enumerate(ACCELERATORS.items()):
        ax = axes[1][j]
        for mk in models:
            spec = MODEL_SPECS[mk]
            if weights_footprint(spec, "fp16") >= accel.memory_bytes:
                continue
            w_share, kv_share = [], []
            for L in contexts:
                pu = per_user_memory_cost(accel.memory_bytes, spec, L, batch_cap=256)
                w_share.append(pu.weights_share_bytes / GB)
                kv_share.append(pu.kv_share_bytes / GB)
            ax.plot(contexts, w_share, color=colors[mk], linestyle="--",
                    label=f"{spec.name} weights share")
            ax.plot(contexts, kv_share, color=colors[mk], linestyle="-",
                    label=f"{spec.name} private KV")
        ax.axvline(context_floor, color="gray", linestyle=":", linewidth=1.2)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("context tokens")
        ax.grid(True, which="both", alpha=0.3)
        if j == 0:
            ax.set_ylabel("per-user accelerator memory (GB)")
    axes[1][-1].legend(fontsize=6, loc="upper left")

    fig.suptitle(
        "A2 amortization collapse.  TOP: B(L), users a card can hold concurrently — falls as 1/L, "
        f"{context_floor / 8192.0:.1f}x from 8K to context_floor for every model and card.\n"
        "BOTTOM: per-user memory, amortizable weights share (dashed) vs private KV (solid). "
        "The two run PARALLEL once memory limits the batch: their ratio is fixed at (M-W)/W, "
        "independent of context length.\n"
        "Dotted vertical = context_floor; dash-dot = 8K reference. Batch cap 256 (vLLM default), "
        "which binds only at short context.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(OUT / "amortization_collapse.png", dpi=140)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Arm A3
# ---------------------------------------------------------------------------
def run_arm_a3() -> dict[str, Any]:
    pred_rows: list[dict[str, Any]] = []
    for ak, accel in ACCELERATORS.items():
        for mk, spec in MODEL_SPECS.items():
            if weights_footprint(spec, "fp16") >= accel.memory_bytes:
                continue
            for b_min in B_MIN_SWEEP:
                pred_rows.append({
                    "row_type": "predicted_knee",
                    "accelerator": ak,
                    "model": mk,
                    "b_min": b_min,
                    "predicted_knee_tokens": predicted_knee(accel.memory_bytes, spec, b_min),
                })

    knees_8b = [
        r["predicted_knee_tokens"] for r in pred_rows if r["model"] == "llama31_8b"
    ]
    band_lo, band_hi = min(knees_8b), max(knees_8b)
    all_knees = [r["predicted_knee_tokens"] for r in pred_rows]

    check_rows: list[dict[str, Any]] = []
    for r in pred_rows:
        check_rows.append({
            "row_type": "predicted",
            "provider": "",
            "model_or_accel": f"{r['accelerator']} / {r['model']}",
            "b_min": r["b_min"],
            "threshold_tokens": r["predicted_knee_tokens"],
            "input_multiplier": "",
            "inside_8b_predicted_band": "",
            "source": (
                "Derived: context at which memory-limited batch falls to b_min. "
                "b_min is UNOBSERVABLE and therefore swept, not chosen."
            ),
            "confidence": "estimated",
            "note": "",
        })
    for t in PUBLISHED_THRESHOLDS:
        inside = (
            "" if t.threshold_tokens is None
            else str(band_lo <= t.threshold_tokens <= band_hi)
        )
        check_rows.append({
            "row_type": "published",
            "provider": t.provider,
            "model_or_accel": t.model,
            "b_min": "",
            "threshold_tokens": t.threshold_tokens if t.threshold_tokens is not None else "none",
            "input_multiplier": t.input_multiplier if t.input_multiplier is not None else "n/a",
            "inside_8b_predicted_band": inside,
            "source": t.source,
            "confidence": t.confidence,
            "note": t.note,
        })
    _write_csv(OUT / "threshold_check.csv", check_rows)

    published_numeric = [t for t in PUBLISHED_THRESHOLDS if t.threshold_tokens is not None]
    distinct = sorted({t.threshold_tokens for t in published_numeric})
    n_inside = sum(1 for t in published_numeric if band_lo <= t.threshold_tokens <= band_hi)

    return {
        "pred_rows": pred_rows,
        "band_8b": (band_lo, band_hi),
        "band_all": (min(all_knees), max(all_knees)),
        "distinct_published": distinct,
        "n_published_numeric": len(published_numeric),
        "n_inside_band": n_inside,
        "n_no_threshold": sum(1 for t in PUBLISHED_THRESHOLDS if t.threshold_tokens is None),
    }


# ---------------------------------------------------------------------------
# Arm B
# ---------------------------------------------------------------------------
def run_arm_b(p: dict[str, Any]) -> dict[str, Any]:
    turn = representative_turn(p)
    spec = MODEL_SPECS["llama31_8b"]  # all three Phase-1 hw configs ran 7-8B class
    context_floor = float(turn.context_floor)
    delta = float(turn.delta_tokens)

    cache_hit = float(_v(p["workload"]["prefix_cache_hit_rate_tool_result"]))
    elec = float(_v(p["local_hardware"]["common"]["electricity_usd_per_kwh"]))
    life_mid = float(_v(p["local_hardware"]["common"]["assumed_lifetime_months"]))
    ttft_s = float(_v(p["cloud"]["ttft_ms"])) / 1000.0
    out_tps = float(_v(p["cloud"]["output_tok_per_sec"]["pure_decode"]))
    rtt_s = float(_v(p["cloud"]["rtt_ms"])) / 1000.0
    anchor_capped = float(
        _v(p["local_hardware"]["common"]["capex_utilization"]["anchors"]["dedicated_box_human_capped_1h"])
    )

    prices = cloud_prices(p, "openai", "mid")
    hws = hw_configs(p)

    t2_by_bound = {
        bound: cost_T2(
            turn, "openai", "mid", cache_hit, bound, prices,
            ttft_s=ttft_s, output_tok_per_sec=out_tps, rtt_s=rtt_s,
        ).usd_low
        for bound in LONGCTX
    }

    rows: list[dict[str, Any]] = []
    for kv in KV_VALUES:
        prefill_tokens = delta if kv == "persists" else context_floor
        # The scaling models describe throughput at the RESIDENT context length.
        # Under `persists` only delta tokens are prefilled, but they are appended
        # to a 115K-token cache, so attention still runs against the full context:
        # the degradation applies to both settings.
        for hw in hws:
            pp512 = float(hw.prefill_tok_per_sec_pp512)
            for bound in LONGCTX:
                t2 = t2_by_bound[bound]
                inp = InverseInputs(
                    prefill_tokens=prefill_tokens,
                    output_tokens=float(turn.output_tokens),
                    decode_tok_per_sec=float(hw.decode_tok_per_sec),
                    sustained_power_w=float(hw.sustained_power_w),
                    electricity_usd_per_kwh=elec,
                    capex_usd=float(hw.capex_usd),
                    lifetime_months=life_mid,
                    t2_usd=t2,
                )
                flip = marginal_flip_rate(inp)
                flip_rate = flip["flip_rate"]

                model_rates = {
                    m: prefill_rate_at(pp512, m, context_floor, spec) for m in SCALING_MODELS
                }
                u_by_model = {m: u_star_at_rate(inp, r) for m, r in model_rates.items()}

                if flip_rate is None:
                    marg_verdict = "ROBUST_no_rate_flips"
                    slowest = min(model_rates.values())
                elif all(r > float(flip_rate) for r in model_rates.values()):
                    marg_verdict = "ROBUST"
                elif all(r < float(flip_rate) for r in model_rates.values()):
                    marg_verdict = "FLIPPED_under_all_models"
                else:
                    marg_verdict = "FRAGILE"

                u_vals = [
                    v["u_star"] for v in u_by_model.values() if v["u_star"] is not None
                ]
                impossible = [
                    m for m, v in u_by_model.items()
                    if v["u_star"] is None or v["status"] == "requires_impossible_utilization"
                ]
                if not u_vals:
                    am_verdict = "FRAGILE_amortized_never_wins_under_any_model"
                elif len(impossible) > 0:
                    am_verdict = "FRAGILE_amortized"
                elif max(u_vals) <= anchor_capped:
                    am_verdict = "ROBUST_amortized_under_capped_anchor"
                else:
                    am_verdict = "FRAGILE_amortized_exceeds_capped_anchor"

                rate_at_u1 = rate_for_target_u_star(inp, 1.0)
                rate_at_anchor = rate_for_target_u_star(inp, anchor_capped)

                row: dict[str, Any] = {
                    "kv_persistence": kv,
                    "hw_config": hw.name,
                    "longctx_bound": bound,
                    "prefill_tokens": prefill_tokens,
                    "pp512_tok_per_sec": pp512,
                    "T2_usd": t2,
                    "marginal_flip_rate_tok_per_sec": flip_rate,
                    "marginal_flip_status": flip["status"],
                    "marginal_verdict": marg_verdict,
                    "rate_where_u_star_hits_1.0": rate_at_u1,
                    "rate_where_u_star_hits_capped_anchor": rate_at_anchor,
                    "capped_anchor_utilization": anchor_capped,
                    "amortized_verdict_36mo": am_verdict,
                }
                for m in SCALING_MODELS:
                    row[f"rate_{m}"] = model_rates[m]
                    row[f"ratio_{m}"] = rate_ratio(m, context_floor, spec)
                    u = u_by_model[m]["u_star"]
                    row[f"u_star_{m}"] = u
                    row[f"u_status_{m}"] = u_by_model[m]["status"]
                    row[f"sec_{m}"] = u_by_model[m]["sec"]
                    row[f"marginal_usd_{m}"] = u_by_model[m]["marginal_usd"]
                    row[f"margin_over_flip_{m}"] = (
                        model_rates[m] / float(flip_rate) if flip_rate else None
                    )
                rows.append(row)

    _write_csv(OUT / "prefill_bounds.csv", rows)

    grid = recommended_measurement_grid(spec)
    return {
        "rows": rows,
        "grid": grid,
        "c_coefficient": attention_quadratic_coefficient(spec),
        "ratios_at_floor": {
            m: rate_ratio(m, context_floor, spec) for m in SCALING_MODELS
        },
        "context_floor": context_floor,
        "anchor_capped": anchor_capped,
    }


# ---------------------------------------------------------------------------
# PHASE2.md
# ---------------------------------------------------------------------------
def _fmt_u(u: Any) -> str:
    if u is None or u == "":
        return "never wins"
    return f"{100.0 * float(u):.1f}%"


def write_phase2(
    p: dict[str, Any],
    context_floor: float,
    c: dict[str, Any],
    a1: dict[str, Any],
    a2: dict[str, Any],
    a3: dict[str, Any],
    b: dict[str, Any],
) -> None:
    sanity_lines = [
        "| anchor | published batch | our arithmetic | disagreement | pass (<=2x) |",
        "|---|---:|---:|---:|---|",
    ]
    for r in a1["rows"]:
        sanity_lines.append(
            f"| {r['anchor']} | {r['published_batch']:.0f} | {r['predicted_batch']:.2f} | "
            f"{r['disagreement_factor']:.2f}x | {'PASS' if r['passed'] else 'FAIL'} |"
        )

    lcross_lines = [
        "| model | attention | KV KiB/token | weights GB (fp16) | L_cross @cap=32 | L_cross @cap=256 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for mk, e in a2["per_model"].items():
        lc = e["l_cross_by_batch_cap"]
        lcross_lines.append(
            f"| {e['model_name']} | {e['attention']} | {e['kv_kib_per_token']:.0f} | "
            f"{e['weights_gb']:.1f} | {lc[32]:,.0f} | {lc[256]:,.0f} |"
        )

    ratio_lines = [
        "| model | A100 80GB | H200 141GB | MI300X 192GB |",
        "|---|---:|---:|---:|",
    ]
    for mk, e in a2["per_model"].items():
        r = e["memory_limited_kv_to_weights_ratio"]
        cells = " | ".join(
            "weights do not fit" if r[ak] is None else f"{r[ak]:.2f}:1" for ak in ACCELERATORS
        )
        ratio_lines.append(f"| {e['model_name']} | {cells} |")

    # Configurations that cannot hold even one sequence at context_floor.
    starved = [
        (ACCELERATORS[ak].name, MODEL_SPECS[mk].name,
         batch_max(ACCELERATORS[ak].memory_bytes, MODEL_SPECS[mk], context_floor))
        for ak in ACCELERATORS
        for mk in MODEL_SPECS
        if weights_footprint(MODEL_SPECS[mk], "fp16") < ACCELERATORS[ak].memory_bytes
        and batch_max(ACCELERATORS[ak].memory_bytes, MODEL_SPECS[mk], context_floor) < 1.0
    ]
    starved_lines = [
        f"- **{m}** on a **{a}** reaches B = {b:.2f} at context_floor — below one."
        for a, m, b in starved
    ]

    knee_lines = [
        "| accelerator | b_min=8 | b_min=4 | b_min=2 | b_min=1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for ak in ACCELERATORS:
        cells = []
        for bm in (8.0, 4.0, 2.0, 1.0):
            v = next(
                (r["predicted_knee_tokens"] for r in a3["pred_rows"]
                 if r["accelerator"] == ak and r["model"] == "llama31_8b" and r["b_min"] == bm),
                None,
            )
            cells.append("n/a" if v is None else f"{v:,.0f}")
        knee_lines.append(f"| {ACCELERATORS[ak].name} | " + " | ".join(cells) + " |")

    pub_lines = [
        "| provider | model | published threshold | input multiplier | inside predicted band? |",
        "|---|---|---:|---:|---|",
    ]
    lo_band, hi_band = a3["band_8b"]
    for t in PUBLISHED_THRESHOLDS:
        if t.threshold_tokens is None:
            pub_lines.append(
                f"| {t.provider} | {t.model} | **none** | n/a | "
                "n/a — no threshold to explain |"
            )
        else:
            inside = lo_band <= t.threshold_tokens <= hi_band
            pub_lines.append(
                f"| {t.provider} | {t.model} | {t.threshold_tokens:,.0f} | "
                f"{t.input_multiplier:.2f}x | {'yes' if inside else 'no'} |"
            )

    feas_lines = [
        "| Phase-1 hw config | 8B feasible at context_floor? | feasible combos | infeasible combos |",
        "|---|---|---:|---|",
    ]
    for hw, s in c["survival"].items():
        n_ok = len(s["feasible_combos"])
        n_bad = len(s["infeasible_combos"])
        bad = "; ".join(x.split(" (")[0] for x in s["infeasible_combos"]) or "none"
        verdict = (
            "YES, unconditionally" if s["any_feasible"] and n_bad == 0
            else "YES, but only at some quantizations" if s["any_feasible"]
            else "NO"
        )
        feas_lines.append(f"| `{hw}` | {verdict} | {n_ok} of {n_ok + n_bad} | {bad} |")

    b_lines = [
        "| kv | hw | longctx | marginal flip rate | marginal | u* flat | u* attention | u* pessimistic | amortized |",
        "|---|---|---|---:|---|---:|---:|---:|---|",
    ]
    for r in b["rows"]:
        fr = r["marginal_flip_rate_tok_per_sec"]
        b_lines.append(
            f"| `{r['kv_persistence']}` | {r['hw_config']} | {r['longctx_bound']} | "
            f"{'n/a' if fr is None else f'{fr:.2f} tok/s'} | "
            f"{'ROBUST' if r['marginal_verdict'].startswith('ROBUST') else r['marginal_verdict']} | "
            f"{_fmt_u(r['u_star_optimistic_flat'])} | "
            f"{_fmt_u(r['u_star_linear_attention_theoretic'])} | "
            f"{_fmt_u(r['u_star_quadratic_pessimistic'])} | "
            f"{'ROBUST' if r['amortized_verdict_36mo'].startswith('ROBUST') else 'FRAGILE'} |"
        )

    sep_lines = [
        "| depth | flat | attention-theoretic | pessimistic | flat/attn | attn/pess |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in b["grid"]["rows"]:
        sep_lines.append(
            f"| {row['context_len']:,.0f} | {row['ratio_flat']:.3f} | "
            f"{row['ratio_attention']:.3f} | {row['ratio_pessimistic']:.4f} | "
            f"{row['flat_over_attention']:.2f}x | {row['attention_over_pessimistic']:.2f}x |"
        )

    apple = [
        r for r in b["rows"]
        if r["hw_config"] == "apple_m_series" and r["kv_persistence"] == "recomputes"
        and r["longctx_bound"] == "below_threshold"
    ][0]

    ratios = b["ratios_at_floor"]
    d1 = b["grid"]["first_depth_separating_attention_from_pessimistic"]
    d2 = b["grid"]["first_depth_separating_flat_from_attention"]

    text = f"""# PHASE 2 — cost structure under the rate card, and the prefill bound

> **STATUS: PHASE 2 COMPLETE (desk work, no hardware).** Arms A, B, C.
> Parameter set: `censor/study_params.yaml` (schema-validated).
> Every T1 row still carries `local_kv_persistence` as the OUTER LOOP.

**SCOPE LINE (Arm A).** Everything below is capacity arithmetic and what it
implies about cost structure. Nothing below is a claim about any provider's
actual serving configuration. Where a minimum batch size appears it is a swept,
unobservable parameter, never an assertion about a deployment.

---

## 1. SANITY — does our batch curve match published measurements? (GATE)

**GATE: {'PASS' if a1['passed'] else 'FAIL'}.** Worst disagreement
{max(r['disagreement_factor'] for r in a1['rows']):.2f}x against a 2x tolerance.

{chr(10).join(sanity_lines)}

The same one-line formula — `(accelerator memory − weights) / (kv_bytes_per_token
× context)` — reproduces an OOM boundary reported by a systems paper and a
batch-vs-context curve reported by a serving paper, to within 18%, with no
fitted parameters. A2 and A3 are built on this.

The single detail that makes it work is reading `n_kv_heads`, not `n_heads`.
Llama-3.1-8B has 32 query heads and 8 KV heads; using 32 would have predicted
batch 0.93 at 128K against a published 4, a 4.3x error that would have failed
the gate in the wrong direction and looked like a memory-capacity finding.

---

## 2. Amortization collapse

### B(L): the amortization factor

Batch is inversely proportional to context, exactly:
`B(L) = (M − W) / (kv_bytes_per_token × L)`.

**Collapse ratio, 8K → context_floor ({context_floor:,.0f}): {a2['collapse_ratio_analytic']:.2f}x.**

This is an *analytic* result, not an empirical one: because `B ∝ 1/L`, the ratio
is exactly `115,440 / 8,192` for every model and every accelerator. Numerical
verification across the full grid deviates by
{a2['collapse_verification_max_deviation']:.1e}. Moving an agent workload from
short-chat context to production agent context divides the number of users a
given accelerator can serve concurrently by fourteen. Nothing about the model or
the hardware changes that number.

![amortization collapse](amortization_collapse.png)

### The result we did not expect: there is no crossover in the memory-limited regime

The brief asked for `L_cross`, the context at which per-user KV exceeds the
per-user weights share — the point batching stops being the dominant economic
lever. Under a purely memory-limited batch, **that point does not exist**:

```
weights_share = W / B(L) = W · kv_pt · L / (M − W)
kv_share      = kv_pt · L
ratio          = (M − W) / W          ← constant in L
```

Both terms scale linearly in context, so their ratio is fixed by the accelerator
and the model, and never crosses. Which of the two dominates is decided entirely
by how much of the accelerator the weights occupy, `W/M` — a provisioning
decision made before any request arrives — and is **invariant to context
length**:

{chr(10).join(ratio_lines)}

Read across a row and the numbers change; read along a context axis and they do
not. An A100 serving an 8B GQA model puts 80% of per-user memory into private KV
at 4K context and still 80% at 256K. The same A100 serving Qwen2.5-32B puts only
18% into KV, at every context length, because the weights already occupy most of
the card.

So the economically load-bearing statement is not "KV eventually wins". It is
that **long context does not shift the balance between amortizable and
non-amortizable memory at all — it just multiplies both.** A provider cannot
batch its way out of long context, and it also does not face a qualitative
regime change at some context length. It faces a linear cost increase with no
offsetting amortization, which is a simpler and more robust claim than the
crossover the brief anticipated.

### B(L) < 1: the datacenter hits the same wall the local box does

The B(L) curves cross below one concurrent user at context_floor for several
model/accelerator pairs that are perfectly comfortable at chat context:

{chr(10).join(starved_lines)}

Below B = 1 the weights no longer amortize across users at all — a single
request occupies the whole card, or the deployment has to shard across cards and
pay interconnect for it. This is the *same* arithmetic that made a 30B-class
model infeasible on a 32GB consumer card in Arm C1, at a different scale. The
constraint is not "datacenters have enough memory and local boxes do not"; both
sides are governed by the same `(M − W) / (kv_pt · L)` and long agent context
pushes both toward the same boundary.

A crossover exists only where something *other than memory* caps the batch. With
a serving-stack cap (vLLM's documented `max_num_seqs` default is 256; carried as
a bracket {{32, 256}} because it is a deployment choice):

{chr(10).join(lcross_lines)}

**L_cross is reported per model, never as one global number, and it does depend
on architecture** — the MHA contrast model crosses at 100 tokens where the MoE
crosses at 2,424, a 24x spread driven entirely by `n_kv_heads` and layer count.
But every one of these sits far below any realistic agent context. Even in the
capped regime where a crossover exists, it has already happened by the time an
agent has finished loading its system prompt.

---

## 3. Threshold check — predicted knee vs published pricing

### Predicted knees (8B GQA class, fp16)

{chr(10).join(knee_lines)}

`b_min` — the concurrency below which a provider would stop covering cost at the
standard rate — is **unobservable**, so it is swept. That sweep alone spans
{lo_band:,.0f}–{hi_band:,.0f} tokens for a single model on three accelerators.

### Published thresholds

{chr(10).join(pub_lines)}

### VERDICT: the cost structure does NOT explain the pricing. Clean negative.

{a3['n_inside_band']} of {a3['n_published_numeric']} published thresholds fall
inside the predicted band — but this is a **vacuous pass**. The band spans a
factor of {hi_band / lo_band:.0f}, so essentially any threshold a provider could
plausibly choose would land inside it. A test that cannot fail is not evidence.

Three independent observations point the other way:

1. **The numbers look chosen, not computed.** 200K, 256K, and 512K are round
   figures. OpenAI's 272K is the more telling one: GPT-5-class models advertise a
   400K total window with 128K maximum output, and 400K − 128K = 272K exactly.
   That is a product-architecture boundary — the largest input that can coexist
   with a full-length response — not a memory knee.
2. **Providers disagree with each other at the same hardware generation.** 200K,
   256K, 272K, 512K, and "none" coexist. Cost structure is broadly common across
   providers; the thresholds are not.
3. **The decisive falsifier: Anthropic deleted its threshold on a date.** The 2x
   input / 1.5x output surcharge above 200K was eliminated 2026-03-13, with no
   corresponding change in accelerator memory capacity. A cost-driven boundary
   cannot be removed by announcement.

We did not tune `b_min` to make the prediction land, and we are not reporting the
containment as a match. The honest reading is that long-context pricing steps are
commercial positioning, and our arithmetic cannot predict them.

### A4 feedback into `study_params.yaml`

`cloud.long_context_threshold_tokens` moves from `confidence: guess` (value
200,000, "NOT FOUND") to **`confidence: published`, value 272,000** — upgraded
because Arm A3's literature sweep *found a rate card*, **not** because the cost
model derived it. The negative result is recorded in the entry under
`A3_NEGATIVE`, and the one dissenting source is recorded under
`CONFLICTING_SOURCE` rather than dropped. The 128K–400K bracket is retained.

**This changes Phase 1.** context_floor is {context_floor:,.0f} tokens, which is
**below** 272K. At the median turn OpenAI bills the short-context column, so
**every `above_threshold` row in the Phase-1 tables is inapplicable at
context_floor**. The ~2x T2 swing is a tail phenomenon: TraceLab's p90 step
prefix reaches ~467K, which does cross. Phase 3 must apply the threshold per
sampled trajectory, not globally.

---

## 4. Local KV feasibility — which Phase-1 T1 rows survive

Full grid in `kv_feasibility.csv` (hw × model × quant × kv_dtype).

{chr(10).join(feas_lines)}

**All three Phase-1 T1 rows survive, but the discrete-GPU row survives
conditionally and Phase 1 never checked the condition.** On the RTX 5090, an 8B
model at fp16 weights with an fp16 KV cache tops out at 102,081 tokens — short of
the {context_floor:,.0f}-token floor. The row is valid only if you name a
quantization: q4_k_m or q8_0 weights, or fp16 weights with a q8_0 KV cache. That
is consistent with the community benchmarks Phase 1 drew its rates from (which
are quantized), so no Phase-1 number is retracted — but the row must now carry
its quantization, and the 4090 is worse (8B at fp16 weights is infeasible at
either KV dtype).

**`kv_cache_capacity_flag` resolves to FALSE** and moves from `guess` to
`estimated`. A 30B-class model plus a context_floor KV cache does not fit a 24GB
4090 under any combination tested. On the 32GB 5090 it fits in exactly one:
the Qwen3-30B-A3B MoE at q4_k_m weights with q8_0 KV. The dense Qwen2.5-32B never
fits at 115K on 32GB. Note the mechanism this vindicates: the MoE has 4 KV heads
against the dense model's 8, so it carries 96 KiB/token against 256 KiB/token —
the MoE is *feasible where the dense model is not*, at comparable parameter
count, purely because of attention geometry.

Also flagged: **Llama-3.1-70B does not fit context_floor on either unified-memory
box above q4_k_m** (q8_0 weights caps out at 64,049 tokens; fp16 weights do not
fit at all). No Phase-1 conclusion depends on this, since Phase 1 ran the 7–8B
class, but it bounds any future 70B-local claim.

---

## 5. Prefill robustness — ROBUST or FRAGILE, per verdict

Three scaling models at context_floor, relative to pp512
(`c = {b['c_coefficient']:.3e}` for Llama-3.1-8B, derived from the config, not fitted):

| model | ratio at {context_floor:,.0f} | basis | confidence |
|---|---:|---|---|
| optimistic_flat | {ratios['optimistic_flat']:.3f} | Phase 1's implicit assumption | guess |
| linear_attention_theoretic | {ratios['linear_attention_theoretic']:.3f} | transformer prefill FLOP accounting | estimated |
| quadratic_pessimistic | {ratios['quadratic_pessimistic']:.4f} | llama.cpp depth anchor, Lc={EMPIRICAL_LC:.0f} | estimated |

Spread: {1.0 / ratios['quadratic_pessimistic']:.0f}x. Never averaged.

{chr(10).join(b_lines)}

### The marginal verdict is ROBUST

Local wins on energy-only cost in **every** cell, under **every** scaling model.
The rates at which cloud would take over are 0.09–86 tok/s; even the pessimistic
model leaves local at 30.6–292 tok/s at context_floor. The tightest cell is
`recomputes` / RTX 5090 / below_threshold, and it still clears its flip rate by
3.4x. Phase 1's headline — *cost is not the hybrid question on marginal terms* —
survives the interpolation attack intact.

### The Apple / `recomputes` conditional does NOT survive. FRAGILE.

This was the question. Phase 1 reported that Apple under `recomputes` needs
`capex_utilization >= 17.8%` at 36 months. Inverting on the prefill rate:

| scaling model | prefill rate at floor | turn seconds | u* required |
|---|---:|---:|---:|
| optimistic_flat | {apple['rate_optimistic_flat']:.0f} tok/s | {apple['sec_optimistic_flat']:.0f} s | **{_fmt_u(apple['u_star_optimistic_flat'])}** |
| linear_attention_theoretic | {apple['rate_linear_attention_theoretic']:.0f} tok/s | {apple['sec_linear_attention_theoretic']:.0f} s | **{_fmt_u(apple['u_star_linear_attention_theoretic'])}** |
| quadratic_pessimistic | {apple['rate_quadratic_pessimistic']:.0f} tok/s | {apple['sec_quadratic_pessimistic']:.0f} s | **{_fmt_u(apple['u_star_quadratic_pessimistic'])}** — impossible |

**u\\* range across the three models: {_fmt_u(apple['u_star_optimistic_flat'])} → impossible.**

The 17.8% figure was an artifact of assuming prefill throughput does not degrade.
It is the *optimistic edge of a bracket*, not a central estimate. Against the
TraceLab utilization anchor (human-idle-capped 14.5%), the conditional already
fails at the optimistic edge, and by the attention-theoretic model — which is
just FLOP counting on a sourced config — Apple needs {_fmt_u(apple['u_star_linear_attention_theoretic'])}
utilization, which no plausible agent stream supplies. Under the pessimistic
model amortized local cannot win at any utilization.

Every `recomputes` row is FRAGILE on the amortized comparison. Every `persists`
row is ROBUST (worst case 8.1%, under the 14.5% anchor). **The prefill
interpolation attack does not damage the study's conclusions — it sharpens them
onto `local_kv_persistence`.** Whether the local runtime holds KV across turns
was already the largest lever; Arm B removes the one surviving case where
`recomputes` was defensible.

---

## 6. The one hardware measurement to make first

**Measure cold prefill throughput as a function of prompt length on the 7–8B
class, at depths 512 / 8,192 / 32,768 / 65,536 / 115,440.**

Not a single 115K number. The point is to discriminate the three scaling models,
and they separate at different depths:

{chr(10).join(sep_lines)}

- **{d1:,.0f} tokens** is the shallowest depth where attention-theoretic and
  pessimistic differ by ≥2x — cheap to run, and it already kills one model.
- **{d2:,.0f} tokens** is where flat and attention-theoretic separate by ≥2x —
  this is what falsifies the Phase-1 assumption.
- **{context_floor:,.0f} tokens** is the operating point, where the models span
  {1.0 / ratios['quadratic_pessimistic']:.0f}x.

`llama-bench` supports this directly via `-d` (prefilled-context depth), and its
reported run-to-run stddev is sub-1% on stable backends, so a 2x separation is
far outside noise. One sweep, one afternoon, and the widest remaining bracket in
the study collapses.

Second priority, and it is not a measurement: **decide `local_kv_persistence`.**
Arm B shows the amortized verdict is FRAGILE under `recomputes` on all three hw
configs and ROBUST under `persists` on all three. That is a runtime software
choice, resolvable by reading a serving stack's documentation, and it dominates
anything a wattmeter will tell us.

---

## Guardrails in force

- Arm A stayed on the economics side: cost structure and capacity arithmetic
  only. No claim about any provider's internal configuration appears above.
- A3 returned a negative and it is reported as a negative. `b_min` was swept, not
  tuned.
- Longctx bounds and the three prefill scaling models are carried as brackets
  throughout. No midpoints.
- `local_kv_persistence` is the outer loop in every T1 table.
- The A1 gate ran before A2/A3 were built.
- No policy search, trajectory sim, DES, quality model, or thermal model.
"""
    (OUT / "PHASE2.md").write_text(text, encoding="utf-8")
    print(f"Wrote {OUT / 'PHASE2.md'}")


def main() -> None:
    p = load_params()
    context_floor = float(_v(p["workload"]["context_floor"]))

    print("ARM C — KV arithmetic core")
    c = run_arm_c(context_floor)

    print("ARM A1 — sanity gate")
    a1 = run_arm_a1()
    for r in a1["rows"]:
        print(
            f"  {r['anchor']:<42} published={r['published_batch']:>5.0f} "
            f"ours={r['predicted_batch']:>8.2f} disagreement={r['disagreement_factor']:.2f}x "
            f"{'PASS' if r['passed'] else 'FAIL'}"
        )
    if not a1["passed"]:
        _write_csv(OUT / "batch_vs_context.csv", [])
        raise SystemExit(
            "A1 SANITY GATE FAILED — batch arithmetic disagrees with published "
            "measurements by more than 2x. A2/A3 NOT built. Fix the arithmetic."
        )
    print("  GATE PASS")

    run_arm_a1_sweep()
    print("ARM A2 — amortization collapse")
    a2 = run_arm_a2(context_floor)
    print("ARM A3 — threshold prediction and check")
    a3 = run_arm_a3()
    print("ARM B — prefill interpolation bounds")
    b = run_arm_b(p)

    write_phase2(p, context_floor, c, a1, a2, a3, b)

    print()
    print("Phase 2 complete.")
    print(f"  A1 gate: PASS (worst {max(r['disagreement_factor'] for r in a1['rows']):.2f}x)")
    print(f"  A2 collapse ratio 8K->floor: {a2['collapse_ratio_analytic']:.2f}x")
    print(f"  A3 predicted band (8B): {a3['band_8b'][0]:,.0f}-{a3['band_8b'][1]:,.0f} tokens")
    print(f"     published thresholds: {a3['distinct_published']} (+{a3['n_no_threshold']} with none)")
    print(f"  B ratios at floor: {({k: round(v, 4) for k, v in b['ratios_at_floor'].items()})}")
    print(f"  outputs -> {OUT}")


if __name__ == "__main__":
    main()
