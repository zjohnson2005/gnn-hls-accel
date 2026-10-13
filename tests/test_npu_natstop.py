"""NPU-NATSTOP: the rule by code, the child record, the launcher.

Hardware-free. openvino_genai is replaced by a fake.
"""

from __future__ import annotations

import builtins
import copy
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

import tools.npu_natstop as ns  # noqa: E402
import tools.run_npu_profile as rnp  # noqa: E402

LAUNCHER = ROOT / "tools" / "launch_t2s_natstop.ps1"
TEXT_IDS = list(range(1000, 1064))
THINK_IDS = [151668, 271] * 32


def _cell(device: str, template: str, n: int, **over: Any) -> dict[str, Any]:
    cell: dict[str, Any] = {
        "device": device,
        "template": template,
        "n_tokens": n,
        "complete": True,
        "child_exit_code": 0,
        "load_error": None,
        "generate_returned": True,
        "realized_tokens": n,
        "pipeline_input_tokens": n + (8 if template == "DOUBLE" else 0),
        "text": "The answer is short and plain.",
        "generated_ids": list(TEXT_IDS),
        "completion_tokens": 64,
    }
    cell.update(over)
    return cell


DEGENERATE = {"text": "</think>\n\n" * 32, "generated_ids": list(THINK_IDS)}
EMPTY_EOS = {"text": "", "generated_ids": [], "completion_tokens": 0}


def _cells(npu_single: dict | None = None, npu_double: dict | None = None, **gpu: Any) -> dict:
    out: dict[str, Any] = {}
    for n in ns.LENGTHS:
        out[ns.cell_key("GPU", "SINGLE", n)] = _cell("GPU", "SINGLE", n, **gpu.get("single", {}))
        out[ns.cell_key("GPU", "DOUBLE", n)] = _cell("GPU", "DOUBLE", n, **gpu.get("double", {}))
        out[ns.cell_key("NPU", "SINGLE", n)] = _cell("NPU", "SINGLE", n, **(npu_single or {}))
        out[ns.cell_key("NPU", "DOUBLE", n)] = _cell("NPU", "DOUBLE", n, **(npu_double or {}))
    return out


# ---------------------------------------------------------------- rule


def test_cell_order_is_16_lengths_ascending_npu_first() -> None:
    order = ns.cell_order()
    assert len(order) == 16
    assert order[:4] == [
        ("NPU", "SINGLE", 64),
        ("NPU", "DOUBLE", 64),
        ("GPU", "SINGLE", 64),
        ("GPU", "DOUBLE", 64),
    ]
    assert [n for _, _, n in order[::4]] == [64, 768, 960, 1984]


def test_n1_when_npu_single_matches_gpu_single_everywhere() -> None:
    assert ns.classify(_cells(npu_double=DEGENERATE)) == "N1"


def test_n1_uses_only_the_first_16_ids() -> None:
    late = {"generated_ids": TEXT_IDS[:16] + [7] * 48}
    assert ns.classify(_cells(npu_single=late)) == "N1"
    early = {"generated_ids": [7] + TEXT_IDS[1:]}
    assert ns.classify(_cells(npu_single=early)) != "N1"


def test_n2_when_single_fails_and_double_matches() -> None:
    assert ns.classify(_cells(npu_single=DEGENERATE)) == "N2"
    assert ns.classify(_cells(npu_single=EMPTY_EOS)) == "N2"


def test_n2_needs_gpu_double_to_write_text() -> None:
    cells = _cells(npu_single=DEGENERATE, npu_double=DEGENERATE, double=DEGENERATE)
    # NPU DOUBLE "matches" a degenerate GPU DOUBLE: not N2. Both NPU templates fail: N3.
    assert ns.classify(cells) == "N3"


def test_n3_when_npu_fails_under_both_templates() -> None:
    assert ns.classify(_cells(npu_single=DEGENERATE, npu_double=EMPTY_EOS)) == "N3"


def test_n4_when_gpu_single_does_not_write_text() -> None:
    assert ns.classify(_cells(single=DEGENERATE)) == "N4"


