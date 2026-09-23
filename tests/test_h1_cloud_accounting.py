"""R0 cloud accounting: per-request log, cost invariant, cache policy, cloud_only arm."""

from __future__ import annotations

import json
from pathlib import Path

from tools.h1_cloud_accounting import (
    DEFAULT_CACHING_POLICY,
    apply_caching_policy,
    cloud_request_record,
    cloud_usd_nondecreasing,
    usage_field,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_3entries.json"


def test_request_record_splits_input_and_preserves_missing_cache() -> None:
    rec = cloud_request_record(
        turn=1,
        request_index_within_turn=0,
        ok=True,
        system="sys",
        tools="tool-schema",
        history="older",
        new="fresh",
        input_tokens=10,
        output_tokens=2,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
    )
    parts = (
        rec["system_tokens"] + rec["tool_schema_tokens"] + rec["history_tokens"] + rec["new_tokens"]
    )
    assert parts == 10
    assert rec["input_tokens"] == 10
    assert rec["output_tokens"] == 2
    assert rec["cache_creation_input_tokens"] is None
    assert rec["cache_read_input_tokens"] is None
    assert rec["request_index_within_turn"] == 0
    assert DEFAULT_CACHING_POLICY == "none"


def test_usage_field_absent_is_missing_not_zero() -> None:
    class _Usage:
        input_tokens = 0

    assert usage_field(_Usage(), "input_tokens") == 0
    assert usage_field(_Usage(), "cache_creation_input_tokens") is None
    assert usage_field(None, "input_tokens") is None


def test_caching_policy_none_does_not_set_cache_control() -> None:
    kwargs = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        "tools": [{"name": "fn", "input_schema": {"type": "object"}}],
    }
    plain = apply_caching_policy(kwargs, "none")
    assert "cache_control" not in json.dumps(plain)
    cached = apply_caching_policy(kwargs, "ephemeral")
    assert cached["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    from tools.bfcl_feasibility_probe import _anthropic_create_kwargs

    built = _anthropic_create_kwargs(
        model="claude-sonnet-5",
        max_tokens=8,
        messages=kwargs["messages"],
        tools=kwargs["tools"],
    )
    assert "cache_control" not in json.dumps(built)


def test_cloud_usd_invariant_fails_when_more_cloud_turns_cost_less() -> None:
    failed = cloud_usd_nondecreasing(
        [
            {"entry_id": "e", "policy": "slo_escalate", "n_cloud_turns": 1, "cloud_usd": 2.0},
            {"entry_id": "e", "policy": "cloud_only", "n_cloud_turns": 3, "cloud_usd": 1.0},
        ]
    )
    assert failed["status"] == "FAIL"
    assert failed["n_violations"] == 1
    ok = cloud_usd_nondecreasing(
        [
            {"entry_id": "e", "policy": "slo_escalate", "n_cloud_turns": 0, "cloud_usd": 0.0},
            {"entry_id": "e", "policy": "cloud_only", "n_cloud_turns": 2, "cloud_usd": 0.2},
        ]
    )
    assert ok["status"] == "PASS"


def test_cloud_only_is_an_interleaved_policy_and_seal_records_cache(tmp_path: Path) -> None:
    from tools.run_h1_hybrid import (
        INTERLEAVE_POLICIES,
        StubCloudBackend,
        StubLocalBackend,
        _resolve_interleaved_policies,
        run_interleaved_session,
    )

    assert _resolve_interleaved_policies([]) == INTERLEAVE_POLICIES
    assert _resolve_interleaved_policies(["cloud_only"]) == ("cloud_only",)
    fix = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out = tmp_path / "cloud-only"
    summary = run_interleaved_session(
        entries=fix["entries"],
        out_dir=out,
        local=StubLocalBackend(script=fix["local_script"]),
        cloud=StubCloudBackend(tokens_in=1000, tokens_out=200),
        policies=("cloud_only",),
        policy_caps_usd={"cloud_only": 50.0},
        session_max_usd=50.0,
        run_id="acct-cloud-only",
        skip_entry_assert=True,
        seal=False,
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["caching_policy"] == "none"
    assert plan["arm_order"] == ["cloud_only"]
    assert summary["cloud_usd_invariant"]["status"] == "PASS"
    assert summary["caching_policy"] == "none"


def test_anthropic_backend_copies_per_request_log(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import tools.bfcl_feasibility_probe as probe
    from tools.run_h1_hybrid import AnthropicCloudBackend

    def _fake(**kwargs: object) -> dict:
        assert kwargs["caching_policy"] == "none"
        return {
            "calls": [
                {
                    "turn": 0,
                    "request_index_within_turn": 0,
                    "input_tokens": 4,
                    "output_tokens": 1,
                    "cache_creation_input_tokens": None,
                    "cache_read_input_tokens": None,
                    "system_tokens": 0,
                    "tool_schema_tokens": 1,
                    "history_tokens": 1,
                    "new_tokens": 2,
                    "prompt_tokens": 4,
                    "completion_tokens": 1,
                    "usd": 0.01,
                    "latency_s": 0.01,
                    "ok": True,
                }
            ],
            "n_user_turns": 1,
            "prompt_tokens_sum": 4,
            "completion_tokens_sum": 1,
            "usd": 0.01,
            "model_result_decoded": [[]],
        }

    monkeypatch.setattr(probe, "run_cloud_multi_turn_agent_entry", _fake)
    backend = AnthropicCloudBackend(client=object(), cloud_model="m")
    turn = backend.run_turn(
        {"id": "e", "question": [[{"role": "user", "content": "hi"}]]}, 0, model="m"
    )
    assert turn.cloud_requests is not None
    logged = turn.cloud_requests[0]
    assert logged["request_index_within_turn"] == 0
    assert logged["system_tokens"] == 0
    assert logged["tool_schema_tokens"] == 1
    assert logged["history_tokens"] == 1
    assert logged["new_tokens"] == 2
    assert logged["cache_read_input_tokens"] is None
