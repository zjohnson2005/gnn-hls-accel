"""NPU cell validity. A refused or infeasible cell is never a timing.

The output parser is seam.backends.local_openvino.parse_tool_calls, the
parser the GPU backend uses for the same prompt. See docs/NPU_PROTOCOL.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from seam.backends.local_openvino import parse_tool_calls

NGRAM = 4
REPEAT_FRACTION_MAX = 0.5
CITATION_GARBAGE = "openvino.genai#3255"
CITATION_INT8 = "openvino#35641"


def whitespace_tokens(text: str) -> list[str]:
    if not text:
        return []
    return text.split()


def fourgram_repeat_fraction(tokens: Sequence[Any]) -> float | None:
    """Share of 4-grams that repeat an earlier 4-gram. None when fewer than 4 tokens."""
    if len(tokens) < NGRAM:
        return None
    grams = [tuple(tokens[i : i + NGRAM]) for i in range(len(tokens) - NGRAM + 1)]
    seen: set[tuple[Any, ...]] = set()
    repeats = 0
    for gram in grams:
        if gram in seen:
            repeats += 1
        else:
            seen.add(gram)
    return repeats / len(grams)


def output_parses(text: str) -> bool:
    """True when the GPU tool-call parser accepts the text.

    Text with no ``<tool_call>`` envelope parses as no calls, which is what
    the GPU parser returns. A ``<tool_call>`` envelope that yields no call
    is a parse failure.
    """
    return "<tool_call>" not in text or bool(parse_tool_calls(text))


def decide_npu_cell(
    *,
    output_text: str,
    gpu_output_text: str | None,
    prompt_text: str,
    max_prompt_len: int | None,
    weight_precision: str,
    prompt_tokens: int | None = None,
    output_tokens: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Decide whether an NPU cell may be timed.

    ``max_prompt_len`` is ``NPUW_LLM_MAX_PROMPT_LEN`` as loaded. A prompt
    longer than that value, and an int8 weight load, are infeasible cells.
    Parse failures and degenerate repeats refuse the cell. Exact match with
    the paired GPU output is recorded and is not required.
    """
    tokens = prompt_tokens if prompt_tokens is not None else len(whitespace_tokens(prompt_text))
    record: dict[str, Any] = {
        "max_prompt_len_property": "NPUW_LLM_MAX_PROMPT_LEN",
        "max_prompt_len": max_prompt_len,
        "prompt_length": tokens,
        "weight_precision": weight_precision,
        "exact_match_vs_gpu": None,
        "repeat_4gram_fraction": None,
        "timed": False,
        "citation": None,
    }
    if weight_precision.lower() == "int8":
        record.update(
            status="infeasible",
            reason="npu_int8_not_run_past_load",
            citation=CITATION_INT8,
        )
        return record
    if max_prompt_len is None:
        record.update(status="refused", reason="max_prompt_len_not_recorded")
        return record
    if tokens > max_prompt_len:
        record.update(
            status="infeasible",
            reason="prompt_longer_than_max_prompt_len",
            citation=CITATION_GARBAGE,
        )
        return record
    if gpu_output_text is None:
        record.update(status="refused", reason="missing_gpu_reference")
        return record
    record["exact_match_vs_gpu"] = output_text == gpu_output_text
    if not output_parses(output_text):
        record.update(status="refused", reason="output_did_not_parse")
        return record
    gram_tokens = (
        list(output_tokens) if output_tokens is not None else whitespace_tokens(output_text)
    )
    fraction = fourgram_repeat_fraction(gram_tokens)
    record["repeat_4gram_fraction"] = fraction
    if fraction is not None and fraction > REPEAT_FRACTION_MAX:
        record.update(
            status="refused",
            reason="repeat_4gram",
            citation=CITATION_GARBAGE,
        )
        return record
    record.update(status="valid", reason=None, timed=True)
    return record
