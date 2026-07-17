"""Rev C orchestration-arm configuration.

Interventions are flags consumed by both harness adapters. They are deliberately
configuration, not forked harness implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


BASELINE_NAIVE = "baseline_naive"
ORCHESTRATION_OPTIMIZED = "orchestration_optimized"

B_CACHE = "B-CACHE"
B_APPEND = "B-APPEND"
B_LAYOUT = "B-LAYOUT"
B_SHAPE = "B-SHAPE"

KNOWN_INTERVENTIONS = frozenset({B_CACHE, B_APPEND, B_LAYOUT, B_SHAPE})


@dataclass(frozen=True)
class ArmConfig:
    arm: str
    interventions_active: tuple[str, ...] = ()
    causal_class: str = "Class_II"

    def __post_init__(self) -> None:
        if self.arm not in {BASELINE_NAIVE, ORCHESTRATION_OPTIMIZED}:
            raise ValueError(f"unknown rev C arm: {self.arm}")
        unknown = set(self.interventions_active) - KNOWN_INTERVENTIONS
        if unknown:
            raise ValueError(f"unknown rev C interventions: {sorted(unknown)}")
        if self.arm == BASELINE_NAIVE and self.interventions_active:
            raise ValueError("baseline_naive cannot activate Arm B interventions")
        if self.causal_class not in {"Class_I", "Class_II"}:
            raise ValueError(f"unknown causal class: {self.causal_class}")
        if (
            self.causal_class == "Class_I"
            and self.arm == ORCHESTRATION_OPTIMIZED
            and set(self.interventions_active) != {B_CACHE}
        ):
            raise ValueError("Class I Arm B is the byte-identical B-CACHE-only mechanism proof")

    @property
    def use_cache(self) -> bool:
        return B_CACHE in self.interventions_active

    @property
    def append_only(self) -> bool:
        return B_APPEND in self.interventions_active

    @property
    def prefix_stable_layout(self) -> bool:
        return B_LAYOUT in self.interventions_active

    @property
    def cloud_shape(self) -> bool:
        return B_SHAPE in self.interventions_active


def baseline(*, causal_class: str = "Class_II") -> ArmConfig:
    return ArmConfig(BASELINE_NAIVE, (), causal_class=causal_class)


def optimized_full(*, cloud: bool, causal_class: str = "Class_II") -> ArmConfig:
    interventions = [B_APPEND, B_LAYOUT]
    if cloud:
        interventions.append(B_SHAPE)
    else:
        interventions.insert(0, B_CACHE)
    return ArmConfig(
        ORCHESTRATION_OPTIMIZED,
        tuple(interventions),
        causal_class=causal_class,
    )


def cache_only() -> ArmConfig:
    return ArmConfig(ORCHESTRATION_OPTIMIZED, (B_CACHE,), causal_class="Class_I")


def append_layout_only(*, cloud: bool = False) -> ArmConfig:
    interventions = [B_APPEND, B_LAYOUT]
    if cloud:
        interventions.append(B_SHAPE)
    return ArmConfig(
        ORCHESTRATION_OPTIMIZED,
        tuple(interventions),
        causal_class="Class_II",
    )


def normalize_interventions(values: Iterable[str]) -> tuple[str, ...]:
    values = tuple(dict.fromkeys(str(value) for value in values))
    unknown = set(values) - KNOWN_INTERVENTIONS
    if unknown:
        raise ValueError(f"unknown rev C interventions: {sorted(unknown)}")
    return values
