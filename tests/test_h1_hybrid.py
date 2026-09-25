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
    CLOUD_DEAD_CONSECUTIVE_N,
    BackendTurn,
    CloudDeadPathError,
    CloudDeadPathGuard,
    CostCapExceeded,
    CostGuard,
    StubCloudBackend,
    StubLocalBackend,
    assert_seal_allowed,
    cloud_turn_is_dead,
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


def test_cloud_dead_path_guard_n_from_6c7f88f1() -> None:
    assert CLOUD_DEAD_CONSECUTIVE_N == 3
    dead = BackendTurn(
        n_ctx=0,
        ttft_s=None,
        decode_tok_s=None,
        emitted_parseable_tool_call=False,
        cloud_tokens_in=0,
        cloud_tokens_out=0,
        cloud_usd=0.0,
    )
    ok = BackendTurn(
        n_ctx=100,
        ttft_s=None,
        decode_tok_s=None,
        emitted_parseable_tool_call=True,
        cloud_tokens_in=1000,
        cloud_tokens_out=50,
        cloud_usd=0.01,
    )
    assert cloud_turn_is_dead(dead)
    assert not cloud_turn_is_dead(ok)
    g = CloudDeadPathGuard(n=3)
    g.observe(dead, entry_id="e1", turn=0, policy="emission_escalate")
    g.raise_if_refused()
    g.observe(dead, entry_id="e1", turn=1, policy="emission_escalate")
    g.raise_if_refused()
    g.observe(dead, entry_id="e1", turn=2, policy="emission_escalate")
    with pytest.raises(CloudDeadPathError, match="CLOUD_DEAD_PATH_STREAK"):
        g.raise_if_refused()


def test_cloud_dead_path_guard_resets_on_healthy() -> None:
    dead = BackendTurn(
        n_ctx=0,
        ttft_s=None,
        decode_tok_s=None,
        emitted_parseable_tool_call=False,
        cloud_tokens_in=0,
        cloud_tokens_out=0,
    )
    ok = BackendTurn(
        n_ctx=10,
        ttft_s=None,
        decode_tok_s=None,
        emitted_parseable_tool_call=True,
        cloud_tokens_in=10,
        cloud_tokens_out=5,
    )
    g = CloudDeadPathGuard(n=3)
    g.observe(dead, entry_id="a", turn=0, policy="x")
    g.observe(dead, entry_id="a", turn=1, policy="x")
    g.observe(ok, entry_id="b", turn=0, policy="x")
    assert g.consecutive == 0
    g.observe(dead, entry_id="c", turn=0, policy="x")
    g.raise_if_refused()


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

    # slo_escalate: entry_0 turn1 has ttft_s=11 > 10 -> escalate (ctx alone must not)
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
    assert "ttft>" in (er0.turns[1].escalate_reason or "")
    assert "ctx>" not in (er0.turns[1].escalate_reason or "")
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
    # One cloud turn ~= cloud_usd(1000,200) = 0.006
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
    esc, reason = decide_slo_escalate(already_on_cloud=False, ttft_s=11.0, decode_tok_s=10.0)
    assert esc and "ttft>" in (reason or "")
    esc, reason = decide_slo_escalate(already_on_cloud=False, ttft_s=1.0, decode_tok_s=3.0)
    assert esc and "decode<" in (reason or "")
    # High ctx alone must NOT escalate under the RESIDENT rule.
    esc, reason = decide_slo_escalate(already_on_cloud=False, ttft_s=1.0, decode_tok_s=12.0)
    assert not esc
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
                "--allow-dirty",
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

    # emission_escalate: empty_execute on last local turn -> cloud from that turn.
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
    # Cloud did not stay after bounce - turn 3 is local again.
    assert er.cloud_usd_entry == 3 * cloud_usd(100, 20)
    # Context injection recorded for each bounce turn (cell-keyed).
    cell = StubLocalBackend.cell_key("bounce_all_triggers", "full_signal_bounceback")
    assert local._cloud_context[cell][0]
    assert local._cloud_context[cell][1]
    assert local._cloud_context[cell][2]


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


