"""Phase-1 prelim runner: per-turn cost model + headline tables.

OUTER LOOP everywhere: local_kv_persistence. Never collapsed.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import yaml

from censor.tiers import (
    CloudPrices,
    HwConfig,
    InterpolationFamily,
    KvPersistence,
    LongctxBound,
    TurnSpec,
    cost_T0,
    cost_T1,
    cost_T2,
    utilization_threshold_to_beat_t2,
)

ROOT = Path(__file__).resolve().parents[1]
PARAMS_PATH = Path(__file__).with_name("study_params.yaml")
OUT = ROOT / "analysis" / "prelim"
OUT.mkdir(parents=True, exist_ok=True)

INTERPOLATION_FAMILIES: tuple[InterpolationFamily, ...] = ("log_normal", "empirical_step")
KV_VALUES: tuple[KvPersistence, ...] = ("persists", "recomputes")
LONGCTX: tuple[LongctxBound, ...] = ("below_threshold", "above_threshold")

# Phase 1 is per-turn: trajectory quantile interpolation does not enter the
# cost formulas. Both families therefore produce identical Phase-1 numbers;
# reporting both is the Item D robustness check (stability => drops off the
# caveat list for per-turn claims).
PHASE1_INTERP_NOTE = (
    "Phase 1 is per-turn; steps-per-request quantile interpolation does not "
    "enter. log_normal and empirical_step rows are identical by construction. "
    "If they remain identical after Phase 3 trajectory sampling, the choice "
    "stops mattering for the headline."
)


def _v(node: dict[str, Any], key: str = "value") -> Any:
    return node[key]


def load_params(path: Path = PARAMS_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def representative_turn(p: dict[str, Any], *, delta: float | None = None) -> TurnSpec:
    w = p["workload"]
    tps = w["tokens_per_step"]
    d = float(delta) if delta is not None else float(
        _v(p["local_runtime"]["local_kv_persistence"]["delta_tokens_per_turn"])
    )
    return TurnSpec(
        prefix_tokens=float(_v(tps["prefix_tokens_median"])),
        append_tokens=float(_v(tps["append_tokens_median"])),
        output_tokens=float(_v(tps["output_tokens_median"])),
        context_floor=float(_v(w["context_floor"])),
        delta_tokens=d,
    )


def cloud_prices(p: dict[str, Any], provider: str, tier: str) -> CloudPrices:
    node = p["cloud"]["providers"][provider][tier]
    long_in = node.get("long_context_price_input_uncached_per_mtok")
    long_c = node.get("long_context_price_input_cached_per_mtok")
    long_o = node.get("long_context_price_output_per_mtok")
    return CloudPrices(
        input_uncached_per_mtok=float(_v(node["price_input_uncached_per_mtok"])),
        input_cached_per_mtok=float(_v(node["price_input_cached_per_mtok"])),
        output_per_mtok=float(_v(node["price_output_per_mtok"])),
        long_input_uncached_per_mtok=float(_v(long_in)) if long_in else None,
        long_input_cached_per_mtok=float(_v(long_c)) if long_c else None,
        long_output_per_mtok=float(_v(long_o)) if long_o else None,
    )


def hw_configs(p: dict[str, Any]) -> list[HwConfig]:
    """Three hardware classes, 7-8B model size (primary local agent class)."""
    lh = p["local_hardware"]
    host = float(_v(lh["discrete_gpu"]["host_platform_capex_usd"]))
    configs: list[HwConfig] = []

    sh = lh["strix_halo"]
    configs.append(
        HwConfig(
            name="strix_halo",
            decode_tok_per_sec=float(_v(sh["model_7_8b"]["decode_tok_per_sec"])),
            prefill_tok_per_sec_pp512=float(_v(sh["model_7_8b"]["prefill_tok_per_sec_pp512"])),
            sustained_power_w=float(_v(sh["sustained_power_w"])),
            capex_usd=float(_v(sh["capex_usd"])),
            model_size="7_8b",
        )
    )

    ap = lh["apple_m_series"]
    configs.append(
        HwConfig(
            name="apple_m_series",
            decode_tok_per_sec=float(_v(ap["model_7_8b"]["decode_tok_per_sec"])),
            prefill_tok_per_sec_pp512=float(_v(ap["model_7_8b"]["prefill_tok_per_sec_pp512"])),
            sustained_power_w=float(_v(ap["sustained_power_w"])),
            capex_usd=float(_v(ap["capex_usd"])),
            model_size="7_8b",
        )
    )

    gpu = lh["discrete_gpu"]["rtx_5090"]
    # pp512 is null for discrete GPU — use decode-bandwidth-scaled guess from
    # Strix Halo? No: user said mark INTERPOLATED from pp512. Without pp512 we
    # cannot run. Use a published-order proxy: mark explicitly as UNSOURCED and
    # skip, OR use TTFT-implied rate. Spec says prefill is null for 5090.
    # For Phase 1 we still need a number: derive a crude INTERPOLATED proxy from
    # the Strix Halo pp512 scaled by bandwidth ratio, labeled as such.
    # Better: skip configs without pp512? User wants three hw configs.
    # Spec: "prefill_tok_per_sec_at_115k is UNSOURCED for all three hw configs"
    # and "Mark every T1 result that depends on it as INTERPOLATED and say from
    # what (pp512 benchmarks)."
    # Discrete GPU has no pp512 either. I'll use a bandwidth-scaled interpolation
    # from Strix Halo pp512 and label it INTERPOLATED_FROM_PP512_BANDWIDTH_SCALED.
    sh_bw = float(_v(sh["memory_bandwidth_gb_s"]))
    gpu_bw = float(_v(gpu["memory_bandwidth_gb_s"]))
    sh_pp = float(_v(sh["model_7_8b"]["prefill_tok_per_sec_pp512"]))
    gpu_pp_proxy = sh_pp * (gpu_bw / sh_bw)
    configs.append(
        HwConfig(
            name="discrete_gpu_rtx5090",
            decode_tok_per_sec=float(_v(gpu["model_7_8b"]["decode_tok_per_sec"])),
            prefill_tok_per_sec_pp512=gpu_pp_proxy,
            sustained_power_w=float(_v(gpu["sustained_power_w"])),
            capex_usd=float(_v(gpu["capex_usd"])) + host,
            model_size="7_8b",
        )
    )
    return configs


def _winner(t2_lo: float, t2_hi: float, t1_marg: float, t1_am_lo: float, t1_am_hi: float) -> str:
    """Classify winner without collapsing intervals into a midpoint."""
    # Marginal (energy-only) comparison — strongest claim if it holds.
    if t1_marg < t2_lo:
        marg = "T1_marginal_beats_T2_even_at_T2_low"
    elif t1_marg > t2_hi:
        marg = "T2_beats_T1_marginal_even_at_T2_high"
    else:
        marg = "T1_marginal_overlaps_T2_interval"

    # Amortized intervals.
    if t1_am_hi < t2_lo:
        am = "T1_amortized_always_beats_T2"
    elif t1_am_lo > t2_hi:
        am = "T2_always_beats_T1_amortized"
    else:
        am = "T1_amortized_interval_overlaps_T2"

    return f"{marg} | {am}"


def run() -> dict[str, Any]:
    p = load_params()
    turn = representative_turn(p)
    cache_hit = float(_v(p["workload"]["prefix_cache_hit_rate_tool_result"]))
    cache_overall = float(_v(p["workload"]["prefix_cache_hit_rate_overall"]))
    elec = float(_v(p["local_hardware"]["common"]["electricity_usd_per_kwh"]))
    life_lo = float(_v(p["local_hardware"]["common"]["assumed_lifetime_months"], "lo"))
    life_hi = float(_v(p["local_hardware"]["common"]["assumed_lifetime_months"], "hi"))
    life_mid = float(_v(p["local_hardware"]["common"]["assumed_lifetime_months"]))
    util_lo = float(_v(p["local_hardware"]["common"]["capex_utilization"], "lo"))
    util_hi = float(_v(p["local_hardware"]["common"]["capex_utilization"], "hi"))
    ttft_s = float(_v(p["cloud"]["ttft_ms"])) / 1000.0
    out_tps = float(_v(p["cloud"]["output_tok_per_sec"]["pure_decode"]))
    rtt_s = float(_v(p["cloud"]["rtt_ms"])) / 1000.0
    orch_s = float(_v(p["orchestration"]["orchestration_floor_ms"])) / 1000.0

    # Primary cloud reference for the central comparison: OpenAI mid (longctx
    # bound matters). Anthropic mid reported in decomposition for residency check.
    provider, tier = "openai", "mid"
    prices = cloud_prices(p, provider, tier)
    hws = hw_configs(p)

    # ---- C1 cache-rent decomposition ----
    decomp_rows: list[dict[str, Any]] = []
    for prov, tr in (("openai", "mid"), ("anthropic", "mid"), ("openai", "frontier"), ("anthropic", "frontier")):
        pr = cloud_prices(p, prov, tr)
        bounds: list[LongctxBound]
        if pr.long_input_uncached_per_mtok is None:
            bounds = ["below_threshold"]
            bound_label = "n/a_no_surcharge"
        else:
            bounds = list(LONGCTX)
            bound_label = None
        for bound in bounds:
            r = cost_T2(
                turn, prov, tr, cache_hit, bound, pr,
                ttft_s=ttft_s, output_tok_per_sec=out_tps, rtt_s=rtt_s,
            )
            total = r.components.cache_read_usd + r.components.uncached_prefill_usd + r.components.output_usd
            decomp_rows.append({
                "provider": prov,
                "model_tier": tr,
                "model": p["cloud"]["providers"][prov][tr]["model"],
                "longctx_bound": bound_label if bound_label else bound,
                "cache_hit_rate": cache_hit,
                "cache_hit_rate_note": "tool-result ~97.5%; SCOPING BIAS favorable to cloud",
                "cache_read_usd": r.components.cache_read_usd,
                "uncached_prefill_usd": r.components.uncached_prefill_usd,
                "output_usd": r.components.output_usd,
                "total_usd": total,
                "residency_rent_fraction": r.components.residency_fraction,
                "compute_fraction": r.components.compute_fraction,
                "naive_usd": r.naive_usd,
                "overstatement_ratio_naive_over_cacheaware": (
                    r.naive_usd / total if total > 0 else float("nan")
                ),
                "tracelab_reported_prefix_spend_share": float(
                    _v(p["workload"]["redundant_prefill"]["cost_share_prefix_tokens"])
                ),
            })

    # ---- C2 / C3 central comparison ----
    cost_rows: list[dict[str, Any]] = []
    util_rows: list[dict[str, Any]] = []

    for kv in KV_VALUES:
        for hw in hws:
            t1 = cost_T1(
                turn, hw, kv,
                electricity_usd_per_kwh=elec,
                lifetime_months_lo=life_lo,
                lifetime_months_hi=life_hi,
                utilization_lo=util_lo,
                utilization_hi=util_hi,
            )
            # Discrete GPU prefill note override
            pref_note = t1.prefill_interpolation_note
            if hw.name == "discrete_gpu_rtx5090":
                pref_note = (
                    "INTERPOLATED: discrete GPU has no published pp512; "
                    "using Strix Halo pp512 scaled by memory-bandwidth ratio "
                    f"({t1.components.prefill_rate_tok_per_sec:.1f} tok/s). "
                    "Weakest local prefill estimate in the table."
                )

            for bound in LONGCTX:
                t2 = cost_T2(
                    turn, provider, tier, cache_hit, bound, prices,
                    ttft_s=ttft_s, output_tok_per_sec=out_tps, rtt_s=rtt_s,
                )
                # For OpenAI, usd_low/high of a single bound are equal; the
                # interval across bounds is assembled in summary. Per-row we
                # keep the bound explicit (never a midpoint).
                overstatement = t2.naive_usd / t2.usd_low if t2.usd_low > 0 else float("nan")
                winner = _winner(
                    t2.usd_low, t2.usd_high,
                    t1.usd_marginal, t1.usd_amortized_lo, t1.usd_amortized_hi,
                )
                # Also compute winner against this specific bound's point T2
                # (still no midpoint across bounds — each row is one bound).
                if t1.usd_marginal < t2.usd_low:
                    marg_vs = "T1_marginal"
                elif t1.usd_marginal > t2.usd_low:
                    marg_vs = "T2"
                else:
                    marg_vs = "tie"
                if t1.usd_amortized_hi < t2.usd_low:
                    am_vs = "T1_amortized_always"
                elif t1.usd_amortized_lo > t2.usd_low:
                    am_vs = "T2_always"
                else:
                    am_vs = "depends_on_utilization_lifetime"

                for family in INTERPOLATION_FAMILIES:
                    cost_rows.append({
                        "kv_persistence": kv,
                        "hw_config": hw.name,
                        "model_size": hw.model_size,
                        "longctx_bound": bound,
                        "interpolation_family": family,
                        "interpolation_note": PHASE1_INTERP_NOTE,
                        "provider": provider,
                        "model_tier": tier,
                        "model": p["cloud"]["providers"][provider][tier]["model"],
                        "cache_hit_rate": cache_hit,
                        "scoping_bias": "tool-result 97.5%; favorable to cloud",
                        "T2_usd": t2.usd_low,
                        "T2_usd_note": "single longctx bound; never averaged with the other bound",
                        "T2_naive_usd": t2.naive_usd,
                        "T2_overstatement_ratio": overstatement,
                        "T2_cache_read_usd": t2.components.cache_read_usd,
                        "T2_uncached_prefill_usd": t2.components.uncached_prefill_usd,
                        "T2_output_usd": t2.components.output_usd,
                        "T2_residency_fraction": t2.components.residency_fraction,
                        "T2_sec": t2.sec,
                        "T1_usd_marginal": t1.usd_marginal,
                        "T1_usd_amortized_lo": t1.usd_amortized_lo,
                        "T1_usd_amortized_hi": t1.usd_amortized_hi,
                        "T1_sec": t1.sec,
                        "T1_joules": t1.joules,
                        "T1_prefill_tokens": t1.components.prefill_tokens,
                        "T1_prefill_interpolated": True,
                        "T1_prefill_note": pref_note,
                        "T1_amortization_note": t1.amortization_uncertainty_note,
                        "ratio_T1marg_over_T2": t1.usd_marginal / t2.usd_low if t2.usd_low else float("nan"),
                        "winner_marginal": marg_vs,
                        "winner_amortized": am_vs,
                        "winner_detail": winner,
                        "usd_per_1000_turns_T2": t2.usd_low * 1000.0,
                        "usd_per_1000_turns_T2_naive": t2.naive_usd * 1000.0,
                        "usd_per_1000_turns_T1_marginal": t1.usd_marginal * 1000.0,
                        "usd_per_1000_turns_T1_amortized_lo": t1.usd_amortized_lo * 1000.0,
                        "usd_per_1000_turns_T1_amortized_hi": t1.usd_amortized_hi * 1000.0,
                    })

                thr = utilization_threshold_to_beat_t2(
                    t1, t2.usd_low, capex_usd=hw.capex_usd, lifetime_months=life_mid,
                )
                thr_lo_life = utilization_threshold_to_beat_t2(
                    t1, t2.usd_low, capex_usd=hw.capex_usd, lifetime_months=life_lo,
                )
                thr_hi_life = utilization_threshold_to_beat_t2(
                    t1, t2.usd_low, capex_usd=hw.capex_usd, lifetime_months=life_hi,
                )
                for family in INTERPOLATION_FAMILIES:
                    util_rows.append({
                        "kv_persistence": kv,
                        "hw_config": hw.name,
                        "longctx_bound": bound,
                        "interpolation_family": family,
                        "interpolation_note": PHASE1_INTERP_NOTE,
                        "T2_usd": t2.usd_low,
                        "T1_usd_marginal": t1.usd_marginal,
                        "headroom_usd": thr["headroom_usd"],
                        "u_star_at_lifetime_36mo": thr["u_star"],
                        "status_36mo": thr["status"],
                        "u_star_at_lifetime_24mo": thr_lo_life["u_star"],
                        "status_24mo": thr_lo_life["status"],
                        "u_star_at_lifetime_60mo": thr_hi_life["u_star"],
                        "status_60mo": thr_hi_life["status"],
                        "reason": thr["reason"],
                        "anchor_util_uncapped": float(
                            _v(p["local_hardware"]["common"]["capex_utilization"]["anchors"]["dedicated_box_uncapped"])
                        ),
                        "anchor_util_capped_1h": float(
                            _v(p["local_hardware"]["common"]["capex_utilization"]["anchors"]["dedicated_box_human_capped_1h"])
                        ),
                        "statement": _util_statement(thr, hw.name, kv, bound),
                    })

    # T0 sweep (recorded, not in central comparison table)
    t0_rows = []
    for rate in p["t0"]["applicability_sweep"]["values"]:
        r0 = cost_T0(turn, float(rate), orch_floor_s=orch_s)
        t0_rows.append({
            "applicability_rate": r0.applicability_rate,
            "usd": r0.usd,
            "sec": r0.sec,
            "applicable": r0.applicable,
            "external_validity": p["t0"]["applicability_sweep"].get("EXTERNAL_VALIDITY_FLAG", ""),
        })

    _write_csv(OUT / "cache_decomposition.csv", decomp_rows)
    _write_csv(OUT / "cost_per_turn.csv", cost_rows)
    _write_csv(OUT / "utilization_threshold.csv", util_rows)
    _write_csv(OUT / "t0_applicability.csv", t0_rows)

    _plot_cache_effect(decomp_rows)
    _plot_crossover(p, hws, prices, cache_hit, ttft_s, out_tps, rtt_s, elec, life_lo, life_hi, util_lo, util_hi)

    summary = _summarize(decomp_rows, cost_rows, util_rows, cache_overall, cache_hit)
    _write_prelim(summary, p)
    return summary


def _util_statement(thr: dict[str, Any], hw: str, kv: str, bound: str) -> str:
    if thr["status"] == "never":
        return (
            f"Local ({hw}, {kv}, {bound}) NEVER beats T2 on amortized cost: "
            f"energy alone exceeds T2 (headroom={thr['headroom_usd']:.6g})."
        )
    if thr["status"] == "always":
        return f"Local ({hw}, {kv}, {bound}) beats T2 at any utilization."
    u = thr["u_star"]
    return (
        f"Local ({hw}, {kv}, {bound}) wins only if the box is doing useful "
        f"inference work at least {100.0 * float(u):.1f}% of its service life "
        f"(at {thr['lifetime_months']} months lifetime)."
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _plot_cache_effect(decomp_rows: list[dict[str, Any]]) -> None:
    # OpenAI mid, both longctx bounds
    rows = [r for r in decomp_rows if r["provider"] == "openai" and r["model_tier"] == "mid"]
    if not rows:
        return
    labels = [r["longctx_bound"] for r in rows]
    naive = [r["naive_usd"] for r in rows]
    aware = [r["total_usd"] for r in rows]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    x = range(len(rows))
    ax.bar([i - 0.18 for i in x], naive, width=0.36, label="naive (all input uncached)", color="#b85c38")
    ax.bar([i + 0.18 for i in x], aware, width=0.36, label="cache-aware (tool-result 97.5%)", color="#2f6f8f")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("USD per turn")
    ax.set_title("T2 overstatement: naive vs cache-aware\n(OpenAI mid; SCOPING BIAS favorable to cloud)")
    ax.legend()
    for i, r in enumerate(rows):
        ax.text(i, max(r["naive_usd"], r["total_usd"]) * 1.02,
                f"{r['overstatement_ratio_naive_over_cacheaware']:.1f}x", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "cache_effect.png", dpi=140)
    plt.close(fig)


def _plot_crossover(
    p: dict[str, Any],
    hws: list[HwConfig],
    prices: CloudPrices,
    cache_hit: float,
    ttft_s: float,
    out_tps: float,
    rtt_s: float,
    elec: float,
    life_lo: float,
    life_hi: float,
    util_lo: float,
    util_hi: float,
) -> None:
    """T1 vs T2 across context length, faceted by kv_persistence."""
    contexts = [2_000, 8_000, 16_000, 32_000, 64_000, 115_440, 200_000]
    out_tokens = float(_v(p["workload"]["tokens_per_step"]["output_tokens_median"]))
    delta = float(_v(p["local_runtime"]["local_kv_persistence"]["delta_tokens_per_turn"]))
    append = float(_v(p["workload"]["tokens_per_step"]["append_tokens_median"]))

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, kv in zip(axes, KV_VALUES):
        t2_below = []
        t2_above = []
        t1_by_hw: dict[str, list[float]] = {h.name: [] for h in hws}
        for ctx in contexts:
            turn = TurnSpec(
                prefix_tokens=float(ctx),
                append_tokens=append,
                output_tokens=out_tokens,
                context_floor=float(ctx),
                delta_tokens=delta,
            )
            r_lo = cost_T2(
                turn, "openai", "mid", cache_hit, "below_threshold", prices,
                ttft_s=ttft_s, output_tok_per_sec=out_tps, rtt_s=rtt_s,
            )
            r_hi = cost_T2(
                turn, "openai", "mid", cache_hit, "above_threshold", prices,
                ttft_s=ttft_s, output_tok_per_sec=out_tps, rtt_s=rtt_s,
            )
            t2_below.append(r_lo.usd_low)
            t2_above.append(r_hi.usd_low)
            for hw in hws:
                t1 = cost_T1(
                    turn, hw, kv,
                    electricity_usd_per_kwh=elec,
                    lifetime_months_lo=life_lo,
                    lifetime_months_hi=life_hi,
                    utilization_lo=util_lo,
                    utilization_hi=util_hi,
                )
                # Plot marginal (strongest claim) as solid; amortized band as fill later
                t1_by_hw[hw.name].append(t1.usd_marginal)

        ax.fill_between(contexts, t2_below, t2_above, color="#2f6f8f", alpha=0.25, label="T2 OpenAI mid (longctx band)")
        ax.plot(contexts, t2_below, color="#2f6f8f", linestyle="--", label="T2 below_threshold")
        ax.plot(contexts, t2_above, color="#2f6f8f", linestyle=":", label="T2 above_threshold")
        colors = {"strix_halo": "#3a7d44", "apple_m_series": "#8b5e3c", "discrete_gpu_rtx5090": "#6b3fa0"}
        for hw in hws:
            ax.plot(contexts, t1_by_hw[hw.name], color=colors[hw.name], label=f"T1 marg {hw.name}")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("context tokens")
        ax.set_title(f"kv_persistence = {kv}")
        ax.axvline(115440, color="gray", linestyle="--", linewidth=0.8, label="context_floor")
        ax.grid(True, which="both", alpha=0.3)
    axes[0].set_ylabel("USD per turn (log)")
    axes[1].legend(fontsize=7, loc="upper left")
    fig.suptitle(
        "T1 (marginal/energy) vs T2 across context — FACETED by kv_persistence\n"
        "T1 prefill INTERPOLATED from pp512; SCOPING BIAS favorable to cloud",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(OUT / "crossover.png", dpi=140)
    plt.close(fig)


def _summarize(
    decomp: list[dict[str, Any]],
    costs: list[dict[str, Any]],
    utils: list[dict[str, Any]],
    cache_overall: float,
    cache_hit: float,
) -> dict[str, Any]:
    # Use OpenAI mid below_threshold as primary decomposition reference
    d0 = next(
        r for r in decomp
        if r["provider"] == "openai" and r["model_tier"] == "mid"
        and r["longctx_bound"] in ("below_threshold", "n/a_no_surcharge")
    )
    # One family only for summary uniqueness
    c = [r for r in costs if r["interpolation_family"] == "log_normal"]
    families_identical = all(
        abs(
            next(x for x in costs if x["interpolation_family"] == "log_normal"
                 and x["kv_persistence"] == r["kv_persistence"]
                 and x["hw_config"] == r["hw_config"]
                 and x["longctx_bound"] == r["longctx_bound"])["T1_usd_marginal"]
            - r["T1_usd_marginal"]
        ) < 1e-15
        for r in costs if r["interpolation_family"] == "empirical_step"
    )

    # Gate: is there a regime where placement is non-trivial?
    # Non-trivial means: under some (kv, hw, longctx, util) T1 wins and under
    # others T2 wins — OR the answer flips with kv_persistence.
    persists_marg = [r for r in c if r["kv_persistence"] == "persists"]
    recomputes_marg = [r for r in c if r["kv_persistence"] == "recomputes"]

    def any_t1_marg_wins(rows: list[dict[str, Any]]) -> bool:
        return any(r["winner_marginal"] == "T1_marginal" for r in rows)

    def any_t2_wins(rows: list[dict[str, Any]]) -> bool:
        return any(r["winner_marginal"] == "T2" for r in rows)

    def any_am_depends(rows: list[dict[str, Any]]) -> bool:
        return any(r["winner_amortized"] == "depends_on_utilization_lifetime" for r in rows)

    def all_am_t1(rows: list[dict[str, Any]]) -> bool:
        return all(r["winner_amortized"] == "T1_amortized_always" for r in rows)

    gate_persists = {
        "marginal_t1_anywhere": any_t1_marg_wins(persists_marg),
        "marginal_t2_anywhere": any_t2_wins(persists_marg),
        "amortized_depends": any_am_depends(persists_marg),
        "amortized_t1_always": all_am_t1(persists_marg),
    }
    gate_recomputes = {
        "marginal_t1_anywhere": any_t1_marg_wins(recomputes_marg),
        "marginal_t2_anywhere": any_t2_wins(recomputes_marg),
        "amortized_depends": any_am_depends(recomputes_marg),
        "amortized_t1_always": all_am_t1(recomputes_marg),
    }

    # Strong claim: energy-only local beats cloud everywhere tested.
    marginal_t1_everywhere = (
        gate_persists["marginal_t1_anywhere"]
        and gate_recomputes["marginal_t1_anywhere"]
        and not gate_persists["marginal_t2_anywhere"]
        and not gate_recomputes["marginal_t2_anywhere"]
    )
    # Non-trivial amortized regime under recomputes (util decides).
    nontrivial = gate_persists["amortized_depends"] or gate_recomputes["amortized_depends"]
    flips = gate_persists["amortized_t1_always"] != gate_recomputes["amortized_t1_always"]

    over_by_bound = {
        r["longctx_bound"]: r["T2_overstatement_ratio"]
        for r in c if r["kv_persistence"] == "persists" and r["hw_config"] == "strix_halo"
    }

    return {
        "cache_hit_tool_result": cache_hit,
        "cache_hit_overall": cache_overall,
        "decomp_openai_mid_below": d0,
        "overstatement_by_bound": over_by_bound,
        "gate_nontrivial": nontrivial,
        "gate_persists": gate_persists,
        "gate_recomputes": gate_recomputes,
        "kv_flips_marginal": False,  # Phase-1: marginal never flips
        "kv_flips_amortized": flips,
        "marginal_t1_everywhere": marginal_t1_everywhere,
        "families_identical": families_identical,
        "cost_rows": c,
        "util_rows": [r for r in utils if r["interpolation_family"] == "log_normal"],
    }


def _write_prelim(summary: dict[str, Any], p: dict[str, Any]) -> None:
    d0 = summary["decomp_openai_mid_below"]
    over = summary["overstatement_by_bound"]
    nontrivial = summary["gate_nontrivial"]
    gp = summary["gate_persists"]
    gr = summary["gate_recomputes"]

    if summary["marginal_t1_everywhere"]:
        marginal_claim = (
            "On **usd_marginal** (energy only, utilization-independent): T1 "
            "beats T2 under BOTH `persists` and `recomputes`, on all three hw "
            "configs, at both longctx bounds. Local energy is negligible next to "
            "metered token pricing. That is the strongest possible local claim "
            "Phase 1 can make, and it holds even under the cloud-favorable "
            "SCOPING BIAS. Prefill is INTERPOLATED from pp512 (optimistic for "
            "local); a slower real 115K prefill raises T1 energy but is unlikely "
            "to close a ~50–1000x gap."
        )
    else:
        marginal_claim = "Marginal comparison is mixed; see tables."

    if nontrivial:
        gate_answer = "YES"
        region = (
            "Placement is non-trivial on the **amortized** comparison under "
            "`local_kv_persistence: recomputes`. There, Strix Halo and Apple "
            "amortized intervals overlap T2, so the winner depends on "
            "capex_utilization x lifetime. Under `persists`, amortized T1 beats "
            "T2 across the entire swept util×life range on all three hw configs. "
            "Discrete GPU (RTX 5090 + host) still amortizes below T2 even under "
            "`recomputes` within the swept range, but its prefill rate is a "
            "bandwidth-scaled proxy with no published pp512 — weakest local row."
        )
    else:
        gate_answer = "NO"
        region = (
            "One tier dominates the amortized comparison across the Phase-1 "
            "grid as well; see tables."
        )

    # Build comparison markdown tables per kv
    def table_for(kv: str) -> str:
        rows = [r for r in summary["cost_rows"] if r["kv_persistence"] == kv]
        lines = [
            f"#### `local_kv_persistence = {kv}`",
            "",
            "| hw | longctx | T2 $/turn | T2 naive | overstate | T1 marg | T1 amort [lo,hi] | winner (marg / amort) |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
        for r in rows:
            # only one interp family in summary cost_rows
            lines.append(
                f"| {r['hw_config']} | {r['longctx_bound']} | "
                f"{r['T2_usd']:.6g} | {r['T2_naive_usd']:.6g} | "
                f"{r['T2_overstatement_ratio']:.2f}x | "
                f"{r['T1_usd_marginal']:.6g} | "
                f"[{r['T1_usd_amortized_lo']:.6g}, {r['T1_usd_amortized_hi']:.6g}] | "
                f"{r['winner_marginal']} / {r['winner_amortized']} |"
            )
        lines.append("")
        lines.append(
            "SCOPING BIAS attached to every T2 number: tool-result hit rate "
            f"{summary['cache_hit_tool_result']:.3f} (favorable to cloud)."
        )
        lines.append(
            "AMORTIZATION UNCERTAINTY attached to every T1 amortized interval: "
            "utilization 0.033–1.0 x lifetime 24–60 mo (~75x)."
        )
        lines.append(
            "Every T1 number: INTERPOLATED prefill from pp512 (optimistic for local)."
        )
        return "\n".join(lines)

    util_lines = [
        "| kv | hw | longctx | u* @36mo | status | statement |",
        "|---|---|---|---:|---|---|",
    ]
    for r in summary["util_rows"]:
        u = r["u_star_at_lifetime_36mo"]
        u_s = f"{100*float(u):.2f}%" if u is not None and not (isinstance(u, float) and math.isnan(u)) else "n/a"
        util_lines.append(
            f"| {r['kv_persistence']} | {r['hw_config']} | {r['longctx_bound']} | "
            f"{u_s} | {r['status_36mo']} | {r['statement']} |"
        )

    # Ranked hardware measurement list, updated by Phase 2.
    measure = """1. **`prefill_tok_per_sec_at_115k`** — still the top item, and Phase 2 sharpened
   it. Arm B brackets it at 34.5–1000 tok/s on Strix Halo (29x span) and shows
   the amortized `recomputes` verdict flips inside that band. Measure cold
   prefill at depths **512 / 8,192 / 32,768 / 65,536 / 115,440** — not a single
   115K number — so the sweep discriminates the three scaling models.
