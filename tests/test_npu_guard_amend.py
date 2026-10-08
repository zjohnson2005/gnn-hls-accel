"""NPU-1 amendment 2026-10-08: arm before the first probe; decode at the limit.

Hardware-free. The GPU canary cell, power and WorkloadsSessionHost snapshots
are stubbed; the guard's gate logic is real.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import seam.run_environment as run_env  # noqa: E402
import tools.run_npu_profile as rnp  # noqa: E402
import tools.ttft_slo_canary as tsc  # noqa: E402
from tests.test_npu_profile_amend import (  # noqa: E402
    CHECK_MSG,
    _Decoded,
    _fake_genai,
    _fake_ov,
    _n,
)

C = tsc.CALIBRATION_C


def _stub_guard_env(monkeypatch: pytest.MonkeyPatch, cells: list[dict[str, Any]] | None = None):
    """Stub the canary cell. ``cells`` overrides turn times per canary index."""
    events: list[str] = []

    def stub_cell(self: Any) -> dict[str, Any]:
        idx = len(self.canaries)
        override = (cells or [])[idx] if cells and idx < len(cells) else {}
        events.append("canary")
        return {
            "is_canary": True,
            "canary_index": idx,
            "classification": override.get("classification", "OK"),
            "turn1_prefill_s": override.get("t1", 1.0),
            "turn2_prefill_s": override.get("t2", 0.5),
            "execute_ok": True,
        }

    monkeypatch.setattr(tsc.TtftSloCanaryGuard, "_run_cell", stub_cell)
    monkeypatch.setattr(tsc, "capture_canary_power_snapshot", lambda: {"on_ac": True})
    monkeypatch.setattr(tsc, "assert_no_ac_transition", lambda **_kw: {"ok": True})
    monkeypatch.setattr(run_env, "snapshot_workloads_session_host", lambda: {})
    return events


def _guard(tmp_path: Path, *, planned: int = 18, before: bool = True) -> Any:
    return tsc.TtftSloCanaryGuard(
        root=ROOT,
        model_spec=ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml",
        work_dir=tmp_path / "canaries",
        plan_path=None,
        planned_probe_count=planned,
        arm_before_probes=before,
    )


def _drive(guard: Any, n_probes: int, events: list[str]) -> list[bool]:
    """Run ``n_probes`` probes; return the gate's armed bit seen by each probe."""
    seen: list[bool] = []
    probes_log: list[dict[str, Any]] = []

    def one_repeat(n_tokens: int) -> dict[str, Any]:
        seen.append(bool(guard.gate.get("armed")))
        events.append("probe")
        return {"n_tokens": n_tokens, "prefill_s": 1.0, "timed": True, "slo_pass": True}

    rnp.drive_npu_rung(
        64, repeats=n_probes, one_repeat=one_repeat, guard=guard, probes_log=probes_log
    )
    guard.closing(probes_log)
    return seen


# ---------------------------------------------------------------- guard schedule


@pytest.mark.parametrize("n_probes", [1, 3, 18])
def test_armed_before_first_probe_whatever_the_probe_count(monkeypatch, tmp_path, n_probes):
    events = _stub_guard_env(monkeypatch)
    guard = _guard(tmp_path, planned=18)
    guard.opening()
    assert guard.gate["armed"] is True
    seen = _drive(guard, n_probes, events)
    assert len(seen) == n_probes and all(seen)
    assert events[:C] == ["canary"] * C and events[C] == "probe"
    assert [c["after_probe_count"] for c in guard.canaries[:C]] == [-1] * C
    # Every probe is followed by an armed check.
    assert events[-1] == "canary"
    assert guard.canaries[-1]["after_probe_count"] == n_probes - 1
    assert all(c["gate_armed"] for c in guard.canaries[C:])
    assert guard.finalize_or_refuse()["armed"] is True
    assert guard.plan_fragment()["schedule"] == "arm_before_probes"


def test_interval_cadence_unchanged(monkeypatch, tmp_path) -> None:
    events = _stub_guard_env(monkeypatch)
    guard = _guard(tmp_path, planned=18)
    guard.opening()
    _drive(guard, 18, events)
    assert guard.n_every == 4  # floor(18 / (C + 1)), as before
    after = [c["after_probe_count"] for c in guard.canaries[C:]]
    assert after == [3, 7, 11, 15, 17]


def test_closing_skipped_when_last_probe_already_checked(monkeypatch, tmp_path) -> None:
    events = _stub_guard_env(monkeypatch)
    guard = _guard(tmp_path, planned=18)
    guard.opening()
    _drive(guard, 4, events)
    assert [c["after_probe_count"] for c in guard.canaries[C:]] == [3]