def test_slo_rule_ignores_ctx_even_when_above_cold_start() -> None:
    from tools.run_h1_hybrid import (
        CTX_LIMIT_COLD_START,
        decide_slo_escalate,
        decide_slo_escalate_legacy_with_ctx,
    )

    # New rule: ctx=12000 with healthy TTFT/decode -> no escalate.
    esc, reason = decide_slo_escalate(already_on_cloud=False, ttft_s=2.0, decode_tok_s=12.0)
    assert esc is False
    assert reason is None
    # Legacy would fire on ctx alone.
    esc_old, reason_old = decide_slo_escalate_legacy_with_ctx(
        already_on_cloud=False,
        ttft_s=2.0,
        decode_tok_s=12.0,
        n_ctx=CTX_LIMIT_COLD_START + 1,
    )
    assert esc_old is True
    assert "ctx>" in (reason_old or "")


def test_interleave_order_entry_by_entry(tmp_path: Path) -> None:
    from tools.h1_provenance import latin_square_order
    from tools.run_h1_hybrid import INTERLEAVE_POLICIES, run_interleaved_session

    fix = _load_fix()
    local = StubLocalBackend(script=fix["local_script"])
    cloud = StubCloudBackend(
        tokens_in=fix["cloud_tokens_in"],
        tokens_out=fix["cloud_tokens_out"],
    )
    out = tmp_path / "intl"
    summary = run_interleaved_session(
        entries=fix["entries"],
        out_dir=out,
        local=local,
        cloud=cloud,
        policy_caps_usd=dict.fromkeys(INTERLEAVE_POLICIES, 100.0),
        session_max_usd=1000.0,
        run_id="intl-order",
        skip_entry_assert=True,
        seal=False,
    )
    assert summary["session_design"] == "interleaved"
    assert summary["arm_order"] == list(INTERLEAVE_POLICIES)
    ckpt = json.loads((out / "checkpoint.json").read_text(encoding="utf-8"))
    cell_log = ckpt["cell_log"]
    eids = [e["id"] for e in fix["entries"]]
    expected: list[tuple[str, str]] = []
    for eid in eids:
        order = latin_square_order(INTERLEAVE_POLICIES, eid, seed=0)
        for pol in order:
            expected.append((eid, pol))
    got = [(c["entry_id"], c["policy"]) for c in cell_log]
    assert got == expected
    for cell in cell_log:
        assert cell["arm_order_this_entry"] == latin_square_order(
            INTERLEAVE_POLICIES, cell["entry_id"], seed=0
        )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["arm_order_rule"] == "seeded_latin_square"
    assert plan["arm_order_seed"] == 0
    assert plan["session_design"] == "interleaved"
    for pol in INTERLEAVE_POLICIES:
        assert (out / "policies" / pol / "entry_quality.json").is_file()
        assert (out / "policies" / pol / "turn_ledger.json").is_file()


def test_interleave_resume_per_policy_skips_completed(tmp_path: Path) -> None:
    from tools.run_h1_hybrid import INTERLEAVE_POLICIES, run_interleaved_session

    fix = _load_fix()
    local = StubLocalBackend(script=fix["local_script"])
    calls = {"n": 0}

    def _count() -> None:
        calls["n"] += 1

    cloud = StubCloudBackend(
        tokens_in=10,
        tokens_out=5,
        on_call=_count,
    )
    out = tmp_path / "intl_resume"
    caps = dict.fromkeys(INTERLEAVE_POLICIES, 100.0)
    s1 = run_interleaved_session(
        entries=fix["entries"],
        out_dir=out,
        local=local,
        cloud=cloud,
        policy_caps_usd=caps,
        session_max_usd=1000.0,
        run_id="intl-resume",
        skip_entry_assert=True,
        seal=False,
    )
    assert s1["status"] == "complete"
    n_first = calls["n"]
    assert n_first > 0
    calls["n"] = 0
    s2 = run_interleaved_session(
        entries=fix["entries"],
        out_dir=out,
        local=local,
        cloud=cloud,
        policy_caps_usd=caps,
        session_max_usd=1000.0,
        run_id="intl-resume",
        skip_entry_assert=True,
        seal=False,
    )
    assert s2["status"] == "complete"
    assert calls["n"] == 0
    for pol in INTERLEAVE_POLICIES:
        ckpt = json.loads((out / "policies" / pol / "checkpoint.json").read_text(encoding="utf-8"))
        assert set(ckpt["completed_entry_ids"]) == {e["id"] for e in fix["entries"]}


