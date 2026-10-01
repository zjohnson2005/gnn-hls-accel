"""What fits in a fixed time-to-action budget. No model and no preregistration."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any


def what_fits(
    *,
    budget_s: float,
    prefill_s: float,
    decode_tok_s: float,
    tool_tokens: float,
) -> dict[str, Any]:
    """Sequential full calls and thinking tokens that finish inside the budget.

    The first call pays prefill. A later call on a cached prefix pays re-decode
    only, ``(tool_tokens - 1) / decode_tok_s``.
    """
    if decode_tok_s <= 0.0 or tool_tokens <= 1.0:
        raise ValueError("decode rate and tool length must be positive")
    retry_s = (tool_tokens - 1.0) / decode_tok_s
    if prefill_s >= budget_s:
        return {
            "full_calls": 0,
            "thinking_tokens": 0,
            "cached_retries_after_one_call": 0,
            "one_call_fits": False,
            "greedy_tta_s": prefill_s + retry_s,
            "cached_retry_s": retry_s,
        }
    thinking_tokens = math.floor((budget_s - prefill_s) * decode_tok_s)
    greedy_tta_s = prefill_s + retry_s
    one_call_fits = greedy_tta_s <= budget_s
    if not one_call_fits:
        retries = 0
        full_calls = 0
    else:
        remain = budget_s - greedy_tta_s
        retries = math.floor(remain / retry_s) if retry_s > 0.0 else 0
        full_calls = 1 + retries
    return {
        "full_calls": full_calls,
        "thinking_tokens": thinking_tokens,
        "cached_retries_after_one_call": retries,
        "one_call_fits": one_call_fits,
        "greedy_tta_s": greedy_tta_s,
        "cached_retry_s": retry_s,
    }


def streamer_allowed(n_seq: int) -> bool:
    """A streamer is legal only for one sequence.

    openvino.genai continuous_batching/pipeline_impl.cpp:530 rejects a
    streamer unless batch size is 1 and sampling is greedy or multinomial.
    More than one prompt, or num_return_sequences above 1, takes the
    unstreamed generate.
    """
    return int(n_seq) == 1


def isolated_probe(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """One probe. A failure is a row. It does not skip the probes that follow."""
    try:
        row = dict(fn())
    except Exception as exc:
        return {
            "name": name,
            "outcome": "fail",
            "failure_mode": f"{type(exc).__name__}:{exc}"[:500],
        }
    row["name"] = name
    row["outcome"] = "pass"
    row.pop("texts", None)
    return row


def skip_over_budget(
    *,
    name: str,
    projected_wall_s: float | None,
    budget_s: float,
    multiple: float | None,
) -> dict[str, Any] | None:
    """Skip when the projected wall is above multiple times the budget."""
    if projected_wall_s is None or multiple is None:
        return None
    limit = float(multiple) * float(budget_s)
    if float(projected_wall_s) <= limit:
        return None
    return {
        "name": name,
        "outcome": "SKIPPED_OVER_BUDGET",
        "projected_wall_s": float(projected_wall_s),
        "budget_s": float(budget_s),
        "skip_multiple": float(multiple),
        "limit_s": limit,
    }
