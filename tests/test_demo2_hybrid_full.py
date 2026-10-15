"""DEMO-2 build (task AI): hybrid_full policy and --context-window."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.context_window import context_overflow  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    MECHANICAL,
    POLICIES,
    QUALITY,
    CostGuard,
    StubCloudBackend,
    StubLocalBackend,
    attach_context_window,
    main,
    run_hybrid_entry,
)


def _row(**kw: Any) -> dict[str, Any]:
    row = {
        "n_ctx": 400,
        "ttft_s": 1.0,
        "decode_tok_s": 12.0,
        "emitted_parseable_tool_call": True,
        "turn_wall_s": 0.05,
        "t_generate": 0.03,
        "t_tokenize": 0.005,
        "t_template_build": 0.005,
        "t_tool_exec": 0.005,
    }
    row.update(kw)
    return row


def _run(
    rows: list[dict[str, Any]],
    policy: str = "hybrid_full",
    *,
    window: int | None = None,
    stop: str | None = None,
    n: int | None = None,
):
    eid = "e"
    n = n if n is not None else len(rows)
    entry: dict[str, Any] = {"id": eid, "question": [[] for _ in range(n)], "n_user_turns": n}
    if stop:
        entry["stop_reason"] = stop
    local = StubLocalBackend(
        script={eid: rows}, stop_reasons={eid: stop} if stop else {}, context_window=window
    )
    return run_hybrid_entry(
        entry,
        policy=policy,
        local=local,
        cloud=StubCloudBackend(tokens_in=1000, tokens_out=200),
        cost=CostGuard(max_usd=100.0),
        model="stub-4B",
    )


def _summary(er) -> list[tuple[str, str | None, str | None]]:
    return [(t.placement, t.escalate_reason, t.trigger_class) for t in er.turns]


def test_policy_registered() -> None:
    assert "hybrid_full" in POLICIES


def test_context_overflow_rule() -> None:
    assert context_overflow(3584, max_new_tokens=512, window=4096, step=0) is None
    rec = context_overflow(3585, max_new_tokens=512, window=4096, step=2)
    assert rec == {"n_ctx": 3585, "window": 4096, "max_new_tokens": 512, "step": 2}
    assert context_overflow(10**6, max_new_tokens=512, window=None, step=0) is None


def test_ctx_overflow_is_mechanical_and_sticky() -> None:
    er = _run([_row(n_ctx=1000), _row(n_ctx=3700), _row(n_ctx=500)], window=4096)
    assert _summary(er) == [
        ("local", None, None),
        ("cloud", "ctx_overflow", MECHANICAL),
        ("cloud", "stay_cloud", None),
    ]
    row = er.turns[1].as_dict()
    assert row["ctx_overflow"] == {"n_ctx": 3700, "window": 4096, "max_new_tokens": 512, "step": 0}


def test_step0_ttft_and_decode_are_mechanical_and_sticky() -> None:
    er = _run([_row(), _row(ttft_s=10.5), _row()])
    assert _summary(er)[1:] == [
        ("cloud", "ttft>10.0", MECHANICAL),
        ("cloud", "stay_cloud", None),
    ]
    er = _run([_row(decode_tok_s=5.0), _row()])
    assert _summary(er) == [("cloud", "decode<6.0", MECHANICAL), ("cloud", "stay_cloud", None)]


def test_generation_error_is_mechanical() -> None:
    er = _run([_row(), _row(generation_error=True), _row()])
    assert _summary(er)[1] == ("cloud", "generation_error", MECHANICAL)
    # At the local end, as the span's stop reason (OpenVINO path).
    er = _run([_row(), _row(emitted_parseable_tool_call=False)], stop="generation_error", n=3)
    assert _summary(er) == [
        ("local", None, None),
        ("cloud", "generation_error", MECHANICAL),
        ("cloud", "stay_cloud", None),
    ]


@pytest.mark.parametrize(
    ("bad", "trigger"),
    [
        ({"emitted_parseable_tool_call": False}, "no_parseable_tool_call"),
        ({"tool_exec_error": True, "tool_exec_error_class": "KeyError"}, "tool_exec_error"),
        ({"n_steps": 5}, "step_budget"),
    ],
)
def test_quality_triggers_bounce_one_turn(bad: dict[str, Any], trigger: str) -> None:
    er = _run([_row(), _row(**bad), _row()])
    assert _summary(er) == [
        ("local", None, None),
        ("cloud", f"bounce:{trigger}", QUALITY),
        ("local", None, None),
    ]
    assert er.turns[1].as_dict()["trigger_class"] == QUALITY


def test_mechanical_wins_over_quality_on_the_same_turn() -> None:
    er = _run([_row(ttft_s=11.0, emitted_parseable_tool_call=False), _row()])
    assert _summary(er) == [("cloud", "ttft>10.0", MECHANICAL), ("cloud", "stay_cloud", None)]


def test_window_under_existing_policy_escalates_sticky() -> None:
    er = _run([_row(), _row(n_ctx=5000)], policy="slo_escalate", window=4096)
    assert _summary(er) == [("local", None, None), ("cloud", "ctx_overflow", MECHANICAL)]


def test_without_window_existing_rows_have_no_new_keys() -> None:
    er = _run([_row(), _row(ttft_s=12.0)], policy="slo_escalate")
    for t in er.turns:
        d = t.as_dict()
        assert "trigger_class" not in d and "ctx_overflow" not in d


def test_overflow_refused_where_policy_cannot_escalate() -> None:
    with pytest.raises(SystemExit, match="cannot escalate"):
        _run([_row(n_ctx=5000)], policy="local_only", window=4096)
    for policy in ("cloud_only", "local_only", "agnostic_default"):
        with pytest.raises(SystemExit, match="needs a policy that can escalate"):
            attach_context_window(4096, policy, StubLocalBackend(script={}))
    with pytest.raises(SystemExit, match="positive"):
        attach_context_window(0, "hybrid_full", StubLocalBackend(script={}))


def test_fixture_run_records_window_in_plan(tmp_path: Path) -> None:
    fix = {
        "entries": [{"id": "e", "question": [[], []], "n_user_turns": 2}],
        "local_script": {"e": [_row(), _row(n_ctx=5000)]},
    }
    path = tmp_path / "fix.json"
    path.write_text(json.dumps(fix), encoding="utf-8")
    out = tmp_path / "run"
    code = main(
        [
            "--policy",
            "hybrid_full",
            "--fixture",
            str(path),
            "--out",
            str(out),
            "--max-usd",
            "5",
            "--context-window",
            "4096",
            "--allow-dirty",
        ]
    )
    assert code == 0
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["context_window"]["tokens"] == 4096
    ledger = json.loads((out / "turn_ledger.json").read_text(encoding="utf-8"))
    turns = ledger["entries"][0]["turns"]
    assert turns[1]["escalate_reason"] == "ctx_overflow"
    assert turns[1]["trigger_class"] == MECHANICAL


def test_interleaved_refuses_window() -> None:
    with pytest.raises(SystemExit, match="single-arm only"):
        main(["--interleaved", "--out", "x", "--context-window", "4096", "--allow-dirty"])


def test_probe_checks_window_before_generate() -> None:
    src = (ROOT / "tools" / "bfcl_feasibility_probe.py").read_text(encoding="utf-8")
    body = src[src.index("def run_user_turn") :]
    check = body.index("overflow = context_overflow(")
    assert check < body.index("gen = pipe.generate([prompt_full], cfg)")
    assert check < body.index("timed = _timed_generate(pipe, ov_genai, gen_input, cfg_use)")
    assert 'turn_metric["ctx_overflow"]' in body


def test_runner_does_not_read_design_or_prereg() -> None:
    for name in ("run_h1_hybrid.py", "context_window.py", "bfcl_feasibility_probe.py"):
        src = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert "DEMO2_PREREG" not in src and "DEMO2_DESIGN" not in src
        assert "docs/amendments" not in src


def test_launcher_passthrough() -> None:
    text = (ROOT / "tools" / "launch_h1.ps1").read_text(encoding="utf-8")
    assert "[Nullable[int]]$ContextWindow = $null" in text
    assert "' --context-window ' + $ContextWindow" in text
    assert '"full_signal_bounceback", "hybrid_full")]' in text
    assert "-MaxUsd is required for hybrid_full" in text
    assert "-ContextWindow is single-arm only" in text


def test_kv_default_maps_to_bare_gpu_arm_and_expects_dynamic() -> None:
    from tools.run_h1_hybrid import (
        LOCAL_KVS,
        RUNTIME_DEFAULT_KV_READBACK,
        arm_id_for_h1,
        expected_kv_readback,
        local_arm_settings,
    )

    assert "default" in LOCAL_KVS
    assert RUNTIME_DEFAULT_KV_READBACK == "dynamic"
    assert arm_id_for_h1({"placement": "gpu_only", "kv": "default"}) == "gpu_only"
    assert expected_kv_readback("default") == "dynamic"
    for kv in ("u8", "u4", "f16"):
        assert expected_kv_readback(kv) == kv
        assert arm_id_for_h1({"placement": "gpu_only", "kv": kv}) == f"gpu_only_{kv}"
    s = local_arm_settings("hybrid_full", residency="NON_RESIDENT", kv="default")
    assert s == {"placement": "gpu_only", "residency": "NON_RESIDENT", "kv": "default"}


def test_kv_default_readback_check() -> None:
    from tools.run_h1_hybrid import OpenVinoLocalBackend

    def meta(normalized: str) -> dict[str, Any]:
        return {
            "loads": [
                {
                    "kv_cache_precision": {
                        "requested": None,
                        "readback": {"normalized": normalized, "device": "GPU", "ok": True},
                        "match": True,
                        "enforced": False,
                        "failure_mode": None,
                    }
                }
            ]
        }

    OpenVinoLocalBackend._assert_kv_readback(meta("dynamic"), expected="dynamic")
    with pytest.raises(SystemExit):
        OpenVinoLocalBackend._assert_kv_readback(meta("u8"), expected="dynamic")


def test_launcher_accepts_kv_default() -> None:
    text = (ROOT / "tools" / "launch_h1.ps1").read_text(encoding="utf-8")
    assert '[ValidateSet("", "u8", "u4", "f16", "default")]' in text
