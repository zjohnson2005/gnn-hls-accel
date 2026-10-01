"""P1 vote, retry, budget fallback, and the runner's refusal to read a prereg."""

from __future__ import annotations

import math
from pathlib import Path

import yaml

from seam.tools.p1_quality import (
    in_budget_pass,
    majority_vote,
    normalize_tool_call,
    run_smoke,
    should_resample,
    thinking_token_cap,
)

ROOT = Path(__file__).resolve().parents[1]


def test_vote_tie_keeps_the_first_sample() -> None:
    call = '{"name": "get_weather", "arguments": {"city": "Paris"}}'
    other = '{"name": "get_weather", "arguments": {"city": "Lyon"}}'
    vote = majority_vote([call, other, other, call])
    assert vote["tie"] is True
    assert vote["index"] == 0
    assert normalize_tool_call(str(vote["winner"])) == normalize_tool_call(call)


def test_resample_stops_at_the_budget() -> None:
    assert should_resample(arm="A2", reason="empty", elapsed_s=4.0, budget_s=10.0) is True
    assert should_resample(arm="A2", reason="empty", elapsed_s=10.0, budget_s=10.0) is False
    assert should_resample(arm="A3", reason="exec", elapsed_s=9.5, budget_s=10.0) is True
    assert should_resample(arm="A0", reason="empty", elapsed_s=1.0, budget_s=10.0) is False


def test_in_budget_pass_requires_every_step() -> None:
    assert in_budget_pass(passed=True, steps=[{"met_budget": True}, {"met_budget": False}]) is False
    assert in_budget_pass(passed=False, steps=[{"met_budget": True}]) is False
    assert in_budget_pass(passed=True, steps=[{"met_budget": True}]) is True


def test_thinking_cap_matches_the_warm_spare() -> None:
    decode = 25.269383662886206
    length = 102.04468915458858
    prefill = 0.419609313
    one = prefill + (length - 1.0) / decode
    spare = 10.0 - one
    assert thinking_token_cap(spare_s=spare, decode_tok_s=decode) == 141
    cfg = yaml.safe_load((ROOT / "configs" / "p1_quality.yaml").read_text(encoding="utf-8"))
    assert int(cfg["thinking_cap_tokens"]) == 141
    assert math.floor(spare * decode) == 141


def test_smoke_covers_vote_retry_and_fallback() -> None:
    result = run_smoke()
    assert result["ok"] is True
    assert result["arms"]["A1"][0]["n_samples"] == 4
    assert result["arms"]["A2"][0]["retried"] is True
    assert result["arms"]["A3"][0]["retried"] is True
    assert result["arms"]["A1"][1]["fallback"] is True
    assert result["arms"]["A4"][0]["tokens"] == 141


def test_runner_does_not_read_a_preregistration() -> None:
    banned = ("EXCHANGE_RATE_PREREG", "LOCAL_QUALITY_AMENDMENT", "LOCAL_QUALITY_PREREG")
    paths = [
        ROOT / "tools" / "run_p1_quality.py",
        ROOT / "seam" / "tools" / "p1_quality.py",
        ROOT / "configs" / "p1_quality.yaml",
        ROOT / "tools" / "launch_p1_a0.ps1",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path.name} mentions {token}"


def test_first_boot_is_a0_and_fits() -> None:
    text = (ROOT / "tools" / "launch_boot1.ps1").read_text(encoding="utf-8")
    assert 'Name = "P1 A0"; Kind = "p1"; EstimateS = 4814' in text
    assert 4814 <= 7200
    assert "--smoke" in text