def test_n4_when_mixed_by_length() -> None:
    cells = _cells()
    cells[ns.cell_key("NPU", "SINGLE", 1984)].update(DEGENERATE)
    cells[ns.cell_key("NPU", "DOUBLE", 1984)].update(DEGENERATE)
    assert ns.classify(cells) == "N4"


@pytest.mark.parametrize(
    "broken",
    [
        {"child_exit_code": 1},
        {"child_exit_code": None},
        {"complete": False},
        {"load_error": "RuntimeError: load"},
        {"generate_returned": False},
        {"pipeline_input_tokens": None},
        {"pipeline_input_tokens": 63},
    ],
)
def test_n4_when_any_npu_single_cell_is_not_ok(broken: dict[str, Any]) -> None:
    cells = _cells()
    cells[ns.cell_key("NPU", "SINGLE", 64)].update(broken)
    assert ns.classify(cells) == "N4"


def test_n4_when_a_cell_is_missing() -> None:
    cells = _cells()
    del cells[ns.cell_key("NPU", "SINGLE", 960)]
    assert ns.classify(cells) == "N4"


def test_double_input_count_may_exceed_realized() -> None:
    cell = _cell("NPU", "DOUBLE", 64)
    assert cell["pipeline_input_tokens"] == 72 and ns.cell_ok(cell)
    single = _cell("NPU", "SINGLE", 64, pipeline_input_tokens=72)
    assert not ns.cell_ok(single)


def test_definitions() -> None:
    assert ns.real_text("</think>\n\n</think>\n\n") == ""
    assert ns.real_text("<think>\n\n</think>\n\nHi") == "Hi"
    eos = _cell("NPU", "SINGLE", 64, **EMPTY_EOS)
    assert ns.stop_reason(eos) == "EOS" and ns.ends_at_once(eos) and ns.fails(eos)
    full = _cell("GPU", "SINGLE", 64)
    assert ns.stop_reason(full) == "max" and ns.writes_text(full)
    assert ns.stop_reason(_cell("NPU", "SINGLE", 64, generate_returned=False)) == "error"
    deg = _cell("NPU", "SINGLE", 64, **DEGENERATE)
    assert ns.degenerate(deg) and not ns.ends_at_once(deg)
    assert ns.id_repeat_fraction(deg) > rnp.REPEAT_FRACTION_MAX
    # Text after the tags, but the ids loop: degenerate by id 4-grams.
    loop = _cell("NPU", "SINGLE", 64, text="a a a a", generated_ids=[5, 6] * 32)
    assert ns.degenerate(loop)
    # Short and stopped with real text: writes text, not degenerate.
    short = _cell("NPU", "SINGLE", 64, text="OK.", generated_ids=[9, 10], completion_tokens=2)
    assert ns.stop_reason(short) == "EOS" and ns.writes_text(short)


def test_matches_short_lists_need_full_equality() -> None:
    a = _cell("NPU", "SINGLE", 64, generated_ids=[1, 2, 3], completion_tokens=3)
    b = _cell("GPU", "SINGLE", 64, generated_ids=[1, 2, 3], completion_tokens=3)
    c = _cell("GPU", "SINGLE", 64, generated_ids=[1, 2], completion_tokens=2)
    assert ns.matches(a, b)
    assert not ns.matches(a, c)
    assert not ns.matches(a, _cell("GPU", "SINGLE", 64))


def test_classify_file_round_trip(tmp_path: Path) -> None:
    cells = _cells(npu_single=DEGENERATE)
    path = tmp_path / "summary.json"
    path.write_text(json.dumps({"cells": cells, "verdict": "N2"}), encoding="utf-8")
    assert ns.classify_file(path) == 0
    path.write_text(json.dumps({"cells": cells, "verdict": "N1"}), encoding="utf-8")
    assert ns.classify_file(path) == 1


# ---------------------------------------------------------------- generation config


class _Cfg:
    def __init__(self) -> None:
        self.max_new_tokens = 0
        self.min_new_tokens = 0
        self.do_sample = True
        self.apply_chat_template = True


def test_npu1_generation_config_is_unchanged() -> None:
    cfg = rnp.generation_config(types.SimpleNamespace(GenerationConfig=_Cfg))
    assert cfg.max_new_tokens == 8 and cfg.min_new_tokens == 8
    assert cfg.do_sample is False and cfg.apply_chat_template is False


