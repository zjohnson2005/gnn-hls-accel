from __future__ import annotations

from apu_characterization.cap01.contracts import load_protocol
from apu_characterization.cap01.verification_audit import (
    axis6_decision_realism,
    axis7_attempt_abstraction,
    render_verification_audit_markdown,
    run_verification_audit,
)


def test_protocol_defines_g8() -> None:
    protocol = load_protocol()
    g8 = protocol["gates"]["G8"]
    assert g8["name"] == "verifier_cost_parity"
    assert g8["relative_tolerance"] == 0.15
    assert g8["absolute_half_width_ms"] == 0.25
    assert g8["absolute_floor_applies_when_median_below_ms"] == 1.0
    assert g8["minimum_repeats_per_harness_domain"] == 200


def test_g8_absolute_floor_for_sub_millisecond_medians() -> None:
    from apu_characterization.cap01.verification_audit import _within_band

    ok, median, errors = _within_band(
        {"langgraph": 0.11, "raw_python": 0.07},
        relative=0.15,
    )
    assert ok
    assert median == 0.09
    assert errors == []
    # Relative-only would fail; IQR floor absorbs within-harness noise.
    ok, _, errors = _within_band(
        {"langgraph": 1.52, "raw_python": 0.78},
        relative=0.15,
        iqrs_ms={"langgraph": 0.67, "raw_python": 0.21},
    )
    assert ok
    assert errors == []
    ok, _, errors = _within_band(
        {"langgraph": 100.0, "raw_python": 50.0},
        relative=0.15,
    )
    assert not ok
    assert errors


def test_axis6_and_axis7_pass_on_current_loop() -> None:
    assert axis6_decision_realism().verdict == "PASS"
    assert axis7_attempt_abstraction().verdict == "PASS"


def test_skip_expensive_audit_renders_table() -> None:
    aggregate = run_verification_audit(skip_expensive=True)
    by_name = {axis["name"]: axis for axis in aggregate["axes"]}
    assert by_name["agent_decision_realism"]["verdict"] == "PASS"
    assert by_name["attempt_abstraction"]["verdict"] == "PASS"
    # Synthetic debug pools trip the retargeted Axis-2 gate via cross-task
    # identical outputs (the original 99.8%-duplicate bug signature).
    assert by_name["candidate_pool_realism"]["verdict"] == "FAIL"
    assert "cross_task_identical" in by_name["candidate_pool_realism"]["measurement"]
    assert by_name["verifier_cost_parity"]["verdict"] == "FLAGGED"
    markdown = render_verification_audit_markdown(aggregate)
    assert "## Summary table" in markdown
    assert "verifier_cost_parity" in markdown
    assert "G8" in markdown
    assert "shared-verifier" in markdown or "shared verifier" in markdown
    assert "Schedule-ready" in markdown
    assert "0% audited" in markdown
    assert "2048" in markdown
    assert "DEAD-classification" in markdown or "DEAD@128" in markdown
    assert "below measurement resolution" in markdown or "timer-resolution" in markdown
    assert aggregate["summary"]["PASS"] >= 2


def test_protocol_g8_load_bearing_shared_verifier() -> None:
    protocol = load_protocol()
    g8 = protocol["gates"]["G8"]
    assert "shared_verifier" in g8["load_bearing_constraint"]
    assert "dispatch" in g8["what_g8_tests"]


def test_died_ledger_entry5_records_process_wound() -> None:
    import json
    from pathlib import Path

    ledger = json.loads(
        (Path(__file__).resolve().parents[2] / "cap01" / "died_ledger.json").read_text(
            encoding="utf-8"
        )
    )
    entry = next(item for item in ledger["entries"] if item["id"] == 5)
    joined = " ".join(entry["evidence"])
    assert "AFTER-THE-FACT AMENDMENT" in joined
    assert "STANDING PRINCIPLE" in joined
    assert "freeze time" in joined