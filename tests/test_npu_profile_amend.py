"""NPU-1 amendment 2026-10-07: key, capacity probes, single template.

Hardware-free. openvino and openvino_genai are replaced by fakes.
"""

from __future__ import annotations

import builtins
import io
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.run_npu_profile as rnp  # noqa: E402

CHECK_MSG = (
    "Check 'data->input_ids.get_size() <= m_max_prompt_len' failed at x:367:\n"
    "Stateful LLM pipeline on NPU may only process prompts or hold chat history up to "
    "{cap} tokens. {n} is passed.\n"
)


class _Cfg:
    def __init__(self) -> None:
        self.max_new_tokens = 0
        self.do_sample = True
        self.apply_chat_template = True


class _StreamerBase:
    def __init__(self) -> None:
        pass


class _Ttft:
    mean = 1300.0


class _Metrics:
    def __init__(self, n_in: int) -> None:
        self.n_in = n_in

    def get_num_input_tokens(self) -> int:
        return self.n_in

    def get_num_generated_tokens(self) -> int:
        return 8

    def get_ttft(self) -> _Ttft:
        return _Ttft()


class _Decoded:
    def __init__(self, text: str, n_in: int) -> None:
        self.texts = [text]
        self.perf_metrics = _Metrics(n_in)


def _n(prompt: str) -> int:
    return int(prompt[1:])


class _Pipe:
    """Accepts up to ``cap`` tokens; reports ``n + extra`` input tokens."""

    def __init__(self, cap: int, *, extra: int = 0, text: str = "a b c d e f g h") -> None:
        self.cap, self.extra, self.text = cap, extra, text
        self.calls: list[tuple[Any, Any]] = []

    def generate(self, inputs: Any, cfg: Any, streamer: Any) -> Any:
        self.calls.append((inputs, cfg))
        if not isinstance(inputs, list):
            return self.text
        n = _n(inputs[0])
        if n > self.cap:
            raise RuntimeError(CHECK_MSG.format(cap=self.cap, n=n))
        for _ in range(3):
            streamer.write(1)
        return _Decoded(self.text, n + self.extra)


def _fake_genai(pipes: dict[str, Any], loads: list[tuple[str, dict]]) -> types.ModuleType:
    mod = types.ModuleType("openvino_genai")
    mod.GenerationConfig = _Cfg
    mod.StreamerBase = _StreamerBase
    mod.StreamingStatus = types.SimpleNamespace(RUNNING=0)

    def pipeline(path: str, device: str, **props: Any) -> Any:
        loads.append((device, props))
        return pipes[device]

    mod.LLMPipeline = pipeline
    mod.Tokenizer = lambda _path: object()
    return mod


def _fake_ov() -> types.ModuleType:
    mod = types.ModuleType("openvino")

    class Core:
        def get_property(self, device: str, name: str) -> Any:
            return 1024

    mod.Core = Core
    return mod


# ---------------------------------------------------------------- units


def test_load_key_is_max_prompt_len_with_min_response_len() -> None:
    props = rnp.npu_load_props(2048, 1024)
    assert props == {
        "NPUW_LLM_PREFILL_CHUNK_SIZE": 1024,
        "MAX_PROMPT_LEN": 2048,
        "MIN_RESPONSE_LEN": 8,
    }
    assert "NPUW_LLM_MAX_PROMPT_LEN" not in props


def test_generation_config_is_single_template_greedy() -> None:
    cfg = rnp.generation_config(types.SimpleNamespace(GenerationConfig=_Cfg))
    assert (cfg.apply_chat_template, cfg.do_sample, cfg.max_new_tokens) == (False, False, 8)


def test_generate_once_uses_list_form_and_pipeline_count() -> None:
    genai = _fake_genai({}, [])
    pipe = _Pipe(1024, extra=0)
    row = rnp.generate_once(genai, pipe, "P900")
    inputs, cfg = pipe.calls[0]
    assert inputs == ["P900"]
    assert cfg.apply_chat_template is False
    assert row["prompt_tokens"] == 900
    assert row["prefill_s"] is not None


