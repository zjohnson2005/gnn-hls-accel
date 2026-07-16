from __future__ import annotations

from apu_characterization.turntrace_v2.audit import (
    audit_call_record,
    check_conservation,
    headline_eligible,
)
from apu_characterization.turntrace_v2.schema import CallRecord, StepFeatures


def _record(**overrides):
    base = dict(
        trajectory_id="t1",
        turn_index=0,
        harness_id="raw_python",
        deployment_id="L1b",
        step_type_semantic="read_file",
        step_features=StepFeatures(
            is_tool_call=True,
            tool_class="read_only",
            repeat_count=1,
            loop_membership=False,
            fanout_siblings=0,
            trajectory_position=0.0,
        ),
        t_orch_pre_ms=1.0,
        t_orch_post_ms=1.0,
        t_network_ms=0.0,
        network_method="measured",
        t_prefill_ms=10.0,
        prefill_method="direct",
        t_decode_ms=5.0,
        context_tokens_in=100,
        engine_tokens_in=100,
        requested_tokens_in=100,
        token_reconciliation_delta=0,
        tokens_out=10,
        call_shape_ratio=10.0,
        cache_state="disabled",
        prefix_hit_tokens=0,
        prefill_necessary_tokens=20,
        prefill_redundant_tokens=80,
        t_prefill_necessary_ms=2.0,
        t_prefill_redundant_ms=8.0,
        retemplated_tokens=0,
        pred_context_tokens=100,
        pred_cache_state="disabled",
        pred_decode_tokens=10.0,
        pred_t_prefill_ms=10.0,
        pred_t_decode_ms=5.0,
        energy_j=None,
        model_id="m",
        quantization="fp16",
        reasoning_mode="off",
        engine="mock",
        engine_version="0.1",
        wall_clock_start=0.0,
        wall_clock_end=0.017,  # 17 ms wall == 1+10+5+0+1
        audit_flags=[],
    )
    base.update(overrides)
    return CallRecord(**base)


def test_conservation_passes() -> None:
    record = _record()
    assert check_conservation(record) is None


def test_conservation_flags_residual() -> None:
    record = _record(wall_clock_end=1.0)  # 1000 ms wall vs ~17 ms accounted
    assert check_conservation(record) == "residual_exceeds_budget"


def test_audit_profile_drift() -> None:
    record = _record(t_prefill_ms=100.0, wall_clock_end=0.107)

    def f(n: int) -> float:
        return 10.0

    flags = audit_call_record(record, f_prefill=f)
    assert "profile_drift" in flags


def test_headline_eligible_filters() -> None:
    ok = _record()
    bad = _record(trajectory_id="t2", audit_flags=["profile_drift"])
    assert headline_eligible([ok, bad]) == [ok]


def test_attribution_out_of_domain_fires_below_grid_min() -> None:
    """F1: n below fitted floor must flag — the exact silent-extrapolation failure mode."""
    record = _record(
        engine_tokens_in=20,
        context_tokens_in=20,
        requested_tokens_in=20,
        token_reconciliation_delta=0,
        t_prefill_ms=10.0,
        wall_clock_end=0.017,
    )
    flags = audit_call_record(record, f_prefill=lambda n: 10.0, grid_min=39, grid_max=1537)
    assert "attribution_out_of_domain" in flags
    # In-domain twin must not get the flag.
    ok = _record(
        trajectory_id="t_ok",
        engine_tokens_in=48,
        context_tokens_in=48,
        requested_tokens_in=48,
        token_reconciliation_delta=0,
    )
    flags_ok = audit_call_record(ok, f_prefill=lambda n: 10.0, grid_min=39, grid_max=1537)
    assert "attribution_out_of_domain" not in flags_ok
