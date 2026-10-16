"""DEMO-2 runner options (Task AS part 6): defaults off, validation, load path, telemetry.

No OpenVINO: openvino / openvino_genai are faked in sys.modules where needed.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from seam import genai_runtime as gr  # noqa: E402
from seam import turn_memory as tmem  # noqa: E402
from tools import run_h1_hybrid as rh  # noqa: E402

PA_LOG = "Model: LLM with Paged Attention\n  KV_CACHE_PRECISION: i8\n"


def _opts(**kw: Any) -> dict[str, Any] | None:
    base = {"residency": "RESIDENT", "kv": "default", "placement": "gpu_only"}
    base.update(kw)
    return gr.build_runtime_options(**base)


def test_no_flags_means_none() -> None:
    assert _opts() is None
    args = rh.build_argparser().parse_args(["--policy", "hybrid_full"])
    flags = rh.runtime_flags(args)
    assert not rh.runtime_flags_set(flags)
    assert (
        rh.resolve_runtime_options(
            {"residency": "RESIDENT", "kv": "u8", "placement": "gpu_only"}, flags
        )
        is None
    )


def test_scheduler_needs_both_fields_and_resident() -> None:
    with pytest.raises(ValueError, match="both"):
        _opts(kv="u4", sched_max_batched_tokens=4096)
    with pytest.raises(ValueError, match="RESIDENT"):
        _opts(
            kv="u4",
            residency="NON_RESIDENT",
            sched_prefix_caching="on",
            sched_max_batched_tokens=4096,
        )
    with pytest.raises(ValueError, match="not RESIDENT"):
        _opts(kv="u4", sched_prefix_caching="off", sched_max_batched_tokens=4096)
    o = _opts(
        kv="u4", sched_prefix_caching="on", sched_max_batched_tokens=4096, sched_cache_size_gb=2
    )
    assert o["scheduler_overrides"] == {
        "enable_prefix_caching": True,
        "max_num_batched_tokens": 4096,
        "cache_size": 2,
    }


def test_prompt_lookup_needs_settings() -> None:
    with pytest.raises(ValueError, match="num-assistant-tokens"):
        _opts(kv="u4", prompt_lookup=True)
    with pytest.raises(ValueError, match="need --prompt-lookup"):
        _opts(kv="u4", num_assistant_tokens=3)
    o = _opts(kv="u4", prompt_lookup=True, num_assistant_tokens=3, max_ngram_size=3)
    assert o["generation"] == {"num_assistant_tokens": 3, "max_ngram_size": 3}
    assert o["extra_properties"] == {"prompt_lookup": True}


def test_require_true_default_rules() -> None:
    o = _opts(require_true_default=True, cache_dir="C:/cache")
    assert o["compiled_readback"] and o["require_true_default"]
    assert o["scheduler_overrides"] is None and o["generation"] is None
    assert o["extra_properties"] == {"CACHE_DIR": "C:/cache"}
    with pytest.raises(ValueError, match="kv"):
        _opts(require_true_default=True, kv="u8")
    with pytest.raises(ValueError, match="sched"):
        _opts(require_true_default=True, sched_prefix_caching="on", sched_max_batched_tokens=4096)


def test_refuse_flags_without_openvino_backend() -> None:
    args = rh.build_argparser().parse_args(["--policy", "hybrid_full", "--debug-raw-text"])
    with pytest.raises(SystemExit, match="OpenVINO local backend"):
        rh.refuse_runtime_flags_without_openvino(args, rh.StubLocalBackend(script={}))


def _fake_ov(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    class _Core:
        def set_property(self, *_a: Any, **_k: Any) -> None:
            return None

        def get_property(self, _device: str, _name: str) -> str:
            return "dynamic"

    class _SchedulerConfig:
        def __init__(self) -> None:
            self.max_num_batched_tokens = 256
            self.enable_prefix_caching = False
            self.cache_size = 0

    ov = types.ModuleType("openvino")
    ov.Core = _Core  # type: ignore[attr-defined]
    ov.__version__ = "fake"  # type: ignore[attr-defined]
    genai = types.ModuleType("openvino_genai")
    genai.SchedulerConfig = _SchedulerConfig  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openvino", ov)
    monkeypatch.setitem(sys.modules, "openvino_genai", genai)

    import tools.bfcl_feasibility_probe as probe

    def _make(_g: Any, device: str, *args: Any, **kwargs: Any) -> str:
        seen["device"] = device
        seen["args"] = args
        seen["kwargs"] = kwargs
        os.write(1, PA_LOG.encode())
        return "pipe"

    monkeypatch.setattr(probe, "_make_llm_pipeline", _make)
    return seen


def test_load_default_path_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _fake_ov(monkeypatch)
    import tools.bfcl_feasibility_probe as probe

    pipe, meta, _ = probe.load_arm_pipeline("gpu_only", enable_prefix_caching=None)
    assert pipe == "pipe" and seen["args"] == () and seen["kwargs"] == {}
    assert "compiled_readback" not in meta["loads"][0]
    assert "extra_properties" not in meta["loads"][0]


def test_load_with_options(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _fake_ov(monkeypatch)
    import tools.bfcl_feasibility_probe as probe

    _pipe, meta, _ = probe.load_arm_pipeline(
        "gpu_only",
        scheduler_overrides={"enable_prefix_caching": True, "max_num_batched_tokens": 4096},
        extra_properties={"CACHE_DIR": "c", "prompt_lookup": True},
        compiled_readback=True,
    )
    sc = seen["args"][0]["scheduler_config"]
    assert sc.max_num_batched_tokens == 4096 and sc.enable_prefix_caching is True
    assert seen["kwargs"] == {"CACHE_DIR": "c", "prompt_lookup": True}
    load = meta["loads"][0]
    assert load["compiled_readback"]["backend"] == "PA"
    assert load["compiled_readback"]["kv_cache_precision"] == "i8"
    assert meta["scheduler_config"]["source"] == "explicit_SchedulerConfig_full"
    with pytest.raises(ValueError, match="exclusive"):
        probe.load_arm_pipeline(
            "gpu_only",
            enable_prefix_caching=False,
            scheduler_overrides={"enable_prefix_caching": True, "max_num_batched_tokens": 1},
        )


def _backend(runtime: dict[str, Any], tmp_path: Path) -> rh.OpenVinoLocalBackend:
    obj = rh.OpenVinoLocalBackend.__new__(rh.OpenVinoLocalBackend)
    obj.runtime = runtime
    obj.telemetry_path = tmp_path / "local_turn_telemetry.jsonl"
    return obj


def _meta(kv: str, backend_log: str = PA_LOG, rt_override: bool = False) -> dict[str, Any]:
    cr = gr.parse_genai_load_log(backend_log.replace("i8", kv))
    cr["ir_rt_info"] = {"checked": True, "override": rt_override, "kv_cache_precision": None}
    return {"loads": [{"device": "GPU", "compiled_readback": cr}]}


def test_arm_a_stop_rule(tmp_path: Path) -> None:
    b = _backend({"require_true_default": True, "compiled_readback": True}, tmp_path)
    meta = _meta("i8")
    b._check_compiled_readback(meta)
    assert meta["true_default_verdict"]["valid"]
    with pytest.raises(SystemExit, match="ARM_A_INVALID"):
        _backend({"require_true_default": True}, tmp_path)._check_compiled_readback(_meta("u4"))
    fallback = "Falling back to SDPA backend\n" + PA_LOG
    with pytest.raises(SystemExit, match="SDPA"):
        _backend({"require_true_default": True}, tmp_path)._check_compiled_readback(
            _meta("i8", fallback)
        )


def test_readback_must_not_change_between_loads(tmp_path: Path) -> None:
    b = _backend({"compiled_readback": True}, tmp_path)
    b._check_compiled_readback(_meta("u4"))
    b._check_compiled_readback(_meta("u4"))
    with pytest.raises(SystemExit, match="changed between loads"):
        b._check_compiled_readback(_meta("i8"))


def test_telemetry_sidecar(tmp_path: Path) -> None:
    b = _backend({"debug_raw_text": True}, tmp_path)
    tm = {
        "prompt_tokens": 4000,
        "memory": {"peak_rss_mb": 1.0},
        "steps": [{"step": 0, "raw_text": "<tool_call>x</tool_call>", "ok": True, "wall_s": 1.0}],
    }
    b._write_telemetry("multi_turn_base_1\0hybrid_full", 0, tm)
    row = json.loads(b.telemetry_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["entry_id"] == "multi_turn_base_1" and row["policy"] == "hybrid_full"
    assert row["steps"][0]["raw_text"].startswith("<tool_call>")
    assert "ok" not in row["steps"][0]


def test_gpu_counter_parse_and_sampler() -> None:
    text = (
        "\\\\h\\gpu process memory(pid_12_luid_0x1_phys_0)\\shared usage=1048576\n"
        "\\\\h\\gpu process memory(pid_12_luid_0x1_phys_0)\\dedicated usage=0\n"
        "\\\\h\\gpu process memory(pid_12_luid_0x2_phys_0)\\shared usage=1048576\n"
    )
    assert tmem.parse_gpu_counter_lines(text) == {"shared_usage_mb": 2.0, "dedicated_usage_mb": 0.0}
    s = tmem.TurnMemorySampler(interval_s=0.01)
    s.start()
    rec = s.stop()
    assert rec["peak_rss_mb"] > 0 and "end_rss_mb" in rec


def test_new_modules_ascii() -> None:
    for rel in ("seam/genai_runtime.py", "seam/turn_memory.py"):
        (ROOT / rel).read_bytes().decode("ascii")


def test_session_hooks_are_guarded_and_ordered() -> None:
    src = (ROOT / "tools" / "bfcl_feasibility_probe.py").read_text(encoding="utf-8")
    body = src[src.index("def run_user_turn") :]
    apply = body.index("for key, value in self.gen_cfg_extra.items():")
    assert apply < body.index("timed = _timed_generate(pipe, ov_genai, gen_input, cfg_use)")
    assert "if self.debug_raw_text:\n                # Debug only" in body
    assert (
        "if self.turn_telemetry is not None:\n            # Present only with --mem-telemetry"
        in body
    )
    assert body.index("self.turn_telemetry.start()") < body.index("t_turn0 = time.perf_counter()")


def test_fixture_run_refuses_runner_flags(tmp_path: Path) -> None:
    fix = {
        "entries": [{"id": "e", "question": [[]], "n_user_turns": 1}],
        "local_script": {"e": [{"n_ctx": 100, "ttft_s": 0.1, "decode_tok_s": 30.0}]},
    }
    path = tmp_path / "fix.json"
    path.write_text(json.dumps(fix), encoding="utf-8")
    argv = ["--policy", "hybrid_full", "--fixture", str(path), "--out", str(tmp_path / "o")]
    argv += ["--max-usd", "1", "--allow-dirty", "--mem-telemetry"]
    with pytest.raises(SystemExit, match="OpenVINO local backend"):
        rh.main(argv)


def test_launcher_passes_new_flags() -> None:
    text = (ROOT / "tools" / "launch_h1.ps1").read_text(encoding="utf-8")
    for flag in (
        "--cache-dir",
        "--compiled-readback",
        "--require-true-default",
        "--sched-prefix-caching",
        "--sched-max-batched-tokens",
        "--sched-cache-size",
        "--prompt-lookup",
        "--num-assistant-tokens",
        "--max-ngram-size",
        "--mem-telemetry",
        "--gpu-mem-counters",
        "--debug-raw-text",
        "--confirmation-run",
    ):
        assert f"' {flag}" in text, flag


def test_pilot_overrides_default_off() -> None:
    from tools import boot4_session as b4

    assert b4.SCHEDULER_OVERRIDE is None and b4._resident_high() == b4.RESIDENT_HIGH
    b4.set_pilot_overrides(
        scheduler={"enable_prefix_caching": True, "max_num_batched_tokens": 4096},
        resident_high=45000,
    )
    try:
        assert b4._resident_high() == 45000
        assert b4.SCHEDULER_OVERRIDE == {
            "enable_prefix_caching": True,
            "max_num_batched_tokens": 4096,
        }
    finally:
        b4.set_pilot_overrides()
    assert b4.SCHEDULER_OVERRIDE is None and b4._resident_high() == b4.RESIDENT_HIGH
    src = (ROOT / "seam" / "tools" / "_delta_n_child.py").read_text(encoding="utf-8")
    assert "pipes[device] = ov_genai.LLMPipeline(model_dir, device, **properties)" in src
    assert 'sched_spec = spec.get("scheduler_config")' in src
