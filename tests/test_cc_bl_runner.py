"""Task BL: amendment harness options (A4 timeout, A5 validity, A6 trace, CC-GROW, CC-CONC)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.boot4_session as b4  # noqa: E402
import tools.run_resident_limit as rrl  # noqa: E402
from seam.tools import _delta_n_child as child  # noqa: E402

SPEC = ["--arm", "gpu_only_f16", "--model-spec", "configs/models/Qwen3-4B-int4-ov.yaml"]


def _route(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def fake(name: str) -> Any:
        def run(**kw: Any) -> int:
            seen["runner"] = name
            seen["cc"] = dict(b4.CC_OVERRIDE)
            seen["scheduler"] = b4.SCHEDULER_OVERRIDE
            return 0

        return run

    monkeypatch.setattr(rrl, "run_resident_limit", fake("limit"))
    monkeypatch.setattr(rrl, "run_cc_series", fake("series"))
    try:
        assert rrl.main(argv) == 0
    finally:
        b4.set_pilot_overrides()
        b4.set_cc_overrides()
    return seen


def test_defaults_route_to_limit_with_no_cc_state(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _route(monkeypatch, SPEC)
    assert seen["runner"] == "limit" and seen["cc"] == {}


def test_timeout_and_trace_and_wide_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _route(
        monkeypatch,
        [
            *SPEC,
            "--cc-cell",
            "CC-MECH-XPS:u4:c256",
            "--high",
            "110000",
            "--resolution",
            "1000",
            "--probe-timeout-s",
            "3600",
            "--mem-trace-hz",
            "10",
            "--sched-max-batched-tokens",
            "256",
        ],
    )
    assert seen["runner"] == "limit"
    assert seen["cc"]["probe_timeout_s"] == 3600 and seen["cc"]["mem_trace_hz"] == 10
    assert seen["scheduler"]["enable_prefix_caching"] is True


def test_conc_routes_to_series_with_prefix_caching_off(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _route(
        monkeypatch,
        [
            *SPEC,
            "--cc-cell",
            "CC-CONC-T2S:ii",
            "--conc-sessions",
            "7,8,9,10,11,12",
            "--conc-tokens",
            "32768",
            "--sched-max-batched-tokens",
            "256",
            "--sched-no-prefix-caching",
        ],
    )
    assert seen["runner"] == "series"
    assert seen["cc"]["conc"] == {
        "sessions": [7, 8, 9, 10, 11, 12],
        "tokens": 32768,
        "new_tokens": 16,
    }
    assert seen["scheduler"] == {"enable_prefix_caching": False, "max_num_batched_tokens": 256}


def test_grow_routes_to_series(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _route(
        monkeypatch,
        [*SPEC, "--cc-cell", "CC-GROW:f16:unl", "--grow-step", "2048", "--grow-max", "110000"],
    )
    assert seen["runner"] == "series"
    assert seen["cc"]["grow"] == {"step_tokens": 2048, "max_tokens": 110000, "new_tokens": 1}


@pytest.mark.parametrize(
    "extra",
    [
        ["--conc-sessions", "9,8", "--conc-tokens", "32768"],
        ["--grow-step", "2048"],
        ["--sched-no-prefix-caching"],
        ["--grow-step", "2048", "--grow-max", "9000", "--points", "4096"],
    ],
)
def test_bad_combinations_refuse(monkeypatch: pytest.MonkeyPatch, extra: list[str]) -> None:
    monkeypatch.setattr(rrl, "run_resident_limit", lambda **_kw: 0)
    monkeypatch.setattr(rrl, "run_cc_series", lambda **_kw: 0)
    with pytest.raises(SystemExit, match="REFUSED"):
        rrl.main([*SPEC, "--cc-cell", "x", *extra])
    b4.set_pilot_overrides()
    b4.set_cc_overrides()


def test_cc_cfg_overrides_only_the_timeout_and_only_when_set() -> None:
    cfg = {"generation": {"timeout_s": 1800, "max_new_tokens": 8}}
    assert b4._cc_cfg(cfg) is cfg
    b4.set_cc_overrides(cell="x", probe_timeout_s=3600)
    try:
        out = b4._cc_cfg(cfg)
        assert out["generation"]["timeout_s"] == 3600.0 and cfg["generation"]["timeout_s"] == 1800
    finally:
        b4.set_cc_overrides()


def test_model_window_and_validity(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(
        json.dumps({"max_position_embeddings": 40960, "rope_scaling": None}), encoding="utf-8"
    )
    w = b4.model_window(tmp_path)
    assert w["max_position_embeddings"] == 40960 and w["rope_scaling"] is None
    assert b4.validity_fields(87000, w) == {
        "L_mem": 87000,
        "L_valid": 40960,
        "past_trained_positions": True,
    }
    assert b4.validity_fields(24000, w)["past_trained_positions"] is False
    assert "error" in b4.model_window(tmp_path / "missing")


class _Core:
    def __init__(self) -> None:
        self.n = 0

    def get_property(self, device: str, name: str) -> Any:
        if name == "GPU_MEMORY_STATISTICS":
            self.n += 1
            return {"usm_device": 100 * self.n, "cl_mem": 1}
        if name == "GPU_DEVICE_MAX_ALLOC_MEM_SIZE":
            return 4 * 2**30
        raise RuntimeError("unsupported property")


def test_mem_trace_samples_and_device_props() -> None:
    core = _Core()
    with child.MemTrace(50.0, {"GPU": core}) as tr:
        time.sleep(0.15)
    r = tr.result()
    assert r["n"] >= 2 and r["errors"] == 0
    assert r["gpu_stat_total_peak_bytes"] >= r["gpu_stat_total_first_bytes"]
    props = child.device_mem_props(core, "GPU")
    assert props["GPU_DEVICE_MAX_ALLOC_MEM_SIZE"] == 4 * 2**30
    assert str(props["GPU_DEVICE_TOTAL_MEM_SIZE"]).startswith("error")


def test_traced_is_a_passthrough_without_the_flag() -> None:
    assert child._traced({}, lambda: {"a": 1}) == {"a": 1}
