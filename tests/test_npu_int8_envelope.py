"""NPU amendment 2026-10-13b: the int8 envelope path of run_npu_profile.

Hardware-free. openvino and openvino_genai are replaced by fakes. The int4
default path is covered by test_npu_profile*.py and must stay unchanged.
"""

from __future__ import annotations

import builtins
import hashlib
import io
import json
import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.npu_natstop as natstop  # noqa: E402
import tools.run_npu_profile as rnp  # noqa: E402

AMENDMENT = ROOT / "docs" / "amendments" / "NPU_AMEND_2026-10-13b_INT8_ENVELOPE.md"
LAUNCHER = ROOT / "tools" / "launch_boot1.ps1"
T2S_LAUNCHER = ROOT / "tools" / "launch_t2s_npu1.ps1"
INT8_SPEC = ROOT / "configs" / "models" / "Qwen3-4B-int8-ov.yaml"


# ---------------------------------------------------------------- constants


def test_constants_match_the_amendment() -> None:
    text = AMENDMENT.read_text(encoding="utf-8")
    assert "K = 62" in text and rnp.VALID_MIN_REAL_TOKENS == 62
    assert "T = 27/61" in text and rnp.VALID_REPEAT_MAX == 27 / 61
    assert rnp.VALID_MIN_REAL_TOKENS == natstop.VALID_MIN_REAL_TOKENS
    assert rnp.VALID_REPEAT_MAX == natstop.VALID_REPEAT_MAX
    assert f'"{rnp.CONTENT_QUESTION}"' in " ".join(text.split())
    assert natstop.CHAT_PROMPTS["chat1"] == rnp.CONTENT_QUESTION
    assert rnp.CONTENT_KEYWORD == natstop.CHAT1_KEYWORD == "paris"
    assert "max_new_tokens 64" in text and rnp.ENVELOPE_MAX_NEW_TOKENS == 64
    assert "max_new_tokens 1" in text and rnp.ENVELOPE_TIMING_MAX_NEW_TOKENS == 1
    assert "Bisection high is S - 64" in text and rnp.envelope_high(2048) == 1984
    assert "MIN_RESPONSE_LEN 8" in text and rnp.MIN_RESPONSE_LEN == 8


def test_estimates_match_the_amendment_table() -> None:
    text = AMENDMENT.read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\| (\d+) \| envelope \| (\d+) s \|$", text, flags=re.M))
    assert {int(k): int(v) for k, v in rows.items()} == {
        s: rnp.envelope_estimate_s(s) for s in (1024, 2048, 4096, 8192)
    }
    lo = dict(re.findall(r"^\| (\d+) \| load-only[^|]*\| (\d+) s \|$", text, flags=re.M))
    assert {int(k): int(v) for k, v in lo.items()} == {
        s: rnp.envelope_load_only_estimate_s(s) for s in (16384, 32768)
    }
    assert "9027 s" in text and rnp.envelope_estimate_s(16384) == 9027
    assert rnp.envelope_estimate_s(16384) > rnp.SESSION_BUDGET_S
    for s, ttft in ((1024, "4.27"), (2048, "8.93"), (4096, "21.08"), (8192, "51.39")):
        assert f"{rnp.envelope_ttft_estimate_s(rnp.envelope_high(s)):.2f}" == ttft
        assert f"| {s} | {rnp.envelope_high(s)} | {ttft} s |" in text


# ---------------------------------------------------------------- units


def _gen(**kw: Any) -> dict[str, Any]:
    base = {
        "generate_returned": True,
        "realized_tokens": 100,
        "pipeline_input_tokens": 100,
        "stop": "max",
        "real_token_count": 64,
        "id_repeat_fraction": 0.0,
        "generated_ids": list(range(64)),
        "text": "words",
    }
    base.update(kw)
    return base