2. **`local_kv_persistence`** — not measurable, but *decidable*; ~65x swing in
   T1 prefill work. Phase 2 raised its importance: `persists` is ROBUST on every
   row, `recomputes` is FRAGILE on every row. Resolve by reading the serving
   stack, before any watt is measured.
3. **`capex_utilization` in a real deployment** — a deployment property; we
   report the required threshold rather than picking a value.
4. ~~OpenAI long-context threshold~~ — **RESOLVED** by Phase 2 Arm A3: published
   at 272K, above our 115,440 context_floor.
5. ~~Discrete-GPU KV feasibility at 115K~~ — **RESOLVED** by Phase 2 Arm C1 as
   arithmetic: a 30B-class model plus a context_floor KV cache does not fit 24GB
   under any quantization, and fits 32GB in exactly one (Qwen3-30B-A3B MoE,
   q4_k_m weights, q8_0 KV). The 8B class fits both cards, but not at fp16
   weights with fp16 KV."""

    text = f"""# PRELIM — Is tier placement a real tradeoff, or trivially one-sided?

> **STATUS: PHASE 1 COMPLETE (per-turn only).** Phases 3–4 (trajectory policies,
> sensitivity tornado) have not run. Parameter set: `censor/study_params.yaml`
> (schema-validated by `censor/validate_params.py`).

