from __future__ import annotations

from apu_characterization.turntrace_v2.attribution import (
    attribute_prefill,
    harness_tax_ms,
    token_lcp_diff,
    tokenize_text,
)


def test_token_lcp_diff_counts_suffix_as_new() -> None:
    prior = tokenize_text("a b c d")
    current = tokenize_text("a b c e f")
    diff = token_lcp_diff(prior, current)
    assert diff.lcp_tokens == 3
    assert diff.new_tokens_this_turn == 2
    assert diff.retemplated_tokens == 0


def test_retemplated_tokens_still_count_as_new() -> None:
    prior = tokenize_text("sys user hello world")
    # Surface rewrite of prior semantic tokens after LCP break.
    current = tokenize_text("sys USER hello world extra")
    diff = token_lcp_diff(
        prior,
        current,
        prior_semantic_tokens=prior,
    )
    assert diff.new_tokens_this_turn == 4  # USER hello world extra
    assert diff.retemplated_tokens >= 1


def test_attribute_prefill_splits_via_f() -> None:
    def f(n: int) -> float:
        return 0.1 * n

    result = attribute_prefill(
        t_prefill_ms=50.0,
        context_tokens_in=1000,
        new_tokens_this_turn=100,
        prefix_hit_tokens=0,
        f_prefill=f,
    )
    assert result.prefill_necessary_tokens == 100
    assert result.prefill_redundant_tokens == 900
    assert result.t_prefill_necessary_ms == 10.0
    assert result.t_prefill_redundant_ms == 40.0
    assert result.negative_residual is False


def test_negative_residual_clamped() -> None:
    def f(n: int) -> float:
        return 100.0

    result = attribute_prefill(
        t_prefill_ms=10.0,
        context_tokens_in=50,
        new_tokens_this_turn=50,
        prefix_hit_tokens=0,
        f_prefill=f,
    )
    assert result.t_prefill_redundant_ms == 0.0
    assert result.negative_residual is True


def test_harness_tax() -> None:
    assert harness_tax_ms(t_orch_pre_ms=2.0, t_orch_post_ms=1.0, t_prefill_redundant_ms=7.0) == 10.0
