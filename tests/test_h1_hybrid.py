"""Tests for tools/run_h1_hybrid.py (D-2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.phase_timers import phases_sum_to_wall  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    CostCapExceeded,
    CostGuard,
    StubCloudBackend,
    StubLocalBackend,
    assert_seal_allowed,
    cloud_usd,
    decide_bounceback,
    decide_emission_escalate,
    decide_slo_escalate,
    run_hybrid_entry,
    run_session,
)

FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_3entries.json"


def _load_fix() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_blinding_runner_source_has_no_prediction_paths() -> None:
    src = (ROOT / "tools" / "run_h1_hybrid.py").read_text(encoding="utf-8")
    # Exact prediction artifact names must never appear (read or cited).
    forbidden = (
        "H1_PREDICTIONS.md",
        "h1_predictions.json",
        "derived/d1_replay/H1_PREDICTIONS",
        "derived\\d1_replay\\H1_PREDICTIONS",
    )
    for tok in forbidden:
        assert tok not in src, f"blinding violated: {tok!r} appears in run_h1_hybrid.py"


def test_phase_timers_sum_on_hybrid_ledger(tmp_path: Path) -> None:
    fix = _load_fix()
    local = StubLocalBackend(script=fix["local_script"])
    cloud = StubCloudBackend(tokens_in=100, tokens_out=20)
    cost = CostGuard(max_usd=100.0)
    er = run_hybrid_entry(
        fix["entries"][2],
        policy="slo_escalate",
        local=local,
        cloud=cloud,
        cost=cost,
        model="stub-4B",
    )
    assert er.turns
    for t in er.turns:
        d = t.as_dict()
        assert phases_sum_to_wall(d, tol_s=1e-3)


def test_policy_dispatch_slo_and_emission_on_3entry_fixture(tmp_path: Path) -> None:
    fix = _load_fix()
    local = StubLocalBackend(script=fix["local_script"])
    cloud = StubCloudBackend(
        tokens_in=fix["cloud_tokens_in"],
        tokens_out=fix["cloud_tokens_out"],
    )

    # slo_escalate: entry_0 turn1 has n_ctx=12000 > 10000 → escalate
    er0 = run_hybrid_entry(
        fix["entries"][0],
        policy="slo_escalate",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert er0.turns[0].placement == "local"
    assert er0.turns[0].escalated is False
    assert er0.turns[1].escalated is True
    assert er0.turns[1].placement == "cloud"
    assert "ctx>" in (er0.turns[1].escalate_reason or "")
    assert er0.turns[2].placement == "cloud"
    assert er0.turns[2].escalate_reason == "stay_cloud"

    # emission_escalate: entry_1 turn0 has no parseable tool call
    er1 = run_hybrid_entry(
        fix["entries"][1],
        policy="emission_escalate",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert er1.turns[0].escalated is True
    assert er1.turns[0].escalate_reason == "no_parseable_tool_call"
    assert er1.turns[1].placement == "cloud"

    # cloud_only: every turn cloud
    er2 = run_hybrid_entry(
        fix["entries"][2],
        policy="cloud_only",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert all(t.placement == "cloud" and t.escalated for t in er2.turns)


def test_cost_guard_trips(tmp_path: Path) -> None:
    fix = _load_fix()
    local = StubLocalBackend(script=fix["local_script"])
    # One cloud turn ≈ cloud_usd(1000,200) = 0.006
    per = cloud_usd(1000, 200)
    cloud = StubCloudBackend(tokens_in=1000, tokens_out=200)
    with pytest.raises(CostCapExceeded) as ei:
        run_hybrid_entry(
            fix["entries"][2],
            policy="cloud_only",
            local=local,
            cloud=cloud,
            cost=CostGuard(max_usd=per * 0.5),
            model="stub-4B",
        )
    assert ei.value.partial is not None
    assert ei.value.partial.status == "aborted_cap"

    summary = run_session(
        policy="cloud_only",
        entries=fix["entries"],
        out_dir=tmp_path / "cap",
        max_usd=per * 0.5,
        local=local,
        cloud=cloud,
        skip_entry_assert=True,
    )
    assert summary["status"] == "aborted_cap"
    assert (tmp_path / "cap" / "checkpoint.json").is_file()
    assert (tmp_path / "cap" / ".sealed").is_file()


def test_resume_skips_completed_entries(tmp_path: Path) -> None:
    fix = _load_fix()
    local = StubLocalBackend(script=fix["local_script"])
    calls = {"n": 0}

    def _count() -> None:
        calls["n"] += 1

    cloud = StubCloudBackend(tokens_in=10, tokens_out=5, on_call=_count)
    out = tmp_path / "resume"
    # First run completes all under large cap
    s1 = run_session(
        policy="cloud_only",
        entries=fix["entries"],
        out_dir=out,
        max_usd=100.0,
        local=local,
        cloud=cloud,
        run_id="resume-test",
        skip_entry_assert=True,
        seal=False,
    )
    assert s1["status"] == "complete"
    n_first = calls["n"]
    assert n_first > 0

    # Second run with same out_dir must skip all entries (no new cloud calls)
    calls["n"] = 0
    s2 = run_session(
        policy="cloud_only",
        entries=fix["entries"],
        out_dir=out,
        max_usd=100.0,
        local=local,
        cloud=cloud,
        run_id="resume-test",
        skip_entry_assert=True,
        seal=True,
    )
    assert s2["status"] == "complete"
    assert calls["n"] == 0
    ckpt = json.loads((out / "checkpoint.json").read_text(encoding="utf-8"))
    assert set(ckpt["completed_entry_ids"]) == {e["id"] for e in fix["entries"]}


def test_decide_helpers() -> None:
    esc, reason = decide_slo_escalate(
        already_on_cloud=False, ttft_s=11.0, decode_tok_s=10.0, n_ctx=100
    )
    assert esc and "ttft>" in (reason or "")
    esc, reason = decide_slo_escalate(
        already_on_cloud=False, ttft_s=1.0, decode_tok_s=3.0, n_ctx=100
    )
    assert esc and "decode<" in (reason or "")
    esc, _ = decide_emission_escalate(already_on_cloud=False, emitted_parseable_tool_call=True)
    assert not esc


def test_agnostic_default_refused_live(tmp_path: Path) -> None:
    fix = _load_fix()
    with pytest.raises(SystemExit, match="derive-r1"):
        run_session(
            policy="agnostic_default",
            entries=fix["entries"],
            out_dir=tmp_path / "r1",
            max_usd=0.0,
            local=StubLocalBackend(script=fix["local_script"]),
            cloud=StubCloudBackend(),
            skip_entry_assert=True,
            seal=False,
        )


def test_stub_cannot_seal_hybrid(tmp_path: Path) -> None:
    fix = _load_fix()
    local = StubLocalBackend(script=fix["local_script"])
    cloud = StubCloudBackend()
    with pytest.raises(SystemExit, match="OpenVinoLocalBackend"):
        assert_seal_allowed(seal=True, local=local, policy="slo_escalate")
    with pytest.raises(SystemExit, match="OpenVinoLocalBackend"):
        run_session(
            policy="slo_escalate",
            entries=fix["entries"][:1],
            out_dir=tmp_path / "nosseal",
            max_usd=100.0,
            local=local,
            cloud=cloud,
            skip_entry_assert=True,
            seal=True,
        )


def test_fixture_cli_refuses_seal(tmp_path: Path) -> None:
    from tools import run_h1_hybrid as mod

    with pytest.raises(SystemExit, match="incompatible with --fixture"):
        mod.main(
            [
                "--policy",
                "cloud_only",
                "--max-usd",
                "1",
                "--out",
                str(tmp_path / "fx"),
                "--fixture",
                str(FIXTURE),
                "--seal",
            ]
        )


EARLY_STOP = ROOT / "tests" / "fixtures" / "h1_hybrid_early_stop.json"


def _load_early_stop() -> dict:
    return json.loads(EARLY_STOP.read_text(encoding="utf-8"))


def test_early_stop_all_four_policies() -> None:
    """Entry stops at turn 2 of 5 (D-2d). Denominators and stop_reason per policy."""
    fix = _load_early_stop()
    entry = fix["entries"][0]
    local = StubLocalBackend(
        script=fix["local_script"],
        stop_reasons=fix["stop_reasons"],
    )
    cloud = StubCloudBackend(
        tokens_in=fix["cloud_tokens_in"],
        tokens_out=fix["cloud_tokens_out"],
    )

    # cloud_only: local span ignored; all 5 turns on cloud.
    er_cloud = run_hybrid_entry(
        entry,
        policy="cloud_only",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert er_cloud.turns_in_entry == 5
    assert er_cloud.turns_executed == 5
    assert er_cloud.stop_reason == "completed"
    assert all(t.placement == "cloud" for t in er_cloud.turns)

    # agnostic_default: stop at local span; turns 2..4 did not happen.
    er_agn = run_hybrid_entry(
        entry,
        policy="agnostic_default",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert er_agn.turns_in_entry == 5
    assert er_agn.turns_executed == 2
    assert er_agn.stop_reason == "empty_execute"
    assert er_agn.status == "stopped_early"
    assert [t.turn for t in er_agn.turns] == [0, 1]
    assert all(t.placement == "local" for t in er_agn.turns)

    # slo_escalate: short entry is not an SLO violation; fraction over turns that ran.
    er_slo = run_hybrid_entry(
        entry,
        policy="slo_escalate",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert er_slo.turns_in_entry == 5
    assert er_slo.turns_executed == 2
    assert er_slo.stop_reason == "empty_execute"
    assert er_slo.status == "stopped_early"
    assert er_slo.slo_fraction == 1.0  # both ran turns meet SLO; unexecuted excluded
    assert not any(t.escalated for t in er_slo.turns)

    # emission_escalate: empty_execute on last local turn → cloud from that turn.
    er_em = run_hybrid_entry(
        entry,
        policy="emission_escalate",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert er_em.turns_in_entry == 5
    assert er_em.turns_executed == 5
    assert er_em.stop_reason == "empty_execute"
    assert er_em.status == "complete"
    assert er_em.turns[0].placement == "local"
    assert er_em.turns[1].placement == "cloud"
    assert er_em.turns[1].escalated is True
    assert er_em.turns[1].escalate_reason == "empty_execute"
    assert all(t.placement == "cloud" for t in er_em.turns[1:])


def test_early_stop_generation_error_is_not_emission_escalate() -> None:
    entry = {
        "id": "gen_err_entry",
        "question": [[], [], []],
        "n_user_turns": 3,
        "stop_reason": "generation_error",
    }
    script = {
        "gen_err_entry": [
            {
                "n_ctx": 400,
                "ttft_s": 1.0,
                "decode_tok_s": 12.0,
                "emitted_parseable_tool_call": True,
                "turn_wall_s": 0.05,
                "t_generate": 0.03,
                "t_tokenize": 0.005,
                "t_template_build": 0.005,
                "t_tool_exec": 0.005,
            },
            {
                "n_ctx": 400,
                "ttft_s": 1.0,
                "decode_tok_s": 12.0,
                "emitted_parseable_tool_call": False,
                "turn_wall_s": 0.05,
                "t_generate": 0.03,
                "t_tokenize": 0.005,
                "t_template_build": 0.005,
                "t_tool_exec": 0.005,
            },
        ]
    }
    local = StubLocalBackend(
        script=script,
        stop_reasons={"gen_err_entry": "generation_error"},
    )
    cloud = StubCloudBackend(tokens_in=10, tokens_out=5)
    er = run_hybrid_entry(
        entry,
        policy="emission_escalate",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert er.turns_executed == 2
    assert er.stop_reason == "generation_error"
    assert er.status == "stopped_early"
    assert all(t.placement == "local" for t in er.turns)


BOUNCE_FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_bounceback.json"


def test_r2c_full_signal_bounceback_each_trigger_once() -> None:
    """Entry triggers each bounce class once, then resumes local."""
    fix = json.loads(BOUNCE_FIXTURE.read_text(encoding="utf-8"))
    entry = fix["entries"][0]
    local = StubLocalBackend(script=fix["local_script"])
    cloud = StubCloudBackend(
        tokens_in=fix["cloud_tokens_in"],
        tokens_out=fix["cloud_tokens_out"],
    )
    er = run_hybrid_entry(
        entry,
        policy="full_signal_bounceback",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert er.turns_in_entry == 4
    assert er.turns_executed == 4
    assert [(b.turn, b.trigger) for b in er.bounces] == [
        (0, "no_parseable_tool_call"),
        (1, "step_budget"),
        (2, "tool_exec_error"),
    ]
    assert (
        er.turns[0].placement == "cloud" and er.turns[0].bounce_trigger == "no_parseable_tool_call"
    )
    assert er.turns[1].placement == "cloud" and er.turns[1].bounce_trigger == "step_budget"
    assert er.turns[2].placement == "cloud" and er.turns[2].bounce_trigger == "tool_exec_error"
    assert er.turns[2].tool_exec_error is True
    assert er.turns[2].tool_exec_error_class == "RuntimeError"
    assert isinstance(er.turns[2].tool_exec_error, bool)
    assert er.turns[3].placement == "local" and not er.turns[3].escalated
    assert er.turns[3].tool_exec_error is False
    assert er.turns[3].tool_exec_error_class is None
    # Cloud did not stay after bounce — turn 3 is local again.
    assert er.cloud_usd_entry == 3 * cloud_usd(100, 20)
    # Context injection recorded for each bounce turn.
    assert local._cloud_context["bounce_all_triggers"][0]
    assert local._cloud_context["bounce_all_triggers"][1]
    assert local._cloud_context["bounce_all_triggers"][2]


def test_decide_bounceback_priority() -> None:
    esc, reason = decide_bounceback(
        emitted_parseable_tool_call=False, n_steps=1, tool_exec_error=True
    )
    assert esc and reason == "tool_exec_error"
    esc, reason = decide_bounceback(
        emitted_parseable_tool_call=True, n_steps=5, tool_exec_error=False
    )
    assert esc and reason == "step_budget"
    esc, reason = decide_bounceback(
        emitted_parseable_tool_call=False, n_steps=1, tool_exec_error=False
    )
    assert esc and reason == "no_parseable_tool_call"
    esc, reason = decide_bounceback(
        emitted_parseable_tool_call=True, n_steps=4, tool_exec_error=False
    )
    assert not esc


def test_tool_exec_error_ledger_fields_typed() -> None:
    """LEDGER-C: per-turn tool_exec_error bool + error class on hybrid ledger."""
    from tools.phase_timers import finalize_phase_timers
    from tools.run_h1_hybrid import TurnLedger

    phases = finalize_phase_timers(
        turn_wall_s=0.05,
        t_tool_exec=0.01,
        t_template_build=0.01,
        t_tokenize=0.01,
        t_generate=0.02,
    )
    tl = TurnLedger(
        entry_id="e",
        turn=0,
        placement="local",
        model="stub",
        n_ctx=100,
        ttft_s=1.0,
        decode_tok_s=10.0,
        emitted_parseable_tool_call=True,
        escalated=False,
        escalate_reason=None,
        cloud_tokens_in=0,
        cloud_tokens_out=0,
        cloud_usd=0.0,
        turn_wall_s=phases["turn_wall_s"],
        t_tool_exec=phases["t_tool_exec"],
        t_template_build=phases["t_template_build"],
        t_tokenize=phases["t_tokenize"],
        t_generate=phases["t_generate"],
        t_other=phases["t_other"],
        tool_exec_error=True,
        tool_exec_error_class="ValueError",
    )
    d = tl.as_dict()
    assert d["tool_exec_error"] is True
    assert isinstance(d["tool_exec_error"], bool)
    assert d["tool_exec_error_class"] == "ValueError"
    assert isinstance(d["tool_exec_error_class"], str)

    tl_ok = TurnLedger(
        entry_id="e",
        turn=1,
        placement="local",
        model="stub",
        n_ctx=100,
        ttft_s=1.0,
        decode_tok_s=10.0,
        emitted_parseable_tool_call=True,
        escalated=False,
        escalate_reason=None,
        cloud_tokens_in=0,
        cloud_tokens_out=0,
        cloud_usd=0.0,
        turn_wall_s=phases["turn_wall_s"],
        t_tool_exec=phases["t_tool_exec"],
        t_template_build=phases["t_template_build"],
        t_tokenize=phases["t_tokenize"],
        t_generate=phases["t_generate"],
        t_other=phases["t_other"],
    )
    d_ok = tl_ok.as_dict()
    assert d_ok["tool_exec_error"] is False
    assert d_ok["tool_exec_error_class"] is None


def test_entry_quality_dict_shape() -> None:
    from tools.run_h1_hybrid import EntryResult

    er = EntryResult(entry_id="e", n_turns=1, turns_in_entry=1, turns_executed=1)
    er.trajectory_pass = False
    er.score_error_type = "multi_turn:empty_turn_model_response"
    er.score_error_message = "x"
    er.model_result_decoded = [[["foo()"]]]
    er.quality_scope = "local_probe"
    q = er.as_quality_dict()
    assert q["trajectory_pass"] is False
    assert q["model_result_decoded"] == [[["foo()"]]]
    assert q["quality_scope"] == "local_probe"
    # Decoded stays out of the compact ledger row.
    led = er.as_ledger_dict()
    assert "model_result_decoded" not in led
    assert led["trajectory_pass"] is False


if __name__ == "__main__":
    import tempfile

    test_blinding_runner_source_has_no_prediction_paths()
    test_decide_helpers()
    test_decide_bounceback_priority()
    test_tool_exec_error_ledger_fields_typed()
    test_entry_quality_dict_shape()
    test_early_stop_all_four_policies()
    test_early_stop_generation_error_is_not_emission_escalate()
    test_r2c_full_signal_bounceback_each_trigger_once()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        test_phase_timers_sum_on_hybrid_ledger(p)
        test_policy_dispatch_slo_and_emission_on_3entry_fixture(p)
        test_cost_guard_trips(p)
        test_resume_skips_completed_entries(p)
        test_agnostic_default_refused_live(p)
        test_stub_cannot_seal_hybrid(p)
        test_fixture_cli_refuses_seal(p)
    print("PASS tests/test_h1_hybrid.py")
