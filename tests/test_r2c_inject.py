"""R2C-INJECT tests: cloud->local context handoff for full_signal_bounceback."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.r2c_inject import SharedBfclToolState  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    CostGuard,
    StubCloudBackend,
    StubLocalBackend,
    assert_seal_allowed,
    cloud_usd,
    run_hybrid_entry,
)

INJECT_FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_r2c_inject.json"


def _load() -> dict:
    return json.loads(INJECT_FIXTURE.read_text(encoding="utf-8"))


def test_r2c_inject_bounce_turn1_then_local_sees_cloud() -> None:
    """Bounce at turn 1; turns 2-3 complete locally with cloud text in context."""
    fix = _load()
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
    assert b0.re_prefill_s == 0.0
    assert b0.re_prefill_source == "stub_zero"

    assert er.turns[0].placement == "cloud"
    assert er.turns[0].bounce_trigger == "no_parseable_tool_call"
    assert er.turns[1].placement == "local" and not er.turns[1].escalated
    assert er.turns[2].placement == "local" and not er.turns[2].escalated

    assert local.context_contains(entry["id"], cloud_text)
    hist = local.history_for(entry["id"])
    cloud_idxs = [
        i
        for i, m in enumerate(hist)
        if m.get("source") == "cloud" and cloud_text in str(m.get("content"))
    ]
    assert cloud_idxs, "injected cloud assistant missing from local history"
    assert any(i > cloud_idxs[0] and m.get("source") == "local" for i, m in enumerate(hist))


def test_r2c_inject_stub_still_refuses_seal() -> None:
    fix = _load()
    local = StubLocalBackend(script=fix["local_script"])
    with pytest.raises(SystemExit, match="OpenVinoLocalBackend|REFUSED"):
        assert_seal_allowed(seal=True, local=local, policy="full_signal_bounceback")


def test_r2c_shared_tool_state_is_single_path() -> None:
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


def test_r2c_inject_module_documents_kv_invalid() -> None:
    import tools.r2c_inject as mod

    assert "Invalid" in (mod.__doc__ or "") or "invalid" in (mod.__doc__ or "").lower()
    receipt = mod.build_injection_receipt(
        entry_id="e",
        bounce_turn=0,
        trigger_class="no_parseable_tool_call",
        assistant_text="hi",
    )
    assert receipt.kv_valid_after_inject is False
    assert receipt.re_prefill_required is True
    assert receipt.control_return_turn == 1