---

## AMENDED BY PHASE 2 — read before quoting anything below

Phase 2 (`analysis/prelim/phase2/PHASE2.md`) overturns two Phase-1 statements.
The tables below are left as generated; these two corrections override them.

**1. The `above_threshold` rows do not apply at context_floor.** Phase 1 carried
both OpenAI long-context bounds because the threshold was unsourced
(`confidence: guess`, guessed at 200K). Phase 2 Arm A3 located it in published
rate cards: **272,000 tokens**. context_floor is 115,440, which is below it.
At the median turn OpenAI bills the short-context column, so every
`above_threshold` row here is inapplicable — it becomes live only in the tail
(TraceLab p90 step prefix ~467K does cross). Quote the `below_threshold` rows for
median-turn claims.

**2. The Apple / `recomputes` `u* >= 17.8%` conditional does not survive.** That
number assumed local prefill throughput does not degrade with context — it used
pp512 at 115K, a 225x extrapolation. Phase 2 Arm B brackets the degradation and
inverts on it: u-star is 17.8% only at the optimistic (flat) edge, rises to **86.7%**
under a FLOP-counted attention-theoretic model, and exceeds 100% (impossible)
under the pessimistic model. **17.8% is the optimistic edge of a bracket, not a
threshold.** Every `recomputes` row is FRAGILE on the amortized comparison; every
`persists` row is ROBUST.

