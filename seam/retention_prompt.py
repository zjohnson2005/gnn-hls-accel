"""Semantic retention and the OBS_MASK arm.

docs/RETENTION_PROTOCOL.md is the registered rule. The prompt is the
required spans in original order, with nothing inserted in the gaps, and
its resident token count must equal the POSITIONAL budget for the cell.
OBS_MASK runs beside it and records K. This module does not read a
preregistration.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from seam.errors import SeamError

Span = tuple[int, int]
TokenCount = Callable[[str], int]


class RetentionError(SeamError):
    """A retention cell cannot be built without changing the rules."""


def whitespace_tokens(text: str) -> int:
    """CPU smoke counter. A cell passes its own counter into ``build_cell``."""
    if not text:
        return 0
    return len(text.split())


def semantic_prompt(source: str, spans: Sequence[Span]) -> str:
    """Concatenate required slices in document order. Insert nothing."""
    ordered = _ordered_spans(source, spans)
    return "".join(source[start:end] for start, end in ordered)


def mask_observation(text: str, k: int) -> str:
    """Keep the first K whitespace tokens. Drop the rest. Add no marker."""
    if k < 1:
        raise RetentionError(f"obs_mask K must be >= 1, got {k}")
    return " ".join(text.split()[:k])


def build_cell(
    *,
    source: str,
    spans: Sequence[Span],
    positional_budget_tokens: int,
    observations: Sequence[str],
    obs_mask_k: int,
    token_count: TokenCount = whitespace_tokens,
) -> dict[str, object]:
    """Build SEMANTIC and OBS_MASK for one cell. No device call."""
    if positional_budget_tokens < 1:
        raise RetentionError(f"positional budget must be >= 1, got {positional_budget_tokens}")
    prompt = semantic_prompt(source, spans)
    resident = token_count(prompt)
    if resident != positional_budget_tokens:
        raise RetentionError(
            "semantic resident token count "
            f"{resident} != positional budget {positional_budget_tokens}"
        )
    masked = [mask_observation(item, obs_mask_k) for item in observations]
    return {
        "semantic_prompt": prompt,
        "semantic_tokens": resident,
        "positional_budget_tokens": positional_budget_tokens,
        "obs_mask_k": obs_mask_k,
        "obs_mask": masked,
    }


def _ordered_spans(source: str, spans: Sequence[Span]) -> tuple[Span, ...]:
    if not spans:
        raise RetentionError("required spans are empty")
    ordered = tuple(sorted(spans, key=lambda item: (item[0], item[1])))
    cursor = 0
    for start, end in ordered:
        if start < cursor or end <= start or end > len(source):
            raise RetentionError(
                f"span {(start, end)} is out of order, overlapping, or outside the source"
            )
        cursor = end
    return ordered