def test_interleave_policy_cap_does_not_rebill_other_arms(tmp_path: Path) -> None:
    """Cap abort on emission_escalate must not prevent slo/bounceback completion."""
    from tools.run_h1_hybrid import cloud_usd, run_interleaved_session

    fix = _load_fix()
    local = StubLocalBackend(script=fix["local_script"])
    per = cloud_usd(1000, 200)
    cloud = StubCloudBackend(tokens_in=1000, tokens_out=200)
    out = tmp_path / "intl_cap"
    # Tiny emission cap trips quickly; other arms keep full budget.
    caps = {
        "slo_escalate": 100.0,
        "emission_escalate": per * 0.5,
        "full_signal_bounceback": 100.0,
    }
    summary = run_interleaved_session(
        entries=fix["entries"],
        out_dir=out,
        local=local,
        cloud=cloud,
        policy_caps_usd=caps,
        session_max_usd=1000.0,
        run_id="intl-cap",
        skip_entry_assert=True,
        seal=False,
    )
    assert summary["policies"]["emission_escalate"]["status"] == "aborted_cap"
    assert summary["policies"]["slo_escalate"]["status"] == "complete"
    assert summary["policies"]["full_signal_bounceback"]["status"] == "complete"
    slo_ckpt = json.loads(
        (out / "policies" / "slo_escalate" / "checkpoint.json").read_text(encoding="utf-8")
    )
    assert set(slo_ckpt["completed_entry_ids"]) == {e["id"] for e in fix["entries"]}


def test_interleave_2policy_excludes_r2c_in_plan_and_seal(tmp_path: Path) -> None:
    """H1-2POLICY: subset arms; plan/summary record R2c exclusion (not 3-policy)."""
    from tools.h1_provenance import latin_square_order
    from tools.run_h1_hybrid import (
        INTERLEAVE_POLICIES_2POLICY,
        R2C_EXCLUSION_REASON,
        run_interleaved_session,
    )

    fix = _load_fix()
    local = StubLocalBackend(script=fix["local_script"])
    cloud = StubCloudBackend(
        tokens_in=fix["cloud_tokens_in"],
        tokens_out=fix["cloud_tokens_out"],
    )
    out = tmp_path / "intl_2p"
    summary = run_interleaved_session(
        entries=fix["entries"],
        out_dir=out,
        local=local,
        cloud=cloud,
        policy_caps_usd=dict.fromkeys(INTERLEAVE_POLICIES_2POLICY, 100.0),
        session_max_usd=25.0,
        policies=INTERLEAVE_POLICIES_2POLICY,
        run_id="intl-2policy",
        skip_entry_assert=True,
        seal=False,
    )
    assert summary["kind"] == "h1_2policy_interleaved"
    assert summary["r2c_excluded"] is True
    assert summary["r2c_exclusion_reason"] == R2C_EXCLUSION_REASON
    assert "full_signal_bounceback" not in summary["policies"]
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["kind"] == "h1_2policy_interleaved"
    assert plan["full_three_policy_comparison"] is False
    assert plan["excluded_policies"]["full_signal_bounceback"]["blocked_on"] == "R2C-TURNWISE"
    assert plan["arm_order"] == list(INTERLEAVE_POLICIES_2POLICY)
    ckpt = json.loads((out / "checkpoint.json").read_text(encoding="utf-8"))
    cell_log = ckpt["cell_log"]
    eids = [e["id"] for e in fix["entries"]]
    expected: list[tuple[str, str]] = []
    for eid in eids:
        for pol in latin_square_order(INTERLEAVE_POLICIES_2POLICY, eid, seed=0):
            expected.append((eid, pol))
    got = [(c["entry_id"], c["policy"]) for c in cell_log]
    assert got == expected
    assert not (out / "policies" / "full_signal_bounceback").exists()


