"""NPU-MAXLEN-DIAG: classify() per D-case, and the runner readback copy."""

from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.npu_maxlen_diag import (  # noqa: E402
    arm_props,
    classify,
    classify_file,
    dirty_tracked,
    generate_direct,
    length_check_refusal,
    main,
    parse_bands,
    prompt_status,
    runner_readback,
    stated_cap,
    validity,
    watchdog_state,
)

RUNNER = ROOT / "tools" / "run_npu_profile.py"
DIAG = ROOT / "tools" / "npu_maxlen_diag.py"


def _prompt(band: list[int], realized: int, **over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "band": band,
        "realized_tokens": realized,
        "generate_returned": True,
        "exception": None,
        "pipeline_input_tokens": realized,
        "valid": True,
    }
    row.update(over)
    return row


def _arm(r1_after: int | None = 2048, a: dict | None = None, b: dict | None = None) -> dict:
    return {
        "result_present": True,
        "timed_out": False,
        "child_exit_code": 0,
        "load_error": None,
        "r1_after_value": r1_after,
        "prompts": [
            a if a is not None else _prompt([850, 950], 900),
            b if b is not None else _prompt([1450, 1550], 1500),
        ],
    }


def _results(doc: dict | None = None, npuw: dict | None = None) -> dict:
    return {
        "request": 2048,
        "arms": {"doc": doc if doc is not None else _arm(), "npuw": npuw or _arm()},
    }


REFUSED_B = _prompt(
    [1450, 1550],
    1500,
    generate_returned=False,
    exception={"class": "RuntimeError", "message": "prompt too long"},
    pipeline_input_tokens=None,
    valid=None,
)
TRUNCATED_B = _prompt([1450, 1550], 1500, pipeline_input_tokens=1024)
INVALID_B = _prompt([1450, 1550], 1500, valid=False)


# ---------------------------------------------------------------- rule v1
# _results() without rule_version is v1, as run 1 output is.


def test_d1_none_both_arms_apply_and_read_back() -> None:
    assert classify(_results()) == ("D1", "none")


def test_d1_key_fix_only_doc_applies() -> None:
    res = _results(npuw=_arm(r1_after=1024, b=REFUSED_B))
    assert classify(res) == ("D1", "key_fix")


def test_d1_readback_fix_both_apply_readback_stale() -> None:
    res = _results(doc=_arm(r1_after=1024), npuw=_arm(r1_after=1024))
    assert classify(res) == ("D1", "readback_fix")


def test_d1_readback_fix_from_one_ok_arm_is_enough() -> None:
    res = _results(doc=_arm(r1_after=2048), npuw=_arm(r1_after=1024))
    assert classify(res) == ("D1", "readback_fix")


def test_d1_key_fix_and_readback_fix() -> None:
    res = _results(doc=_arm(r1_after=1024), npuw=_arm(r1_after=1024, b=TRUNCATED_B))
    assert classify(res) == ("D1", "key_fix+readback_fix")


def test_d1_when_only_npuw_applies_has_no_key_fix() -> None:
    res = _results(doc=_arm(b=REFUSED_B), npuw=_arm(r1_after=2048))
    assert classify(res) == ("D1", "none")


def test_d2_refused_in_both() -> None:
    res = _results(doc=_arm(b=REFUSED_B), npuw=_arm(b=REFUSED_B))
    assert classify(res) == ("D2", "-")


def test_d2_truncated_counts_as_rejected() -> None:
    res = _results(doc=_arm(b=TRUNCATED_B), npuw=_arm(b=REFUSED_B))
    assert classify(res) == ("D2", "-")


def test_d3_accepted_but_invalid() -> None:
    res = _results(doc=_arm(b=INVALID_B), npuw=_arm(b=REFUSED_B))
    assert classify(res) == ("D3", "-")
    res = _results(doc=_arm(b=INVALID_B), npuw=_arm(b=INVALID_B))
    assert classify(res) == ("D3", "-")


@pytest.mark.parametrize(
    "breakage",
    [
        {"load_error": "RuntimeError: x"},
        {"child_exit_code": 0xC0000005},
        {"child_exit_code": None, "timed_out": True},
        {"result_present": False},
    ],
)
def test_d4_broken_arm_overrides_d1(breakage: dict) -> None:
    broken = _arm()
    broken.update(breakage)
    assert classify(_results(npuw=broken)) == ("D4", "-")