def test_generate_once_reports_no_count_when_pipeline_does_not() -> None:
    genai = _fake_genai({}, [])

    class StrPipe(_Pipe):
        def generate(self, inputs: Any, cfg: Any, streamer: Any) -> Any:
            return "text"

    row = rnp.generate_once(genai, StrPipe(1024), "P900")
    assert row["prompt_tokens"] is None
    assert row["metric_error"] is not None


def test_generate_once_flags_length_check_refusal() -> None:
    row = rnp.generate_once(_fake_genai({}, []), _Pipe(1024), "P1100")
    assert row["ok"] is False
    assert row["length_check_refusal"] is True


def _probe(pipe: _Pipe, cap: int) -> dict[str, Any]:
    genai = _fake_genai({}, [])
    return rnp.capacity_probe(
        cap=cap,
        build_prompt=lambda n: f"P{n}",
        count_tokens=_n,
        generate=lambda prompt: rnp.generate_once(genai, pipe, prompt),
    )


def test_capacity_probe_accepts_when_cap_applied() -> None:
    res = _probe(_Pipe(2048), 2048)
    assert res["passed"] is True
    assert res["P1"]["target_tokens"] == 1984
    assert res["P1"]["pipeline_input_tokens"] == 1984
    assert res["P2"]["target_tokens"] == 2112
    assert res["P2"]["length_check_refusal"] is True
    assert res["timed"] is False


def test_capacity_probe_refuses_when_setting_did_not_apply() -> None:
    res = _probe(_Pipe(1024), 2048)
    assert res["passed"] is False
    assert res["P1"]["pass"] is False
    assert res["P1"]["ok"] is False


def test_capacity_probe_refuses_when_cap_is_larger_than_requested() -> None:
    res = _probe(_Pipe(4096), 2048)
    assert res["P1"]["pass"] is True
    assert res["P2"]["pass"] is False
    assert res["passed"] is False


def test_capacity_probe_refuses_double_template_count() -> None:
    res = _probe(_Pipe(4096, extra=8), 2048)
    assert res["P1"]["pass"] is False


def test_capacity_probe_refuses_invalid_output() -> None:
    res = _probe(_Pipe(2048, text="a b a b a b a b a b"), 2048)
    assert res["P1"]["valid"] is False
    assert res["passed"] is False


def test_capacity_probe_p2_other_error_is_not_the_length_check() -> None:
    class Boom(_Pipe):
        def generate(self, inputs: Any, cfg: Any, streamer: Any) -> Any:
            if _n(inputs[0]) > self.cap:
                raise RuntimeError("std::bad_alloc")
            return super().generate(inputs, cfg, streamer)

    res = _probe(Boom(2048), 2048)
    assert res["P2"]["pass"] is False
    assert res["passed"] is False


# ---------------------------------------------------------------- run_hardware