def test_natstop_config_forces_nothing() -> None:
    genai = types.SimpleNamespace(GenerationConfig=_Cfg)
    for template, flag in (("SINGLE", False), ("DOUBLE", True)):
        cfg = rnp.generation_config(
            genai,
            max_new_tokens=ns.MAX_NEW_TOKENS,
            min_new_tokens=None,
            apply_chat_template=template == "DOUBLE",
        )
        assert cfg.max_new_tokens == 64
        assert cfg.min_new_tokens == 0  # the GenAI default, not set by us
        assert cfg.do_sample is False and cfg.apply_chat_template is flag


# ---------------------------------------------------------------- child, fake GenAI


class _Ttft:
    mean = 900.0


class _Metrics:
    def __init__(self, n_in: int, n_out: int) -> None:
        self.n_in, self.n_out = n_in, n_out

    def get_num_input_tokens(self) -> int:
        return self.n_in

    def get_num_generated_tokens(self) -> int:
        return self.n_out

    def get_ttft(self) -> _Ttft:
        return _Ttft()


class _Decoded:
    def __init__(self, text: str, n_in: int, n_out: int) -> None:
        self.texts = [text]
        self.perf_metrics = _Metrics(n_in, n_out)


class _Ids:
    def __init__(self, n: int) -> None:
        self.shape = (1, n)


class _Tokenizer:
    """One token per whitespace word; the template adds two words."""

    def encode(self, text: str) -> Any:
        return types.SimpleNamespace(input_ids=_Ids(len(text.split())))

    def apply_chat_template(self, messages: list, **_: Any) -> str:
        return "<u> " + messages[0]["content"] + " </u>"

    def decode(self, ids: list[int]) -> str:
        return f"t{ids[0]}"


def _fake_genai(loads: list[tuple[str, dict]], calls: list[Any], ids: list[int]) -> Any:
    mod = types.ModuleType("openvino_genai")
    mod.GenerationConfig = _Cfg
    mod.StreamerBase = type("StreamerBase", (), {"__init__": lambda _self: None})
    mod.StreamingStatus = types.SimpleNamespace(RUNNING=0)
    mod.Tokenizer = lambda _path: _Tokenizer()

    class Pipe:
        def generate(self, inputs: Any, cfg: Any, streamer: Any) -> Any:
            calls.append((inputs, cfg))
            assert isinstance(inputs, list)
            for token in ids:
                streamer.write(token)
            n_in = len(inputs[0].split()) + (8 if cfg.apply_chat_template else 0)
            return _Decoded("Hello there.", n_in, len(ids))

        def get_generation_config(self) -> Any:
            return types.SimpleNamespace(eos_token_id=151645, stop_token_ids={151645, 151643})

    def pipeline(path: str, device: str, **props: Any) -> Any:
        loads.append((device, props))
        return Pipe()

    mod.LLMPipeline = pipeline
    return mod


def _child(monkeypatch, tmp_path: Path, device: str, template: str, ids: list[int]) -> tuple:
    loads: list[tuple[str, dict]] = []
    calls: list[Any] = []
    monkeypatch.setitem(sys.modules, "openvino_genai", _fake_genai(loads, calls, ids))
    result = tmp_path / f"{device}_{template}.json"
    argv = ["--child", "--device", device, "--template", template, "--n-tokens", "64"]
    assert ns.main([*argv, "--result", str(result)]) == 0
    return json.loads(result.read_text(encoding="utf-8")), loads, calls


def test_npu_child_records_every_field(monkeypatch, tmp_path: Path) -> None:
    rec, loads, calls = _child(monkeypatch, tmp_path, "NPU", "SINGLE", [11, 12, 151645])
    assert loads == [
        (
            "NPU",
            {"NPUW_LLM_PREFILL_CHUNK_SIZE": 1024, "MAX_PROMPT_LEN": 2048, "MIN_RESPONSE_LEN": 8},
        )
    ]
    (_inputs, cfg) = calls[0]
    assert cfg.apply_chat_template is False and cfg.max_new_tokens == 64
    assert cfg.min_new_tokens == 0
    assert rec["complete"] is True
    assert rec["realized_tokens"] == 64 and rec["pipeline_input_tokens"] == 64
    assert rec["generated_ids"] == [11, 12, 151645]
    assert rec["completion_tokens"] == 3 and rec["streamer_tokens"] == 3
    assert rec["first_token_id"] == 11 and rec["first_token_text"] == "t11"
    assert rec["last_id_in_stop_set"] is True
    assert rec["text"] == "Hello there."
    assert isinstance(rec["ttft_s"], float)
    assert rec["kv_room"] == 2048 + 8 - 64
    assert rec["generation_config"]["min_new_tokens"] == 0