def test_validity_rule() -> None:
    assert rnp.envelope_valid(_gen(), _gen())["valid"] is True
    assert rnp.envelope_valid(_gen(real_token_count=61), _gen())["reason"] == "too_few_real_tokens"
    # A GPU that stopped by EOS after 7 real tokens sets the floor to 7.
    short_ref = _gen(stop="EOS", real_token_count=7)
    assert rnp.envelope_valid(_gen(stop="EOS", real_token_count=7), short_ref)["valid"] is True
    assert rnp.envelope_valid(_gen(real_token_count=6), short_ref)["valid"] is False
    assert rnp.envelope_valid(_gen(id_repeat_fraction=0.45), _gen())["reason"] == "id_4gram_repeat"
    assert rnp.envelope_valid(_gen(id_repeat_fraction=27 / 61), _gen())["valid"] is True
    bad_count = _gen(pipeline_input_tokens=108)
    assert rnp.envelope_valid(bad_count, _gen())["reason"] == "input_count_mismatch"
    assert rnp.envelope_valid(_gen(generate_returned=False), _gen())["valid"] is False
    # Floor never below 1.
    zero_ref = _gen(stop="EOS", real_token_count=0)
    assert rnp.envelope_valid(_gen(real_token_count=0), zero_ref)["valid"] is False


def test_real_token_count_skips_stops_think_tags_and_whitespace() -> None:
    pieces = {1: "<think>", 2: "\n", 3: "Paris", 4: "</think>", 5: " is", 9: "eos"}
    assert rnp.real_token_count([1, 2, 3, 4, 5, 9], [9], lambda t: pieces[t]) == 2


def _rung(n: int, *, passes: bool, valid: bool = True) -> dict[str, Any]:
    return {"n_tokens": n, "slo_pass": passes, "valid": valid, "validity": {"npu": {}}}


def test_binding_categories() -> None:
    cap = rnp.envelope_binding(rungs=[_rung(64, passes=True), _rung(960, passes=True)], high=960)
    assert cap["binding"] == "TOOLCHAIN_CAP" and cap["ttft_limit_n"] == 960
    lat = rnp.envelope_binding(
        rungs=[
            _rung(64, passes=True),
            _rung(4032, passes=False),
            _rung(2048, passes=True),
            _rung(3008, passes=False),
            _rung(2112, passes=False),
        ],
        high=4032,
    )
    assert lat == {
        "binding": "LATENCY",
        "ttft_limit_n": 2048,
        "deciding_rung": 2112,
        "decode_tok_s_at_limit": None,
    }
    val = rnp.envelope_binding(
        rungs=[_rung(64, passes=True), _rung(1984, passes=False, valid=False)], high=1984
    )
    assert val["binding"] == "VALIDITY" and val["ttft_limit_n"] == 64
    none = rnp.envelope_binding(rungs=[_rung(64, passes=False, valid=False)], high=960)
    assert none["binding"] == "VALIDITY" and none["ttft_limit_n"] is None


def test_content_outcome() -> None:
    gpu = _gen(stop="EOS", real_token_count=7, text="The capital of France is Paris.")
    npu_ok = _gen(stop="EOS", real_token_count=7, text="The capital of France is Paris.")
    npu_bad = _gen(stop="EOS", real_token_count=7, text="The capital of France is Lyon.")
    assert rnp.content_outcome(npu_ok, gpu) == "CONTENT_OK"
    assert rnp.content_outcome(npu_bad, gpu) == "CONTENT_FAIL"
    assert rnp.content_outcome(npu_ok, npu_bad) == "CONTENT_REFERENCE_UNUSABLE"
    assert rnp.content_outcome(_gen(text="<think>paris</think>"), _gen(text="Paris"))
    nolimit = rnp.run_content_check(
        limit=None,
        build=str,
        npu_generate=dict,
        gpu_generate=dict,
        npu_stops=[],
        gpu_stops=[],
        decode=str,
    )
    assert nolimit["outcome"] == "NO_LIMIT"