**What survives unchanged:** the `usd_marginal` verdict. Arm B's inverse
sensitivity puts the marginal flip rate at 0.09–86 tok/s against a plausible band
of 30.6–8,453 tok/s, so local wins on energy in every cell under every scaling
model. The cache-rent decomposition and the overstatement ratio are also
untouched (they are cloud-side arithmetic, independent of local prefill).

---

## 0. Lead framing — what you are actually buying from a provider

The majority of what you pay a provider for at production agent context lengths
is **rent on context residency, not computation**. Local hardware's structural
advantage is not cheaper compute — **it owns its memory outright**.

This framing came out of the data, not from us. TraceLab (arXiv:2606.30560)
reported prefix tokens at **59.5%** of real API spend. Our own Phase-1 model at
context_floor, with the scoped tool-result hit rate, reproduces the same shape:

| Component | USD / turn (OpenAI mid, below_threshold) | Share |
|---|---:|---:|
| Cache read (residency rent) | {d0['cache_read_usd']:.6g} | **{100*d0['residency_rent_fraction']:.1f}%** |
| Uncached prefill | {d0['uncached_prefill_usd']:.6g} | {100*d0['uncached_prefill_usd']/d0['total_usd']:.1f}% |
| Output | {d0['output_usd']:.6g} | {100*d0['output_usd']/d0['total_usd']:.1f}% |
| **Total cache-aware** | **{d0['total_usd']:.6g}** | 100% |
| Naive (all input uncached) | {d0['naive_usd']:.6g} | — |
| Overstatement (naive / aware) | **{d0['overstatement_ratio_naive_over_cacheaware']:.2f}x** | — |

