"""NPU positive control: parse, repeats, prompt limit, paired GPU text."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.npu_validity import decide_npu_cell, fourgram_repeat_fraction  # noqa: E402


def test_repeat_fraction_over_half_refuses() -> None:
    tokens = ["a", "b", "c", "d"] * 3
    fraction = fourgram_repeat_fraction(tokens)
    assert fraction is not None and fraction > 0.5
    decision = decide_npu_cell(
        output_text="a b c d " * 3,
        gpu_output_text="plain gpu text",
        prompt_text="hello there",
        max_prompt_len=128,
        weight_precision="int4",
        output_tokens=tokens,
    )
    assert decision["status"] == "refused"
    assert decision["reason"] == "repeat_4gram"
    assert decision["timed"] is False
    assert decision["exact_match_vs_gpu"] is False


def test_half_repeats_are_not_a_refusal() -> None:
    tokens = ["the", "the", "the", "the", "the"]
    fraction = fourgram_repeat_fraction(tokens)
    assert fraction == 0.5
    decision = decide_npu_cell(
        output_text="the the the the the",
        gpu_output_text="the the the the the",
        prompt_text="one two",
        max_prompt_len=8,
        weight_precision="int4",
        output_tokens=tokens,
    )
    assert decision["status"] == "valid"
    assert decision["timed"] is True
    assert decision["exact_match_vs_gpu"] is True


def test_prompt_past_max_prompt_len_is_infeasible() -> None:
    decision = decide_npu_cell(
        output_text="should not be timed",
        gpu_output_text="should not be timed",
        prompt_text="one two three four",
        max_prompt_len=3,
        weight_precision="int4",
    )
    assert decision["status"] == "infeasible"
    assert decision["reason"] == "prompt_longer_than_max_prompt_len"
    assert decision["prompt_length"] == 4
    assert decision["max_prompt_len"] == 3
    assert decision["max_prompt_len_property"] == "NPUW_LLM_MAX_PROMPT_LEN"
    assert decision["timed"] is False


def test_int8_is_infeasible_and_not_run_past_load() -> None:
    decision = decide_npu_cell(
        output_text="",
        gpu_output_text=None,
        prompt_text="short",
        max_prompt_len=128,
        weight_precision="int8",
    )
    assert decision["status"] == "infeasible"
    assert decision["reason"] == "npu_int8_not_run_past_load"
    assert decision["citation"] == "openvino#35641"
    assert decision["timed"] is False


def test_malformed_tool_call_refuses() -> None:
    decision = decide_npu_cell(
        output_text="<tool_call>{not json}</tool_call>",
        gpu_output_text='<tool_call>{"name": "add", "arguments": {}}</tool_call>',
        prompt_text="add two numbers",
        max_prompt_len=32,
        weight_precision="int4",
    )
    assert decision["status"] == "refused"
    assert decision["reason"] == "output_did_not_parse"
    assert decision["timed"] is False


def test_gpu_mismatch_is_recorded_and_still_valid() -> None:
    text = '<tool_call>{"name": "add", "arguments": {}}</tool_call>'
    decision = decide_npu_cell(
        output_text=text,
        gpu_output_text=text + " ",
        prompt_text="add",
        max_prompt_len=16,
        weight_precision="int4",
    )
    assert decision["status"] == "valid"
    assert decision["exact_match_vs_gpu"] is False
    assert decision["timed"] is True
