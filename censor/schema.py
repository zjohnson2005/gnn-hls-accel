"""Normalized trajectory schema for the censor engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Sequence

Tier = Literal["local", "cloud"]
OutcomeSource = Literal[
    "swebench_exact",
    "llm_judge",
    "synthetic",
    "unknown",
]


@dataclass(frozen=True)
class SourcedFloat:
    """Numeric constant with a mandatory provenance string."""

    value: float
    source: str

    def __post_init__(self) -> None:
        if not self.source or not str(self.source).strip():
            raise ValueError("SourcedFloat.source must be non-empty")


@dataclass
class Turn:
    turn_index: int
    context_len_before: int
    tokens_out: int
    tool_type: str
    step_type_semantic: str
    logged_latency_ms: float | None
    logged_cost_usd: float | None
    necessary_prefill_tokens: int | None
    # Observed outcomes on the logged tier; local is typically unobserved.
    cloud_success: bool | None
    local_success: bool | None
    local_observed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Trajectory:
    trajectory_id: str
    scaffold: str
    task_id: str
    task_class: str
    logged_tier: Tier
    task_outcome: bool | None
    outcome_source: OutcomeSource
    truncated: bool
    parse_failure: bool
    censored: bool
    turns: list[Turn] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def group_by_scaffold(trajectories: Sequence[Trajectory]) -> dict[str, list[Trajectory]]:
    out: dict[str, list[Trajectory]] = {}
    for tr in trajectories:
        out.setdefault(tr.scaffold, []).append(tr)
    return out
