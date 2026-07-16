from __future__ import annotations

from apu_characterization.turntrace_v2.calibration import (
    NetworkBaseline,
    synthesize_decode_profile,
    synthesize_prefill_sweep,
)


def test_synthetic_prefill_passes_r2_gate() -> None:
    profile = synthesize_prefill_sweep(seed=11)
    assert profile.acceptance_passed()
    assert profile.quadratic is not None
    assert profile.quadratic.r2_held_out >= 0.99
    # Predict roughly linear+quadratic growth
    assert profile.predict_ms(1024) < profile.predict_ms(16384)


def test_decode_profile_slows_with_kv_depth() -> None:
    profile = synthesize_decode_profile(seed=2)
    assert profile.tokens_per_sec_at(0) > profile.tokens_per_sec_at(65536)


def test_network_baseline_summary() -> None:
    net = NetworkBaseline(endpoint_id="C1")
    for slot in ("a", "b", "c"):
        for i in range(40):
            net.add_probe(10.0 + i * 0.01, tod_slot=slot)
    summary = net.summary()
    assert summary["n"] >= 100
    assert summary["meets_tod_slots"] is True
    assert summary["median_ms"] > 0