def test_interleave_2policy_kind_and_exclusion_helpers() -> None:
    """Kind + exclusion helpers distinguish 2-policy from full 3-policy seals."""
    from tools.run_h1_hybrid import (
        INTERLEAVE_POLICIES,
        INTERLEAVE_POLICIES_2POLICY,
        R2C_EXCLUSION_REASON,
        interleaved_exclusion_meta,
        interleaved_kind,
    )

    meta = interleaved_exclusion_meta(INTERLEAVE_POLICIES_2POLICY)
    assert meta["r2c_excluded"] is True
    assert meta["r2c_exclusion_reason"] == R2C_EXCLUSION_REASON
    assert interleaved_kind(INTERLEAVE_POLICIES_2POLICY) == "h1_2policy_interleaved"
    full = interleaved_exclusion_meta(INTERLEAVE_POLICIES)
    assert full["r2c_excluded"] is False
    assert full["full_three_policy_comparison"] is True
    assert interleaved_kind(INTERLEAVE_POLICIES) == "h1_3policy_interleaved"


def test_resolve_interleaved_policies_subset() -> None:
    from tools.run_h1_hybrid import (
        INTERLEAVE_POLICIES,
        INTERLEAVE_POLICIES_2POLICY,
        _resolve_interleaved_policies,
    )

    assert _resolve_interleaved_policies([]) == INTERLEAVE_POLICIES
    assert (
        _resolve_interleaved_policies(["slo_escalate", "emission_escalate"])
        == INTERLEAVE_POLICIES_2POLICY
    )


def test_h1_3policy_prediction_files_exist() -> None:
    base = ROOT / "derived" / "h1_hybrid"
    for name in (
        "H1_3POLICY_PREDICTIONS.json",
        "H1_3POLICY_PREDICTIONS.md",
        "slo_rule_old_vs_new_86d0f4cf.json",
        "r2a_class_c_census.json",
    ):
        assert (base / name).is_file(), f"missing {name}"


INJECT_FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_r2c_inject.json"