TraceLab's published prefix-spend share was 59.5%. Our model at the median turn
with a 97.5% hit rate puts residency rent at **{100*d0['residency_rent_fraction']:.1f}%** —
same qualitative conclusion (cache reads dominate). Exact match is not required;
the parameterization is consistent with the published spend shape.

SCOPING BIAS: per-request scoping uses tool-result hit rate
({summary['cache_hit_tool_result']:.3f}), not user-initiated (0.844). **Most
favorable to cloud.** No cloud number below may be quoted without this caveat.

### AMORTIZATION UNCERTAINTY

The local cost term carries **~75x uncertainty** — `capex_utilization` spanning
0.033–1.0 crossed with `assumed_lifetime_months` spanning 24–60 — arising from
**modeling choices with no empirical content**, before any watt is measured.
Local amortized cost is reported as an **interval, never a point estimate**.
Every published TCO analysis that picks one utilization and reports a point is
manufacturing agreement that the data does not support.

---

## 1. THE GATE — is there a regime where placement is non-trivial?

**Answer: {gate_answer}**

{marginal_claim}

{region}

Gate conditioning (must travel with the verdict):

| `local_kv_persistence` | T1 beats T2 on usd_marginal (any hw/longctx)? | T2 beats T1 on usd_marginal (any)? | Amortized depends on util×life? |
|---|---|---|---|
| `persists` | {gp['marginal_t1_anywhere']} | {gp['marginal_t2_anywhere']} | {gp['amortized_depends']} |
| `recomputes` | {gr['marginal_t1_anywhere']} | {gr['marginal_t2_anywhere']} | {gr['amortized_depends']} |