def test_d4_band_a_fails() -> None:
    bad_a = _prompt([850, 950], 900, valid=False)
    assert classify(_results(npuw=_arm(a=bad_a))) == ("D4", "-")
    trunc_a = _prompt([850, 950], 900, pipeline_input_tokens=800)
    assert classify(_results(doc=_arm(a=trunc_a))) == ("D4", "-")


def test_d4_realized_outside_band() -> None:
    assert classify(_results(doc=_arm(a=_prompt([850, 950], 960)))) == ("D4", "-")
    assert classify(_results(doc=_arm(b=_prompt([1450, 1550], 1400)))) == ("D4", "-")
    assert classify(_results(doc=_arm(b=_prompt([1450, 1550], None)))) == ("D4", "-")


def test_d4_truncation_unknown_is_not_d1_d2_or_d3() -> None:
    unknown = _prompt([1450, 1550], 1500, pipeline_input_tokens=None)
    assert prompt_status(unknown) == "truncation_unknown"
    res = _results(doc=_arm(b=unknown), npuw=_arm(b=REFUSED_B))
    assert classify(res) == ("D4", "-")


def test_d4_missing_arm() -> None:
    res = _results()
    del res["arms"]["npuw"]
    assert classify(res) == ("D4", "-")


def test_prompt_status_reported_above_realized_is_accepted() -> None:
    assert prompt_status(_prompt([1450, 1550], 1500, pipeline_input_tokens=1510)) == "accepted"


def test_validity_uses_protocol_threshold() -> None:
    assert validity("a b c d e f g h")["valid"] is True
    assert validity("a b a b a b a b a b")["valid"] is False
    assert validity('<tool_call>{"bad"</tool_call>')["valid"] is False


def test_arm_props() -> None:
    doc = arm_props("doc", 2048)
    assert doc == {
        "NPUW_LLM_PREFILL_CHUNK_SIZE": 1024,
        "MAX_PROMPT_LEN": 2048,
        "MIN_RESPONSE_LEN": 8,
    }
    npuw = arm_props("npuw", 2048)
    assert npuw == {"NPUW_LLM_PREFILL_CHUNK_SIZE": 1024, "NPUW_LLM_MAX_PROMPT_LEN": 2048}


def test_parse_bands_and_dirty() -> None:
    assert parse_bands("850-950,1450-1550", 1) == [[850, 950], [1450, 1550]]
    assert parse_bands("850-950,1450-1550,2100-2150") == [[850, 950], [1450, 1550], [2100, 2150]]
    with pytest.raises(SystemExit):
        parse_bands("850-950,1450-1550")
    assert dirty_tracked("?? derived/npu/diag/diag_x/\n") == []
    assert dirty_tracked(" M tools/x.py\n?? y\n") == [" M tools/x.py"]


def test_watchdog_gate(tmp_path: Path) -> None:
    log = tmp_path / "watchdog.log"
    log.write_text(
        '[2026-10-07T01:00:00Z] {"action": "empty_flag"}\n'
        '[2026-10-07T01:01:00Z] {"digest": "x"}\n',
        encoding="utf-8",
    )
    assert watchdog_state(str(log))["idle"] is True
    log.write_text('{"action": "launched"}\n{"digest": "x"}\n', encoding="utf-8")
    assert watchdog_state(str(log))["idle"] is False
    assert watchdog_state(str(tmp_path / "missing.log"))["idle"] is False


# ---------------------------------------------------------------- readback pin


def _runner_readback_block() -> ast.If:
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and ast.unparse(node.test) == (
            "pipe is not None and weight == 'int4'"
        ):
            return node
    raise AssertionError("runner readback block not found")


class _Pipe:
    def __init__(self, value: Any = None, exc: Exception | None = None) -> None:
        self.value, self.exc = value, exc

    def get_property(self, name: str) -> Any:
        assert name == "NPUW_LLM_MAX_PROMPT_LEN"
        if self.exc is not None:
            raise self.exc
        return self.value


class _Core:
    def __init__(self, value: Any = None, exc: Exception | None = None) -> None:
        self.value, self.exc = value, exc

    def get_property(self, device: str, name: str) -> Any:
        assert (device, name) == ("NPU", "NPUW_LLM_MAX_PROMPT_LEN")
        if self.exc is not None:
            raise self.exc
        return self.value


