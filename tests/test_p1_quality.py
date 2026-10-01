"""P1 vote, retry, budget fallback, and the runner's refusal to read a prereg."""

from __future__ import annotations

import inspect
import json
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
    assert "Invoke-P1Smokes" not in text
    assert "Invoke-P1Budget" in text
    assert '$smokeArgs = @($PythonExe, "-u", $P1Py, "--canary-calibrate")' in text
    pre = (ROOT / "tools" / "launch_p1_preflight.ps1").read_text(encoding="utf-8")
    assert "--smoke" in pre
    assert "run_p1_quality.py" in pre


def test_canary_opening_runs_before_the_pipeline_is_loaded() -> None:
    from tools.run_p1_quality import prepare_measurement_canary

    events: list[str] = []

    class Slot:
        def release(self) -> None:
            events.append("release")

        def load(self) -> None:
            events.append("load")

    class Guard:
        def __init__(self) -> None:
            self.run_canary = self._run

        def opening(self) -> None:
            events.append("opening")
            self.run_canary(after_probe_count=-1, warmup=True)
            self.run_canary(after_probe_count=-1)

        def _run(self, **_kwargs: object) -> dict[str, object]:
            events.append("canary")
            return {}

    guard = Guard()
    prepare_measurement_canary(guard, Slot())
    guard.run_canary(after_probe_count=31)
    assert events == [
        "opening",
        "canary",
        "canary",
        "load",
        "release",
        "canary",
        "load",
    ]
    import tools.run_p1_quality as runner

    source = inspect.getsource(runner.run_measurement)
    assert "prepare_measurement_canary" in source
    assert "load_arm_pipeline" not in source


def test_summary_carries_canary_series_and_thresholds() -> None:
    from tools.run_p1_quality import quality_summary

    class Guard:
        gate = {
            "threshold_t1": 0.07709453214145699,
            "threshold_t2": 0.1642942216508742,
            "ref_turn1_prefill_s": 2.57162915,
            "ref_turn2_prefill_s": 0.963638488,
        }
        canaries = [{"canary_index": 0, "warmup": True, "turn2_prefill_s": 1.0}]

        def plan_fragment(self) -> dict[str, object]:
            return {"canary_gate": self.gate}

    summary = quality_summary(
        session_id="s",
        status="FAIL_CANARY_DRIFT",
        arm="A0",
        seed=1,
        points=[{"passed": False, "in_budget_pass": False}],
        guard=Guard(),
        pipeline_loads=1,
        load_s=1.0,
        load_meta=None,
        abort_reason="drift",
    )
    assert summary["entries_completed"] == 1
    assert summary["n_probes"] == 1
    assert summary["canaries"] == Guard.canaries
    assert summary["thresholds"]["threshold_t2"] == 0.1642942216508742
    assert summary["canary"]["canary_gate"]["ref_turn2_prefill_s"] == 0.963638488


def test_healthy_calibration_band_is_the_pooled_settled_range() -> None:
    from tools.run_p1_quality import calibration_ref_in_healthy_range

    assert calibration_ref_in_healthy_range(0.70)
    assert calibration_ref_in_healthy_range(0.76)
    assert calibration_ref_in_healthy_range(0.719)
    assert calibration_ref_in_healthy_range(0.963638488) is False
    assert calibration_ref_in_healthy_range(0.699) is False


def test_refused_session_summary_records_the_canary_series() -> None:
    path = ROOT / "derived" / "p1_quality" / "26118b6c-e584-4670-947b-8abae38f584d" / "summary.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["status"] == "FAIL_CANARY_DRIFT"
    assert doc["entries_completed"] == 101
    assert doc["n_probes"] == 101
    assert len(doc["canary_series"]) == 5
    assert len(doc["canaries"]) == 5
    assert doc["thresholds"]["threshold_t1"] == 0.07709453214145699
    assert doc["thresholds"]["threshold_t2"] == 0.1642942216508742
    assert doc["thresholds"]["ref_turn2_prefill_s"] == 0.963638488
    assert doc["canary_series"][0]["warmup"] is True
    assert doc["canary_series"][-1]["t2"] == 0.771533325
    assert doc["pipeline_state"]["canary_process_ids"] == [17844, 17844, 17844, 17844, 17844]
