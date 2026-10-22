"""Retention budget for DEMO-2 revised arm C (Task BC; default off).

Registered in docs/amendments/DEMO2_ARMS_REVISED_2026-10-21.md. Two parts:

1. Insertion truncation. Each tool observation longer than K model tokens is
   cut once, when it is inserted, to at most K kept tokens plus one marker
   "[... N tokens elided ...]". Shapes:
   - "head": the first K tokens (L1 comparison only; rejected for arm C);
   - "h70t30": the first ceil(0.7 K) tokens and the last K - head tokens
     (tail at least 128), marker between them;
   - "json": if the text parses as a JSON object or array, shrink the longest
     list (drop middle items, keep head and tail items, insert one marker
     string item) or the longest string (keep head and tail characters) until
     the dump is at most K tokens; every key and every scalar outside the
     shrunk containers is kept. Falls back to h70t30 if the text is not JSON
     or cannot be brought under K.
   Observations of at most K tokens are passed through byte-identical (unlike
   OBS_MASK, whitespace is never collapsed).

2. Lazy age-masking (age_mask=True). Only when a step's rendered prompt plus
   max_new_tokens would exceed the context window: replace the oldest tool
   observation (never one of the last 3 tool messages) with
   "[earlier tool output omitted: N tokens]", re-render, repeat until it fits
   or nothing is left to mask. A masked observation stays masked (frozen).
   If it still does not fit, the existing ctx_overflow check fires.

Same interface as tools.h1_obs_mask.ObservationMask (apply, plan_record,
ledger, context), so it plugs into the local session and the cloud loop the
same way. Tool state is never changed; only the text the model sees.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from typing import Any

ARM = "RETENTION_BUDGET"
SHAPES = ("head", "h70t30", "json")
MIN_TAIL = 128
KEEP_LAST_TOOL_MESSAGES = 3

Encode = Callable[[str], list[int]]
Decode = Callable[[list[int]], str]


def marker(n: int) -> str:
    return f"[... {n} tokens elided ...]"


def mask_text(n: int) -> str:
    return f"[earlier tool output omitted: {n} tokens]"


def _head_tail_split(k: int) -> tuple[int, int]:
    head = math.ceil(0.7 * k)
    tail = k - head
    if tail < MIN_TAIL:
        tail = min(MIN_TAIL, k)
        head = k - tail
    return head, tail


def truncate_tokens(text: str, k: int, shape: str, encode: Encode, decode: Decode) -> str:
    """head or h70t30 on model tokens. Text of at most K tokens is unchanged."""
    ids = encode(text)
    n = len(ids)
    if n <= k:
        return text
    if shape == "head":
        return decode(ids[:k]) + "\n" + marker(n - k)
    head, tail = _head_tail_split(k)
    return decode(ids[:head]) + "\n" + marker(n - head - tail) + "\n" + decode(ids[n - tail :])


def _longest(node: Any, path: tuple[Any, ...] = ()) -> tuple[int, tuple[Any, ...]] | None:
    """(size, path) of the largest list (by items) or string (by chars) inside node."""
    best: tuple[int, tuple[Any, ...]] | None = None
    if isinstance(node, list):
        best = (len(node) * 8, path) if len(node) > 2 else None
        children: Any = enumerate(node)
    elif isinstance(node, dict):
        children = node.items()
    else:
        if isinstance(node, str) and len(node) > 64:
            return (len(node), path)
        return None
    for key, child in children:
        cand = _longest(child, (*path, key))
        if cand is not None and (best is None or cand[0] > best[0]):
            best = cand
    return best


def _get(node: Any, path: tuple[Any, ...]) -> Any:
    for key in path:
        node = node[key]
    return node


def _set(root: Any, path: tuple[Any, ...], value: Any) -> Any:
    if not path:
        return value
    parent = _get(root, path[:-1])
    parent[path[-1]] = value
    return root


def _shrink(value: Any) -> Any:
    """One shrink step: halve a list's middle or a string's middle."""
    if isinstance(value, list):
        n = len(value)
        keep = max(2, n // 2)
        head = math.ceil(keep * 0.7)
        tail = keep - head
        dropped = n - head - tail
        return [*value[:head], f"[... {dropped} items elided ...]", *value[n - tail :]]
    s = str(value)
    keep = max(32, len(s) // 2)
    head = math.ceil(keep * 0.7)
    tail = keep - head
    return s[:head] + f"[... {len(s) - head - tail} chars elided ...]" + s[len(s) - tail :]


def truncate_json(text: str, k: int, encode: Encode, decode: Decode) -> str:
    """JSON-aware shrink; h70t30 fallback. Text of at most K tokens is unchanged."""
    n = len(encode(text))
    if n <= k:
        return text
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return truncate_tokens(text, k, "h70t30", encode, decode)
    if not isinstance(doc, (dict, list)):
        return truncate_tokens(text, k, "h70t30", encode, decode)
    for _ in range(200):
        out = json.dumps(doc)
        m = len(encode(out))
        if m <= k:
            return out + "\n" + marker(n - m)
        target = _longest(doc)
        if target is None:
            break
        doc = _set(doc, target[1], _shrink(_get(doc, target[1])))
    return truncate_tokens(text, k, "h70t30", encode, decode)


def truncate_observation(text: str, k: int, shape: str, encode: Encode, decode: Decode) -> str:
    if shape not in SHAPES:
        raise ValueError(f"retention shape must be one of {SHAPES}, got {shape!r}")
    if int(k) < 1:
        raise ValueError(f"retention K must be >= 1, got {k}")
    if shape == "json":
        return truncate_json(text, k, encode, decode)
    return truncate_tokens(text, k, shape, encode, decode)


class RetentionBudget:
    """Insertion truncation at K tokens and (optionally) lazy age-masking."""

    def __init__(
        self,
        k: int,
        *,
        shape: str,
        encode: Encode,
        decode: Decode,
        age_mask: bool = False,
    ) -> None:
        if shape not in SHAPES:
            raise ValueError(f"retention shape must be one of {SHAPES}, got {shape!r}")
        if int(k) < 1:
            raise ValueError(f"retention K must be >= 1, got {k}")
        self.k = int(k)
        self.shape = shape
        self.encode = encode
        self.decode = decode
        self.age_mask = bool(age_mask)
        self.records: list[dict[str, Any]] = []
        self.mask_events: list[dict[str, Any]] = []
        self.context: dict[str, Any] = {}

    def apply(
        self,
        calls: Sequence[Any],
        results: Sequence[Any],
        *,
        source: str,
        entry_id: str,
        turn: int | None,
    ) -> list[str]:
        out: list[str] = []
        for call, result in zip(calls, results, strict=False):
            text = str(result)
            kept = truncate_observation(text, self.k, self.shape, self.encode, self.decode)
            n0 = len(self.encode(text))
            self.records.append(
                {
                    **self.context,
                    "source": source,
                    "entry_id": entry_id,
                    "turn": turn,
                    "call": str(call).split("(", 1)[0],
                    "original_tokens": n0,
                    "kept_tokens": len(self.encode(kept)),
                    "truncated": kept != text,
                }
            )
            out.append(kept)
        return out

    def fit(
        self,
        messages: list[dict[str, Any]],
        *,
        count: Callable[[list[dict[str, Any]]], int],
        max_new_tokens: int,
        window: int,
        where: dict[str, Any],
    ) -> list[int]:
        """Mask oldest tool messages in place until count + max_new fits. Returns masked idx."""
        masked: list[int] = []
        if not self.age_mask:
            return masked
        n = count(messages)
        while n + int(max_new_tokens) > int(window):
            tool_idx = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
            eligible = [
                i
                for i in tool_idx[: max(0, len(tool_idx) - KEEP_LAST_TOOL_MESSAGES)]
                if not str(messages[i].get("content", "")).startswith("[earlier tool output")
            ]
            if not eligible:
                break
            i = eligible[0]
            old = str(messages[i].get("content", ""))
            messages[i] = {**messages[i], "content": mask_text(len(self.encode(old)))}
            masked.append(i)
            before = n
            n = count(messages)
            self.mask_events.append(
                {**self.context, **where, "message_index": i, "prompt_before": before, "after": n}
            )
        return masked

    def plan_record(self) -> dict[str, Any]:
        return {
            "arm": ARM,
            "k": self.k,
            "unit": "model tokens (pinned HF tokenizer)",
            "shape": self.shape,
            "age_mask": self.age_mask,
            "keep_last_tool_messages": KEEP_LAST_TOOL_MESSAGES,
            "marker": marker(0).replace("0", "N"),
            "transform": "tools.h1_retention_budget.truncate_observation",
            "applies_to": ["local session tool observations", "cloud agent tool results"],
        }

    def ledger(self) -> dict[str, Any]:
        return {
            **self.plan_record(),
            "n_observations": len(self.records),
            "n_truncated": sum(1 for r in self.records if r["truncated"]),
            "observations": list(self.records),
            "age_mask_events": list(self.mask_events),
        }


def hf_codec(tokenizer: Any) -> tuple[Encode, Decode]:
    def encode(text: str) -> list[int]:
        return list(tokenizer(text, add_special_tokens=False)["input_ids"])

    def decode(ids: list[int]) -> str:
        return str(tokenizer.decode(ids, skip_special_tokens=False))

    return encode, decode