def test_r2c_inject_bounce_turn1_then_local_sees_cloud() -> None:
    """Bounce at turn 1; turns 2-3 complete locally with cloud text in context."""
    from tools.r2c_inject import SharedBfclToolState

    fix = json.loads(INJECT_FIXTURE.read_text(encoding="utf-8"))
    entry = fix["entries"][0]
    cloud_text = fix["cloud_context_text"]
    shared = SharedBfclToolState(model_name="stub_shared_bfcl")
    local = StubLocalBackend(script=fix["local_script"], shared_tools=shared)
    cloud = StubCloudBackend(
        tokens_in=fix["cloud_tokens_in"],
        tokens_out=fix["cloud_tokens_out"],
        cloud_context_text=cloud_text,
    )
    er = run_hybrid_entry(
        entry,
        policy="full_signal_bounceback",
        local=local,
        cloud=cloud,
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )
    assert er.turns_in_entry == 3
    assert er.turns_executed == 3
    assert len(er.bounces) == 1
    b0 = er.bounces[0]
    assert b0.turn == 0
    assert b0.trigger == "no_parseable_tool_call"
    assert b0.cloud_tokens_in == fix["cloud_tokens_in"]
    assert b0.cloud_tokens_out == fix["cloud_tokens_out"]
    assert b0.cloud_usd == cloud_usd(fix["cloud_tokens_in"], fix["cloud_tokens_out"])
    assert b0.re_prefill_required is True
    assert b0.kv_valid_after_inject is False
    assert b0.control_return_turn == 1
    assert b0.shared_tool_exec is True
    # After turn 1 local runs, stub_zero re-prefill is backfilled onto the bounce.
    assert b0.re_prefill_s == 0.0
    assert b0.re_prefill_source == "stub_zero"

    assert er.turns[0].placement == "cloud"
    assert er.turns[0].bounce_trigger == "no_parseable_tool_call"
    assert er.turns[1].placement == "local" and not er.turns[1].escalated
    assert er.turns[2].placement == "local" and not er.turns[2].escalated

    # Cloud assistant turn is present in local history; later local turns see it.
    assert local.context_contains(entry["id"], cloud_text)
    hist = local.history_for(entry["id"])
    cloud_idxs = [
        i
        for i, m in enumerate(hist)
        if m.get("source") == "cloud" and cloud_text in str(m.get("content"))
    ]
    assert cloud_idxs, "injected cloud assistant missing from local history"
    assert any(i > cloud_idxs[0] and m.get("source") == "local" for i, m in enumerate(hist))


def test_r2c_inject_stub_still_refuses_seal(tmp_path: Path) -> None:
    fix = json.loads(INJECT_FIXTURE.read_text(encoding="utf-8"))
    local = StubLocalBackend(script=fix["local_script"])
    with pytest.raises(SystemExit, match=r"OpenVinoLocalBackend|REFUSED"):
        assert_seal_allowed(seal=True, local=local, policy="full_signal_bounceback")


def test_r2c_shared_tool_state_is_single_path() -> None:
    """Local and cloud-inject tool exec share one SharedBfclToolState (not duplicated)."""
    from tools.r2c_inject import SharedBfclToolState

    shared = SharedBfclToolState(model_name="shared_bfcl_r2c")
    out_a, _ = shared.execute(
        ["alpha()"],
        initial_config={},
        involved_classes=[],
        test_entry_id="e",
        long_context=False,
    )
    out_b, _ = shared.execute(
        ["beta()"],
        initial_config={},
        involved_classes=[],
        test_entry_id="e",
        long_context=False,
    )
    assert out_a and out_b
    assert len(shared.calls) == 2
    assert {c["model_name"] for c in shared.calls} == {"shared_bfcl_r2c"}


if __name__ == "__main__":
    import tempfile

    test_blinding_runner_source_has_no_prediction_paths()
    test_decide_helpers()
    test_decide_bounceback_priority()
    test_tool_exec_error_ledger_fields_typed()
    test_entry_quality_dict_shape()
    test_slo_rule_ignores_ctx_even_when_above_cold_start()
    test_early_stop_all_four_policies()
    test_early_stop_generation_error_is_not_emission_escalate()
    test_r2c_full_signal_bounceback_each_trigger_once()
    test_r2c_inject_bounce_turn1_then_local_sees_cloud()
    test_r2c_shared_tool_state_is_single_path()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        test_phase_timers_sum_on_hybrid_ledger(p)
        test_policy_dispatch_slo_and_emission_on_3entry_fixture(p)
        test_cost_guard_trips(p)
        test_resume_skips_completed_entries(p)
        test_agnostic_default_refused_live(p)
        test_stub_cannot_seal_hybrid(p)
        test_fixture_cli_refuses_seal(p)
        test_r2c_inject_stub_still_refuses_seal(p)
        test_interleave_order_entry_by_entry(p)
        test_interleave_resume_per_policy_skips_completed(p)
        test_interleave_policy_cap_does_not_rebill_other_arms(p)
    print("PASS tests/test_h1_hybrid.py (prediction file check skipped in __main__)")