@pytest.mark.parametrize(
    ("pipe", "core"),
    [
        (_Pipe(2048), _Core(1024)),
        (_Pipe(exc=AttributeError("no get_property")), _Core(1024)),
        (_Pipe(exc=RuntimeError("x")), _Core(exc=RuntimeError("y"))),
        (_Pipe("2048"), _Core(1024)),
    ],
)
def test_readback_copy_matches_runner_source(pipe: Any, core: Any) -> None:
    block = _runner_readback_block()
    code = compile(ast.Module(body=block.body, type_ignores=[]), str(RUNNER), "exec")
    scope: dict[str, Any] = {
        "pipe": pipe,
        "core": core,
        "max_prompt_len": None,
        "read_errors": [],
    }
    exec(code, scope)
    mine = runner_readback(copy.copy(pipe), core)
    assert mine["value"] == scope["max_prompt_len"]
    assert mine["read_errors"] == scope["read_errors"]


def test_readback_before_load_is_core_only() -> None:
    assert runner_readback(None, _Core(1024)) == {
        "value": 1024,
        "source": "core",
        "read_errors": [],
    }


# ---------------------------------------------------------------- plumbing


def test_smoke_parent_and_children(tmp_path: Path, capsys) -> None:
    assert main(["--smoke", "--out", str(tmp_path), "--child-timeout", "120"]) == 0
    last = capsys.readouterr().out.strip().splitlines()[-1]
    verdict, sub, out_dir = last.split(" ", 3)[1:]
    assert last.startswith("DIAG_VERDICT ")
    assert Path(out_dir).parent == tmp_path
    assert (Path(out_dir) / "diag.json").is_file()
    assert (Path(out_dir) / "arm_doc.stdout.log").is_file()
    assert (Path(out_dir) / "arm_npuw.stderr.log").is_file()
    # Smoke children report r1_after None, so D1 cannot be readback-clean.
    assert (verdict, sub) == ("D1", "readback_fix")


def test_smoke_rule_v1_still_runs(tmp_path: Path, capsys) -> None:
    assert main(["--smoke", "--rule-version", "1", "--out", str(tmp_path)]) == 0
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert last.split(" ")[1:3] == ["D1", "readback_fix"]


