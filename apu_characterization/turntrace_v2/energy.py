"""Energy sampling hooks (nullable; designed-in from day one)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Sequence


PowerSampleFn = Callable[[], tuple[float, float]]
# Returns (gpu_watts, cpu_package_watts)


@dataclass
class PowerSample:
    t_mono: float
    gpu_w: float
    cpu_w: float


@dataclass
class EnergySampler:
    """Sidecar-style sampler writing timestamped streams for post-hoc merge."""

    sample_fn: PowerSampleFn
    hz: float = 10.0
    samples: list[PowerSample] = field(default_factory=list)
    idle_baseline_w: float | None = None

    def sample_once(self) -> PowerSample:
        gpu_w, cpu_w = self.sample_fn()
        sample = PowerSample(t_mono=time.monotonic(), gpu_w=float(gpu_w), cpu_w=float(cpu_w))
        self.samples.append(sample)
        return sample

    def integrate_joules(
        self,
        t_start: float,
        t_end: float,
        *,
        baseline_subtract: bool = True,
    ) -> dict[str, float | None]:
        window = [s for s in self.samples if t_start <= s.t_mono <= t_end]
        if len(window) < 2:
            # Too noisy / sparse for per-phase — report null phase split.
            return {
                "energy_j_gross": None,
                "energy_j_baseline_subtracted": None,
                "phase_attribution": None,
                "note": "insufficient_samples_fallback_per_call_only",
            }
        joules = 0.0
        for a, b in zip(window, window[1:]):
            dt = max(0.0, b.t_mono - a.t_mono)
            joules += dt * (a.gpu_w + a.cpu_w)
        baseline = 0.0
        if baseline_subtract and self.idle_baseline_w is not None:
            baseline = self.idle_baseline_w * max(0.0, t_end - t_start)
        return {
            "energy_j_gross": joules,
            "energy_j_baseline_subtracted": max(0.0, joules - baseline),
            "phase_attribution": "timestamp_aligned_if_windows_provided",
            "note": None,
        }


def attribute_energy_phases(
    *,
    total_j: float,
    t_orch_ms: float,
    t_prefill_ms: float,
    t_decode_ms: float,
    t_prefill_redundant_ms: float,
) -> dict[str, float]:
    """Proportional fallback when 10 Hz is too coarse for hard phase boundaries.

    Callers must log that this is proportional, not silent interpolation of missing
    power samples.
    """
    weights = {
        "E_orch": t_orch_ms,
        "E_prefill": t_prefill_ms,
        "E_decode": t_decode_ms,
    }
    total_w = sum(weights.values()) or 1.0
    out: dict[str, float] = {k: total_j * (v / total_w) for k, v in weights.items()}
    prefill = out["E_prefill"]
    if t_prefill_ms > 0:
        out["E_prefill_redundant"] = prefill * (t_prefill_redundant_ms / t_prefill_ms)
    else:
        out["E_prefill_redundant"] = 0.0
    return out


def null_energy_sampler() -> EnergySampler:
    return EnergySampler(sample_fn=lambda: (0.0, 0.0), hz=10.0)
