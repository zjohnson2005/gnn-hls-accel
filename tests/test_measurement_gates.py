"""PORT-2 measurement gate behaviour (no live host required)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from seam.measurement_gates import (
    UNCOLD_UPTIME_REASON,
    GateResult,
    evaluate_measurement_gates,
    load_platform_measurement_gates,
    run_environment_gate_fields,
)

REPO = Path(__file__).resolve().parents[1]


def test_aipc_c1_floor_and_onset_from_platform_yaml() -> None:
    gates = load_platform_measurement_gates(REPO, "aipc-c1")
    assert gates["pre_run_available_mb_min"] == 7000
    assert gates["onset_s"] == 657
    assert gates["onset_status"] == "measured"
    assert gates["max_uptime_s"] == 7200


def test_evo_t2_unknown_onset_and_derived_floor() -> None:
    gates = load_platform_measurement_gates(REPO, "evo-t2")
    assert gates["pre_run_available_mb_min"] == 24000
    assert gates["onset_s"] is None
    assert gates["onset_status"] == "unknown"
    assert gates["onset_s"] is None


def test_ac_no_battery_passes_with_recorded_reason() -> None:
    ac = GateResult(
        name="ac",
        passed=True,
        reason="no_battery_mains_only_assume_ac",
        detail={"battery_present": False, "ac_ok": True},
    )
    proc = GateResult(
        name="processor_ac",
        passed=True,
        reason="processor_ac_100_100",
        detail={
            "scheme_guid": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
            "scheme_name": "High performance",
            "procthrottlemin_ac": 100,
            "procthrottlemax_ac": 100,
        },
    )
    report = evaluate_measurement_gates(
        REPO,
        platform_id="evo-t2",
        available_mb=30000.0,
        uptime_s=100.0,
        skip_host_probes=True,
        ac_override=ac,
        processor_override=proc,
    )
    assert report.all_passed
    ac_gate = next(g for g in report.gates if g.name == "ac")
    assert ac_gate.passed
    assert "no_battery" in ac_gate.reason
    fields = run_environment_gate_fields(report)
    assert fields["measurement_gates"]["ac"]["reason"] == ac.reason
    assert fields["measurement_gates"]["onset_status"] == "unknown"
    assert fields["measurement_gates"]["onset_s"] is None
    assert fields["measurement_gates"]["onset_seal_note"]


def test_power_gate_is_processor_100_100_not_guid() -> None:
    """Stock High performance GUID must pass when AC throttle is 100/100."""
    ac = GateResult(name="ac", passed=True, reason="ac_ok", detail={})
    proc_ok = GateResult(
        name="processor_ac",
        passed=True,
        reason="processor_ac_100_100",
        detail={
            "scheme_guid": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
            "procthrottlemin_ac": 100,
            "procthrottlemax_ac": 100,
        },
    )
    report = evaluate_measurement_gates(
        REPO,
        platform_id="aipc-c1",
        available_mb=8000.0,
        uptime_s=60.0,
        skip_host_probes=True,
        ac_override=ac,
        processor_override=proc_ok,
    )
    assert report.all_passed
    fields = run_environment_gate_fields(report)
    assert fields["measurement_gates"]["processor_ac"]["scheme_guid"] == (
        "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
    )
    assert fields["measurement_gates"]["processor_ac"]["procthrottlemin_ac"] == 100
    assert fields["measurement_gates"]["processor_ac"]["procthrottlemax_ac"] == 100

    proc_bad = GateResult(
        name="processor_ac",
        passed=False,
        reason="processor_ac_not_100_100",
        detail={
            "scheme_guid": "ec87a53a-19a6-4f4a-980f-ab27cc929b25",
            "procthrottlemin_ac": 5,
            "procthrottlemax_ac": 100,
        },
    )
    report_bad = evaluate_measurement_gates(
        REPO,
        platform_id="aipc-c1",
        available_mb=8000.0,
        uptime_s=60.0,
        skip_host_probes=True,
        ac_override=ac,
        processor_override=proc_bad,
    )
    assert not report_bad.all_passed
    assert any("processor_ac" in r for r in report_bad.refusal_reasons)


def test_platform_yaml_floor_enforced() -> None:
    ac = GateResult(name="ac", passed=True, reason="ac_ok", detail={})
    proc = GateResult(
        name="processor_ac",
        passed=True,
        reason="processor_ac_100_100",
        detail={"procthrottlemin_ac": 100, "procthrottlemax_ac": 100},
    )
    low = evaluate_measurement_gates(
        REPO,
        platform_id="aipc-c1",
        available_mb=6999.0,
        uptime_s=10.0,
        skip_host_probes=True,
        ac_override=ac,
        processor_override=proc,
    )
    assert not low.all_passed
    assert any("available_mb" in r for r in low.refusal_reasons)

    ok = evaluate_measurement_gates(
        REPO,
        platform_id="evo-t2",
        available_mb=24000.0,
        uptime_s=10.0,
        skip_host_probes=True,
        ac_override=ac,
        processor_override=proc,
    )
    assert ok.all_passed
    assert run_environment_gate_fields(ok)["measurement_gates"]["available_mb"]["floor_mb"] == 24000


def test_unknown_onset_recorded_in_run_environment_fields() -> None:
    ac = GateResult(
        name="ac",
        passed=True,
        reason="no_battery_mains_only_assume_ac",
        detail={},
    )
    proc = GateResult(
        name="processor_ac",
        passed=True,
        reason="processor_ac_100_100",
        detail={"procthrottlemin_ac": 100, "procthrottlemax_ac": 100},
    )
    report = evaluate_measurement_gates(
        REPO,
        platform_id="evo-t2",
        available_mb=25000.0,
        uptime_s=30.0,
        skip_host_probes=True,
        ac_override=ac,
        processor_override=proc,
    )
    fields = run_environment_gate_fields(report)["measurement_gates"]
    assert fields["onset_status"] == "unknown"
    assert fields["onset_s"] is None
    assert fields["onset_seal_note"]
    onset_gate = next(g for g in report.gates if g.name == "onset")
    assert onset_gate.passed
    assert onset_gate.reason == "onset_unknown"


def test_evo_t2_declared_mains_only_skips_host_battery_probe() -> None:
    proc = GateResult(
        name="processor_ac",
        passed=True,
        reason="processor_ac_100_100",
        detail={"procthrottlemin_ac": 100, "procthrottlemax_ac": 100},
    )
    report = evaluate_measurement_gates(
        REPO,
        platform_id="evo-t2",
        available_mb=30000.0,
        uptime_s=10.0,
        skip_host_probes=True,
        processor_override=proc,
    )
    assert report.all_passed
    ac_gate = next(g for g in report.gates if g.name == "ac")
    assert ac_gate.passed
    assert ac_gate.detail["battery_present"] is False
    assert ac_gate.detail["ac_ok"] is True


def test_evo_t2_yaml_declares_no_battery() -> None:
    data = yaml.safe_load(
        (REPO / "configs" / "platforms" / "evo-t2.yaml").read_text(encoding="utf-8")
    )
    assert data["power"]["has_battery"] is False


def test_missing_measurement_gates_raises_runtime_error(tmp_path: Path) -> None:
    platform_id = "tmp-missing-gates"
    cfg = tmp_path / "configs" / "platforms"
    cfg.mkdir(parents=True)
    (cfg / f"{platform_id}.yaml").write_text(f"platform_id: {platform_id}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="measurement_gates block missing"):
        load_platform_measurement_gates(tmp_path, platform_id)


def _evo_overrides() -> tuple[GateResult, GateResult]:
    ac = GateResult(
        name="ac",
        passed=True,
        reason="no_battery_platform_mains_only",
        detail={"battery_present": False, "ac_ok": True},
    )
    proc = GateResult(
        name="processor_ac",
        passed=True,
        reason="processor_ac_100_100",
        detail={"procthrottlemin_ac": 100, "procthrottlemax_ac": 100},
    )
    return ac, proc


def test_skip_uptime_records_uncold_and_keeps_memory_floor() -> None:
    ac, proc = _evo_overrides()
    skipped = evaluate_measurement_gates(
        REPO,
        platform_id="evo-t2",
        available_mb=25000.0,
        uptime_s=90000.0,
        skip_host_probes=True,
        skip_uptime=True,
        ac_override=ac,
        processor_override=proc,
    )
    assert skipped.all_passed
    up = next(g for g in skipped.gates if g.name == "uptime")
    assert up.passed
    assert up.reason == "uptime_skipped_noreboot_deviation"
    assert up.detail["deviation"]["kind"] == "UNCOLD_UPTIME"
    assert up.detail["deviation"]["uptime_s"] == 90000.0
    assert up.detail["deviation"]["reason"] == UNCOLD_UPTIME_REASON
    low = evaluate_measurement_gates(
        REPO,
        platform_id="evo-t2",
        available_mb=1000.0,
        uptime_s=90000.0,
        skip_host_probes=True,
        skip_uptime=True,
        ac_override=ac,
        processor_override=proc,
    )
    assert not low.all_passed
    assert any(r.startswith("available_mb:") for r in low.refusal_reasons)
    assert not any(r.startswith("uptime:") for r in low.refusal_reasons)
    warm = evaluate_measurement_gates(
        REPO,
        platform_id="evo-t2",
        available_mb=25000.0,
        uptime_s=90000.0,
        skip_host_probes=True,
        skip_uptime=False,
        ac_override=ac,
        processor_override=proc,
    )
    assert not warm.all_passed
    assert any(r.startswith("uptime:") for r in warm.refusal_reasons)


def test_wrong_type_measurement_gates_raises_type_error(tmp_path: Path) -> None:
    platform_id = "tmp-bad-gates"
    cfg = tmp_path / "configs" / "platforms"
    cfg.mkdir(parents=True)
    (cfg / f"{platform_id}.yaml").write_text(
        f"platform_id: {platform_id}\nmeasurement_gates: not-a-dict\n",
        encoding="utf-8",
    )
    with pytest.raises(TypeError, match="measurement_gates must be a dict"):
        load_platform_measurement_gates(tmp_path, platform_id)