def test_legacy_schedule_still_refuses_unarmed_seal(monkeypatch, tmp_path) -> None:
    """The 8ccfb38c shape: opening + one interval canary in 6 probes, never armed."""
    events = _stub_guard_env(monkeypatch)
    guard = _guard(tmp_path, planned=18, before=False)
    guard.opening()
    seen = _drive(guard, 6, events)
    assert not any(seen)
    assert len(guard.canaries) == 2 and guard.gate["armed"] is False
    with pytest.raises(tsc.CanaryUnarmedSealRefuse):
        guard.finalize_or_refuse()
    assert "schedule" not in guard.plan_fragment()


def test_closing_canary_can_trip(monkeypatch, tmp_path) -> None:
    cells = [{}] * C + [{"t1": 2.0}]
    events = _stub_guard_env(monkeypatch, cells)
    guard = _guard(tmp_path, planned=18)
    guard.opening()
    with pytest.raises(tsc.CanaryDriftAbort):
        _drive(guard, 2, events)


def test_thresholds_unchanged_by_schedule(monkeypatch, tmp_path) -> None:
    _stub_guard_env(monkeypatch)
    guard = _guard(tmp_path)
    guard.opening()
    assert guard.gate["threshold_t1"] == tsc.drift_threshold(0.0, guard.gate["rel_drift_floor_t1"])
    assert guard.gate["rel_drift_floor_t1"] == pytest.approx(0.07709453214145699)
    assert guard.gate["rel_drift_floor_t2"] == pytest.approx(0.1642942216508742)


# ---------------------------------------------------------------- runner end to end


class _EosPipe:
    """Streams one token unless min_new_tokens forces more. Refuses above ``cap``."""

    def __init__(self, cap: int, events: list[str] | None = None) -> None:
        self.cap, self.events = cap, events
        self.calls: list[tuple[Any, Any]] = []

    def generate(self, inputs: Any, cfg: Any, streamer: Any) -> Any:
        self.calls.append((inputs, cfg))
        n = _n(inputs[0])
        if n > self.cap:
            raise RuntimeError(CHECK_MSG.format(cap=self.cap, n=n))
        if self.events is not None:
            self.events.append(f"gen{n}")
        k = max(1, int(getattr(cfg, "min_new_tokens", 0) or 0))
        for _ in range(k):
            time.sleep(0.0005)
            streamer.write(1)
        return _Decoded("a b c d e f g h" if k > 1 else "", n)