def test_gpu_double_child(monkeypatch, tmp_path: Path) -> None:
    rec, loads, calls = _child(monkeypatch, tmp_path, "GPU", "DOUBLE", list(range(64)))
    assert loads == [("GPU", {})]
    assert calls[0][1].apply_chat_template is True
    assert rec["pipeline_input_tokens"] == 72 and rec["kv_room"] is None
    assert len(rec["generated_ids"]) == 64


def test_child_never_opens_rule_or_amendment(monkeypatch, tmp_path: Path) -> None:
    real_open = builtins.open

    def guarded(file, *args, **kwargs):
        text = str(file).replace("\\", "/")
        name = text.rsplit("/", 1)[-1].upper()
        if "/docs/amendments/" in text.lower() or (
            "/derived/" in text.lower()
            and any(t in name for t in ("PREREG", "PREDICTIONS", "AMEND", "RULE"))
        ):
            raise AssertionError(f"natstop opened {file}")
        if "NPU_PROTOCOL" in name:
            raise AssertionError(f"natstop opened {file}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded)
    monkeypatch.setattr(io, "open", guarded)
    rec, _, _ = _child(monkeypatch, tmp_path, "NPU", "DOUBLE", [1, 2, 3])
    assert rec["complete"] is True


def test_smoke_parent_runs_16_children_in_order(tmp_path: Path) -> None:
    assert ns.main(["--smoke", "--out", str(tmp_path)]) == 0
    (run_dir,) = tmp_path.glob("natstop_*")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "complete" and summary["smoke"] is True
    assert summary["measurement"] is False
    assert summary["ended_utc"]
    assert summary["cell_order"] == [ns.cell_key(*c) for c in ns.cell_order()]
    assert set(summary["cells"]) == set(summary["cell_order"])
    for cell in summary["cells"].values():
        assert cell["child_exit_code"] == 0 and cell["derived"]["cell_ok"]
    assert summary["verdict"] == "N1"
    assert (run_dir / "plan.json").is_file()


def test_parent_refuses_dirty_tree(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(ns, "_git", lambda *a: " M tools/x.py\n" if a[0] == "status" else "abc\n")
    assert ns.main(["--out", str(tmp_path)]) == 1
    assert "REFUSED" in capsys.readouterr().out
    assert not list(tmp_path.glob("natstop_*"))


def test_parent_refuses_busy_watchdog(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(ns, "_git", lambda *a: "" if a[0] == "status" else "abc\n")
    monkeypatch.setattr(ns, "watchdog_state", lambda _p: {"idle": False, "last_line": "busy"})
    assert ns.main(["--out", str(tmp_path)]) == 1
    assert "watchdog not idle" in capsys.readouterr().out


def test_derived_fields_do_not_mutate() -> None:
    cell = _cell("NPU", "SINGLE", 64, **DEGENERATE)
    before = copy.deepcopy(cell)
    fields = ns.derived_fields(cell)
    assert cell == before
    assert fields["degenerate"] and fields["fails"] and not fields["writes_text"]


# ---------------------------------------------------------------- launcher


def test_launcher_shape() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert text.isascii()
    assert "[switch]$Detach" in text and "[switch]$Rehearsal" in text
    assert "npu-natstop_" in text and "npu-1.log" not in text
    assert "spawn_detached.ps1" in text
    assert "npu_natstop.py" in text
    assert "REHEARSAL_COMPLETE" in text and "NATSTOP_COMPLETE" in text
    assert "launch-check" in text and "24000" in text
    assert "Assert-SeamMachineLockClear" in text
    assert "WmiPrvSE.exe" in text and "sshd.exe" in text
    # One-shot commands call the script directly, no nested powershell -Command.
    for line in text.splitlines():
        if line.lstrip("# ").startswith("ssh "):
            assert ".\\tools\\launch_t2s_natstop.ps1" in line
            assert "powershell" not in line
            assert line.count("'") == 2


def test_run_dir_is_derived_npu_natstop() -> None:
    assert ns.DEFAULT_OUT == ROOT / "derived" / "npu"
    source = (ROOT / "tools" / "npu_natstop.py").read_text(encoding="utf-8")
    assert '"filler": "natstop_", "chat": "natstop_b_", "f1": "natstop_f1_"' in source
    assert 'out_dir = Path(args.out) / f"{prefix}{run_id}"' in source


# ---------------------------------------------------------------- NPU-NATSTOP-B

AMEND = ROOT / "docs" / "amendments" / "NPU_AMEND_2026-10-12_VALIDITY.md"
SEALED_N3 = ROOT / "derived" / "npu" / "sealed_natstop_6b39a76e-0df4-4a90-84c1-4c1dd15bff35"


def _chat_cell(device: str, template: str, prompt: str, **over: Any) -> dict[str, Any]:
    cell = _cell(device, template, 0, n_tokens=None, prompt_id=prompt)
    cell["realized_tokens"] = 20
    cell["pipeline_input_tokens"] = 20 + (8 if template == "DOUBLE" else 0)
    cell["real_token_count"] = 64
    cell.update(over)
    return cell


SHORT_EOS = {"generated_ids": list(range(1000, 1012)), "completion_tokens": 12}
EOS_FIRST = {"text": "", "generated_ids": [151645], "completion_tokens": 1, "real_token_count": 0}


def _chat_cells(npu_single: dict | None = None, npu_double: dict | None = None, **gpu: Any):
    out: dict[str, Any] = {}
    for p in ns.CHAT_PROMPTS:
        for t in ns.TEMPLATES:
            out[ns.cell_key("GPU", t, p)] = _chat_cell("GPU", t, p, **gpu.get(t.lower(), {}))
        out[ns.cell_key("NPU", "SINGLE", p)] = _chat_cell("NPU", "SINGLE", p, **(npu_single or {}))
        out[ns.cell_key("NPU", "DOUBLE", p)] = _chat_cell("NPU", "DOUBLE", p, **(npu_double or {}))
    return out


def test_chat_cell_order_is_8_cells() -> None:
    order = [ns.cell_key(*c) for c in ns.cell_order("chat")]
    assert order == [
        "NPU_SINGLE_chat1",
        "NPU_DOUBLE_chat1",
        "GPU_SINGLE_chat1",
        "GPU_DOUBLE_chat1",
        "NPU_SINGLE_chat2",
        "NPU_DOUBLE_chat2",
        "GPU_SINGLE_chat2",
        "GPU_DOUBLE_chat2",
    ]
    assert [ns.cell_key(*c) for c in ns.cell_order()] == [
        ns.cell_key(*c) for c in ns.cell_order("filler")
    ]


def test_validity_constants_come_from_the_n3_gpu_cells() -> None:
    summary = json.loads((SEALED_N3 / "summary.json").read_text(encoding="utf-8"))
    gpu = [c for c in summary["cells"].values() if c["device"] == "GPU"]
    assert len(gpu) == 8
    repeats = [ns.id_repeat_fraction(c) for c in gpu]
    assert max(repeats) == ns.VALID_REPEAT_MAX
    # Real tokens: ids less think tags and the one newline after <think>.
    counts = []
    for c in gpu:
        ids = [i for i in c["generated_ids"] if i not in (151667, 151668)]
        counts.append(len(ids) - (1 if c["template"] == "DOUBLE" else 0))
    assert min(counts) == ns.VALID_MIN_REAL_TOKENS
    assert ns.classify(summary["cells"]) == "N3" == summary["verdict"]


def test_valid_uses_k_t_and_the_short_gpu_reference() -> None:
    gpu_max = _chat_cell("GPU", "SINGLE", "chat1")
    assert ns.valid(_chat_cell("NPU", "SINGLE", "chat1"), gpu_max)
    assert not ns.valid(_chat_cell("NPU", "SINGLE", "chat1", real_token_count=61), gpu_max)
    gpu_short = _chat_cell("GPU", "SINGLE", "chat1", real_token_count=12, **SHORT_EOS)
    assert ns.valid(_chat_cell("NPU", "SINGLE", "chat1", real_token_count=12), gpu_short)
    assert not ns.valid(_chat_cell("NPU", "SINGLE", "chat1", real_token_count=11), gpu_short)
    assert not ns.valid(_chat_cell("NPU", "SINGLE", "chat1", **EOS_FIRST), gpu_short)
    looping = _chat_cell("NPU", "DOUBLE", "chat1", generated_ids=list(THINK_IDS))
    assert not ns.valid(looping, gpu_max)
    assert not ns.valid(_chat_cell("NPU", "SINGLE", "chat1", real_token_count=None), gpu_max)


def test_scope_b1_when_npu_writes_nothing_valid() -> None:
    assert ns.classify_scope(_chat_cells(EOS_FIRST, EOS_FIRST)) == "B1"


def test_scope_b2_when_one_template_is_valid_on_both_prompts() -> None:
    assert ns.classify_scope(_chat_cells(None, EOS_FIRST)) == "B2"
    assert ns.classify_scope(_chat_cells(EOS_FIRST, None)) == "B2"


def test_scope_b3_when_mixed_by_prompt() -> None:
    cells = _chat_cells(EOS_FIRST, EOS_FIRST)
    cells[ns.cell_key("NPU", "SINGLE", "chat1")] = _chat_cell("NPU", "SINGLE", "chat1")
    assert ns.classify_scope(cells) == "B3"


def test_scope_b4_when_gpu_single_is_not_valid() -> None:
    assert ns.classify_scope(_chat_cells(single=EOS_FIRST)) == "B4"


def test_chat_child_renders_the_fixed_prompt(monkeypatch, tmp_path: Path) -> None:
    loads: list[tuple[str, dict]] = []
    calls: list[Any] = []
    monkeypatch.setitem(sys.modules, "openvino_genai", _fake_genai(loads, calls, [11, 12, 151645]))
    seen: list[str] = []
    monkeypatch.setattr(ns, "render_user", lambda _tok, text: seen.append(text) or text)
    result = tmp_path / "chat.json"
    argv = ["--child", "--device", "NPU", "--template", "SINGLE", "--prompt-id", "chat2"]
    assert ns.main([*argv, "--result", str(result)]) == 0
    rec = json.loads(result.read_text(encoding="utf-8"))
    assert seen == [ns.CHAT_PROMPTS["chat2"]]
    assert rec["prompt_id"] == "chat2" and rec["n_tokens"] is None
    assert rec["real_token_count"] == 2  # t11, t12; the stop id is not counted
    assert calls[0][1].max_new_tokens == 64 and calls[0][1].min_new_tokens == 0


def test_smoke_parent_chat_runs_8_children(tmp_path: Path, capsys) -> None:
    assert ns.main(["--smoke", "--prompt-set", "chat", "--out", str(tmp_path)]) == 0
    (run_dir,) = tmp_path.glob("natstop_b_*")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["diagnostic"] == "NPU-NATSTOP-B" and summary["prompt_set"] == "chat"
    assert summary["chat_prompts"] == ns.CHAT_PROMPTS
    assert len(summary["cells"]) == 8
    assert all("valid" in c["derived"] for c in summary["cells"].values())
    assert summary["verdict"] == "B2"
    assert f"NATSTOP_B_VERDICT B2 {run_dir}" in capsys.readouterr().out
    assert ns.main(["--classify", str(run_dir / "summary.json")]) == 0


def test_chat_prompts_and_constants_are_the_amendment_text() -> None:
    text = AMEND.read_text(encoding="utf-8")
    for prompt in ns.CHAT_PROMPTS.values():
        assert prompt in text
    assert "K = 62" in text and "T = 27/61" in text


def test_launcher_passes_the_prompt_set() -> None:
    text = LAUNCHER.read_text(encoding="ascii")
    assert '[ValidateSet("filler", "chat", "f1")]' in text
    assert '"--prompt-set", $PromptSet' in text
    assert '"npu-natstop-b_"' in text
