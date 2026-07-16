"""Prefill attribution and token-level LCP diffing for TurnTrace v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


PrefillFn = Callable[[int], float]


@dataclass(frozen=True)
class TokenDiffResult:
    new_tokens_this_turn: int
    retemplated_tokens: int
    lcp_tokens: int
    prior_len: int
    current_len: int


@dataclass(frozen=True)
class AttributionResult:
    prefill_necessary_tokens: int
    prefill_redundant_tokens: int
    t_prefill_necessary_ms: float
    t_prefill_redundant_ms: float
    negative_residual: bool
    retemplated_tokens: int


def tokenize_text(text: str, *, tokenizer_id: str = "whitespace_v0") -> list[str]:
    """Deterministic tokenizer used for offline tests and delta storage.

    Production runs must substitute the engine's own tokenizer identity and
    encode via that tokenizer; this helper exists so LCP logic is unit-testable
    without llama.cpp / cloud SDKs.

    Engine/API tokenizer IDs (``llamacpp:*``, ``api_usage:*``) fall back to
    whitespace splitting for offline LCP only — CallRecord token *counts* must
    still come from the engine/API usage fields on the raw event.
    """
    if tokenizer_id in ("whitespace_v0",) or tokenizer_id.startswith(
        ("llamacpp:", "llamacpp-python:", "api_usage:")
    ):
        return text.split()
    if tokenizer_id == "char_v0":
        return list(text)
    raise ValueError(f"unsupported tokenizer_id: {tokenizer_id}")


def token_lcp_diff(
    prior_tokens: Sequence[str],
    current_tokens: Sequence[str],
    *,
    prior_semantic_tokens: Sequence[str] | None = None,
) -> TokenDiffResult:
    """Exact token-level LCP diff.

    Tokens after the LCP are *new_tokens_this_turn* (they cost prefill).
    If ``prior_semantic_tokens`` is provided and the failed-LCP region of
    ``current_tokens`` overlaps semantically with prior content under a
    different surface form, those tokens are counted in ``retemplated_tokens``
    but still remain in ``new_tokens_this_turn`` (they genuinely cost prefill).
    """
    n = min(len(prior_tokens), len(current_tokens))
    lcp = 0
    while lcp < n and prior_tokens[lcp] == current_tokens[lcp]:
        lcp += 1
    new_tokens = len(current_tokens) - lcp
    retemplated = 0
    if prior_semantic_tokens is not None and new_tokens > 0:
        # Conservative: any current token after LCP that appears in the prior
        # semantic token multiset is treated as re-templated surface rewrite.
        prior_bag = set(prior_semantic_tokens)
        for tok in current_tokens[lcp:]:
            if tok in prior_bag:
                retemplated += 1
    return TokenDiffResult(
        new_tokens_this_turn=new_tokens,
        retemplated_tokens=retemplated,
        lcp_tokens=lcp,
        prior_len=len(prior_tokens),
        current_len=len(current_tokens),
    )


def count_redundant_tokens(
    *,
    context_tokens_in: int,
    new_tokens_this_turn: int,
    prefix_hit_tokens: int,
) -> int:
    return max(0, context_tokens_in - new_tokens_this_turn - prefix_hit_tokens)


def attribute_prefill(
    *,
    t_prefill_ms: float,
    context_tokens_in: int,
    new_tokens_this_turn: int,
    prefix_hit_tokens: int,
    f_prefill: PrefillFn,
    retemplated_tokens: int = 0,
    ideal_cache: bool = False,
    negative_tol_rel: float | None = None,
) -> AttributionResult:
    """Split observed prefill into necessary vs redundant via f(n).

    Under ideal-cache-simulated mode, necessary tokens are only the new tokens
    this turn (previously seen tokens are treated as prefix hits).

    D1 — Intercept booking (conservative by construction): f(n) typically has a
    nonzero intercept (fixed per-call overhead). Because
    ``t_prefill_redundant = t_prefill − f(necessary_tokens)``, that intercept is
    subtracted once inside f(necessary) and therefore lands entirely in
    t_prefill_necessary, biasing harness tax *downward* — against the thesis,
    deliberately, so we do not over-claim orchestration-induced model time.
    """
    if ideal_cache:
        necessary_tokens = max(0, new_tokens_this_turn)
        redundant_tokens = max(0, context_tokens_in - necessary_tokens - prefix_hit_tokens)
    else:
        necessary_tokens = max(0, new_tokens_this_turn)
        # Tokens whose KV could not have been retained under ideal-cache are
        # already excluded from prefix_hit_tokens; remaining historical tokens
        # without a hit are redundant.
        redundant_tokens = count_redundant_tokens(
            context_tokens_in=context_tokens_in,
            new_tokens_this_turn=new_tokens_this_turn,
            prefix_hit_tokens=prefix_hit_tokens,
        )
    t_necessary = float(f_prefill(necessary_tokens))
    residual = float(t_prefill_ms) - t_necessary
    if negative_tol_rel is None:
        from apu_characterization.turntrace_v2.contracts import load_protocol

        negative_tol_rel = float(load_protocol()["audit_gates"]["profile_consistency_rel"])
    # Within the profile-consistency band, a slightly-under f(necessary) reading
    # is measurement noise — not an integrity failure.
    if residual < 0.0 and t_necessary > 0 and abs(residual) / t_necessary <= float(negative_tol_rel):
        residual = 0.0
    negative = residual < 0.0
    t_redundant = 0.0 if negative else residual
    return AttributionResult(
        prefill_necessary_tokens=necessary_tokens,
        prefill_redundant_tokens=redundant_tokens,
        t_prefill_necessary_ms=t_necessary,
        t_prefill_redundant_ms=t_redundant,
        negative_residual=negative,
        retemplated_tokens=retemplated_tokens,
    )


def harness_tax_ms(*, t_orch_pre_ms: float, t_orch_post_ms: float, t_prefill_redundant_ms: float) -> float:
    return float(t_orch_pre_ms) + float(t_orch_post_ms) + float(t_prefill_redundant_ms)
