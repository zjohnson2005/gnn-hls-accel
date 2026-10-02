"""P1 vote, retry, budget fallback, and the runner's refusal to read a prereg."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from seam.tools.p1_quality import (
    capped_new_tokens,
    check_pre_execution,
    entry_record,
    feedback_sha256,
    feedback_text,
    in_budget_pass,
    majority_vote,
    measured_batch_rate,
    normalize_tool_call,
    recover_entry_record,
    run_smoke,
    should_resample,
    strip_prior_thinking,
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
    override, split, cutoff, backed = result["arms"]["A1"]
    assert override["n_samples"] == 4
    assert override["source"] == "override"
    assert override["override"] is True
    assert override["agreement"] is True
    assert override["met_budget"] is True
    assert len(set(override["extras_call_sha256"])) == 1
    assert override["greedy_call_sha256"] not in override["extras_call_sha256"]
    assert split["source"] == "greedy"
    assert split["override"] is False
    assert split["agreement"] is False
    assert split["met_budget"] is True
    assert cutoff["met_budget"] is True
    assert cutoff["k_used"] == 1
    assert cutoff["tta_s"] == 10.0
    assert backed["fallback_to_greedy"] is True
    assert backed["source"] == "greedy"
    assert backed["met_budget"] is True
    assert result["arms"]["A2"][0]["retried"] is True
    assert result["arms"]["A2"][1]["retry_unfinished"] is True
    assert result["arms"]["A2"][1]["met_budget"] is True
    assert result["arms"]["A3"][0]["retried"] is True
    assert result["arms"]["A3"][1]["met_budget"] is True
    thinking = result["arms"]["A4"][0]
    assert thinking["thinking_stripped"] is True
    assert "<think>" not in thinking["retained_text"]
    assert thinking["emitted_chars"] > thinking["retained_chars"]
    assert thinking["token_cap"] == 100
    recovered, kept = result["arms"]["A5"]
    assert recovered["source"] == "feedback"
    assert recovered["checks"] == ["unknown_function", "ok"]
    assert recovered["executed"] is True
    assert recovered["attempts"] == 2
    assert recovered["met_budget"] is True
    assert kept["source"] == "greedy"
    assert kept["check_result"] == "unknown_function"
    assert kept["executed"] is False
    assert kept["retry_unfinished"] is True
    assert kept["met_budget"] is True


def test_extra_cap_uses_the_measured_batch_row() -> None:
    cfg = yaml.safe_load((ROOT / "configs" / "p1_quality.yaml").read_text(encoding="utf-8"))
    chosen = measured_batch_rate(
        cfg["batched_tok_s"],
        requested_k=int(cfg["extra_batch_k"]),
        n_ctx=4000,
        band_threshold=int(cfg["context_band_threshold"]),
    )
    assert chosen["band"] == 4000
    assert chosen["table_k"] == 4
    assert chosen["rate_tok_s"] == 60.98813887904501
    assert capped_new_tokens(remaining_s=6.0, rate_tok_s=chosen["rate_tok_s"], batch_k=4) == 91
    unknown = measured_batch_rate(
        cfg["batched_tok_s"],
        requested_k=3,
        n_ctx=None,
        band_threshold=int(cfg["context_band_threshold"]),
    )
    assert unknown["band"] == 6000
    wide = measured_batch_rate(
        cfg["batched_tok_s"],
        requested_k=1,
        n_ctx=None,
        band_threshold=int(cfg["context_band_threshold"]),
    )
    assert wide["band"] == 4000
    assert wide["rate_tok_s"] == 25.269383662886206


def test_thinking_strip_drops_the_block_and_keeps_the_answer() -> None:
    call = '{"name": "get_weather", "arguments": {"city": "Paris"}}'
    stripped = strip_prior_thinking("<think>\nplan the call\n</think>\n" + call)
    assert stripped["thinking_stripped"] is True
    assert "<think>" not in stripped["retained_text"]
    assert call in stripped["retained_text"]
    assert stripped["emitted_chars"] > stripped["retained_chars"]


def test_entry_record_keeps_missing_fields_null() -> None:
    point = {
        "id": "multi_turn_base_0",
        "passed": True,
        "in_budget_pass": False,
        "steps": [
            {
                "tta_s": 15.0,
                "fallback": True,
                "met_budget": False,
                "n_samples": 4,
                "tokens": 896,
            }
        ],
    }
    row = entry_record(point)
    assert row["pass"] is True
    assert row["in_budget"] is False
    assert row["steps"][0]["vote_agreement"] is None
    assert row["steps"][0]["k_used"] is None
    recovered = recover_entry_record(point)
    assert recovered["steps"][0]["emitted_tokens"] == 896
    assert recovered["steps"][0]["samples_finished"] == 4
    assert recovered["steps"][0]["k_used"] is None
    assert recovered["steps"][0]["vote_agreement"] is None
    assert recovered["steps"][0]["retained_tokens"] is None


def test_runner_writes_entries_jsonl() -> None:
    from tools.run_p1_quality import run_measurement

    source = inspect.getsource(run_measurement)
    assert "entries.jsonl" in source
    assert "_append_entry_jsonl" in source


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


def test_calibrate_only_skips_the_probe_budget() -> None:
    import inspect

    from tools.boot4_session import _open_canary
    from tools.run_p1_quality import run_canary_calibration
    from tools.ttft_slo_canary import CanaryBudgetRefuse, TtftSloCanaryGuard

    source = inspect.getsource(run_canary_calibration)
    assert "enforce_probe_budget=False" in source
    assert "planned=3" in source
    with pytest.raises(CanaryBudgetRefuse):
        TtftSloCanaryGuard(
            root=ROOT,
            model_spec=ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml",
            work_dir=ROOT / "derived" / "p1_quality" / "_budget_probe",
            planned_probe_count=3,
        )
    guard = TtftSloCanaryGuard(
        root=ROOT,
        model_spec=ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml",
        work_dir=ROOT / "derived" / "p1_quality" / "_budget_probe",
        planned_probe_count=3,
        enforce_probe_budget=False,
    )
    assert guard.budget_preflight["skipped"] is True
    assert guard.n_derivation["refuse"] is False
    opener = inspect.getsource(_open_canary)
    assert "enforce_probe_budget=enforce_probe_budget" in opener


def test_a1_dry_run_is_the_registered_first_half() -> None:
    env = os.environ.copy()
    command = (
        "Set-StrictMode -Version Latest; "
        f"& '{ROOT / 'tools' / 'launch_p1_a1.ps1'}' -DryRun; "
        "exit $LASTEXITCODE"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "DRY_RUN_OK" in combined
    assert "--arm A1" in combined
    assert "--seed 20260930" in combined
    assert "--entry-offset 0" in combined
    assert "--entry-count 100" in combined
    assert "p1_a1_estimate_s=4377" in combined
    assert "fits_one_window=true" in combined


def test_a4_dry_run_is_the_registered_first_half() -> None:
    env = os.environ.copy()
    command = (
        "Set-StrictMode -Version Latest; "
        f"& '{ROOT / 'tools' / 'launch_p1_a4.ps1'}' -DryRun; "
        "exit $LASTEXITCODE"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "DRY_RUN_OK" in combined
    assert "--arm A4" in combined
    assert "--seed 20260930" in combined
    assert "--entry-offset 0" in combined
    assert "--entry-count 100" in combined
    assert "p1_a4_estimate_s=4500" in combined
    assert "fits_one_window=true" in combined
    boot = (ROOT / "tools" / "launch_boot1.ps1").read_text(encoding="utf-8")
    assert "p1-a4" in boot
    assert "-P1Seed $P1Seed -P1EntryOffset $P1EntryOffset -P1EntryCount $P1EntryCount" in boot


def test_amendment_5_keeps_the_measured_ranges_and_labels_the_unbounded_run() -> None:
    from tools.score_p1_a0 import K_COUNTS, pass_at_k_ceiling, rate_arm

    path = ROOT / "derived" / "h1_hybrid" / "LOCAL_QUALITY_AMENDMENT_5.json"
    amendment = json.loads(path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == "a98697c9b3ccc819e3a9d687fc137cd68dcf1770e90aacce338ffe2e760d1569"
    assert amendment["a1_measurement_status"] == "not_started"
    assert amendment["registered_before_any_a1_rerun"] is True
    assert amendment["prior_amendments_unchanged"] is True
    unbounded = amendment["a1_unbounded"]
    assert unbounded["label"] == "A1-unbounded"
    assert unbounded["registered_comparison"] is False
    assert unbounded["run_id"] == "385cd4f6-47d4-4ed0-8031-87ac7ef21816"
    assert unbounded["passes"] == 14
    assert unbounded["in_budget_passes"] == 9
    a1 = amendment["predictions"]["A1"]
    assert a1["in_budget_passes_per_seed"]["low"] == 23
    assert a1["in_budget_passes_per_seed"]["high"] == pass_at_k_ceiling(23, K_COUNTS)
    assert amendment["predictions"]["A2"]["in_budget_passes_per_seed"] == rate_arm(23, 46)
    assert amendment["predictions"]["A3"]["in_budget_passes_per_seed"] == rate_arm(23, 35)
    assert amendment["predictions"]["A4"]["in_budget_passes_per_seed"] == 4
    assert amendment["direction"] == "greater than A0"
    prior = json.loads(
        (ROOT / "derived" / "h1_hybrid" / "LOCAL_QUALITY_AMENDMENT_4.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        amendment["amended_file_sha256"]
        == hashlib.sha256(
            (ROOT / "derived" / "h1_hybrid" / "LOCAL_QUALITY_AMENDMENT_4.json").read_bytes()
        ).hexdigest()
    )
    assert prior["id"] == "LOCAL-QUALITY-AMENDMENT-4"


def test_amendment_6_registers_the_unanimous_rule_and_the_a4_schedule() -> None:
    path = ROOT / "derived" / "h1_hybrid" / "LOCAL_QUALITY_AMENDMENT_6.json"
    amendment = json.loads(path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == "c082e57a855d17a01bc108fa0c012598903795ae13f502109d1f7a61cc845105"
    assert amendment["registered_before_any_a4_run"] is True
    assert amendment["prior_amendments_unchanged"] is True
    assert amendment["next_arm"] == "A4"
    assert amendment["schedule"] == ["A4", "A2", "A3", "A1"]
    assert amendment["a4_measurement_status"] == "not_started"
    assert amendment["a1_bounded_measurement_status"] == "not_started"
    result = amendment["a1_unbounded_result"]
    assert result["run_id"] == "385cd4f6-47d4-4ed0-8031-87ac7ef21816"
    assert result["raw_pass"] == {
        "b_a0_pass_a1_fail": 1,
        "c_a0_fail_a1_pass": 1,
        "p_exact": 1.0,
    }
    assert result["in_budget"]["b_a0_pass_a1_fail"] == 6
    assert result["in_budget"]["c_a0_fail_a1_pass"] == 1
    assert result["in_budget"]["p_exact"] == 0.125
    assert result["n_steps_tta_gt_10"] == 51
    assert result["n_steps"] == 822
    assert amendment["predictions"]["A1"]["vote"] == "unanimous finished extras, or keep greedy"
    assert amendment["predictions"]["A4"]["estimates_s"] == {"first_100": 4500, "second_100": 3898}
    assert (
        amendment["amended_file_sha256"]
        == hashlib.sha256(
            (ROOT / "derived" / "h1_hybrid" / "LOCAL_QUALITY_AMENDMENT_5.json").read_bytes()
        ).hexdigest()
    )


def test_a0_score_and_amendment_4_use_the_measured_rate() -> None:
    from tools.score_p1_a0 import (
        K_COUNTS,
        a0_points,
        paired_local_pass,
        pass_at_k_ceiling,
        rate_arm,
        step_stats,
    )

    points = a0_points()
    stats = step_stats(points)
    paired = paired_local_pass()
    assert sum(1 for point in points if point["in_budget_pass"]) == 23
    assert len(points) == 200
    assert stats["n_tta_gt_10"] == 0
    assert stats["n_fallback"] == 14
    assert paired["entries_that_differ"] == 2
    assert paired["both"] == 21
    ceiling = pass_at_k_ceiling(23, K_COUNTS)
    amendment = json.loads(
        (ROOT / "derived" / "h1_hybrid" / "LOCAL_QUALITY_AMENDMENT_4.json").read_text(
            encoding="utf-8"
        )
    )
    a1 = amendment["predictions"]["A1"]
    assert a1["in_budget_passes_per_seed"]["low"] == 23
    assert a1["in_budget_passes_per_seed"]["high"] == ceiling
    assert amendment["predictions"]["A2"]["in_budget_passes_per_seed"] == rate_arm(23, 46)
    assert amendment["predictions"]["A3"]["in_budget_passes_per_seed"] == rate_arm(23, 35)
    assert amendment["predictions"]["A4"]["uses_baseline_rate"] is False
    closeout = json.loads(
        (ROOT / "derived" / "p1_quality" / "analysis" / "A0_8a529053_CLOSEOUT.json").read_text(
            encoding="utf-8"
        )
    )
    assert closeout["verdict"] == "MISS_HIGH"
    assert closeout["observed_in_budget_passes"] == 23
    assert closeout["steps"]["n_steps"] == stats["n_steps"]
    assert closeout["verify_seal"] == "MATCH"


def _weather_tools() -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        }
    ]


def test_pre_execution_check_names_schema_failures() -> None:
    tools = _weather_tools()
    empty = check_pre_execution("  ", tools)
    assert empty["result"] == "empty" and empty["ok"] is False
    broken = check_pre_execution("not a call", tools)
    assert broken["result"] == "unparseable"
    unknown = check_pre_execution(
        json.dumps({"name": "missing_fn", "arguments": {}}),
        tools,
    )
    assert unknown["result"] == "unknown_function"
    assert unknown["name"] == "missing_fn"
    missing = check_pre_execution(
        json.dumps({"name": "get_weather", "arguments": {}}),
        tools,
    )
    assert missing["result"] == "missing_argument" and missing["argument"] == "city"
    extra = check_pre_execution(
        json.dumps({"name": "get_weather", "arguments": {"city": "Paris", "units": "C"}}),
        tools,
    )
    assert extra["result"] == "extra_argument" and extra["argument"] == "units"
    ill = check_pre_execution(
        json.dumps({"name": "get_weather", "arguments": {"city": 1}}),
        tools,
    )
    assert ill["result"] == "ill_typed" and ill["expected_type"] == "string"
    ok = check_pre_execution(
        json.dumps({"name": "get_weather", "arguments": {"city": "Paris"}}),
        tools,
    )
    assert ok["ok"] is True and ok["result"] == "ok"
    named = feedback_text(unknown)
    assert "missing_fn" in named
    assert feedback_sha256(named) == hashlib.sha256(named.encode("utf-8")).hexdigest()


def test_a5_dry_run_is_the_registered_first_half() -> None:
    command = (
        "Set-StrictMode -Version Latest; "
        f"& '{ROOT / 'tools' / 'launch_p1_a5.ps1'}' -DryRun; "
        "exit $LASTEXITCODE"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        env=os.environ.copy(),
        check=False,
        capture_output=True,
        text=True,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "DRY_RUN_OK" in combined
    assert "--arm A5" in combined
    assert "--seed 20260930" in combined
    assert "--entry-offset 0" in combined
    assert "--entry-count 100" in combined
    assert "p1_a5_estimate_s=2991" in combined
    assert "fits_one_window=true" in combined
    boot = (ROOT / "tools" / "launch_boot1.ps1").read_text(encoding="utf-8")
    assert "p1-a5" in boot
    assert "-P1Seed $P1Seed -P1EntryOffset $P1EntryOffset -P1EntryCount $P1EntryCount" in boot


def test_amendment_7_registers_feedback_retry_after_a4() -> None:
    from tools.score_p1_a0 import a0_points, rate_arm

    path = ROOT / "derived" / "h1_hybrid" / "LOCAL_QUALITY_AMENDMENT_7.json"
    amendment = json.loads(path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == "fc58a6abb1c253ceabf01483e0ff3186247716c939c3c86866c37c3a7ce15983"
    assert amendment["registered_before_any_a5_run"] is True
    assert amendment["prior_amendments_unchanged"] is True
    assert amendment["a5_measurement_status"] == "not_started"
    assert amendment["next_arm"] == "A4"
    assert amendment["schedule"] == ["A4", "A5", "A2", "A3", "A1"]
    assert amendment["comparison"].startswith("Paired McNemar against A0, computed per seed")
    points = a0_points()
    failturn = json.loads(
        (
            ROOT
            / "derived"
            / "h1_hybrid"
            / "analysis_d482c621"
            / "failturn"
            / "FAILTURN_RESULTS.json"
        ).read_text(encoding="utf-8")
    )
    classes = {
        str(row["entry_id"]): str(row["first_fail_bucket"])
        for row in failturn["per_entry"]
        if row["policy"] == "slo_escalate"
    }
    ordered = sorted(points, key=lambda row: str(row["id"]))
    failures = [row for row in ordered if not row["passed"]]
    buckets: dict[str, int] = {}
    for row in failures:
        bucket = classes[str(row["id"])]
        buckets[bucket] = buckets.get(bucket, 0) + 1
    assert len(ordered) == 200
    assert len(failures) == 177
    assert buckets == {"EMPTY": 44, "EXEC_RESP": 35, "MISMATCH": 98}
    eligible_ids = [str(row["id"]) for row in failures if classes[str(row["id"])] == "EMPTY"]
    assert len(eligible_ids) == 44
    halves = [str(row["id"]) for row in ordered[:100]], [str(row["id"]) for row in ordered[100:]]
    half_counts = [sum(1 for entry_id in half if entry_id in set(eligible_ids)) for half in halves]
    assert half_counts == [25, 19]
    prediction = amendment["predictions"]["A5"]
    assert prediction["in_budget_passes_per_seed"]["low"] == 23
    assert prediction["in_budget_passes_per_seed"]["high"] == rate_arm(23, 44)
    assert prediction["direction"] == "greater than A0"
    extra = (4239.760204818709 - 4055.8199962596145) / 46
    load_s = 5.211120400010259
    canary_s = 752.1359013
    walls = [
        sum(float(row["wall_s"]) for row in ordered[:100]),
        sum(float(row["wall_s"]) for row in ordered[100:]),
    ]
    estimates = [
        math.ceil(wall + count * extra + load_s + canary_s)
        for wall, count in zip(walls, half_counts, strict=True)
    ]
    assert estimates == [2991, 2863]
    assert prediction["estimates_s"] == {"first_100": 2991, "second_100": 2863}
    assert 2991 <= 7200 and 2863 <= 7200
    prior = ROOT / "derived" / "h1_hybrid" / "LOCAL_QUALITY_AMENDMENT_6.json"
    assert amendment["amended_file_sha256"] == hashlib.sha256(prior.read_bytes()).hexdigest()
    assert json.loads(prior.read_text(encoding="utf-8"))["schedule"] == ["A4", "A2", "A3", "A1"]
    cfg = yaml.safe_load((ROOT / "configs" / "p1_quality.yaml").read_text(encoding="utf-8"))
    assert cfg["arms"] == ["A0", "A1", "A2", "A3", "A4", "A5"]


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
