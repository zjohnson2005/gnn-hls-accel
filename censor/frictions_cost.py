"""Cost-side frictions F1–F4. Deterministic; no counterfactual quality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from censor.phase2_constants import F1Params, F2Params, F3Params, F4Params, InferenceParams
from censor.schema import Tier, Trajectory, Turn


@dataclass(frozen=True)
class F1Result:
    seconds: float
    joules: float
    orch_floor_ms: float
    router_cost_ms: float
    router_exceeds_local_crossover: bool
    flag: str | None


def F1_decision_cost(turn: Turn, params: F1Params) -> F1Result:
    """Cost of DECIDING, paid regardless of decision quality.

    = orchestration_floor + router_inference_cost
    """
    if not params.enabled:
        return F1Result(
            seconds=0.0,
            joules=0.0,
            orch_floor_ms=0.0,
            router_cost_ms=0.0,
            router_exceeds_local_crossover=False,
            flag=None,
        )
    if params.router_type not in params.router_cost_ms:
        raise KeyError(
            f"unknown router_type={params.router_type!r}; "
            f"known={sorted(params.router_cost_ms)}"
        )
    orch_ms = float(params.orch_floor_ms.value)
    router_ms = float(params.router_cost_ms[params.router_type].value)
    total_ms = orch_ms + router_ms
    seconds = total_ms / 1000.0
    joules = seconds * float(params.decision_power_w.value)
    # Flag when router alone sits above the local-model crossover band.
    exceeds = router_ms > float(params.local_model_latency_ms_lo.value)
    flag = None
    if exceeds:
        flag = (
            "HEADLINE: router_cost_ms exceeds local-model crossover band "
            f"[{params.local_model_latency_ms_lo.value}, "
            f"{params.local_model_latency_ms_hi.value}] ms "
            f"(router_type={params.router_type}, router_ms={router_ms})"
        )
    _ = turn  # decision cost is turn-indexed but structure-independent here
    return F1Result(
        seconds=seconds,
        joules=joules,
        orch_floor_ms=orch_ms,
        router_cost_ms=router_ms,
        router_exceeds_local_crossover=exceeds,
        flag=flag,
    )


@dataclass(frozen=True)
class F2Result:
    tokens: float
    seconds: float
    usd: float
    switched: bool
    warm_tokens: float
    warm_seconds: float
    warm_usd: float
    delta_tokens: float
    delta_seconds: float
    delta_usd: float


def _prefill_rate_ms(tier: Tier, params: F2Params) -> float:
    if tier == "cloud":
        return float(params.cloud_prefill_ms_per_token.value)
    return float(params.local_prefill_ms_per_token.value)


def _cloud_input_usd(tokens: float, params: F2Params, *, cached: bool) -> float:
    rate = (
        params.cloud_usd_per_1m_cached_input.value
        if cached
        else params.cloud_usd_per_1m_input.value
    )
    return (tokens / 1_000_000.0) * float(rate)


def F2_switching_cost(
    turn: Turn,
    prev_tier: Tier | None,
    new_tier: Tier,
    params: F2Params,
) -> F2Result:
    """KV cannot cross a commercial API boundary → re-prefill on switch.

    MUST depend on ``context_len_before``. Also computes the no-switch (warm)
    continuation so the delta is explicit.

    Cost SHAPE correction (prelim Phase 0, 2026-07-27): this docstring previously
    claimed "growth with turn index is the point". That is wrong at production
    context lengths. TraceLab (arXiv:2606.30560) shows a median step already
    carrying ~119K prefix tokens after a median of 2 steps per request, because
    the system prompt, codebase context, and tool definitions are resident from
    turn one. Switching cost is therefore a STEP FUNCTION at the context floor,
    expensive from turn one; accumulation adds only ~3% at the median trajectory
    (though ~1/3 more at p90). The formula below is unchanged and remains correct
    -- it scales with ``context_len_before`` either way -- but the expected shape
    of that quantity across turns is flat-and-high, not a ramp.
    """
    ctx = int(turn.context_len_before)
    new_tok = int(
        turn.necessary_prefill_tokens
        if turn.necessary_prefill_tokens is not None
        else max(0, ctx)  # cold-path fallback: treat all as new
    )
    # Warm: only new tokens at destination; redundant prefix cached on cloud.
    warm_tokens = float(new_tok)
    warm_seconds = (warm_tokens * _prefill_rate_ms(new_tier, params)) / 1000.0
    if new_tier == "cloud":
        redundant = max(0.0, float(ctx) - warm_tokens)
        warm_usd = _cloud_input_usd(warm_tokens, params, cached=False)
        if params.warm_uses_cached_rate and prev_tier == "cloud":
            warm_usd += _cloud_input_usd(redundant, params, cached=True)
        else:
            # First cloud turn or local→cloud warm is ill-defined; bill new only.
            pass
    else:
        warm_usd = 0.0  # local USD booked in inference energy model

    switched = prev_tier is not None and prev_tier != new_tier
    if not params.enabled:
        return F2Result(
            tokens=0.0,
            seconds=0.0,
            usd=0.0,
            switched=False,
            warm_tokens=warm_tokens,
            warm_seconds=warm_seconds,
            warm_usd=warm_usd,
            delta_tokens=0.0,
            delta_seconds=0.0,
            delta_usd=0.0,
        )

    if not switched:
        return F2Result(
            tokens=warm_tokens,
            seconds=warm_seconds,
            usd=warm_usd,
            switched=False,
            warm_tokens=warm_tokens,
            warm_seconds=warm_seconds,
            warm_usd=warm_usd,
            delta_tokens=0.0,
            delta_seconds=0.0,
            delta_usd=0.0,
        )

    # Switch: full re-prefill of accumulated context at destination tier.
    switch_tokens = float(ctx)
    switch_seconds = (switch_tokens * _prefill_rate_ms(new_tier, params)) / 1000.0
    if new_tier == "cloud":
        switch_usd = _cloud_input_usd(switch_tokens, params, cached=False)
    else:
        switch_usd = 0.0

    return F2Result(
        tokens=switch_tokens,
        seconds=switch_seconds,
        usd=switch_usd,
        switched=True,
        warm_tokens=warm_tokens,
        warm_seconds=warm_seconds,
        warm_usd=warm_usd,
        delta_tokens=switch_tokens - warm_tokens,
        delta_seconds=switch_seconds - warm_seconds,
        delta_usd=switch_usd - warm_usd,
    )


@dataclass(frozen=True)
class F3Result:
    feasible: bool
    throttle_factor: float
    effective_speedup: float
    max_speedup: float
    assumed_concurrency: float


def F3_cloud_capacity(trajectory: Trajectory, params: F3Params) -> F3Result:
    """Cloud rate-limit capacity ceiling.

    Beyond ``max_speedup``, additional parallelism yields no speedup.
    """
    _ = trajectory
    assumed = float(params.assumed_concurrency.value)
    max_s = float(params.max_speedup.value)
    if not params.enabled:
        # Unlimited-capacity fantasy: grant full assumed concurrency.
        return F3Result(
            feasible=True,
            throttle_factor=1.0,
            effective_speedup=max(1.0, assumed),
            max_speedup=max_s,
            assumed_concurrency=assumed,
        )
    effective = min(max(1.0, assumed), max_s)
    # throttle_factor scales a naive assumed speedup down to the ceiling.
    throttle = effective / max(1.0, assumed) if assumed > 0 else 1.0
    feasible = assumed <= max_s + 1e-12
    return F3Result(
        feasible=feasible,
        throttle_factor=throttle,
        effective_speedup=effective,
        max_speedup=max_s,
        assumed_concurrency=assumed,
    )


@dataclass(frozen=True)
class F4Result:
    throughput_factor: float
    measurement_status: str
    label: str


def F4_local_capacity(
    trajectory: Trajectory,
    elapsed_load: float,
    params: F4Params,
) -> F4Result:
    """Local sustained throughput under continuous load.

    Phase 2 stub: capacity_factor default 1.0. ALL outputs marked UNMEASURED.
    """
    _ = trajectory
    _ = elapsed_load
    if not params.enabled:
        return F4Result(
            throughput_factor=1.0,
            measurement_status="UNMEASURED",
            label="F4 UNMEASURED (disabled; factor=1.0)",
        )
    factor = float(params.capacity_factor.value)
    status = params.measurement_status
    return F4Result(
        throughput_factor=factor,
        measurement_status=status,
        label=f"F4 {status}",
    )


@dataclass(frozen=True)
class TierTurnCost:
    seconds: float
    usd: float
    joules: float


def inference_cost(
    turn: Turn,
    tier: Tier,
    params: InferenceParams,
    *,
    f4_throughput_factor: float = 1.0,
) -> TierTurnCost:
    """Per-turn inference cost on a tier (excludes F1/F2)."""
    ctx = float(turn.context_len_before)
    out = float(turn.tokens_out)
    new_tok = float(
        turn.necessary_prefill_tokens
        if turn.necessary_prefill_tokens is not None
        else ctx
    )
    if tier == "cloud":
        if turn.logged_latency_ms is not None and turn.logged_latency_ms > 0:
            seconds = float(turn.logged_latency_ms) / 1000.0
        else:
            seconds = (
                new_tok * float(params.cloud_prefill_ms_per_token.value)
                + out * float(params.cloud_decode_ms_per_token.value)
            ) / 1000.0
        usd_in = (new_tok / 1_000_000.0) * float(params.cloud_usd_per_1m_input.value)
        usd_out = (out / 1_000_000.0) * float(params.cloud_usd_per_1m_output.value)
        if turn.logged_cost_usd is not None and turn.logged_cost_usd > 0:
            usd = float(turn.logged_cost_usd)
        else:
            usd = usd_in + usd_out
        return TierTurnCost(seconds=seconds, usd=usd, joules=0.0)

    # local
    prefill_s = (ctx * float(params.local_prefill_ms_per_token.value)) / 1000.0
    decode_s = (out * float(params.local_decode_ms_per_token.value)) / 1000.0
    seconds = (prefill_s + decode_s) / max(1e-12, f4_throughput_factor)
    joules = seconds * float(params.local_power_w.value)
    kwh = joules / 3_600_000.0
    usd = kwh * float(params.local_usd_per_kwh.value)
    return TierTurnCost(seconds=seconds, usd=usd, joules=joules)


def any_f4_enabled(params_f4: F4Params) -> bool:
    return bool(params_f4.enabled)


def f4_output_label(params_f4: F4Params) -> str:
    """Every F4-dependent output must carry this label."""
    return f"F4 {params_f4.measurement_status}"


def collect_f1_headline_flags(
    turns: Sequence[Turn], params: F1Params
) -> list[str]:
    flags: list[str] = []
    for turn in turns:
        r = F1_decision_cost(turn, params)
        if r.flag and r.flag not in flags:
            flags.append(r.flag)
    return flags
