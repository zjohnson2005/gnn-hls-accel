"""Per-turn cost model for the three-tier preliminary study (T0 / T1 / T2).

Phase 1 only. No policy search, trajectory sim, DES, quality, or thermal model.

``local_kv_persistence`` is an OUTER LOOP parameter of every consumer of these
functions: never collapsed, never averaged, never an inner column.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

KvPersistence = Literal["persists", "recomputes"]
LongctxBound = Literal["below_threshold", "above_threshold"]
InterpolationFamily = Literal["log_normal", "empirical_step"]

SECONDS_PER_MONTH = 2.628e6  # study_params.yaml amortization formula


@dataclass(frozen=True)
class TurnSpec:
    """Token shape of one agent turn at production context length."""

    prefix_tokens: float
    append_tokens: float
    output_tokens: float
    context_floor: float
    delta_tokens: float

    @property
    def total_input_tokens(self) -> float:
        return float(self.prefix_tokens) + float(self.append_tokens)


@dataclass(frozen=True)
class T2Components:
    cache_read_usd: float
    uncached_prefill_usd: float
    output_usd: float

    @property
    def residency_fraction(self) -> float:
        total = self.cache_read_usd + self.uncached_prefill_usd + self.output_usd
        if total <= 0:
            return float("nan")
        return self.cache_read_usd / total

    @property
    def compute_fraction(self) -> float:
        total = self.cache_read_usd + self.uncached_prefill_usd + self.output_usd
        if total <= 0:
            return float("nan")
        return (self.uncached_prefill_usd + self.output_usd) / total


@dataclass(frozen=True)
class T2Result:
    usd_low: float
    usd_high: float
    sec: float
    joules: float
    naive_usd: float
    components: T2Components
    longctx_bound: LongctxBound
    cache_hit_rate: float
    provider: str
    model_tier: str
    scoping_bias_note: str = (
        "SCOPING BIAS: per-request scoping uses tool-result hit rate (~97.5%), "
        "the assumption most favorable to cloud."
    )


@dataclass(frozen=True)
class T1Components:
    energy_usd: float
    capex_usd_lo: float
    capex_usd_hi: float
    prefill_tokens: float
    prefill_sec: float
    decode_sec: float
    prefill_rate_tok_per_sec: float
    decode_rate_tok_per_sec: float


@dataclass(frozen=True)
class T1Result:
    usd_marginal: float
    usd_amortized_lo: float
    usd_amortized_hi: float
    sec: float
    joules: float
    components: T1Components
    kv_persistence: KvPersistence
    hw_config: str
    model_size: str
    prefill_interpolated: bool
    prefill_interpolation_note: str
    amortization_uncertainty_note: str = (
        "AMORTIZATION UNCERTAINTY: amortized local cost is an interval over "
        "capex_utilization x lifetime (~75x), never a point estimate."
    )


@dataclass(frozen=True)
class T0Result:
    usd: float
    sec: float
    joules: float
    applicable: bool
    applicability_rate: float


@dataclass(frozen=True)
class CloudPrices:
    input_uncached_per_mtok: float
    input_cached_per_mtok: float
    output_per_mtok: float
    # Optional long-context column (OpenAI). None => no surcharge.
    long_input_uncached_per_mtok: float | None = None
    long_input_cached_per_mtok: float | None = None
    long_output_per_mtok: float | None = None


@dataclass(frozen=True)
class HwConfig:
    name: str
    decode_tok_per_sec: float
    prefill_tok_per_sec_pp512: float | None
    sustained_power_w: float
    capex_usd: float
    # Whole-system capex already includes host for Strix/Apple; for discrete GPU
    # this should be GPU + host_platform_capex.
    model_size: str


def _prices_for_bound(prices: CloudPrices, longctx_bound: LongctxBound) -> tuple[float, float, float]:
    if longctx_bound == "above_threshold" and prices.long_input_uncached_per_mtok is not None:
        return (
            float(prices.long_input_uncached_per_mtok),
            float(prices.long_input_cached_per_mtok),
            float(prices.long_output_per_mtok),
        )
    return (
        float(prices.input_uncached_per_mtok),
        float(prices.input_cached_per_mtok),
        float(prices.output_per_mtok),
    )


def cost_T2(
    turn: TurnSpec,
    provider: str,
    model_tier: str,
    cache_hit_rate: float,
    longctx_bound: LongctxBound,
    prices: CloudPrices,
    *,
    ttft_s: float,
    output_tok_per_sec: float,
    rtt_s: float = 0.0,
) -> T2Result:
    """Metered cloud turn cost with cache-aware and naive (all-uncached) USD.

    ``longctx_bound`` is REQUIRED (no default). At ~115K the OpenAI threshold
    position is unsourced and swings T2 ~2x. Callers must emit BOTH bounds;
    never a midpoint.
    """
    if not 0.0 <= cache_hit_rate <= 1.0:
        raise ValueError(f"cache_hit_rate out of range: {cache_hit_rate}")
    if longctx_bound not in ("below_threshold", "above_threshold"):
        raise ValueError(f"longctx_bound must be explicit, got {longctx_bound!r}")

    total_in = turn.total_input_tokens
    cached_in = total_in * cache_hit_rate
    uncached_in = total_in * (1.0 - cache_hit_rate)
    out = float(turn.output_tokens)

    p_in, p_cached, p_out = _prices_for_bound(prices, longctx_bound)

    cache_read_usd = (cached_in / 1_000_000.0) * p_cached
    uncached_prefill_usd = (uncached_in / 1_000_000.0) * p_in
    output_usd = (out / 1_000_000.0) * p_out
    usd = cache_read_usd + uncached_prefill_usd + output_usd

    naive_usd = (total_in / 1_000_000.0) * p_in + (out / 1_000_000.0) * p_out

    # For providers without a long-context surcharge, both bounds are identical.
    # Still return them as usd_low == usd_high so the table schema is uniform.
    # When OpenAI longctx is above, this call only produces the above_threshold
    # number; the caller pairs both calls. usd_low/usd_high here equal `usd`
    # for a single bound; the runner widens across bounds when reporting.
    sec = float(ttft_s) + (out / float(output_tok_per_sec) if output_tok_per_sec > 0 else float("inf"))
    sec += float(rtt_s)

    return T2Result(
        usd_low=usd,
        usd_high=usd,
        sec=sec,
        joules=0.0,
        naive_usd=naive_usd,
        components=T2Components(
            cache_read_usd=cache_read_usd,
            uncached_prefill_usd=uncached_prefill_usd,
            output_usd=output_usd,
        ),
        longctx_bound=longctx_bound,
        cache_hit_rate=cache_hit_rate,
        provider=provider,
        model_tier=model_tier,
    )


def cost_T1(
    turn: TurnSpec,
    hw: HwConfig,
    kv_persistence: KvPersistence,
    *,
    electricity_usd_per_kwh: float,
    lifetime_months_lo: float,
    lifetime_months_hi: float,
    utilization_lo: float,
    utilization_hi: float,
) -> T1Result:
    """Local turn cost: marginal (energy) and amortized (energy + capex interval).

    Prefill tokens:
      persists   -> delta_tokens
      recomputes -> context_floor

    Prefill rate at 115K is UNSOURCED; this function uses the published pp512
    rate and labels the result INTERPOLATED.
    """
    if kv_persistence not in ("persists", "recomputes"):
        raise ValueError(f"kv_persistence must be explicit, got {kv_persistence!r}")
    if hw.prefill_tok_per_sec_pp512 is None or hw.prefill_tok_per_sec_pp512 <= 0:
        raise ValueError(
            f"hw_config={hw.name!r} model_size={hw.model_size!r}: "
            "prefill_tok_per_sec_pp512 is missing; cannot INTERPOLATE"
        )

    if kv_persistence == "persists":
        prefill_tokens = float(turn.delta_tokens)
    else:
        prefill_tokens = float(turn.context_floor)

    prefill_rate = float(hw.prefill_tok_per_sec_pp512)
    decode_rate = float(hw.decode_tok_per_sec)
    prefill_sec = prefill_tokens / prefill_rate
    decode_sec = float(turn.output_tokens) / decode_rate if decode_rate > 0 else float("inf")
    sec = prefill_sec + decode_sec
    joules = sec * float(hw.sustained_power_w)

    energy_usd = (joules / 3_600_000.0) * float(electricity_usd_per_kwh)

    # Capex per inference-second = capex / (lifetime * SPM * U).
    # Lowest amortized cost: longest life, highest utilization.
    # Highest amortized cost: shortest life, lowest utilization.
    def capex_usd(lifetime: float, util: float) -> float:
        return (float(hw.capex_usd) * sec) / (lifetime * SECONDS_PER_MONTH * util)

    capex_lo = capex_usd(lifetime_months_hi, utilization_hi)
    capex_hi = capex_usd(lifetime_months_lo, utilization_lo)

    return T1Result(
        usd_marginal=energy_usd,
        usd_amortized_lo=energy_usd + capex_lo,
        usd_amortized_hi=energy_usd + capex_hi,
        sec=sec,
        joules=joules,
        components=T1Components(
            energy_usd=energy_usd,
            capex_usd_lo=capex_lo,
            capex_usd_hi=capex_hi,
            prefill_tokens=prefill_tokens,
            prefill_sec=prefill_sec,
            decode_sec=decode_sec,
            prefill_rate_tok_per_sec=prefill_rate,
            decode_rate_tok_per_sec=decode_rate,
        ),
        kv_persistence=kv_persistence,
        hw_config=hw.name,
        model_size=hw.model_size,
        prefill_interpolated=True,
        prefill_interpolation_note=(
            "INTERPOLATED: prefill_tok_per_sec_at_115k is unsourced; "
            f"using published pp512 rate ({prefill_rate:.1f} tok/s). "
            "Optimistic for local — real 115K prefill is slower."
        ),
    )


def cost_T0(turn: TurnSpec, applicability_rate: float, *, orch_floor_s: float = 0.0) -> T0Result:
    """Deterministic / cached tier. Applicability is a swept parameter."""
    _ = turn
    if not 0.0 <= applicability_rate <= 1.0:
        raise ValueError(f"applicability_rate out of range: {applicability_rate}")
    # Stochastic applicability is resolved outside; here we report the rate and
    # mark applicable as a structural flag for the rate (rate > 0).
    return T0Result(
        usd=0.0,
        sec=float(orch_floor_s),
        joules=0.0,
        applicable=applicability_rate > 0.0,
        applicability_rate=float(applicability_rate),
    )


def utilization_threshold_to_beat_t2(
    t1: T1Result,
    t2_usd: float,
    *,
    capex_usd: float,
    lifetime_months: float,
) -> dict[str, float | str | None]:
    """Solve for the utilization U required for T1_amortized to beat T2.

    U >= (capex * sec) / ((T2 - usd_marginal) * lifetime * SPM)

    Returns a structured result; never invents a point estimate for U when
    local energy alone already loses.
    """
    headroom = float(t2_usd) - float(t1.usd_marginal)
    if headroom <= 0:
        return {
            "u_star": None,
            "status": "never",
            "reason": "usd_marginal alone exceeds T2; amortization cannot help",
            "headroom_usd": headroom,
            "lifetime_months": lifetime_months,
        }
    u_star = (float(capex_usd) * float(t1.sec)) / (
        headroom * float(lifetime_months) * SECONDS_PER_MONTH
    )
    if u_star > 1.0:
        status = "requires_impossible_utilization"
    elif u_star <= 0.0:
        status = "always"
    else:
        status = "threshold"
    return {
        "u_star": u_star,
        "status": status,
        "reason": None,
        "headroom_usd": headroom,
        "lifetime_months": lifetime_months,
    }


def pair_t2_bounds(below: T2Result, above: T2Result) -> T2Result:
    """Combine the two required longctx calls into one interval result."""
    if below.provider != above.provider or below.model_tier != above.model_tier:
        raise ValueError("pair_t2_bounds requires matching provider/model_tier")
    usd_lo = min(below.usd_low, above.usd_low)
    usd_hi = max(below.usd_high, above.usd_high)
    # Prefer the bound with larger usd for naive (conservative overstatement
    # of the naive figure uses the same prices as the matching bound). Report
    # naive as the below_threshold naive; overstatement ratio uses matching prices.
    return T2Result(
        usd_low=usd_lo,
        usd_high=usd_hi,
        sec=below.sec,
        joules=0.0,
        naive_usd=below.naive_usd,  # reported separately per-bound in tables
        components=below.components,
        longctx_bound="below_threshold",  # paired; interval is in usd_low/high
        cache_hit_rate=below.cache_hit_rate,
        provider=below.provider,
        model_tier=below.model_tier,
    )