def test_content_prompt_is_exact_and_ends_with_the_question(monkeypatch) -> None:
    monkeypatch.setattr(rnp, "render_user", lambda _tok, text: f"<u>{text}</u>")
    monkeypatch.setattr(rnp, "id_count", lambda _tok, text: len(text.split()))
    prompt = rnp.content_prompt(None, 40, unit="filler ", salt="npu")
    assert len(prompt.split()) == 40
    assert prompt.endswith("\n\n" + rnp.CONTENT_QUESTION + "</u>")
    assert prompt.startswith("<u>npu ")


def test_ir_refusal() -> None:
    good = {"xml_present": True, "xml_matches_pin": True, "summary": {"mode": "INT8_ASYM"}}
    assert rnp.envelope_ir_refusal(good) is None
    assert "pin" in rnp.envelope_ir_refusal({**good, "xml_matches_pin": False})
    assert "absent" in rnp.envelope_ir_refusal({**good, "xml_present": False})
    assert "INT4_SYM" in rnp.envelope_ir_refusal({**good, "summary": {"mode": "INT4_SYM"}})


# ---------------------------------------------------------------- run_hardware


class _Cfg:
    def __init__(self) -> None:
        self.max_new_tokens = 0
        self.do_sample = True
        self.apply_chat_template = True


class _StreamerBase:
    def __init__(self) -> None:
        pass


class _Metrics:
    def __init__(self, n_in: int, n_out: int) -> None:
        self.n_in, self.n_out = n_in, n_out

    def get_num_input_tokens(self) -> int:
        return self.n_in

    def get_num_generated_tokens(self) -> int:
        return self.n_out

    def get_ttft(self) -> Any:
        return types.SimpleNamespace(mean=1300.0)


class _Decoded:
    def __init__(self, text: str, n_in: int, n_out: int) -> None:
        self.texts = [text]
        self.perf_metrics = _Metrics(n_in, n_out)


def _n(prompt: str) -> int:
    return int(prompt[1:])


class _Pipe:
    """Writes max_new_tokens distinct ids; the content prompt (Q...) answers Paris."""

    def __init__(self, cap: int, *, answer: str = "The capital of France is Paris.") -> None:
        self.cap, self.answer = cap, answer
        self.calls: list[tuple[str, Any]] = []

    def get_generation_config(self) -> Any:
        return types.SimpleNamespace(eos_token_id=151645, stop_token_ids=[151643, 151645])

    def generate(self, inputs: Any, cfg: Any, streamer: Any) -> Any:
        prompt = inputs[0]
        self.calls.append((prompt, cfg))
        n = _n(prompt)
        if n > self.cap:
            raise RuntimeError("input_ids.get_size() <= m_max_prompt_len failed")
        if prompt.startswith("Q"):
            for token in range(1, 8):
                streamer.write(1000 + token)
            streamer.write(151645)
            return _Decoded(self.answer, n, 8)
        count = int(cfg.max_new_tokens)
        for token in range(count):
            streamer.write(1000 + token)
        return _Decoded("w " * count, n, count)


class _Tok:
    def decode(self, ids: list[int]) -> str:
        return "" if ids[0] in (151643, 151645) else "w"


def _fake_genai(pipes: dict[str, Any], loads: list[tuple[str, dict]]) -> types.ModuleType:
    mod = types.ModuleType("openvino_genai")
    mod.GenerationConfig = _Cfg
    mod.StreamerBase = _StreamerBase
    mod.StreamingStatus = types.SimpleNamespace(RUNNING=0)

    def pipeline(path: str, device: str, **props: Any) -> Any:
        loads.append((device, props))
        return pipes[device]

    mod.LLMPipeline = pipeline
    mod.Tokenizer = lambda _path: _Tok()
    return mod


def _fake_ov() -> types.ModuleType:
    mod = types.ModuleType("openvino")

    class Core:
        def get_property(self, device: str, name: str) -> Any:
            return 1024

    mod.Core = Core
    return mod