def _run(monkeypatch, tmp_path, npu, args, *, cells=None, events=None):
    import json

    ev = _stub_guard_env(monkeypatch, cells)
    if events is not None:
        ev = events
        orig = tsc.TtftSloCanaryGuard._run_cell

        def tagged(self: Any) -> dict[str, Any]:
            events.append("canary")
            return orig(self)

        monkeypatch.setattr(tsc.TtftSloCanaryGuard, "_run_cell", tagged)
    loads: list[tuple[str, dict]] = []
    gpu = _EosPipe(10**6)
    monkeypatch.setitem(sys.modules, "openvino_genai", _fake_genai({"NPU": npu, "GPU": gpu}, loads))
    monkeypatch.setitem(sys.modules, "openvino", _fake_ov())
    monkeypatch.setattr(rnp, "load_local_spec", lambda _path: {"ir_dir": str(tmp_path)})
    monkeypatch.setattr(rnp, "_filler", lambda: "x")
    monkeypatch.setattr(rnp, "rendered_exact_prompt", lambda _tok, n, **_kw: f"P{n}")
    monkeypatch.setattr(rnp, "id_count", lambda _tok, text: _n(text))
    out = tmp_path / "run"
    code = rnp.main(
        [
            "--cell",
            "npu1-setting",
            "--out",
            str(out),
            "--model-spec",
            str(ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"),
            *args,
        ]
    )
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    return code, plan, summary, ev


def _rung_generates(events: list[str], rung_ns: set[int]) -> list[int]:
    return [i for i, e in enumerate(events) if e.startswith("gen") and int(e[3:]) in rung_ns]


def test_run_1024_two_rungs_arms_before_probes_and_records_decode(monkeypatch, tmp_path) -> None:
    """The 8ccfb38c shape: 64 and 1024 pass, 6 probes. Now armed before probe 1."""
    events: list[str] = []
    npu = _EosPipe(1024, events)
    code, plan, summary, _ = _run(
        monkeypatch, tmp_path, npu, ["--max-prompt-len", "1024"], events=events
    )
    assert code == 0, summary
    assert summary["status"] == "complete"
    assert summary["armed"] is True and summary["UNGUARDED"] is False
    assert [r["n_tokens"] for r in summary["rungs"]] == [64, 1024]
    canaries = summary["canaries"]
    assert [c["after_probe_count"] for c in canaries[:C]] == [-1] * C
    assert canaries[C - 1]["gate_armed"] is True
    assert canaries[-1]["after_probe_count"] == 5  # closing check after probe 6
    first_rung = _rung_generates(events, {64, 1024})[0]
    assert events[:first_rung].count("canary") >= C
    assert summary["binding"] == "TOOLCHAIN_CAP"
    assert summary["ttft_limit_n"] == 1024
    assert isinstance(summary["decode_tok_s_at_limit"], float)
    rows = [r for rung in summary["rungs"] for r in rung["repeats"]]
    assert all(r["npu_streamer_tokens"] == 8 and r["decode_reason"] is None for r in rows)
    assert summary["capacity_check"]["passed"] is True
    assert plan["guard_schedule"].startswith("arm_before_probes")
    assert all(cfg.min_new_tokens == 8 for _, cfg in npu.calls)


def test_run_eighteen_probes_arms_before_probes(monkeypatch, tmp_path) -> None:
    """The 04d189da shape: the 1024 rung is refused and the bisection runs 18 probes."""
    events: list[str] = []
    npu = _EosPipe(1000, events)
    # P2 at 1088 must still be refused by the length check; P1 at 960 accepted.
    code, _, summary, _ = _run(
        monkeypatch, tmp_path, npu, ["--max-prompt-len", "1024"], events=events
    )
    assert code == 0, summary
    assert [r["n_tokens"] for r in summary["rungs"]] == [64, 1024, 512, 768, 896, 960]
    canaries = summary["canaries"]
    assert [c["after_probe_count"] for c in canaries[:C]] == [-1] * C
    assert [c["after_probe_count"] for c in canaries[C:]] == [3, 7, 11, 15, 17]
    assert all(c["gate_armed"] for c in canaries[C - 1 :])
    rung_ns = {r["n_tokens"] for r in summary["rungs"]}
    first_rung = _rung_generates(events, rung_ns - {960})[0]
    assert events[:first_rung].count("canary") == C
    assert summary["ttft_limit_n"] == 960
    assert summary["decode_tok_s_at_limit"] is not None


def test_run_refuses_before_any_probe_when_calibration_does_not_arm(monkeypatch, tmp_path) -> None:
    events: list[str] = []
    npu = _EosPipe(1024, events)
    bad = [{"classification": "OTHER", "t1": None, "t2": None}] * C
    code, _, summary, _ = _run(
        monkeypatch, tmp_path, npu, ["--max-prompt-len", "1024"], cells=bad, events=events
    )
    assert code == 1
    assert summary["status"] == "REFUSED_UNARMED_CANARY"
    assert summary["UNGUARDED"] is True and summary["armed"] is False
    assert summary["timed"] is False and "rungs" not in summary
    # Only the capacity probes (960, 1088 refused) touched the NPU.
    assert _rung_generates(events, {64, 1024}) == []


def test_run_armed_trip_is_fail_canary_drift(monkeypatch, tmp_path) -> None:
    cells = [{}] * C + [{"t1": 3.0}]
    code, _, summary, _ = _run(
        monkeypatch, tmp_path, _EosPipe(1024), ["--max-prompt-len", "1024"], cells=cells
    )
    assert code == 1
    assert summary["status"] == "FAIL_CANARY_DRIFT"


def test_decode_reason_when_one_token_streams() -> None:
    class Cfg:
        pass

    genai = _fake_genai({}, [])
    genai.GenerationConfig = Cfg
    pipe = _EosPipe(1024)
    orig = rnp.generation_config

    def no_min(ov_genai: Any) -> Any:
        cfg = orig(ov_genai)
        cfg.min_new_tokens = 0
        return cfg

    row_forced = rnp.generate_once(genai, pipe, "P64")
    assert row_forced["streamer_tokens"] == 8 and row_forced["decode_tok_s"] is not None
    rnp_cfg = rnp.generation_config
    try:
        rnp.generation_config = no_min
        row = rnp.generate_once(genai, pipe, "P64")
    finally:
        rnp.generation_config = rnp_cfg
    assert row["decode_tok_s"] is None
    assert row["decode_reason"].startswith("streamer_tokens=1")


def test_bind_setting_states_why_decode_at_limit_is_null() -> None:
    rung = {
        "n_tokens": 1024,
        "slo_pass": True,
        "prefill_s": [1.3],
        "decode_tok_s": [None],
        "repeats": [{"decode_reason": "streamer_tokens=1; decode needs two or more"}],
    }
    bound = rnp.bind_setting(load_ok=True, cap=1024, rungs=[rung])
    assert bound["ttft_limit_n"] == 1024
    assert bound["decode_tok_s_at_limit"] is None
    assert "streamer_tokens=1" in bound["decode_tok_s_at_limit_reason"]
    ok = dict(rung, decode_tok_s=[15.0, 16.0, 17.0])
    bound = rnp.bind_setting(load_ok=True, cap=1024, rungs=[ok])
    assert bound["decode_tok_s_at_limit"] == 16.0
    assert "decode_tok_s_at_limit_reason" not in bound


def test_rehearsal_smoke_path_still_runs(tmp_path) -> None:
    out = tmp_path / "smoke"
    assert rnp.main(["--cell", "npu1-setting", "--out", str(out), "--smoke"]) == 0
    assert (out / "summary.json").is_file()
