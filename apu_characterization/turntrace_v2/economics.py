"""Cloud token economics and C-D4 three-way cache accounting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from apu_characterization.turntrace_v2.schema import CallRecord


@dataclass(frozen=True)
class ModelCostBreakdown:
    input_tokens: int
    cached_input_tokens: int
    uncached_input_tokens: int
    output_tokens: int
    input_usd: float
    cached_input_usd: float
    output_usd: float
    total_usd: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


def calculate_model_cost(
    calls: Sequence[CallRecord],
    *,
    usd_per_1m_input: float,
    usd_per_1m_cached_input: float,
    usd_per_1m_output: float,
) -> ModelCostBreakdown:
    input_tokens = sum(record.engine_tokens_in for record in calls)
    cached = sum(
        min(record.engine_tokens_in, max(0, record.provider_cached_tokens))
        for record in calls
    )
    uncached = max(0, input_tokens - cached)
    output = sum(record.tokens_out for record in calls)
    input_usd = uncached / 1_000_000.0 * usd_per_1m_input
    cached_usd = cached / 1_000_000.0 * usd_per_1m_cached_input
    output_usd = output / 1_000_000.0 * usd_per_1m_output
    return ModelCostBreakdown(
        input_tokens=input_tokens,
        cached_input_tokens=cached,
        uncached_input_tokens=uncached,
        output_tokens=output,
        input_usd=input_usd,
        cached_input_usd=cached_usd,
        output_usd=output_usd,
        total_usd=input_usd + cached_usd + output_usd,
    )


def provider_three_way_split(calls: Sequence[CallRecord]) -> dict[str, int | float]:
    structural = sum(record.structurally_redundant_tokens for record in calls)
    recovered = sum(
        min(record.structurally_redundant_tokens, record.provider_cached_tokens)
        for record in calls
    )
    recomputed = sum(record.actually_recomputed_tokens for record in calls)
    necessary = sum(
        max(0, record.engine_tokens_in - record.structurally_redundant_tokens)
        for record in calls
    )
    reconciled = recovered + recomputed
    return {
        "necessary_tokens": necessary,
        "structurally_redundant_tokens": structural,
        "provider_recovered_tokens": recovered,
        "actually_recomputed_tokens": recomputed,
        "reconciliation_delta_tokens": structural - reconciled,
        "provider_recovery_fraction_of_structural": (
            recovered / structural if structural > 0 else 0.0
        ),
    }