def _ir(tmp_path: Path, etype: str = "u8") -> tuple[Path, str]:
    ir = tmp_path / "ir"
    ir.mkdir()
    xml = (
        '<?xml version="1.0"?><net name="m" version="11"><layers>'
        f'<layer id="0" name="w" type="Const"><data element_type="{etype}" shape="64,32"/></layer>'
        f'<layer id="1" name="z" type="Const"><data element_type="{etype}" shape="64,1"/></layer>'
        "</layers></net>"
    )
    (ir / "openvino_model.xml").write_text(xml, encoding="utf-8")
    return ir, hashlib.sha256(xml.encode("utf-8")).hexdigest()


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    npu: _Pipe,
    extra: list[str],
    *,
    etype: str = "u8",
    pin: str | None = None,
) -> tuple[int, dict[str, Any], dict[str, Any], list[tuple[str, dict]]]:
    loads: list[tuple[str, dict]] = []
    gpu = _Pipe(10**6)
    ir, digest = _ir(tmp_path, etype)
    spec = {"ir_dir": str(ir), "ir_files": {"openvino_model.xml": pin or digest}}
    monkeypatch.setitem(sys.modules, "openvino_genai", _fake_genai({"NPU": npu, "GPU": gpu}, loads))
    monkeypatch.setitem(sys.modules, "openvino", _fake_ov())
    monkeypatch.setattr(rnp, "load_local_spec", lambda _path: spec)
    monkeypatch.setattr(rnp, "_filler", lambda: "x")
    monkeypatch.setattr(rnp, "rendered_exact_prompt", lambda _tok, n, **_kw: f"P{n}")
    monkeypatch.setattr(rnp, "content_prompt", lambda _tok, n, **_kw: f"Q{n}")
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
            "--envelope",
            *extra,
        ]
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    return code, plan, summary, loads


