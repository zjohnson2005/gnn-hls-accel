"""Three-way cost comparison + energy-gap decomposition.

Phase 1 compared local MARGINAL energy $ to cloud PRICE $. Those are different
quantities. This module never conflates them:

  C_energy : local joules/turn  vs cloud joules/turn (estimated)
  C_price  : local fully-loaded $ (energy + amortized capex) vs cloud price $
  C_marg   : local marginal $ (energy only) vs cloud price $
             <- Phase 1's claim; labelled "marginal vs fully-loaded" everywhere

Every output table reports all three or states which one it is.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from censor.anchors import (
    CLOUD_KWH_PER_1K_OUT,
    MAC_STUDIO_INFERENCE_W,
    MAC_STUDIO_PUE,
    cloud_wh_from_output_tokens,
    local_wh,
)
from censor.kv_math import MODEL_SPECS
from censor.prefill_bounds import SCALING_MODELS, prefill_rate_at
from censor.prelim_phase1 import _v, cloud_prices, hw_configs, load_params, representative_turn
from censor.tier_economics import ACCELERATORS, batch_max
from censor.tiers import (
    HwConfig,
    KvPersistence,
    LongctxBound,
    TurnSpec,
    cost_T1,
    cost_T2,
)

ComparisonKind = Literal["C_energy", "C_price", "C_marg"]

# Cloud accelerator assumptions for energy estimate (NOT fitted to 1.6 Wh).
# H100 ~700 W TDP; paper uses PUE 1.25; batch from our A_BATCH arithmetic.
H100_POWER_W = 700.0
CLOUD_PUE = 1.25
# Literature baseline the paper cites for output-dominated work; retained as
# an alternate estimator, never mixed with the H100 batch estimator silently.
CLOUD_OUTPUT_KWH_PER_1K = CLOUD_KWH_PER_1K_OUT


@dataclass(frozen=True)
class ThreeWayRow:
    hw_config: str
    kv_persistence: KvPersistence
    longctx_bound: LongctxBound
    prefill_scaling_model: str
    hit_rate_h: float
    # Energy (Wh and J)
    local_wh: float
    cloud_wh_batch_amortized: float
    cloud_wh_output_formula: float
    local_joules: float
    cloud_joules_batch: float
    # Dollars
    local_marginal_usd: float          # energy only
    local_fully_loaded_usd_lo: float   # energy + capex@hi util
    local_fully_loaded_usd_hi: float   # energy + capex@lo util
    cloud_price_usd: float
    # Ratios — always labelled
    C_energy_ratio_local_over_cloud: float          # local_wh / cloud_wh_batch
    C_price_ratio_local_over_cloud_lo: float        # fully_loaded_lo / cloud_price
    C_price_ratio_local_over_cloud_hi: float
    C_marg_ratio_local_over_cloud: float            # marginal / cloud_price  (Phase 1)
    C_marg_label: str = "marginal_vs_fully_loaded"


@dataclass(frozen=True)
class GapTerm:
    name: str
    wh_attributed: float
    fraction_of_gap: float
    uncertainty_note: str


def cloud_energy_batch_amortized(
    turn: TurnSpec,
    *,
    prefill_rate_tok_per_sec: float,
    decode_rate_tok_per_sec: float,
    batch: float,
    accel_power_w: float = H100_POWER_W,
    pue: float = CLOUD_PUE,
    prefill_tokens: float | None = None,
) -> float:
    """Estimate cloud Wh/turn under memory-limited batch amortization.

    Wall time is sequential for one request; power is shared across `batch`
    concurrent residents, so per-request energy ≈ (P * t * PUE) / batch.
    This is the capacity-bound axis: KV residency sets B, B amortizes power.
    """
    pref = float(prefill_tokens if prefill_tokens is not None else turn.context_floor)
    t_prefill = pref / prefill_rate_tok_per_sec if prefill_rate_tok_per_sec > 0 else float("inf")
    t_decode = turn.output_tokens / decode_rate_tok_per_sec if decode_rate_tok_per_sec > 0 else float("inf")
    t = t_prefill + t_decode
    if batch <= 0:
        return float("inf")
    return (accel_power_w * t * pue / 3600.0) / batch


def local_energy_wh(
    turn: TurnSpec,
    hw: HwConfig,
    kv: KvPersistence,
    *,
    prefill_rate: float,
    pue: float = 1.0,
    hit_rate_h: float = 1.0,
) -> tuple[float, float, float]:
    """Local Wh under the hit-rate mixture. Returns (Wh, joules, seconds)."""
    delta = float(turn.delta_tokens)
    floor = float(turn.context_floor)
    out = float(turn.output_tokens)
    decode = float(hw.decode_tok_per_sec)

    def seconds(pref_tokens: float) -> float:
        return pref_tokens / prefill_rate + out / decode

    if kv == "persists":
        t = hit_rate_h * seconds(delta) + (1.0 - hit_rate_h) * seconds(floor)
    else:
        t = seconds(floor)
    wh = local_wh(float(hw.sustained_power_w), t, pue)
    return wh, wh * 3600.0, t  # Wh, J, s


def three_way_table(
    *,
    hit_rates: tuple[float, ...] = (0.0, 0.5, 0.8, 0.95, 1.0),
    scaling_models: tuple[str, ...] = SCALING_MODELS,
) -> list[dict[str, Any]]:
    p = load_params()
    turn = representative_turn(p)
    spec = MODEL_SPECS["llama31_8b"]
    elec = float(_v(p["local_hardware"]["common"]["electricity_usd_per_kwh"]))
    life_lo = float(_v(p["local_hardware"]["common"]["assumed_lifetime_months"], "lo"))
    life_hi = float(_v(p["local_hardware"]["common"]["assumed_lifetime_months"], "hi"))
    util_lo = float(_v(p["local_hardware"]["common"]["capex_utilization"], "lo"))
    util_hi = float(_v(p["local_hardware"]["common"]["capex_utilization"], "hi"))
    ttft = float(_v(p["cloud"]["ttft_ms"])) / 1000.0
    cloud_tps = float(_v(p["cloud"]["output_tok_per_sec"]["pure_decode"]))
    rtt = float(_v(p["cloud"]["rtt_ms"])) / 1000.0
    cache_hit = float(_v(p["workload"]["prefix_cache_hit_rate_tool_result"]))
    prices = cloud_prices(p, "openai", "mid")

    # Cloud batch at context_floor on A100 (anchored).
    batch_cloud = batch_max(
        ACCELERATORS["a100_80gb"].memory_bytes, spec, turn.context_floor
    )
    # Cloud prefill rate: use a published H100-class ballpark only as a LO/HI
    # bracket, never a point. We do not have a sourced H100 pp@115K; flag it.
    cloud_prefill_lo = 2000.0   # conservative (slow) — EXTRAPOLATED
    cloud_prefill_hi = 15000.0  # optimistic — EXTRAPOLATED

    rows: list[dict[str, Any]] = []
    for hw in hw_configs(p):
        pp512 = float(hw.prefill_tok_per_sec_pp512)
        for model in scaling_models:
            rate = prefill_rate_at(pp512, model, turn.context_floor, spec)
            for kv in ("persists", "recomputes"):
                for h in hit_rates:
                    if kv == "recomputes" and h != 0.0:
                        continue  # recomputes is the h=0 endpoint
                    if kv == "persists" and h == 0.0:
                        # h=0 under persists == recomputes; keep one row via recomputes
                        continue
                    l_wh, l_j, l_sec = local_energy_wh(
                        turn, hw, kv, prefill_rate=rate, hit_rate_h=h if kv == "persists" else 0.0
                    )
                    # Cloud energy: batch-amortized bracket + output-token formula.
                    c_wh_lo = cloud_energy_batch_amortized(
                        turn, prefill_rate_tok_per_sec=cloud_prefill_hi,
                        decode_rate_tok_per_sec=cloud_tps, batch=batch_cloud,
                        prefill_tokens=turn.delta_tokens,  # cloud also caches
                    )
                    c_wh_hi = cloud_energy_batch_amortized(
                        turn, prefill_rate_tok_per_sec=cloud_prefill_lo,
                        decode_rate_tok_per_sec=cloud_tps, batch=max(batch_cloud, 1.0),
                        prefill_tokens=turn.context_floor,  # miss path
                    )
                    c_wh_batch = (c_wh_lo + c_wh_hi) / 2.0  # midpoint of ESTIMATE only;
                    # reported as bracket below — the midpoint is NOT a finding.
                    c_wh_out = cloud_wh_from_output_tokens(turn.output_tokens)

                    t1 = cost_T1(
                        turn, hw, kv,
                        electricity_usd_per_kwh=elec,
                        lifetime_months_lo=life_lo, lifetime_months_hi=life_hi,
                        utilization_lo=util_lo, utilization_hi=util_hi,
                    )
                    # Override T1 energy with the mixture-aware joules for C_marg
                    # consistency when persists+h.
                    energy_usd = (l_j / 3_600_000.0) * elec
                    # Capex scales with wall time.
                    capex_scale = l_sec / t1.sec if t1.sec > 0 else 1.0
                    fully_lo = energy_usd + t1.components.capex_usd_lo * capex_scale
                    fully_hi = energy_usd + t1.components.capex_usd_hi * capex_scale

                    t2 = cost_T2(
                        turn, "openai", "mid", cache_hit, "below_threshold", prices,
                        ttft_s=ttft, output_tok_per_sec=cloud_tps, rtt_s=rtt,
                    )

                    rows.append({
                        "hw_config": hw.name,
                        "kv_persistence": kv,
                        "prefill_scaling_model": model,
                        "hit_rate_h": h if kv == "persists" else 0.0,
                        "local_wh": l_wh,
                        "local_joules": l_j,
                        "local_sec": l_sec,
                        "cloud_wh_batch_lo": c_wh_lo,
                        "cloud_wh_batch_hi": c_wh_hi,
                        "cloud_wh_batch_midpoint_NOT_A_FINDING": c_wh_batch,
                        "cloud_wh_output_formula": c_wh_out,
                        "cloud_batch_at_context_floor": batch_cloud,
                        "C_energy_ratio_lo": l_wh / c_wh_hi if c_wh_hi > 0 else float("inf"),
                        "C_energy_ratio_hi": l_wh / c_wh_lo if c_wh_lo > 0 else float("inf"),
                        "C_energy_vs_output_formula": l_wh / c_wh_out if c_wh_out > 0 else float("inf"),
                        "local_marginal_usd": energy_usd,
                        "local_fully_loaded_usd_lo": fully_lo,
                        "local_fully_loaded_usd_hi": fully_hi,
                        "cloud_price_usd": t2.usd_low,
                        "C_marg_ratio": energy_usd / t2.usd_low if t2.usd_low > 0 else float("inf"),
                        "C_price_ratio_lo": fully_lo / t2.usd_low if t2.usd_low > 0 else float("inf"),
                        "C_price_ratio_hi": fully_hi / t2.usd_low if t2.usd_low > 0 else float("inf"),
                        "C_marg_label": "marginal_vs_fully_loaded",
                        "comparison_note": (
                            "C_marg is Phase 1's claim (local energy $ vs cloud price $). "
                            "C_price is local fully-loaded $ vs cloud price $. "
                            "C_energy is Wh vs Wh. Never conflate."
                        ),
                        "cloud_prefill_rate_bracket": f"[{cloud_prefill_lo}, {cloud_prefill_hi}] EXTRAPOLATED",
                        "workload_mismatch": (
                            "Anchors are output-token-dominated; ours is prefill-dominated "
                            f"at {turn.context_floor / max(turn.output_tokens, 1):.0f}:1 in:out. "
                            "Local should look WORSE on prefill-heavy work."
                        ),
                    })
    return rows


def decompose_energy_gap(
    *,
    local_wh_batch1: float,
    cloud_wh_batched: float,
    batch: float,
    local_wh_at_short_context: float | None = None,
    idle_fraction: float = 0.15,
    pue_cloud: float = CLOUD_PUE,
    pue_local: float = 1.02,
) -> list[dict[str, Any]]:
    """Attribute local-worse energy gap across named mechanisms.

    Accounting is SEQUENTIAL residual attribution so fractions sum to 1.0:
      1. batching (dominant, anchored)
      2. prefill-at-depth (if short-context baseline available)
      3. idle / fixed power
      4. residual
    Cloud PUE is reported as a SIDE note (how much of cloud Wh is cooling),
    not as a positive contributor to the local-worse gap.
    """
    gap = local_wh_batch1 - cloud_wh_batched
    if gap <= 0:
        return [{
            "term": "no_positive_gap",
            "wh_attributed": gap,
            "fraction_of_gap": float("nan"),
            "uncertainty_note": "Local is not worse on this row; decomposition N/A",
        }]

    # Counterfactual: if local ran at cloud's memory-limited batch, Wh drops by ~B.
    local_at_batch = local_wh_batch1 / max(batch, 1.0)
    batching_raw = local_wh_batch1 - local_at_batch
    # Cap at the gap: batching alone may MORE than close it (local_at_batch < cloud).
    batching = min(batching_raw, gap)
    remaining = gap - batching

    if local_wh_at_short_context is not None and local_wh_at_short_context > 0:
        prefill_raw = max(0.0, local_wh_batch1 - local_wh_at_short_context)
        # Only the portion of prefill that isn't already absorbed by the batching
        # residual attribution can claim remaining gap.
        prefill = min(prefill_raw, remaining)
        remaining -= prefill
        prefill_note = (
            "Difference between context_floor local Wh and short-context local Wh, "
            "capped so sequential attribution sums to the gap."
        )
    else:
        prefill = float("nan")
        prefill_note = (
            "Requires short-context local Wh as baseline. "
            "EXTRAPOLATED until Item H fitted exponent is in hand."
        )

    idle_raw = local_wh_batch1 * idle_fraction
    idle = min(idle_raw, remaining) if remaining > 0 else 0.0
    remaining -= idle

    pue_term = cloud_wh_batched * (1.0 - 1.0 / pue_cloud)

    terms = [
        {
            "term": "batching_amortization",
            "wh_attributed": batching,
            "fraction_of_gap": batching / gap,
            "uncertainty_note": (
                f"Counterfactual: local at cloud batch B={batch:.2f} would draw "
                f"{local_at_batch:.2f} Wh (below cloud {cloud_wh_batched:.2f} Wh). "
                f"Raw batching effect {batching_raw:.2f} Wh; capped at gap {gap:.2f}. "
                "Anchored by A_BATCH_*. Dominant: batching alone closes the gap."
            ),
        },
        {
            "term": "prefill_inefficiency_at_depth",
            "wh_attributed": prefill,
            "fraction_of_gap": (prefill / gap) if prefill == prefill else float("nan"),
            "uncertainty_note": prefill_note,
        },
        {
            "term": "idle_fixed_power",
            "wh_attributed": idle,
            "fraction_of_gap": idle / gap,
            "uncertainty_note": (
                f"Assumed idle_fraction={idle_fraction} of local Wh "
                "(Mac Studio paper notes ~25 W idle vs 140 W inference), "
                "capped at residual after batching. confidence: estimated."
            ),
        },
        {
            "term": "unallocated_residual",
            "wh_attributed": remaining,
            "fraction_of_gap": remaining / gap,
            "uncertainty_note": (
                "Remainder after sequential batching → prefill → idle. "
                "Contains model-size mismatch, precision, and estimator error."
            ),
        },
        {
            "term": "cloud_pue_cooling_SIDE_NOTE",
            "wh_attributed": pue_term,
            "fraction_of_gap": float("nan"),
            "uncertainty_note": (
                f"NOT part of the local-worse gap sum. Cloud Wh already includes "
                f"PUE={pue_cloud}; this is the cooling share of cloud's {cloud_wh_batched:.2f} Wh. "
                "prima.cpp notes the gap narrows once datacentre cooling is counted on both sides."
            ),
        },
        {
            "term": "TOTAL_GAP_local_minus_cloud",
            "wh_attributed": gap,
            "fraction_of_gap": 1.0,
            "uncertainty_note": (
                "Sum target. batching+prefill+idle+residual = gap by construction."
            ),
        },
    ]
    return terms


def mac_studio_anchor_decomposition() -> list[dict[str, Any]]:
    """F3 on the ANCHORED regime (Mac Studio vs 1.6 Wh cloud), licensed by F2."""
    # Use the mid local figure (DeepSeek Q4KM 8.3 Wh) as the central row; report
    # the band in notes. Batch on A100 at a chat-like 8K context (closer to the
    # paper's workload than our 115K floor).
    local = local_wh(MAC_STUDIO_INFERENCE_W, 209.0, MAC_STUDIO_PUE)  # 8.3 Wh row
    cloud = 1.6
    batch_8k = batch_max(
        ACCELERATORS["a100_80gb"].memory_bytes, MODEL_SPECS["llama31_8b"], 8192
    )
    # Short-context counterfactual: scale latency by roughly the prefill share.
    # Paper queries are output-dominated; use idle+decode floor ~ latency * 0.3
    # as a LOOSE short-context proxy — flagged estimated.
    short = local * 0.3
    rows = decompose_energy_gap(
        local_wh_batch1=local,
        cloud_wh_batched=cloud,
        batch=batch_8k,
        local_wh_at_short_context=short,
    )
    for r in rows:
        r["anchor_local_wh"] = local
        r["anchor_cloud_wh"] = cloud
        r["anchor_ratio"] = local / cloud
        r["batch_at_8k"] = batch_8k
        r["regime"] = "ANCHORED"
        r["source"] = "arXiv:2604.18566 Table 11 + A_BATCH_HERALD batch@8K"
    return rows