def test_diag_requires_both_arms(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--smoke", "--arms", "doc", "--out", str(tmp_path)])


def test_diag_source_is_ascii() -> None:
    DIAG.read_bytes().decode("ascii")


# ---------------------------------------------------------------- rule v2

RUN1 = ROOT / "derived" / "npu" / "diag" / "diag_20261007T180320Z" / "diag.json"
CHECK_MSG = (
    "Check 'data->input_ids.get_size() <= m_max_prompt_len' failed at x:367:\n"
    "Stateful LLM pipeline on NPU may only process prompts or hold chat history up to "
    "2048 tokens. 2133 is passed.\n"
)
C_REFUSED = _prompt(
    [2100, 2150],
    2125,
    generate_returned=False,
    exception={"class": "RuntimeError", "message": CHECK_MSG},
    pipeline_input_tokens=None,
    valid=None,
)
C_ACCEPTED = _prompt([2100, 2150], 2125, pipeline_input_tokens=2133)
C_OTHER_ERROR = _prompt(
    [2100, 2150],
    2125,
    generate_returned=False,
    exception={"class": "RuntimeError", "message": "bad_alloc"},
    pipeline_input_tokens=None,
    valid=None,
)


def _arm2(r1_after: int | None = 2048, a=None, b=None, c=None) -> dict:
    arm = _arm(r1_after, a, b)
    arm["prompts"].append(c if c is not None else C_REFUSED)
    return arm


def _results2(doc: dict | None = None, npuw: dict | None = None) -> dict:
    return {
        "rule_version": 2,
        "request": 2048,
        "arms": {"doc": doc or _arm2(), "npuw": npuw or _arm2()},
    }


def test_v2_d1_needs_band_c_refused_by_length_check() -> None:
    assert classify(_results2()) == ("D1", "none")
    assert length_check_refusal(C_REFUSED) is True
    assert length_check_refusal(C_OTHER_ERROR) is False
    assert stated_cap(CHECK_MSG) == 2048


def test_v2_band_c_accepted_is_not_a_d1_arm() -> None:
    res = _results2(npuw=_arm2(c=C_ACCEPTED))
    assert classify(res) == ("D1", "key_fix")
    res = _results2(doc=_arm2(c=C_ACCEPTED), npuw=_arm2(c=C_OTHER_ERROR))
    assert classify(res) == ("D4", "-")


def test_v2_d1_subcases() -> None:
    res = _results2(doc=_arm2(r1_after=1024), npuw=_arm2(r1_after=1024, b=REFUSED_B))
    assert classify(res) == ("D1", "key_fix+readback_fix")
    res = _results2(doc=_arm2(r1_after=1024), npuw=_arm2(r1_after=1024))
    assert classify(res) == ("D1", "readback_fix")


def test_v2_d2_d3_unchanged_by_band_c() -> None:
    res = _results2(doc=_arm2(b=REFUSED_B), npuw=_arm2(b=TRUNCATED_B))
    assert classify(res) == ("D2", "-")
    res = _results2(doc=_arm2(b=INVALID_B), npuw=_arm2(b=REFUSED_B, c=C_ACCEPTED))
    assert classify(res) == ("D3", "-")


def test_v2_band_c_out_of_band_or_missing_is_d4() -> None:
    res = _results2(doc=_arm2(c=_prompt([2100, 2150], 2200)))
    assert classify(res) == ("D4", "-")
    two = _arm()  # v1-shaped arm, no band C
    assert classify(_results2(npuw=two)) == ("D4", "-")


def test_v2_broken_arm_still_first() -> None:
    broken = _arm2()
    broken["load_error"] = "RuntimeError: x"
    assert classify(_results2(npuw=broken)) == ("D4", "-")


def test_run1_output_stays_readable_and_d4(capsys) -> None:
    assert classify_file(RUN1) == 0
    out = capsys.readouterr().out
    assert "rule v1 recorded D4 -" in out
    assert out.strip().splitlines()[-1].startswith("DIAG_VERDICT D4 - ")


class _FakeCfg:
    def __init__(self) -> None:
        self.max_new_tokens = 0
        self.do_sample = True
        self.apply_chat_template = True
        self.temperature = 0.6


class _FakeStreamerBase:
    def __init__(self) -> None:
        pass


class _FakeGenai:
    GenerationConfig = _FakeCfg
    StreamerBase = _FakeStreamerBase

    class StreamingStatus:
        RUNNING = 0


class _Ttft:
    mean = 12.5


class _Metrics:
    def get_num_input_tokens(self) -> int:
        return 908

    def get_num_generated_tokens(self) -> int:
        return 8

    def get_ttft(self) -> _Ttft:
        return _Ttft()


class _Decoded:
    def __init__(self) -> None:
        self.texts = ["hello world"]
        self.perf_metrics = _Metrics()


class _FakePipe:
    def __init__(self, exc: Exception | None = None) -> None:
        self.calls: list[tuple[Any, Any]] = []
        self.exc = exc

    def generate(self, inputs: Any, cfg: Any, streamer: Any) -> Any:
        self.calls.append((inputs, cfg))
        if self.exc is not None:
            raise self.exc
        streamer.write(1)
        if isinstance(inputs, list):
            return _Decoded()
        return "hello world"


def test_v2_generate_passes_a_list_and_reads_perf_metrics() -> None:
    pipe = _FakePipe()
    row = generate_direct(_FakeGenai, pipe, "prompt text")
    inputs, cfg = pipe.calls[0]
    assert inputs == ["prompt text"]
    assert (cfg.do_sample, cfg.max_new_tokens, cfg.apply_chat_template) == (False, 8, True)
    assert row["generation_config"]["do_sample"] is False
    assert row["generation_config"]["max_new_tokens"] == 8
    assert row["generation_config"]["apply_chat_template"] is True
    assert row["result_type"] == "_Decoded"
    assert row["pipeline_input_tokens"] == 908
    assert row["perf_metrics_ttft_s"] == pytest.approx(0.0125)
    assert row["metric_error"] is None


def test_v1_generate_str_form_has_no_perf_metrics_and_says_so() -> None:
    pipe = _FakePipe()
    row = generate_direct(_FakeGenai, pipe, "prompt text", version=1)
    assert pipe.calls[0][0] == "prompt text"
    assert row["pipeline_input_tokens"] is None
    assert row["metric_error"] == "no perf_metrics on str"


def test_v2_generate_records_length_check_refusal() -> None:
    pipe = _FakePipe(exc=RuntimeError(CHECK_MSG))
    row = generate_direct(_FakeGenai, pipe, "p")
    assert row["generate_returned"] is False
    assert row["length_check_refusal"] is True
    assert row["stated_cap"] == 2048
    assert row["generation_config"]["do_sample"] is False