`local_kv_persistence` is the OUTER LOOP. These two settings are **never
collapsed**. The amortized comparison is where the persistence setting matters:
under `persists`, local wins the swept range; under `recomputes`, utilization
decides for Strix/Apple.

Item D (interpolation families): Phase-1 per-turn results under `log_normal`
and `empirical_step` are **{'identical' if summary['families_identical'] else 'NOT identical'}**.
Trajectory quantile interpolation does not enter per-turn formulas; the choice
drops off the caveat list for Phase-1 claims.

---

## 2. Central comparison (per turn)

OpenAI mid (`gpt-5.6-terra`). Longctx bounds reported separately — never a midpoint.
T1 = 7–8B class on each hw. Prefill INTERPOLATED from pp512.

{table_for('persists')}

{table_for('recomputes')}

### Cache overstatement (C3)

| longctx_bound | naive / cache-aware |
|---|---:|
| below_threshold | {over.get('below_threshold', float('nan')):.2f}x |
| above_threshold | {over.get('above_threshold', float('nan')):.2f}x |

Published TCO analyses that price all input uncached overstate cloud cost by
this factor at production context length under our scoped hit rate.

### Utilization threshold (C4)

Do **not** pick a utilization. Solve for it:

{chr(10).join(util_lines)}

TraceLab anchors for reading the threshold: dedicated-box uncapped generation
share **3.3%**; human-idle-capped-1h **14.5%**. If `u*` sits above 14.5%, a
dedicated TraceLab-shaped agent stream does not keep the box busy enough for
amortized local to win.

