"""NPU amendment 2026-10-14 (canary state): warm-up rung before calibration, telemetry."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.canary_telemetry as ct  # noqa: E402
import tools.run_npu_profile as rnp  # noqa: E402
import tools.ttft_slo_canary as tsc  # noqa: E402
from tests.test_npu_int8_envelope import _fake_genai, _fake_ov, _ir, _n, _Pipe  # noqa: E402


class _Guard:
    """Stands in for TtftSloCanaryGuard; logs the schedule against NPU calls."""

    instances: list[_Guard] = []

    def __init__(self, npu: _Pipe, **kwargs: Any) -> None:
        self.npu = npu
        self.kwargs = kwargs
        self.events: list[tuple[str, int]] = []
        self.canaries: list[dict[str, Any]] = []
        self.n_derivation: dict[str, Any] = {}
        self.armed = False
        _Guard.instances.append(self)

    def run_canary(self, *, after_probe_count: int, warmup: bool = False) -> dict[str, Any]:
        self.events.append(("record_only" if warmup else "canary", len(self.npu.calls)))
        rec = {"canary_index": len(self.canaries), "warmup": warmup}
        self.canaries.append(rec)
        return rec

    def opening(self) -> None:
        self.events.append(("opening", len(self.npu.calls)))
        for _ in range(3):
            self.run_canary(after_probe_count=-1)
        self.armed = True

    def plan_fragment(self) -> dict[str, Any]:
        return {"canary_gate": {"armed": self.armed}}

    def after_probe(self, _log: list[dict[str, Any]]) -> None:
        return None

    def closing(self, _log: list[dict[str, Any]]) -> None:
        return None

    def finalize_or_refuse(self) -> dict[str, Any]:
        return {}


def _run_guarded(monkeypatch, tmp_path: Path) -> tuple[int, dict, dict, _Pipe, _Guard]:
    loads: list[tuple[str, dict]] = []
    npu, gpu = _Pipe(256), _Pipe(10**6)
    ir, digest = _ir(tmp_path)
    spec = {"ir_dir": str(ir), "ir_files": {"openvino_model.xml": digest}}
    monkeypatch.setitem(sys.modules, "openvino_genai", _fake_genai({"NPU": npu, "GPU": gpu}, loads))
    monkeypatch.setitem(sys.modules, "openvino", _fake_ov())
    monkeypatch.setattr(rnp, "load_local_spec", lambda _path: spec)
    monkeypatch.setattr(rnp, "_filler", lambda: "x")
    monkeypatch.setattr(rnp, "rendered_exact_prompt", lambda _tok, n, **_kw: f"P{n}")
    monkeypatch.setattr(rnp, "content_prompt", lambda _tok, n, **_kw: f"Q{n}")
    monkeypatch.setattr(rnp, "id_count", lambda _tok, text: _n(text))
    _Guard.instances = []
    monkeypatch.setattr(tsc, "TtftSloCanaryGuard", lambda **kw: _Guard(npu, **kw))
    out = tmp_path / "run"
    code = rnp.main(
        [
            "--cell",
            "npu1-setting",
            "--out",
            str(out),
            "--model-spec",
            str(tmp_path / "spec.yaml"),
            "--envelope",
            "--max-prompt-len",
            "256",
        ]
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    return code, plan, summary, npu, _Guard.instances[-1]


def test_guarded_envelope_runs_record_canary_then_warm_rung_then_calibration(
    monkeypatch, tmp_path
) -> None:
    code, plan, summary, npu, guard = _run_guarded(monkeypatch, tmp_path)
    assert code == 0, summary
    kinds = [k for k, _ in guard.events]
    assert kinds[:2] == ["record_only", "opening"]
    record_at, opening_at = guard.events[0][1], guard.events[1][1]
    warm = npu.calls[record_at:opening_at]
    assert [int(cfg.max_new_tokens) for _p, cfg in warm] == [64, 1, 1]
    assert all(prompt == "P64" for prompt, _cfg in warm)
    rec = plan["canary_warmup_rung"]
    assert rec["amendment"] == rnp.CANARY_STATE_AMENDMENT
    assert rec["is_probe"] is False and rec["timed"] is False
    assert [c["device"] for c in rec["calls"]] == ["NPU", "GPU", "NPU", "NPU"]
    assert rec["estimate_s"] == rnp.canary_warmup_rung_estimate_s(64)
    assert "2026-10-14" in plan["guard_schedule"]
    assert isinstance(guard.kwargs["telemetry"], ct.CanaryTelemetry)
    # The warm-up rung is not a probe: rungs and their repeats are unchanged.
    assert {r["n_tokens"] for r in summary["rungs"]} == {64, 192}
    sizes = [int(cfg.max_new_tokens) for prompt, cfg in npu.calls if prompt.startswith("P")]
    assert sizes == [8, 8, 64, 1, 1, 64, 1, 1, 64, 1, 1]
    assert summary["armed"] is True


def test_arm_canary_defaults_are_unchanged(monkeypatch, tmp_path) -> None:
    npu = _Pipe(10)
    _Guard.instances = []
    monkeypatch.setattr(tsc, "TtftSloCanaryGuard", lambda **kw: _Guard(npu, **kw))
    rnp._arm_canary(tmp_path, tmp_path / "spec.yaml", 12, before_probes=True)
    guard = _Guard.instances[-1]
    kinds = [k for k, _ in guard.events]
    assert kinds[0] == "opening" and "record_only" not in kinds
    assert guard.kwargs["telemetry"] is None


def test_amended_schedule_is_envelope_only() -> None:
    src = (ROOT / "tools" / "run_npu_profile.py").read_text(encoding="utf-8")
    assert "if envelope and not args.no_canary:" in src
    block = src[src.index("if envelope and not args.no_canary:") :]
    assert block.index("before_calibration") < block.index("if not arm(")


def test_warm_rung_estimate_is_outside_the_registered_envelope_bound() -> None:
    assert rnp.canary_warmup_rung_estimate_s(64) == 213
    # 2026-10-13b registered figures stay as they were.
    assert [rnp.envelope_estimate_s(s) for s in (1024, 2048, 4096, 8192)] == [
        1689,
        2016,
        2567,
        3823,
    ]


def test_guard_records_telemetry_only_when_given(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(tsc, "capture_canary_power_snapshot", lambda: {"on_ac": True})
    monkeypatch.setattr(tsc, "assert_no_ac_transition", lambda **_kw: {"ok": True})
    import seam.run_environment as env

    monkeypatch.setattr(env, "snapshot_workloads_session_host", lambda: {})
    for telemetry, expect in ((None, False), (lambda: {"processes": {"count": 3}}, True)):
        guard = tsc.TtftSloCanaryGuard(
            root=ROOT,
            model_spec=tmp_path / "s.yaml",
            work_dir=tmp_path / "w",
            enforce_probe_budget=False,
            telemetry=telemetry,
        )
        guard._run_cell = lambda: {  # type: ignore[method-assign]
            "canary_index": 0,
            "classification": "OK",
            "turn1_prefill_s": 1.0,
            "turn2_prefill_s": 0.5,
        }
        rec = guard.run_canary(after_probe_count=-1, warmup=True)
        assert ("telemetry" in rec) is expect
        assert rec["discarded_from_calibration"] is True and rec["drift_tripped"] is False


def test_telemetry_never_raises_and_tracks_process_changes(monkeypatch) -> None:
    seq = iter([Counter({"a.exe": 2}), Counter({"a.exe": 1, "b.exe": 1})])
    monkeypatch.setattr(ct, "_process_names", lambda: (next(seq), None))
    tel = ct.CanaryTelemetry()
    first, second = tel(), tel()
    assert first["processes"]["count"] == 2 and first["processes"]["added_since_previous"] is None
    assert second["processes"]["added_since_previous"] == {"b.exe": 1}
    assert second["processes"]["removed_since_previous"] == {"a.exe": 1}
    assert set(first) == {"cpu_clock", "gpu_clock", "power_plan", "memory", "processes"}

    monkeypatch.setattr(ct, "_process_names", lambda: (None, "RuntimeError: x"))
    monkeypatch.setattr(ct, "_cpu_clock", lambda: {"error": "RuntimeError: x"})
    assert ct.CanaryTelemetry()()["processes"] == {"error": "RuntimeError: x"}


@pytest.mark.parametrize("name", ["tools/canary_telemetry.py", "tools/run_npu_profile.py"])
def test_runner_does_not_open_the_amendment(name: str) -> None:
    text = (ROOT / name).read_text(encoding="utf-8")
    assert "docs/amendments" not in text
