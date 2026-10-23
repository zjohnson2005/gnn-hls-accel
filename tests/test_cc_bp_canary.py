"""CC fix 2026-10-23e (Task BP): one-step CC series and one-point CC cells arm the canary.

Hardware-free. The canary cell, power and WorkloadsSessionHost snapshots and the measured
child are stubbed; the guard's gate logic and the runners' seal path are real.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import seam.run_environment as run_env  # noqa: E402
import seam.tools.delta_n as delta_n  # noqa: E402
import tools.boot4_session as b4  # noqa: E402
import tools.ttft_slo_canary as tsc  # noqa: E402

C = tsc.CALIBRATION_C
SPEC = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"


def _stub(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    holds: list[bool] | None = None,
    cells: list[str] | None = None,
) -> list[str]:
    """Stub everything below the runner. ``holds`` per measured child, ``cells`` per canary."""
    events: list[str] = []
    calls = {"child": 0}

    def stub_cell(self: Any) -> dict[str, Any]:
        idx = len(self.canaries)
        events.append("canary")
        cls = (cells or [])[idx] if cells and idx < len(cells) else "OK"
        return {
            "is_canary": True,
            "canary_index": idx,
            "classification": cls,
            "turn1_prefill_s": 1.0 if cls == "OK" else None,
            "turn2_prefill_s": 0.5 if cls == "OK" else None,
            "execute_ok": cls == "OK",
        }

    def stub_measured(**kw: Any) -> dict[str, Any]:
        i = calls["child"]
        calls["child"] += 1
        events.append("probe")
        ok = (holds or [])[i] if holds and i < len(holds) else True
        gen = {"turn1": {"prefill_s": 1.0}, "turn2": [{"prefill_s": 0.4}]} if ok else {}
        return {
            "result": {
                "outcome": "pass" if ok else "fail",
                "failure_mode": None if ok else "CL_OUT_OF_RESOURCES",
                "parent_wall_s": 30.0,
                "child": {"generation": gen, "loads": []},
            }
        }

    monkeypatch.setattr(tsc.TtftSloCanaryGuard, "_run_cell", stub_cell)
    monkeypatch.setattr(tsc, "capture_canary_power_snapshot", lambda: {"on_ac": True})
    monkeypatch.setattr(tsc, "assert_no_ac_transition", lambda **_kw: {"ok": True})
    monkeypatch.setattr(run_env, "snapshot_workloads_session_host", lambda: {})
    monkeypatch.setattr(delta_n, "measured_repeat", stub_measured)
    monkeypatch.setattr(b4, "require_gates", lambda **_kw: {"stub": True})
    monkeypatch.setattr(
        b4,
        "load_harness",
        lambda _spec: {
            "cfg": {},
            "model_spec": SPEC,
            "model_name": "stub",
            "model_dir": str(tmp_path / "ir"),
            "p_cpus": [0],
        },
    )
    monkeypatch.setattr(b4, "_child_spec", lambda *_a, **_kw: {})
    monkeypatch.setattr(
        b4,
        "_point_failure",
        lambda child: {"failure_kind": None if child.get("outcome") == "pass" else "OOM"},
    )
    monkeypatch.delenv("SEAM_REHEARSAL", raising=False)
    monkeypatch.delenv("SEAM_CELL_STATUS_PATH", raising=False)
    return events


def _summary(out: Path) -> dict[str, Any]:
    return json.loads((out / "summary.json").read_text(encoding="utf-8"))


def _sealed(out: Path) -> Path:
    sid = _summary(out)["session_id"]
    return out.parent / f"sealed_{sid}"


# ---------------------------------------------------------------- series


def test_grow_one_step_arms_before_the_step_and_seals(monkeypatch, tmp_path) -> None:
    events = _stub(monkeypatch, tmp_path)
    monkeypatch.setattr(b4, "CC_OVERRIDE", {"cell": "CC-GROW", "grow": {"step": 1024}})
    out = tmp_path / "s"
    rc = b4.run_cc_series(arm="gpu_only_u4", model_spec=SPEC, session_id="g1", out_dir=out)
    assert rc == 0
    # warm-up + C calibration canaries, the step, then the after-series armed check.
    assert events == ["canary"] * (1 + C) + ["probe", "canary"]
    s = _summary(out)
    assert s["status"] == "complete" and s["canary_finalize"]["armed"] is True
    assert s["canary"]["schedule"] == "arm_before_probes"
    assert s["canary"]["planned_probe_count"] == 1
    assert s["canary"]["budget_preflight"]["budget_rule"].startswith("calibrated_before")
    assert s["canaries"][-1]["gate_armed"] is True
    assert s["canaries"][-1]["after_probe_count"] == 0
    assert (_sealed(out) / ".sealed").is_file()


def test_conc_one_session_arms_and_seals(monkeypatch, tmp_path) -> None:
    events = _stub(monkeypatch, tmp_path)
    monkeypatch.setattr(
        b4, "CC_OVERRIDE", {"cell": "CC-CONC", "conc": {"sessions": (1,), "tokens": 4096}}
    )
    out = tmp_path / "c"
    assert b4.run_cc_series(arm="gpu_only_u4", model_spec=SPEC, session_id="c1", out_dir=out) == 0
    assert events == ["canary"] * (1 + C) + ["probe", "canary"]
    assert _summary(out)["largest_holding_step"] == 1
    assert (_sealed(out) / ".sealed").is_file()


def test_conc_first_step_fails_still_seals_with_the_failure(monkeypatch, tmp_path) -> None:
    events = _stub(monkeypatch, tmp_path, holds=[False])
    monkeypatch.setattr(
        b4, "CC_OVERRIDE", {"cell": "CC-CONC", "conc": {"sessions": (4, 6, 8), "tokens": 8192}}
    )
    out = tmp_path / "f"
    assert b4.run_cc_series(arm="gpu_only_f16", model_spec=SPEC, session_id="f1", out_dir=out) == 0
    assert events.count("probe") == 1
    s = _summary(out)
    assert s["status"] == "complete"
    assert s["largest_holding_step"] is None and s["first_failing_step"] == 4
    assert s["points"][0]["failure_kind"] == "OOM"
    assert s["canary_finalize"]["armed"] is True
    assert (_sealed(out) / "points" / "n4.json").is_file()


def test_no_canary_runs_while_a_series_child_is_resident(monkeypatch, tmp_path) -> None:
    events = _stub(monkeypatch, tmp_path)
    monkeypatch.setattr(
        b4, "CC_OVERRIDE", {"cell": "CC-CONC", "conc": {"sessions": (1, 2, 3), "tokens": 4096}}
    )
    b4.run_cc_series(arm="gpu_only_u4", model_spec=SPEC, session_id="r1", out_dir=tmp_path / "r")
    # Children run to completion inside measured_repeat; every canary sits between them.
    assert events[: 1 + C] == ["canary"] * (1 + C)
    assert "probe" not in events[: 1 + C]
    assert events[-1] == "canary"


def test_unarmed_after_up_front_calibration_refuses_before_any_step(monkeypatch, tmp_path) -> None:
    events = _stub(monkeypatch, tmp_path, cells=["OK", "OK", "OTHER", "OK"])
    monkeypatch.setattr(b4, "CC_OVERRIDE", {"cell": "CC-GROW", "grow": {"step": 1024}})
    out = tmp_path / "u"
    with pytest.raises(SystemExit, match="not armed"):
        b4.run_cc_series(arm="gpu_only_u4", model_spec=SPEC, session_id="u1", out_dir=out)
    assert "probe" not in events
    assert _summary(out)["status"] == "REFUSED_CANARY"
    assert not _sealed(out).exists()


# ---------------------------------------------------------------- limit path


def test_one_point_limit_cell_arms_up_front_and_seals(monkeypatch, tmp_path) -> None:
    events = _stub(monkeypatch, tmp_path)
    monkeypatch.setattr(b4, "CC_OVERRIDE", {"cell": "reh_i8", "points": (1024,)})
    out = tmp_path / "p"
    rc = b4.run_resident_limit(arm="gpu_only_i8", model_spec=SPEC, session_id="p1", out_dir=out)
    assert rc == 0
    assert events == ["canary"] * (1 + C) + ["probe", "canary"]
    s = _summary(out)
    assert s["canary_finalize"]["armed"] is True and s["largest_n_cached"] == 1024
    assert s["canary"]["planned_probe_count"] == 1
    assert (_sealed(out) / ".sealed").is_file()


@pytest.mark.parametrize("points", [(), (1024, 2048), (12000, 13000, 14000)])
def test_limit_paths_that_already_arm_are_unchanged(monkeypatch, tmp_path, points) -> None:
    """Bisections and 2+ point cells (e.g. reh e259520d): warm-up + 1 opening canary, a
    canary after every probe, armed after probe 2, no up-front schedule, planned as before."""
    assert b4.cc_up_front(points) is False
    events = _stub(monkeypatch, tmp_path, holds=[True, False, True, False, True, False])
    over: dict[str, Any] = {"cell": "lim"}
    if points:
        over["points"] = points
    monkeypatch.setattr(b4, "CC_OVERRIDE", over)
    out = tmp_path / "l"
    assert (
        b4.run_resident_limit(arm="gpu_only_f16", model_spec=SPEC, session_id="l1", out_dir=out)
        == 0
    )
    n = events.count("probe")
    assert n >= 2
    assert events == ["canary", "canary"] + ["probe", "canary"] * n
    s = _summary(out)
    frag = s["canary"]
    assert "schedule" not in frag and "budget_rule" not in frag
    assert frag["planned_probe_count"] == max(b4.RESIDENT_PLANNED_PROBES, len(points))
    assert "budget_rule" not in frag["budget_preflight"]
    armed_at = [c["after_probe_count"] for c in s["canaries"] if c.get("gate_armed")]
    assert armed_at[0] == 1
    assert s["canary_finalize"]["armed"] is True


def test_guard_defaults_unchanged() -> None:
    assert tsc.assert_canary_budget_fits(4)["n_budget"] == 1
    with pytest.raises(tsc.CanaryBudgetRefuse):
        tsc.assert_canary_budget_fits(1)
    assert tsc.assert_canary_budget_fits(1, calibrated_before_probes=True)["n_budget"] == 1
    assert tsc.derive_canary_every_n([], planned_probe_count=18)["n_budget"] == 4
    assert (
        tsc.derive_canary_every_n([], planned_probe_count=18, calibrated_before_probes=True)[
            "n_budget"
        ]
        == 4
    )
    with pytest.raises(ValueError):
        tsc.TtftSloCanaryGuard(
            root=ROOT, model_spec=SPEC, work_dir=ROOT, planned_probe_count=4, up_front_budget=True
        )


# ---------------------------------------------------------------- R6 (Task BP part D)


def test_r6_uses_the_override_clause_and_the_windows_formula() -> None:
    from tools import redflags

    xps_total = 16_752_234_496 / 2**20  # a19_dxgi_start.json, window_20261023_132334_cc_v3
    xps_shared = 9_548_773_662 / 2**20
    t2s = {"shared_mib": 48_634, "total_phys_mib": 65_018}
    assert redflags.r6_formula_mib(t2s) == 48_634
    # Without the override the registered 0.50 x M clause is 1,118 MiB off: a RED FLAG.
    no_override = {"shared_mib": xps_shared, "total_phys_mib": xps_total}
    assert redflags._r6({"xps": no_override, "t2s": t2s})[0] == redflags.RED
    # Zach's manual record: Intel Shared GPU Memory Override ON at 57%.
    xps = {**no_override, "override_pct": 57}
    assert abs(redflags.r6_formula_mib(xps) - xps_shared) < 1
    assert redflags._r6({"xps": xps, "t2s": t2s})[0] == redflags.PASS
    assert redflags._r6({"t2s": {"shared_mib": 48_634, "formula_mib": 48_634}})[0] == redflags.PASS
