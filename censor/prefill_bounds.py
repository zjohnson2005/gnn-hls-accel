"""Arm B: bound the pp512 -> 115K prefill extrapolation, then invert it.

Phase 1 used the published pp512 rate directly at 115,440 tokens -- a 225x
extension of the measurement. Attention is O(n^2), so real prefill throughput
DEGRADES with context. The Phase-1 assumption is therefore optimistic for local
and specifically makes ``recomputes`` look better than it is.

Three scaling models are carried as a bracket. Never a midpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from censor.kv_math import MODEL_SPECS, ModelSpec, attention_quadratic_coefficient

ScalingModel = Literal["optimistic_flat", "linear_attention_theoretic", "quadratic_pessimistic"]
SCALING_MODELS: tuple[ScalingModel, ...] = (
    "optimistic_flat",
    "linear_attention_theoretic",
    "quadratic_pessimistic",
)

PP512_ANCHOR_LEN = 512.0

# ---------------------------------------------------------------------------
# B1: the three scaling models
# ---------------------------------------------------------------------------
# Empirical anchor for the pessimistic model. This is the ONLY published
# pp-vs-depth pair we could source, and it is weak: it measures processing 512
# NEW tokens with N tokens already resident, not prefilling N tokens from cold.
# It is used as a pessimistic bound precisely because it is the steeper reading.
EMPIRICAL_ANCHOR = {
    "measurement": "qwen2 7B Q4_K_M, CUDA: pp512 = 7340.20 t/s; pp512 @ d512 = 6425.91 t/s",
    "ratio_at_depth_512": 6425.91 / 7340.20,
    "source": "llama.cpp tools/llama-bench/README.md, 'Different prefilled context' table (commit 12127de).",
    "confidence": "published",
    "caveat": (
        "WEAK ANCHOR. Measures throughput on 512 fresh tokens at depth 512, not "
        "cold prefill of a 512-token prompt, and it is a single hardware/backend "
        "pair. Extrapolating its slope to 115K is exactly the kind of extension "
        "this arm exists to bound, so it is used only as the PESSIMISTIC edge of "
        "the bracket, never as a central estimate."
    ),
}


def _empirical_characteristic_length() -> float:
    """Lc in ratio(L) = 1/(1 + L/Lc), fitted to the single published anchor."""
    r = float(EMPIRICAL_ANCHOR["ratio_at_depth_512"])
    return PP512_ANCHOR_LEN / (1.0 / r - 1.0)


EMPIRICAL_LC = _empirical_characteristic_length()


@dataclass(frozen=True)
class ScalingSpec:
    name: ScalingModel
    description: str
    source: str
    confidence: str


SCALING_SPECS: dict[ScalingModel, ScalingSpec] = {
    "optimistic_flat": ScalingSpec(
        name="optimistic_flat",
        description="Throughput independent of context. R(L) = R_pp512.",
        source=(
            "Not a measurement. This is the IMPLICIT assumption Phase 1 made by "
            "using pp512 at 115K. Carried explicitly so the Phase-1 verdicts can "
            "be located inside the bracket rather than presented as a baseline."
        ),
        confidence="guess",
    ),
    "linear_attention_theoretic": ScalingSpec(
        name="linear_attention_theoretic",
        description=(
            "Prefill time = weight term (2*P*L) + attention term "
            "(4*n_layers*d_model*L^2). Throughput R(L) = R_pp512 * (1+c*512)/(1+c*L) "
            "with c = 2*n_layers*d_model/P_active, derived from the architecture. "
            "Throughput falls linearly in L once the attention term dominates."
        ),
        source=(
            "Standard transformer prefill FLOP accounting; c computed from the "
            "sourced model spec (censor/kv_math.MODEL_SPECS), not fitted. "
            "Assumes compute-bound prefill with no attention-kernel savings."
        ),
        confidence="estimated",
    ),
    "quadratic_pessimistic": ScalingSpec(
        name="quadratic_pessimistic",
        description=(
            "R(L) = R_pp512 * (1+512/Lc)/(1+L/Lc), Lc fitted to the published "
            f"llama.cpp depth anchor (Lc = {EMPIRICAL_LC:.0f} tokens). Degrades far "
            "faster than attention FLOPs alone, capturing bandwidth pressure, KV "
            "re-read, and cache thrash on top of arithmetic."
        ),
        source=EMPIRICAL_ANCHOR["source"] + " " + str(EMPIRICAL_ANCHOR["caveat"]),
        confidence="estimated",
    ),
}


def rate_ratio(
    model: ScalingModel, context_len: float, spec: ModelSpec
) -> float:
    """R(context_len) / R(pp512). Always <= 1 except for the flat model."""
    L = float(context_len)
    if model == "optimistic_flat":
        return 1.0
    if model == "linear_attention_theoretic":
        c = attention_quadratic_coefficient(spec)
        return (1.0 + c * PP512_ANCHOR_LEN) / (1.0 + c * L)
    if model == "quadratic_pessimistic":
        lc = EMPIRICAL_LC
        return (1.0 + PP512_ANCHOR_LEN / lc) / (1.0 + L / lc)
    raise ValueError(f"unknown scaling model: {model!r}")


def prefill_rate_at(
    pp512_rate: float, model: ScalingModel, context_len: float, spec: ModelSpec
) -> float:
    return float(pp512_rate) * rate_ratio(model, context_len, spec)


# ---------------------------------------------------------------------------
# B2: inverse sensitivity
# ---------------------------------------------------------------------------
SECONDS_PER_MONTH = 2.628e6


@dataclass(frozen=True)
class InverseInputs:
    """Everything needed to invert one Phase-1 cell for the prefill rate."""

    prefill_tokens: float
    output_tokens: float
    decode_tok_per_sec: float
    sustained_power_w: float
    electricity_usd_per_kwh: float
    capex_usd: float
    lifetime_months: float
    t2_usd: float


def _energy_usd(sec: float, power_w: float, elec: float) -> float:
    return (sec * power_w / 3_600_000.0) * elec


def marginal_flip_rate(inp: InverseInputs) -> dict[str, float | str | None]:
    """Prefill rate at which T1 energy-only cost equals T2.

    Below this rate the cloud tier wins on marginal cost. Above it, local wins.
    """
    decode_sec = inp.output_tokens / inp.decode_tok_per_sec if inp.decode_tok_per_sec > 0 else float("inf")
    denom = inp.sustained_power_w * inp.electricity_usd_per_kwh
    if denom <= 0:
        return {"flip_rate": None, "status": "degenerate", "decode_sec": decode_sec}
    sec_at_t2 = inp.t2_usd * 3_600_000.0 / denom
    prefill_sec_budget = sec_at_t2 - decode_sec
    if prefill_sec_budget <= 0:
        return {
            "flip_rate": None,
            "status": "decode_alone_exceeds_T2",
            "decode_sec": decode_sec,
            "sec_at_t2": sec_at_t2,
        }
    if inp.prefill_tokens <= 0:
        return {"flip_rate": 0.0, "status": "no_prefill_work", "decode_sec": decode_sec}
    return {
        "flip_rate": inp.prefill_tokens / prefill_sec_budget,
        "status": "threshold",
        "decode_sec": decode_sec,
        "sec_at_t2": sec_at_t2,
    }


def u_star_at_rate(inp: InverseInputs, prefill_rate: float) -> dict[str, float | str | None]:
    """Utilization required for amortized T1 to beat T2 at a given prefill rate."""
    if prefill_rate <= 0:
        return {"u_star": None, "status": "degenerate", "sec": None, "marginal_usd": None}
    decode_sec = inp.output_tokens / inp.decode_tok_per_sec if inp.decode_tok_per_sec > 0 else float("inf")
    sec = inp.prefill_tokens / prefill_rate + decode_sec
    marginal = _energy_usd(sec, inp.sustained_power_w, inp.electricity_usd_per_kwh)
    headroom = inp.t2_usd - marginal
    if headroom <= 0:
        return {
            "u_star": None,
            "status": "never",
            "sec": sec,
            "marginal_usd": marginal,
            "headroom_usd": headroom,
        }
    u = (inp.capex_usd * sec) / (headroom * inp.lifetime_months * SECONDS_PER_MONTH)
    status = "requires_impossible_utilization" if u > 1.0 else "threshold"
    return {
        "u_star": u,
        "status": status,
        "sec": sec,
        "marginal_usd": marginal,
        "headroom_usd": headroom,
    }


def rate_for_target_u_star(
    inp: InverseInputs, target_u: float, *, lo: float = 1e-4, hi: float = 1e7
) -> float | None:
    """Prefill rate at which u* equals ``target_u``. Monotone: slower prefill
    raises u*, so bisect on rate."""

    def f(r: float) -> float | None:
        res = u_star_at_rate(inp, r)
        u = res["u_star"]
        if u is None:
            return None  # u* effectively infinite (local never wins)
        return float(u) - target_u

    f_hi = f(hi)
    if f_hi is None or f_hi > 0:
        return None  # even infinitely fast prefill cannot reach target_u
    f_lo = f(lo)
    if f_lo is not None and f_lo < 0:
        return None  # even absurdly slow prefill stays under target_u
    for _ in range(200):
        mid = (lo * hi) ** 0.5  # geometric bisection: rates span orders of magnitude
        f_mid = f(mid)
        if f_mid is None or f_mid > 0:
            lo = mid
        else:
            hi = mid
        if hi / lo < 1.0 + 1e-9:
            break
    return (lo * hi) ** 0.5


# ---------------------------------------------------------------------------
# B3: which measurement discriminates the three models
# ---------------------------------------------------------------------------
def model_separation(context_len: float, spec: ModelSpec) -> dict[str, float]:
    """Pairwise ratio spread between scaling models at a context length.

    The most informative measurement point is where the models are far apart
    but all still predict a measurable (non-zero) rate.
    """
    r = {m: rate_ratio(m, context_len, spec) for m in SCALING_MODELS}
    return {
        "context_len": context_len,
        "ratio_flat": r["optimistic_flat"],
        "ratio_attention": r["linear_attention_theoretic"],
        "ratio_pessimistic": r["quadratic_pessimistic"],
        "flat_over_attention": r["optimistic_flat"] / r["linear_attention_theoretic"],
        "attention_over_pessimistic": r["linear_attention_theoretic"] / r["quadratic_pessimistic"],
        "flat_over_pessimistic": r["optimistic_flat"] / r["quadratic_pessimistic"],
    }


def recommended_measurement_grid(
    spec: ModelSpec | None = None,
    *,
    candidates: tuple[float, ...] = (512, 2048, 4096, 8192, 16384, 32768, 65536, 115440),
    min_separation: float = 2.0,
) -> dict[str, object]:
    """Pick the depths where a single llama-bench sweep separates the models.

    A depth is 'discriminating' for a pair when the two models predict rates
    differing by at least ``min_separation``x -- comfortably above run-to-run
    noise on llama-bench (which reports sub-1% stddev on stable backends).
    """
    s = spec or MODEL_SPECS["llama31_8b"]
    rows = [model_separation(L, s) for L in candidates]
    first_flat_vs_attn = next(
        (r["context_len"] for r in rows if r["flat_over_attention"] >= min_separation), None
    )
    first_attn_vs_pess = next(
        (r["context_len"] for r in rows if r["attention_over_pessimistic"] >= min_separation), None
    )
    return {
        "rows": rows,
        "first_depth_separating_flat_from_attention": first_flat_vs_attn,
        "first_depth_separating_attention_from_pessimistic": first_attn_vs_pess,
        "min_separation": min_separation,
    }
