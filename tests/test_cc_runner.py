"""Task BJ: CC-cell options of tools/run_resident_limit.py (all default off)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.boot4_session as b4  # noqa: E402
import tools.run_resident_limit as rrl  # noqa: E402
from seam.tools import _delta_n_child as child  # noqa: E402

SPEC = ["--arm", "gpu_only_u4", "--model-spec", "configs/models/Qwen3-4B-int4-ov.yaml"]


def _main(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def fake_run(**kw: Any) -> int:
        seen.update(kw)
        seen["cc"] = dict(b4.CC_OVERRIDE)
        seen["scheduler"] = b4.SCHEDULER_OVERRIDE
        seen["grid"] = (b4._resident_low(), b4._resident_high(), b4._resident_resolution())
        return 0

    monkeypatch.setattr(rrl, "run_resident_limit", fake_run)
    try:
        assert rrl.main(argv) == 0
    finally:
        b4.set_pilot_overrides()
        b4.set_cc_overrides()
    return seen


def test_defaults_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _main(monkeypatch, SPEC)
    assert seen["cc"] == {}
    assert seen["grid"] == (b4.RESIDENT_LOW, b4.RESIDENT_HIGH, b4.RESIDENT_RESOLUTION)
    assert b4.CC_OVERRIDE == {}


def test_cc_options_need_a_cell_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rrl, "run_resident_limit", lambda **_kw: 0)
    with pytest.raises(SystemExit, match="--cc-cell"):
        rrl.main([*SPEC, "--points", "4000,12000"])
    with pytest.raises(SystemExit, match="--cc-cell"):
        rrl.main([*SPEC, "--gpu-mem-stats"])
    b4.set_cc_overrides()


def test_cap_cell_with_grid_and_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _main(
        monkeypatch,
        [
            *SPEC,
            "--cc-cell",
            "CC-MECH-XPS:u4:c256",
            "--high",
            "100000",
            "--low",
            "12000",
            "--resolution",
            "1000",
            "--sched-max-batched-tokens",
            "256",
            "--gpu-mem-stats",
            "--compiled-readback",
        ],
    )
    assert seen["scheduler"] == {"enable_prefix_caching": True, "max_num_batched_tokens": 256}
    assert seen["grid"] == (12000, 100000, 1000)
    assert seen["cc"]["cell"] == "CC-MECH-XPS:u4:c256"
    assert seen["cc"]["gpu_mem_stats"] is True and seen["cc"]["compiled_readback"] is True


def test_points_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _main(
        monkeypatch,
        [
            *SPEC,
            "--cc-cell",
            "CC-BYTES-T2S:u4:unl",
            "--points",
            "4096,12288,24576",
            "--turn2-new-tokens",
            "64",
            "--turn2-repeats",
            "3",
        ],
    )
    assert seen["cc"]["points"] == (4096, 12288, 24576)
    assert seen["cc"]["turn2_new_tokens"] == 64 and seen["cc"]["turn2_repeats"] == 3


def test_grid_must_divide(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rrl, "run_resident_limit", lambda **_kw: 0)
    with pytest.raises(SystemExit, match="multiple"):
        rrl.main([*SPEC, "--cc-cell", "x", "--high", "100000", "--resolution", "700"])
    b4.set_pilot_overrides()
    b4.set_cc_overrides()


def test_fixed_points_records_every_point_in_order() -> None:
    order: list[int] = []

    def attempt(n: int) -> dict[str, Any]:
        order.append(n)
        return {"n_cached": n, "holds": n <= 20000, "turn2_ttft_s": 0.5}

    found = b4.fixed_points((24000, 4000, 12000), attempt)
    assert order == [24000, 4000, 12000]
    assert found["largest_n_cached"] == 12000
    assert found["first_fail_n_cached"] == 24000
    assert found["failure_in_range"] is True


class _Core:
    def __init__(self, raw: Any) -> None:
        self.raw = raw

    def get_property(self, device: str, name: str) -> Any:
        assert name == "GPU_MEMORY_STATISTICS"
        if isinstance(self.raw, Exception):
            raise self.raw
        return self.raw


def test_mem_snapshot_records_errors_never_raises() -> None:
    ok = child.cc_mem_snapshot("loaded", {"GPU": _Core({"usm_device": 10, "cl_mem": 2})})
    assert ok["gpu_memory_statistics"]["GPU"] == {"usm_device": 10, "cl_mem": 2}
    bad = child.cc_mem_snapshot("after_turn1", {"GPU": _Core(RuntimeError("no such property"))})
    assert bad["gpu_memory_statistics"]["GPU"]["error"].startswith("RuntimeError")
    assert "available_mb" in bad["system"] and "gpu_process_counters" in bad


def test_child_hooks_are_gated_on_spec_flags() -> None:
    src = (ROOT / "seam" / "tools" / "_delta_n_child.py").read_text(encoding="utf-8")
    assert 'if spec.get("gpu_mem_stats"):' in src
    assert 'if spec.get("compiled_readback"):' in src
    assert 'mem_probe("after_turn1")' in src


def test_mem_trace_summary(tmp_path: Path) -> None:
    from tools import cc_mem_trace as tr

    mb = 1024 * 1024
    csv_text = "\n".join(
        [
            "t_unix,path,value",
            f"10.0,\\\\h\\gpu adapter memory(luid_0x1_phys_0)\\shared usage,{1000 * mb}",
            f"10.0,\\\\h\\gpu process memory(pid_42_luid_0x1_phys_0)\\shared usage,{600 * mb}",
            f"10.0,\\\\h\\gpu process memory(pid_7_luid_0x1_phys_0)\\shared usage,{50 * mb}",
            "10.0,\\\\h\\memory\\available mbytes,5000",
            "10.0,\\\\h\\memory\\page reads/sec,3",
            f"11.5,\\\\h\\gpu adapter memory(luid_0x1_phys_0)\\shared usage,{2500 * mb}",
            f"11.5,\\\\h\\gpu process memory(pid_42_luid_0x1_phys_0)\\shared usage,{2100 * mb}",
            "11.5,\\\\h\\memory\\available mbytes,1200",
            "11.5,\\\\h\\memory\\page reads/sec,40",
            "12.0,ERROR,Get-Counter returned nothing",
            f"99.0,\\\\h\\gpu adapter memory(luid_0x1_phys_0)\\shared usage,{9000 * mb}",
        ]
    )
    p = tmp_path / "s.csv"
    p.write_text(csv_text + "\n", encoding="ascii")
    s = tr.summarise(tr.read_rows(p), 9.0, 20.0, pids=[42])
    assert s["adapter_shared_peak_mb"] == 2500.0 and s["adapter_shared_last_mb"] == 2500.0
    assert s["process_shared_peak_mb"] == 2100.0
    assert s["available_min_mb"] == 1200.0 and s["page_reads_peak_per_s"] == 40.0
    assert s["errors"] == 1 and s["samples"] == 2


def test_sidecar_is_read_only_and_writes_outside_repo() -> None:
    src = (ROOT / "tools" / "cc_mem_sidecar.ps1").read_text(encoding="ascii")
    for verb in ("Stop-Process", "Set-ItemProperty", "Remove-Item", "shutdown"):
        assert verb not in src
    assert "StopFile" in src and "MaxHours" in src


def test_repeated_points_get_distinct_record_names() -> None:
    src = (ROOT / "tools" / "boot4_session.py").read_text(encoding="utf-8")
    body = src[src.index("def run_resident_limit(*, arm") :]
    assert 'sfx = f"_r{k}" if k else ""' in body
    assert 'tag=f"n{n_cached}{sfx}"' in body
    assert '"points" / f"n{n_cached}{sfx}.json"' in body
