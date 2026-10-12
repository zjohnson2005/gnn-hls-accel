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
    assert "natstop_{run_id}" in (ROOT / "tools" / "npu_natstop.py").read_text(encoding="utf-8")