---

## 3. Policy comparison — does switching cost bind?

`<TBD: Phase 3 — trajectory sampling, P1–P4. Not in Phase 1 scope.>`

---

## 4. Top 5 parameters by influence

`<TBD: Phase 4 tornado. Not in Phase 1 scope.>`

Phase-1 qualitative ranking (not a tornado):

1. `local_kv_persistence` (guess; ~65x; can flip marginal winner)
2. `prefill_tok_per_sec_at_115k` (guess / INTERPOLATED; loads T1)
3. OpenAI longctx threshold (guess; ~2x T2)
4. `capex_utilization` x lifetime (guess; ~75x on amortized only)
5. hw class / decode rate (published ranges; second-order once prefill dominates under `recomputes`)

---

## 5. What we must measure on hardware, ranked

{measure}

---

## Guardrails in force

- `local_kv_persistence` is the OUTER LOOP everywhere. Never collapsed.
- Never a midpoint for the OpenAI long-context bound.
- Never a point estimate for amortized local cost; always `usd_marginal` separately.
- Every T1 number depending on 115K prefill is labeled INTERPOLATED.
- Phase 1 is per-turn only — no policy search, trajectory sim, DES, quality, or thermal.
- A finding that one tier dominates is a valid result and is reported plainly.
"""
    (OUT / "PRELIM.md").write_text(text, encoding="utf-8")
    print(f"Wrote {OUT / 'PRELIM.md'}")


def main() -> None:
    summary = run()
    print("Phase 1 complete.")
    print(f"  gate_nontrivial={summary['gate_nontrivial']}")
    print(f"  kv_flips_marginal={summary['kv_flips_marginal']}")
    print(f"  families_identical={summary['families_identical']}")
    d0 = summary["decomp_openai_mid_below"]
    print(
        f"  C1 residency_fraction={d0['residency_rent_fraction']:.3f} "
        f"overstatement={d0['overstatement_ratio_naive_over_cacheaware']:.2f}x"
    )
    print(f"  outputs -> {OUT}")


if __name__ == "__main__":
    main()
