"""NPU-FORMAT-F1 (amendment 2026-10-13): content check, FA/FB/FC, --model-spec,
IR quantization metadata read from the IR.

Hardware-free. No IR is needed: synthetic IR xml files stand in.
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

import tools.npu_natstop as ns  # noqa: E402
from seam.ir_quantization import ir_quantization  # noqa: E402

AMEND = ROOT / "docs" / "amendments" / "NPU_AMEND_2026-10-13_FORMAT.md"
LAUNCHER = ROOT / "tools" / "launch_t2s_natstop.ps1"
INT4_SPEC = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
INT8_SPEC = ROOT / "configs" / "models" / "Qwen3-4B-int8-ov.yaml"
SEALED_B = ROOT / "derived" / "npu" / "sealed_natstop_b_78fc3478-67bf-44b5-bb50-7d5f476dc43b"

TIPS = (
    "1. **Create a Dedicated Study Space**: pick a quiet area.\n\n"
    "2. **Use the Pomodoro Technique**: study in focused intervals."
)


def _cell(device: str, template: str, prompt: str, **over: Any) -> dict[str, Any]:
    cell: dict[str, Any] = {
        "device": device,
        "template": template,
        "n_tokens": None,
        "prompt_id": prompt,
        "complete": True,
        "child_exit_code": 0,
        "load_error": None,
        "generate_returned": True,
        "realized_tokens": 20,
        "pipeline_input_tokens": 20 + (8 if template == "DOUBLE" else 0),
        "text": "Paris is the capital of France." if prompt == "chat1" else TIPS,
        "generated_ids": list(range(1000, 1064)),
        "completion_tokens": 64,
        "real_token_count": 64,
    }
    cell.update(over)
    return cell


EOS_FIRST = {"text": "", "generated_ids": [151645], "completion_tokens": 1, "real_token_count": 0}
COUNTING = {"text": "1\n\n2\n\n3\n\n4\n\n5", "real_token_count": 40}


def _cells(npu_single: dict | None = None, npu_double: dict | None = None, **gpu: Any):
    out: dict[str, Any] = {}
    for p in ns.CHAT_PROMPTS:
        for t in ns.TEMPLATES:
            out[ns.cell_key("GPU", t, p)] = _cell("GPU", t, p, **gpu.get(t.lower(), {}))
        out[ns.cell_key("NPU", "SINGLE", p)] = _cell("NPU", "SINGLE", p, **(npu_single or {}))
        out[ns.cell_key("NPU", "DOUBLE", p)] = _cell("NPU", "DOUBLE", p, **(npu_double or {}))
    return out


# ---------------------------------------------------------------- content check


def test_chat1_needs_paris_in_the_real_text() -> None:
    assert ns.content_ok("chat1", "Paris is the capital of France.")
    assert ns.content_ok("chat1", "<think>\nthe capital is PARIS</think>")
    assert not ns.content_ok("chat1", "1\n\n2\n\n3")
    assert not ns.content_ok("chat1", "")
    assert not ns.content_ok("chat1", None)


def test_chat2_needs_two_distinct_tip_lines_of_five_words() -> None:
    assert ns.content_ok("chat2", TIPS)
    assert ns.content_ok(
        "chat2", "- Put the phone in another room now\n* Take a short break every hour"
    )
    assert ns.content_ok(
        "chat2", "1) Set one clear goal per session\n\u2022 Turn off all the notifications"
    )
    assert ns.content_ok(
        "chat2",
        "### 1. Plan the session before you start\n2. Remove every distraction from the desk",
    )
    # one tip only, a duplicate, too few words, numerals only, bold text is not a bullet
    assert not ns.content_ok("chat2", "1. Create a dedicated study space")
    assert not ns.content_ok("chat2", "1. Take short breaks often\n2. Take   SHORT breaks often")
    assert not ns.content_ok("chat2", "1. Be calm\n2. Sleep well tonight")
    assert not ns.content_ok("chat2", "1\n\n2\n\n3\n\n4")
    assert not ns.content_ok(
        "chat2", "**Create a quiet study space now**\n**Use a timer for each block**"
    )
    assert not ns.content_ok("chat2", "<think>\nOkay, the user wants three tips. One common tip is")
    assert not ns.content_ok(None, TIPS)


def test_tip_words_need_a_letter() -> None:
    assert ns.tip_lines("1. 25 50 75 100 125\n2. 1 2 3 4 5") == []


# ---------------------------------------------------------------- FA / FB / FC


def test_fa_when_one_npu_template_passes_both_prompts() -> None:
    assert ns.classify_format(_cells(None, EOS_FIRST)) == "FA"
    assert ns.classify_format(_cells(EOS_FIRST, None)) == "FA"


def test_fb_when_every_npu_cell_runs_and_fails_and_gpu_single_passes() -> None:
    assert ns.classify_format(_cells(EOS_FIRST, EOS_FIRST)) == "FB"
    # form-valid but off-topic (the B3 counting cell) is a fail, not a pass
    assert ns.classify_format(_cells(COUNTING, EOS_FIRST)) == "FB"


def test_fc_when_an_npu_cell_does_not_run_past_load() -> None:
    cells = _cells(EOS_FIRST, EOS_FIRST)
    cells[ns.cell_key("NPU", "SINGLE", "chat2")].update(load_error="RuntimeError: x")
    assert ns.classify_format(cells) == "FC"
    cells = _cells(EOS_FIRST, EOS_FIRST)
    cells[ns.cell_key("NPU", "DOUBLE", "chat1")].update(child_exit_code=None, complete=False)
    assert ns.classify_format(cells) == "FC"


def test_fc_when_gpu_single_reference_fails_or_results_are_mixed() -> None:
    assert ns.classify_format(_cells(EOS_FIRST, EOS_FIRST, single={"text": "Lyon."})) == "FC"
    cells = _cells(EOS_FIRST, EOS_FIRST)
    cells[ns.cell_key("NPU", "SINGLE", "chat1")] = _cell("NPU", "SINGLE", "chat1")
    assert ns.classify_format(cells) == "FC"


def test_gpu_double_is_not_the_fb_reference() -> None:
    think = {"text": "<think>\nOkay, three tips. One common tip is"}
    assert ns.classify_format(_cells(EOS_FIRST, EOS_FIRST, double=think)) == "FB"


def test_rule_on_sealed_natstop_b_matches_the_amendment() -> None:
    summary = json.loads((SEALED_B / "summary.json").read_text(encoding="utf-8"))
    cells = summary["cells"]
    got = {
        key: ns.passes(cell, cells[ns.cell_key("GPU", cell["template"], cell["prompt_id"])])
        for key, cell in cells.items()
    }
    assert got == {
        "GPU_SINGLE_chat1": True,
        "GPU_SINGLE_chat2": True,
        "GPU_DOUBLE_chat1": True,
        "GPU_DOUBLE_chat2": False,
        "NPU_SINGLE_chat1": False,
        "NPU_SINGLE_chat2": False,
        "NPU_DOUBLE_chat1": False,
        "NPU_DOUBLE_chat2": False,
    }
    assert ns.valid(cells["NPU_SINGLE_chat1"], cells["GPU_SINGLE_chat1"])
    assert ns.classify_scope(cells) == "B3" == summary["verdict"]
    assert ns.classify_format(cells) == "FB"


def test_constants_are_the_amendment_text() -> None:
    text = AMEND.read_text(encoding="ascii")
    assert ns.TIP_LINE.pattern in text
    assert '"paris"' in text and ns.CHAT1_KEYWORD == "paris"
    assert "at least 5 words" in text and ns.TIP_MIN_WORDS == 5
    assert "at least 2 distinct tip lines" in text and ns.TIP_MIN_LINES == 2
    for verdict in ("FA", "FB", "FC"):
        assert f"- {verdict}:" in text
    for prompt in ns.CHAT_PROMPTS.values():
        assert prompt in text


def test_runner_and_launcher_never_name_the_amendment() -> None:
    for path in (ROOT / "tools" / "npu_natstop.py", LAUNCHER, ROOT / "seam" / "ir_quantization.py"):
        text = path.read_text(encoding="ascii")
        assert "NPU_AMEND_2026-10-13" not in text and "FORMAT.md" not in text


# ---------------------------------------------------------------- model spec


def test_int4_default_is_unchanged() -> None:
    assert ns.DEFAULT_MODEL_SPEC == INT4_SPEC
    source = (ROOT / "tools" / "npu_natstop.py").read_text(encoding="ascii")
    assert 'parser.add_argument("--model-spec", type=Path, default=DEFAULT_MODEL_SPEC)' in source
    text = INT4_SPEC.read_text(encoding="utf-8")
    assert "mode: INT4_SYM" in text and "group_size: 128" in text
    assert "revision: b467368d16b75df14055562fe927ae8e1f15f7ef" in text


def test_default_runs_record_the_int4_spec(tmp_path: Path) -> None:
    assert ns.main(["--smoke", "--prompt-set", "chat", "--out", str(tmp_path)]) == 0
    (run_dir,) = tmp_path.glob("natstop_b_*")
    plan = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
    assert Path(plan["model_spec"]) == INT4_SPEC
    assert plan["model"]["revision"] == "b467368d16b75df14055562fe927ae8e1f15f7ef"
    assert "ir_quantization" in plan["model"] and "content_check" not in plan


def test_f1_refuses_the_int4_default(tmp_path: Path, capsys) -> None:
    assert ns.main(["--smoke", "--prompt-set", "f1", "--out", str(tmp_path)]) == 1
    assert "REFUSED" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


def test_smoke_f1_on_int8_spec(tmp_path: Path, capsys) -> None:
    argv = ["--smoke", "--prompt-set", "f1", "--model-spec", str(INT8_SPEC), "--out", str(tmp_path)]
    assert ns.main(argv) == 0
    (run_dir,) = tmp_path.glob("natstop_f1_*")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["diagnostic"] == "NPU-FORMAT-F1" and summary["prompt_set"] == "f1"
    assert summary["model"]["revision"] == "fd9c3cc8adf942151e48904b7341a57eae58d8d5"
    assert summary["content_check"]["tip_line"] == ns.TIP_LINE.pattern
    assert len(summary["cells"]) == 8
    for cell in summary["cells"].values():
        assert {"valid", "content_ok", "passes"} <= set(cell["derived"])
        assert "--model-spec" in cell["command"] and str(INT8_SPEC) in cell["command"]
    assert summary["verdict"] == "FC" and summary["scope_verdict"] in ("B1", "B2", "B3", "B4")
    out = capsys.readouterr().out
    assert "IR_QUANT " in out and f"NATSTOP_F1_VERDICT FC {run_dir}" in out
    assert ns.main(["--classify", str(run_dir / "summary.json")]) == 0


def _clean(monkeypatch) -> None:
    monkeypatch.setattr(ns, "_git", lambda *a: "" if a[0] == "status" else "abc\n")
    monkeypatch.setattr(ns, "watchdog_state", lambda _p: {"idle": True})


def test_real_run_refuses_without_the_ir(monkeypatch, tmp_path: Path, capsys) -> None:
    _clean(monkeypatch)
    argv = ["--prompt-set", "f1", "--model-spec", str(INT8_SPEC), "--out", str(tmp_path)]
    if (ROOT / "models" / "Qwen3-4B-int8-ov" / "openvino_model.xml").exists():
        pytest.skip("the int8 IR is present on this machine")
    assert ns.main(argv) == 1
    assert "openvino_model.xml absent" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


def test_real_run_refuses_an_unpinned_xml(monkeypatch, tmp_path: Path, capsys) -> None:
    _clean(monkeypatch)
    ir = tmp_path / "ir"
    _write_ir(ir, INT8_ASYM_XML)
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "name: x\nrevision: r\nsource: pre-converted\nself_converted: false\n"
        f"ir_dir: {ir}\nir_sha256: abc\nir_files:\n  openvino_model.xml: {'0' * 64}\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    assert ns.main(["--prompt-set", "f1", "--model-spec", str(spec), "--out", str(out)]) == 1
    assert "does not match the spec pin" in capsys.readouterr().out


# ---------------------------------------------------------------- IR metadata


def _layer(i: int, etype: str, shape: str) -> str:
    return (
        f'<layer id="{i}" name="c{i}" type="Const" version="opset1">'
        f'<data element_type="{etype}" shape="{shape}" offset="0" size="1"/></layer>'
    )


def _xml(layers: list[tuple[str, str]], rt_info: str = "") -> str:
    body = "".join(_layer(i, e, s) for i, (e, s) in enumerate(layers))
    body += '<layer id="99" name="p" type="Parameter" version="opset1"><data element_type="i64" shape="1"/></layer>'
    return f'<?xml version="1.0"?><net name="m" version="11"><layers>{body}</layers><rt_info>{rt_info}</rt_info></net>'


INT4_G128_XML = _xml(
    [
        ("i4", "2560,20,128"),
        ("f16", "2560,20,1"),
        ("i4", "9728,20,128"),
        ("u8", "151936,2560"),
        ("u8", "151936,1"),
        ("f16", "151936,1"),
    ]
)
INT8_ASYM_XML = _xml(
    [
        ("u8", "2560,2560"),
        ("u8", "2560,1"),
        ("f16", "2560,1"),
        ("u8", "151936,2560"),
        ("u8", "151936,1"),
    ]
)
INT4_CW_XML = _xml(
    [("i4", "2560,2560"), ("f16", "2560,1"), ("u8", "151936,2560"), ("u8", "151936,1")]
)
RT_INFO = (
    '<nncf><weight_compression><mode value="int4_sym"/><group_size value="128"/>'
    '<ratio value="1.0"/><awq value="True"/></weight_compression></nncf>'
)


def _write_ir(ir: Path, xml: str, config: dict | None = None) -> str:
    import hashlib

    ir.mkdir(parents=True, exist_ok=True)
    (ir / "openvino_model.xml").write_text(xml, encoding="utf-8")
    if config is not None:
        (ir / "openvino_config.json").write_text(json.dumps(config), encoding="utf-8")
    return hashlib.sha256(xml.encode("utf-8")).hexdigest()


def test_census_reads_int4_group_128_sym(tmp_path: Path) -> None:
    pin = _write_ir(tmp_path, INT4_G128_XML)
    rec = ir_quantization(tmp_path, pin)
    assert rec["xml_matches_pin"] is True and rec["error"] is None
    assert rec["rt_info"] == {}
    assert rec["constants"]["group_sizes"] == {"4bit:128": 2, "8bit:-1": 1}
    assert rec["summary"]["mode"] == "INT4_SYM" and rec["summary"]["group_size"] == 128
    assert rec["summary"]["sym"] is True and rec["summary"]["ratio"] is None
    assert rec["summary"]["source"]["mode"] == "constants"
    assert 0 < rec["constants"]["int4_param_share"] < 1


def test_census_reads_int8_asym_per_channel(tmp_path: Path) -> None:
    _write_ir(tmp_path, INT8_ASYM_XML)
    rec = ir_quantization(tmp_path)
    assert rec["summary"]["mode"] == "INT8_ASYM" and rec["summary"]["group_size"] == -1
    assert rec["summary"]["sym"] is False and rec["xml_matches_pin"] is None
    assert rec["constants"]["zero_point_constants"] == {"u8": 2}


def test_census_reads_int4_channel_wise(tmp_path: Path) -> None:
    _write_ir(tmp_path, INT4_CW_XML)
    rec = ir_quantization(tmp_path)
    assert rec["summary"]["mode"] == "INT4_SYM" and rec["summary"]["group_size"] == -1


def test_rt_info_and_openvino_config_take_precedence_and_conflicts_are_kept(tmp_path: Path) -> None:
    config = {"quantization_config": {"bits": 4, "sym": True, "group_size": 64, "ratio": 0.8}}
    _write_ir(tmp_path, _xml([("i4", "2560,20,128")], RT_INFO), config)
    rec = ir_quantization(tmp_path)
    s = rec["summary"]
    assert (s["mode"], s["group_size"], s["ratio"], s["sym"]) == ("INT4_SYM", 128, 1.0, True)
    assert s["source"] == {
        "mode": "rt_info",
        "group_size": "rt_info",
        "ratio": "rt_info",
        "sym": "rt_info",
    }
    fields = {c["field"] for c in rec["conflicts"]}
    assert fields == {"group_size", "ratio"}
    assert rec["openvino_config"] == config


def test_openvino_config_used_when_rt_info_is_silent(tmp_path: Path) -> None:
    config = {"quantization_config": {"bits": 4, "sym": True, "group_size": -1, "ratio": 1.0}}
    _write_ir(tmp_path, INT4_CW_XML, config)
    s = ir_quantization(tmp_path)["summary"]
    assert s["ratio"] == 1.0 and s["source"]["ratio"] == "openvino_config"
    assert s["group_size"] == -1 and s["source"]["group_size"] == "openvino_config"


def test_missing_ir_is_recorded_not_raised(tmp_path: Path) -> None:
    rec = ir_quantization(tmp_path / "absent", "f" * 64)
    assert rec["xml_present"] is False and rec["error"] == "openvino_model.xml absent"
    assert rec["summary"] == {}


# ---------------------------------------------------------------- launcher


def test_launcher_passes_model_spec_and_f1() -> None:
    text = LAUNCHER.read_text(encoding="ascii")
    assert '[ValidateSet("filler", "chat", "f1")]' in text
    assert '[string]$ModelSpec = ""' in text
    assert 'if ($ModelSpec) { $pyArgs += @("--model-spec", $ModelSpec) }' in text
    assert '$cmd += " -ModelSpec' in text
    assert '"npu-natstop-f1_"' in text