def _run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, npu: _Pipe, extra_args: list[str]
) -> tuple[int, dict[str, Any], dict[str, Any], list[tuple[str, dict]]]:
    loads: list[tuple[str, dict]] = []
    gpu = _Pipe(10**6)
    monkeypatch.setitem(sys.modules, "openvino_genai", _fake_genai({"NPU": npu, "GPU": gpu}, loads))
    monkeypatch.setitem(sys.modules, "openvino", _fake_ov())
    monkeypatch.setattr(rnp, "load_local_spec", lambda _path: {"ir_dir": str(tmp_path)})
    monkeypatch.setattr(rnp, "_filler", lambda: "x")
    monkeypatch.setattr(
        rnp, "rendered_exact_prompt", lambda _tok, n, unit, salt: f"P{n}" if unit and salt else ""
    )
    monkeypatch.setattr(rnp, "id_count", lambda _tok, text: _n(text))
    out = tmp_path / "run"
    code = rnp.main(
        [
            "--cell",
            "npu1-setting",
            "--out",
            str(out),
            "--model-spec",
            str(tmp_path / "spec.yaml"),
            "--no-canary",
            *extra_args,
        ]
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    return code, plan, summary, loads


def test_run_refuses_capacity_when_setting_not_applied(monkeypatch, tmp_path) -> None:
    code, plan, summary, loads = _run(
        monkeypatch, tmp_path, _Pipe(1024), ["--max-prompt-len", "2048"]
    )
    assert code == 1
    assert summary["status"] == "REFUSED_CAPACITY"
    assert summary["generated"] is False and summary["timed"] is False
    assert summary["capacity_check"]["P1"]["pass"] is False
    assert summary["max_prompt_len_readback"] == 1024
    assert loads[0] == ("NPU", rnp.npu_load_props(2048, 1024))
    assert plan["max_prompt_len_property"] == "MAX_PROMPT_LEN"


def test_run_load_only_passes_capacity(monkeypatch, tmp_path) -> None:
    code, plan, summary, _ = _run(
        monkeypatch, tmp_path, _Pipe(2048), ["--max-prompt-len", "2048", "--load-only"]
    )
    assert code == 0
    assert summary["status"] == "loaded_bisect_deferred"
    assert summary["capacity_check"]["passed"] is True
    assert summary["max_prompt_len"] == 2048
    # The device-default readback no longer refuses.
    assert summary["max_prompt_len_readback"] == 1024


def test_run_bisection_prompt_length_is_pipeline_count(monkeypatch, tmp_path) -> None:
    npu = _Pipe(256)
    code, plan, summary, _ = _run(
        monkeypatch, tmp_path, npu, ["--max-prompt-len", "256", "--low", "64", "--resolution", "64"]
    )
    assert code == 0, summary
    assert summary["status"] == "complete"
    rows = [r for rung in summary["rungs"] for r in rung["repeats"]]
    assert rows and all(r["prompt_length"] == r["n_tokens"] for r in rows)
    assert all(r["max_prompt_len"] == 256 for r in rows)
    assert all(cfg.apply_chat_template is False for _, cfg in npu.calls)
    assert all(isinstance(inputs, list) for inputs, _ in npu.calls)


def test_run_does_not_time_when_count_missing(monkeypatch, tmp_path) -> None:
    class NoCount(_Pipe):
        calls_seen = 0

        def generate(self, inputs: Any, cfg: Any, streamer: Any) -> Any:
            out = super().generate(inputs, cfg, streamer)
            NoCount.calls_seen += 1
            if NoCount.calls_seen > 1 and isinstance(out, _Decoded):  # after P1
                out.perf_metrics = None
            return out

    code, plan, summary, _ = _run(
        monkeypatch, tmp_path, NoCount(128), ["--max-prompt-len", "128", "--low", "64"]
    )
    rows = [r for rung in summary["rungs"] for r in rung["repeats"]]
    assert rows and all(r["timed"] is False for r in rows)
    assert {r["reason"] for r in rows} == {"prompt_length_not_reported"}


def test_runner_never_opens_prereg_or_amendment(monkeypatch, tmp_path) -> None:
    real_open = builtins.open
    opened: list[str] = []

    def guarded(file, *args, **kwargs):
        text = str(file).replace("\\", "/")
        name = text.rsplit("/", 1)[-1].upper()
        opened.append(text)
        if "/docs/amendments/" in text.lower() or (
            "/derived/" in text.lower()
            and any(t in name for t in ("PREREG", "PREDICTIONS", "AMEND", "RULE"))
        ):
            raise AssertionError(f"runner opened {file}")
        if "NPU_PROTOCOL" in name:
            raise AssertionError(f"runner opened {file}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded)
    monkeypatch.setattr(io, "open", guarded)
    code, _, summary, _ = _run(
        monkeypatch, tmp_path, _Pipe(256), ["--max-prompt-len", "256", "--low", "64"]
    )
    assert code == 0, summary
    source = (ROOT / "tools" / "run_npu_profile.py").read_text(encoding="utf-8")
    for token in ("NPU1_PREREG", "NPU_AMEND", "docs/amendments"):
        assert token not in source
