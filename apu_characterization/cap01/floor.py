"""Host floor measurement and the CAP-01 G6 reference-band check."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .contracts import load_protocol

NANOSECONDS_PER_MILLISECOND = 1_000_000


@dataclass(frozen=True)
class FloorSample:
    """One serial turn measured at the frozen 20 ms latency anchor."""

    turn_wall_ns: int
    latency_draw_ns: int
    verifier_wall_ns: int = 0
    strict_harness_cpu_ns: int = 0

    @property
    def floor_ns(self) -> int:
        if self.strict_harness_cpu_ns > 0:
            return self.strict_harness_cpu_ns
        return self.turn_wall_ns - self.latency_draw_ns - self.verifier_wall_ns


@dataclass(frozen=True)
class FloorQualification:
    harness: str
    measured_floor_ns: int
    reference_band_ns: tuple[int, int]
    in_reference_band: bool
    x_coordinate_ns: int
    recalibrated: bool
    violations: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.violations

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass": self.passed,
            "harness": self.harness,
            "measured_floor_ns": self.measured_floor_ns,
            "reference_band_ns": list(self.reference_band_ns),
            "in_reference_band": self.in_reference_band,
            "x_coordinate_ns": self.x_coordinate_ns,
            "recalibrated": self.recalibrated,
            "violations": list(self.violations),
        }


def estimate_host_floor(samples: Sequence[FloorSample | Mapping[str, Any]]) -> int:
    """Return the median non-latency, non-verifier wall time in nanoseconds."""
    values: list[int] = []
    for sample in samples:
        normalized = _sample(sample)
        if normalized.turn_wall_ns < 0:
            raise ValueError("turn wall time cannot be negative")
        if normalized.latency_draw_ns < 0 or normalized.verifier_wall_ns < 0:
            raise ValueError("latency and verifier wall time cannot be negative")
        if normalized.floor_ns < 0:
            raise ValueError("turn wall time is smaller than excluded wall terms")
        values.append(normalized.floor_ns)
    if not values:
        raise ValueError("at least one floor sample is required")
    return int(statistics.median(values))


def qualify_floor(
    harness: str,
    measured_floor_ns: int,
    *,
    latency_scale_ms: int = 20,
    protocol: Mapping[str, Any] | None = None,
) -> FloorQualification:
    """Apply G6 without treating a reference-band miss as a gate failure."""
    cfg = dict(protocol or load_protocol())["floor_anchor"]
    violations: list[str] = []
    bands = cfg["promoted_reference_bands_ms"]
    if harness not in bands:
        raise ValueError(f"no CAP-01 floor reference band for {harness!r}")
    low_ms, high_ms = (float(value) for value in bands[harness])
    band_ns = (
        int(round(low_ms * NANOSECONDS_PER_MILLISECOND)),
        int(round(high_ms * NANOSECONDS_PER_MILLISECOND)),
    )
    if measured_floor_ns < 0:
        violations.append("measured harness floor is negative")
    if latency_scale_ms != int(cfg["latency_scale_ms"]):
        violations.append(
            f"floor measured at {latency_scale_ms} ms, expected "
            f"{cfg['latency_scale_ms']} ms anchor"
        )
    finite = math.isfinite(float(measured_floor_ns))
    if not finite:
        violations.append("measured harness floor is not finite")
    in_band = finite and band_ns[0] <= measured_floor_ns <= band_ns[1]
    return FloorQualification(
        harness=harness,
        measured_floor_ns=int(measured_floor_ns),
        reference_band_ns=band_ns,
        in_reference_band=in_band,
        x_coordinate_ns=int(measured_floor_ns),
        recalibrated=not in_band and not violations,
        violations=tuple(violations),
    )


def measure_and_qualify_floor(
    harness: str,
    samples: Sequence[FloorSample | Mapping[str, Any]],
    *,
    latency_scale_ms: int = 20,
    protocol: Mapping[str, Any] | None = None,
) -> FloorQualification:
    return qualify_floor(
        harness,
        estimate_host_floor(samples),
        latency_scale_ms=latency_scale_ms,
        protocol=protocol,
    )


def _sample(value: FloorSample | Mapping[str, Any]) -> FloorSample:
    if isinstance(value, FloorSample):
        return value
    return FloorSample(
        turn_wall_ns=int(
            value.get("turn_wall_ns", value.get("elapsed_ns", value.get("wall_ns", 0)))
        ),
        latency_draw_ns=int(
            value.get("latency_draw_ns", value.get("latency_ns", 0))
        ),
        verifier_wall_ns=int(value.get("verifier_wall_ns", 0)),
        strict_harness_cpu_ns=int(value.get("strict_harness_cpu_ns", 0)),
    )
