"""NPU-1 amendment 2026-10-08b: calibrate after the paired GPU pipeline exists.

Hardware-free. The fake host has a state step: the canary's turn 1 is about
10% faster once the paired GPU pipeline has been created, as in 9d6d7f66 and
8ccfb38c. The guard's gate logic is real.
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
import tools.run_npu_profile as rnp  # noqa: E402
import tools.ttft_slo_canary as tsc  # noqa: E402
from tests.test_npu_guard_amend import _EosPipe  # noqa: E402
from tests.test_npu_profile_amend import _fake_genai, _fake_ov, _n  # noqa: E402

C = tsc.CALIBRATION_C
BEFORE_STEP_T1 = 1.0137  # 9d6d7f66 calibration reference
AFTER_STEP_T1 = 0.9113  # 9d6d7f66 canary 3


class _Host:
    """Records the order of events and carries the GPU-pipeline state step."""

    def __init__(self, *, drift_after: int | None = None, bad_cal: bool = False) -> None:
        self.events: list[str] = []
        self.gpu_created = False
        self.drift_after = drift_after
        self.bad_cal = bad_cal

    def canary_cell(self, guard: Any) -> dict[str, Any]:
        idx = len(guard.canaries)
        self.events.append("canary")
        t1 = AFTER_STEP_T1 if self.gpu_created else BEFORE_STEP_T1
        if self.drift_after is not None and idx >= self.drift_after:
            t1 *= 1.25  # genuine slowdown after calibration
        ok = not (self.bad_cal and idx < C)
        return {
            "is_canary": True,
            "canary_index": idx,
            "classification": "OK" if ok else "OTHER",
            "turn1_prefill_s": t1 if ok else None,
            "turn2_prefill_s": 0.477 if ok else None,
            "execute_ok": ok,
        }


class _GpuPipe(_EosPipe):
    def __init__(self, host: _Host, *, fail: bool = False) -> None:
        super().__init__(10**6)
        self.host, self.fail = host, fail

    def generate(self, inputs: Any, cfg: Any, streamer: Any) -> Any:
        self.host.events.append(f"gpu{_n(inputs[0])}")
        if self.fail:
            raise RuntimeError("CL_OUT_OF_RESOURCES")
        return super().generate(inputs, cfg, streamer)


class _NpuPipe(_EosPipe):
    def __init__(self, host: _Host, cap: int) -> None:
        super().__init__(cap)
        self.host = host

    def generate(self, inputs: Any, cfg: Any, streamer: Any) -> Any:
        self.host.events.append(f"npu{_n(inputs[0])}")
        return super().generate(inputs, cfg, streamer)


def _run(monkeypatch, tmp_path, host: _Host, *, cap: int = 1024, gpu_fail: bool = False):
    monkeypatch.setattr(tsc.TtftSloCanaryGuard, "_run_cell", lambda self: host.canary_cell(self))
    monkeypatch.setattr(tsc, "capture_canary_power_snapshot", lambda: {"on_ac": True})
    monkeypatch.setattr(tsc, "assert_no_ac_transition", lambda **_kw: {"ok": True})
    monkeypatch.setattr(run_env, "snapshot_workloads_session_host", lambda: {})
    npu = _NpuPipe(host, cap)
    gpu = _GpuPipe(host, fail=gpu_fail)
    genai = _fake_genai({"NPU": npu, "GPU": gpu}, [])
    base = genai.LLMPipeline

    def pipeline(path: str, device: str, **props: Any) -> Any:
        if device == "GPU":
            host.gpu_created = True
            host.events.append("gpu_create")
        return base(path, device, **props)

    genai.LLMPipeline = pipeline
    monkeypatch.setitem(sys.modules, "openvino_genai", genai)
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
            "--max-prompt-len",
            str(cap),
        ]
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    return code, plan, summary


def _first(events: list[str], prefix: tuple[str, ...]) -> int:
    return next(i for i, e in enumerate(events) if e.startswith(prefix))


def test_step_reproduces_the_9d6d7f66_trip_when_calibrated_before_the_pipeline(
    monkeypatch, tmp_path
) -> None:
    """The fake is faithful: the 9d6d7f66 values trip under the old order."""
    monkeypatch.setattr(tsc, "capture_canary_power_snapshot", lambda: {"on_ac": True})
    monkeypatch.setattr(tsc, "assert_no_ac_transition", lambda **_kw: {"ok": True})
    monkeypatch.setattr(run_env, "snapshot_workloads_session_host", lambda: {})
    values = iter([1.031677856, 1.01370697, 0.982864379, 0.911252319])

    def cell(self: Any) -> dict[str, Any]:
        return {
            "canary_index": len(self.canaries),
            "classification": "OK",
            "turn1_prefill_s": next(values),
            "turn2_prefill_s": 0.477,
        }

    monkeypatch.setattr(tsc.TtftSloCanaryGuard, "_run_cell", cell)
    guard = tsc.TtftSloCanaryGuard(
        root=ROOT,
        model_spec=ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml",
        work_dir=tmp_path / "c",
        planned_probe_count=18,
        arm_before_probes=True,
    )
    guard.opening()
    assert guard.gate["threshold_t1"] == pytest.approx(0.07709453214145699)
    with pytest.raises(tsc.CanaryDriftAbort, match=r"rel_drift=0\.101"):
        guard.run_canary(after_probe_count=3)


def test_calibration_after_gpu_pipeline_and_warmup_before_first_probe(
    monkeypatch, tmp_path
) -> None:
    host = _Host()
    code, plan, summary = _run(monkeypatch, tmp_path, host)
    assert code == 0, summary
    ev = host.events
    create = ev.index("gpu_create")
    warm = ev.index("gpu64", create)
    cal = [i for i, e in enumerate(ev) if e == "canary"][:C]
    first_probe = _first(ev[cal[-1] :], ("npu64",)) + cal[-1]
    assert create < warm < cal[0] and cal == list(range(warm + 1, warm + 1 + C))
    assert first_probe > cal[-1]
    # The warm-up is not a probe and is not in any rung.
    assert plan["gpu_warmup"]["is_probe"] is False and plan["gpu_warmup"]["ok"] is True
    assert plan["gpu_warmup"]["n_tokens"] == 64
    assert sum(len(r["repeats"]) for r in summary["rungs"]) == 6
    assert "2026-10-08b" in plan["guard_schedule"]


def test_state_step_at_gpu_pipeline_creation_no_longer_trips(monkeypatch, tmp_path) -> None:
    host = _Host()
    code, _, summary = _run(monkeypatch, tmp_path, host)
    assert code == 0, summary
    assert summary["status"] == "complete"
    assert summary["armed"] is True and summary["UNGUARDED"] is False
    gate = summary["canary"]["canary_gate"]
    assert gate["ref_turn1_prefill_s"] == pytest.approx(AFTER_STEP_T1)
    assert all(not c["drift_tripped"] for c in summary["canaries"])
    assert all(c["turn1_prefill_s"] == pytest.approx(AFTER_STEP_T1) for c in summary["canaries"])


def test_genuine_drift_after_calibration_still_trips(monkeypatch, tmp_path) -> None:
    host = _Host(drift_after=C)
    code, _, summary = _run(monkeypatch, tmp_path, host)
    assert code == 1
    assert summary["status"] == "FAIL_CANARY_DRIFT"
    assert summary["armed"] is True
    assert "turn1 rel_drift=0.25" in summary["canary_trip_detail"]


def test_unarmed_calibration_still_refuses_before_any_probe(monkeypatch, tmp_path) -> None:
    host = _Host(bad_cal=True)
    code, _, summary = _run(monkeypatch, tmp_path, host)
    assert code == 1
    assert summary["status"] == "REFUSED_UNARMED_CANARY"
    assert summary["UNGUARDED"] is True
    assert not any(e == "npu64" for e in host.events)


def test_failed_gpu_warmup_refuses_before_any_canary(monkeypatch, tmp_path) -> None:
    host = _Host()
    code, plan, summary = _run(monkeypatch, tmp_path, host, gpu_fail=True)
    assert code == 1
    assert summary["status"] == "REFUSED_GPU_WARMUP"
    assert "canary" not in host.events
    assert plan["gpu_warmup"]["ok"] is False


def test_rehearsal_smoke_path_still_runs(tmp_path) -> None:
    out = tmp_path / "smoke"
    assert rnp.main(["--cell", "npu1-setting", "--out", str(out), "--smoke"]) == 0
    assert json.loads((out / "summary.json").read_text(encoding="utf-8"))["status"] == "smoke"