def test_envelope_session_end_to_end(monkeypatch, tmp_path) -> None:
    real_open = builtins.open

    def guarded(file, *args, **kwargs):
        text = str(file).replace("\\", "/").lower()
        if "/docs/amendments/" in text or "npu_amend" in text:
            raise AssertionError(f"runner opened {file}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded)
    monkeypatch.setattr(io, "open", guarded)
    npu = _Pipe(256)
    code, plan, summary, loads = _run(monkeypatch, tmp_path, npu, ["--max-prompt-len", "256"])
    assert code == 0, summary
    assert summary["status"] == "complete"
    assert plan["weight_precision"] == "int8"
    assert plan["ir_quantization"]["summary"]["mode"] == "INT8_ASYM"
    assert plan["ir_quantization"]["xml_matches_pin"] is True
    assert loads[0] == ("NPU", rnp.npu_load_props(256, 1024))
    assert summary["max_prompt_len"] == 192  # high = S - 64
    assert summary["binding"] == "TOOLCHAIN_CAP" and summary["ttft_limit_n"] == 192
    assert summary["capacity_check"]["envelope_passed"] is True
    rungs = summary["rungs"]
    assert {r["n_tokens"] for r in rungs} == {64, 192}
    for rung in rungs:
        kinds = [r["kind"] for r in rung["repeats"]]
        assert kinds == ["validity", "timing", "timing"]
        assert rung["valid"] is True and rung["validity"]["exact_match_vs_gpu"] is True
        assert rung["validity"]["npu"]["real_token_count"] == 64
    sizes = [cfg.max_new_tokens for prompt, cfg in npu.calls if prompt.startswith("P")]
    # P1 and P2 (8, forced, as 2026-10-07), then per rung 64, 1, 1.
    assert sizes == [8, 8, 64, 1, 1, 64, 1, 1]
    rung_cfgs = [cfg for prompt, cfg in npu.calls[2:] if prompt.startswith("P")]
    assert all(not hasattr(cfg, "min_new_tokens") for cfg in rung_cfgs)
    assert summary["content_check"]["outcome"] == "CONTENT_OK"
    assert summary["content_check"]["n_tokens"] == 192
    assert summary["limit_citable"] is False  # --no-canary: not armed
    assert summary["over_max"]["weight_precision"] == "int8"


def test_envelope_rung_not_valid_skips_timing(monkeypatch, tmp_path) -> None:
    class Short(_Pipe):
        def generate(self, inputs: Any, cfg: Any, streamer: Any) -> Any:
            if inputs[0].startswith("P") and int(cfg.max_new_tokens) == 64:
                self.calls.append((inputs[0], cfg))
                streamer.write(151645)
                return _Decoded("", _n(inputs[0]), 1)
            return super().generate(inputs, cfg, streamer)

    code, _plan, summary, _ = _run(monkeypatch, tmp_path, Short(256), ["--max-prompt-len", "256"])
    assert code == 0, summary
    assert summary["binding"] == "VALIDITY" and summary["ttft_limit_n"] is None
    rows = summary["rungs"][0]["repeats"]
    assert [r["reason"] for r in rows] == [
        "too_few_real_tokens",
        "rung_not_valid",
        "rung_not_valid",
    ]
    assert summary["content_check"]["outcome"] == "NO_LIMIT"


def test_envelope_refuses_unpinned_or_int4_ir(monkeypatch, tmp_path) -> None:
    code, _plan, summary, loads = _run(
        monkeypatch, tmp_path, _Pipe(256), ["--max-prompt-len", "256"], pin="0" * 64
    )
    assert code == 1 and summary["status"] == "REFUSED_IR" and loads == []
    other = tmp_path / "b"
    other.mkdir()
    code, _plan, summary, loads = _run(
        monkeypatch, other, _Pipe(256), ["--max-prompt-len", "256"], etype="i4"
    )
    assert code == 1 and "INT4" in summary["detail"] and loads == []


def test_envelope_load_only(monkeypatch, tmp_path) -> None:
    code, _plan, summary, _ = _run(
        monkeypatch, tmp_path, _Pipe(16384), ["--max-prompt-len", "16384", "--load-only"]
    )
    assert code == 0 and summary["status"] == "loaded_bisect_deferred"
    assert summary["bisect_estimate_s"] == rnp.envelope_estimate_s(16384)


def test_envelope_refused_on_npu2_cell(tmp_path) -> None:
    with pytest.raises(SystemExit, match="npu1-setting only"):
        rnp.main(
            [
                "--cell",
                "npu2-load",
                "--out",
                str(tmp_path),
                "--model-spec",
                str(INT8_SPEC),
                "--envelope",
            ]
        )


# ---------------------------------------------------------------- launchers


def test_launchers_pass_model_spec_and_envelope_with_int4_default() -> None:
    t2s = T2S_LAUNCHER.read_text(encoding="utf-8")
    assert '[string]$ModelSpec = ""' in t2s and "[switch]$Envelope" in t2s
    assert '$launchArgs += @("-ModelSpec", $ModelSpec)' in t2s
    assert '$launchArgs += "-Envelope"' in t2s
    boot = LAUNCHER.read_text(encoding="utf-8")
    assert '[string]$ModelSpec = ""' in boot and "[switch]$Envelope" in boot
    assert '$int4 = "configs\\models\\Qwen3-4B-int4-ov.yaml"' in boot
    assert "$npuModel = $int4" in boot
    assert "Model = $npuModel; MaxPromptLen = $n" in boot
    assert "REFUSED -- -Envelope needs -ModelSpec other than" in boot
    assert "runs only with -Envelope" in boot
    assert boot.count('Name "Envelope") { $workerArgs += "--envelope" }') == 1
    assert boot.count('Name "Envelope") { $args += "--envelope" }') == 1
    assert 'if ($ModelSpec) { $cmd += " -ModelSpec' in boot
    assert "envelope_estimate_s($n)" in boot and "envelope_load_only_estimate_s($n)" in boot
    for text in (t2s, boot):
        assert "NPU_AMEND" not in text and "docs/amendments" not in text
