"""Exchange-rate table arithmetic, and the runner's refusal to read the prereg."""

from __future__ import annotations

from pathlib import Path

from seam.tools.exchange_rate_table import (
    cached_retry_pair,
    isolated_probe,
    skip_over_budget,
    streamer_allowed,
    what_fits,
)

ROOT = Path(__file__).resolve().parents[1]


def test_gpu_4000_matches_the_registered_cold_context_table() -> None:
    row = what_fits(
        budget_s=10.0,
        prefill_s=2.528209228,
        decode_tok_s=24.868473407312436,
        tool_tokens=102.04468915458858,
    )
    assert row["one_call_fits"] is True
    assert row["full_calls"] == 1
    assert row["thinking_tokens"] == 185
    assert row["cached_retries_after_one_call"] == 0
    assert abs(row["greedy_tta_s"] - 6.591373359533581) < 1e-9


def test_cpu_prefill_above_the_budget_fits_nothing() -> None:
    row = what_fits(
        budget_s=10.0,
        prefill_s=23.151441406,
        decode_tok_s=18.619462902214963,
        tool_tokens=102.04468915458858,
    )
    assert row["one_call_fits"] is False
    assert row["full_calls"] == 0
    assert row["thinking_tokens"] == 0


def test_runner_does_not_read_the_prereg() -> None:
    banned = ("EXCHANGE_RATE_PREREG", "LOCAL_QUALITY_AMENDMENT", "LOCAL_QUALITY_PREREG")
    paths = [
        ROOT / "tools" / "run_exchange_rate.py",
        ROOT / "tools" / "exchange_rate_session.py",
        ROOT / "seam" / "tools" / "_exchange_rate_child.py",
        ROOT / "seam" / "tools" / "exchange_rate_table.py",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path.name} mentions {token}"


def test_combined_budget_fits_one_window() -> None:
    text = (ROOT / "tools" / "launch_boot1.ps1").read_text(encoding="utf-8")
    assert 'Name = "P0 EXCHANGE-RATE"; Kind = "exchange"; EstimateS = 3150' in text
    assert 'Name = "RESIDENT-LIMIT u4"; Kind = "resident"; EstimateS = 1132' in text
    assert 1132 + 3150 <= 7200


def test_p0_v2_budget_fits_one_window() -> None:
    text = (ROOT / "tools" / "launch_boot1.ps1").read_text(encoding="utf-8")
    assert 'Name = "P0-V2 EXCHANGE-RATE"; Kind = "exchange"; EstimateS = 3159' in text
    assert 3159 <= 7200
    child = (ROOT / "seam" / "tools" / "_exchange_rate_child.py").read_text(encoding="utf-8")
    assert "pipeline_impl.cpp:530" in child


def test_one_failure_does_not_skip_the_next_probe() -> None:
    def ok() -> dict[str, object]:
        return {"wall_s": 1.0}

    def boom() -> dict[str, object]:
        raise RuntimeError("streaming refused")

    rows = [
        isolated_probe("batch-1", ok),
        isolated_probe("batch-2", boom),
        isolated_probe("batch-4", ok),
    ]
    assert [row["name"] for row in rows] == ["batch-1", "batch-2", "batch-4"]
    assert rows[1]["outcome"] == "fail"
    assert rows[2]["outcome"] == "pass"


def test_streamer_is_refused_above_batch_size_one() -> None:
    assert streamer_allowed(1) is True
    assert streamer_allowed(2) is False
    assert streamer_allowed(4) is False


def test_cpu_projection_above_three_budgets_is_skipped() -> None:
    skipped = skip_over_budget(
        name="batch-4",
        projected_wall_s=83.16506870000006,
        budget_s=10.0,
        multiple=3.0,
    )
    assert skipped is not None
    assert skipped["outcome"] == "SKIPPED_OVER_BUDGET"
    assert skipped["projected_wall_s"] == 83.16506870000006
    assert (
        skip_over_budget(name="batch-1", projected_wall_s=None, budget_s=10.0, multiple=3.0) is None
    )


def test_cached_retry_measures_the_second_call_of_the_same_prompt() -> None:
    prime, measure = cached_retry_pair("shared-prompt")
    assert prime == "shared-prompt"
    assert measure == prime
    calls: list[str] = []

    def generate(prompt: str) -> dict[str, float]:
        calls.append(prompt)
        return {"prefill_s": 2.4 if len(calls) == 1 else 0.08}

    generate(prime)
    reported = generate(measure)
    assert calls == ["shared-prompt", "shared-prompt"]
    assert reported["prefill_s"] == 0.08
    child = (ROOT / "seam" / "tools" / "_exchange_rate_child.py").read_text(encoding="utf-8")
    assert "intervening_prompts" in child
    assert "cached_retry_pair" in child
