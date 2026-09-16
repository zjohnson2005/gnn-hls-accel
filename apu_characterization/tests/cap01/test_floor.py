from __future__ import annotations

from apu_characterization.cap01.floor import (
    FloorSample,
    estimate_host_floor,
    qualify_floor,
)


def test_floor_excludes_actual_latency_and_measured_verifier_wall() -> None:
    samples = [
        FloorSample(25_000_000, 20_000_000, 1_000_000),
        FloorSample(26_000_000, 20_000_000, 1_000_000),
        FloorSample(27_000_000, 20_000_000, 1_000_000),
    ]
    assert estimate_host_floor(samples) == 5_000_000


def test_g6_out_of_band_recalibrates_x_without_failure() -> None:
    result = qualify_floor("rust", 2_000_000)
    assert result.passed
    assert not result.in_reference_band
    assert result.recalibrated
    assert result.x_coordinate_ns == 2_000_000


def test_g6_requires_frozen_20ms_anchor() -> None:
    result = qualify_floor("raw_python", 220_000, latency_scale_ms=10)
    assert not result.passed
    assert not result.recalibrated
