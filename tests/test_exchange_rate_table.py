"""Exchange-rate table arithmetic, and the runner's refusal to read the prereg."""

from __future__ import annotations

from pathlib import Path

from seam.tools.exchange_rate_table import what_fits

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
