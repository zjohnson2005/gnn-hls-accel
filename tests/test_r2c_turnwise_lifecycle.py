"""TURNWISE lifecycle: OpenVinoLocalBackend begin/finish + interleaved isolation.

Drives ``run_hybrid_entry`` through the real backend class with stubbed generate
for all three H1-3POLICY arms. Asserts no ``run_user_turn requires an active
session`` crash and no cross-policy session leakage.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytest.importorskip("transformers")

from tools.bfcl_feasibility_probe import (  # noqa: E402
    MODEL_DIR,
    encode_execute_calls_as_qwen_tool_text,
    select_multi_turn_entries,
)
from tools.run_h1_hybrid import (  # noqa: E402
    INTERLEAVE_POLICIES,
    CostGuard,
    OpenVinoLocalBackend,
    StubCloudBackend,
    openvino_backend_stubbed_generate,
    run_hybrid_entry,
    run_turnwise_lifecycle_smoke,
)


class _FakeGenResult:
    def __init__(self, text: str) -> None:
        self.texts = [text]
        self.perf_metrics = None


class _GoldToolPipe:
    """Gold execute strings as Qwen tool_call text; fresh queue per begin."""

    def __init__(self, entry: dict[str, Any]) -> None:
        self._entry = entry
        self._queue: list[str] = []
        self.reset()

    def reset(self) -> None:
        self._queue = []
        for turn in self._entry.get("reference") or []:
            if turn:
                self._queue.append(encode_execute_calls_as_qwen_tool_text(list(turn)))
            self._queue.append("Task complete.")

    def generate(self, prompts: Any, cfg: Any = None, streamer: Any = None) -> _FakeGenResult:
        del prompts, cfg, streamer
        text = self._queue.pop(0) if self._queue else "Task complete."
        return _FakeGenResult(text)

    def finish_chat(self) -> None:
        return None

    def get_tokenizer(self) -> None:
        return None


@pytest.fixture(scope="module")
def hf_tokenizer():
    from transformers import AutoTokenizer

    if not MODEL_DIR.is_dir():
        pytest.skip(f"model dir missing: {MODEL_DIR}")
    return AutoTokenizer.from_pretrained(str(MODEL_DIR))


@pytest.fixture(scope="module")
def fixture_entry():
    entries = select_multi_turn_entries()
    if not entries:
        pytest.skip("no multi_turn_base entries available")
    entry = min(entries, key=lambda e: len(e.get("question") or []))
    assert entry.get("raw_entry") and entry.get("question")
    return entry


def test_openvino_backend_interleaved_lifecycle_no_leak(hf_tokenizer, fixture_entry) -> None:
    """Three policies share one backend; each cell begin/finish is isolated."""
    entry = fixture_entry
    local = openvino_backend_stubbed_generate(hf_tokenizer)
    cloud = StubCloudBackend(tokens_in=8, tokens_out=4)
    session_obj_ids: list[int] = []

    for policy in INTERLEAVE_POLICIES:
        assert local._active_cell is None
        er = run_hybrid_entry(
            entry,
            policy=policy,
            local=local,
            cloud=cloud,
            cost=CostGuard(max_usd=50.0),
            model="stub-lifecycle-4B",
        )
        assert er.status in ("complete", "stopped_early", "aborted_cap")
        assert local._active_cell is None
        assert local._sessions == {}
        key = OpenVinoLocalBackend.cell_key(str(entry["id"]), policy)
        assert key in local._entry_cache
        session_obj_ids.append(id(local._entry_cache[key]))
        # Prior policies' caches remain (isolation of keys, not wipe-all).
        for prior in INTERLEAVE_POLICIES:
            if prior == policy:
                break
            prior_key = OpenVinoLocalBackend.cell_key(str(entry["id"]), prior)
            assert prior_key in local._entry_cache

    assert len(local._entry_cache) >= 3
    keys = {OpenVinoLocalBackend.cell_key(str(entry["id"]), p) for p in INTERLEAVE_POLICIES}
    assert keys <= set(local._entry_cache)


def test_three_policy_gold_tools_zero_instance_mismatch(hf_tokenizer, fixture_entry) -> None:
    """Re-verify after TURNWISE-STATE fix: one entry x 3 policies, stub cloud.

    Gold tool calls exercise real BFCL instance evolution. Assert zero
    ``multi_turn:instance_state_mismatch`` across all three arms (the 6c7f88f1
    interleaved re-begin corruption class).
    """
    entry = fixture_entry
    n_calls = sum(len(t) for t in (entry.get("reference") or []))
    if n_calls < 1:
        pytest.skip("fixture entry has no gold tool calls")

    gold = _GoldToolPipe(entry)
    local = openvino_backend_stubbed_generate(hf_tokenizer)

    def _gold_generate(prompt: Any, cfg: Any = None, streamer: Any = None) -> _FakeGenResult:
        del prompt, cfg
        if streamer is not None:
            write = getattr(streamer, "write", None)
            if callable(write):
                write(1)
            end = getattr(streamer, "end", None)
            if callable(end):
                end()
        text = gold._queue.pop(0) if gold._queue else "Task complete."
        return _FakeGenResult(text)

    local.pipe.generate = _gold_generate  # type: ignore[method-assign]
    # Stub cloud returns healthy tokens so dead-path guard does not trip.
    cloud = StubCloudBackend(tokens_in=8, tokens_out=4)
    mismatches: list[str] = []

    for policy in INTERLEAVE_POLICIES:
        gold.reset()
        er = run_hybrid_entry(
            entry,
            policy=policy,
            local=local,
            cloud=cloud,
            cost=CostGuard(max_usd=50.0),
            model="stub-gold-4B",
        )
        key = OpenVinoLocalBackend.cell_key(str(entry["id"]), policy)
        row = local._entry_cache.get(key) or {}
        score = row.get("score") or {}
        err = score.get("error_type")
        if err == "multi_turn:instance_state_mismatch":
            mismatches.append(f"{policy}:{err}:{score.get('error_message')}")
        assert er.status in ("complete", "stopped_early", "aborted_cap")
        # Gold tools should score valid when begin resets cleanly.
        assert score.get("valid") is True, (policy, score)

    assert mismatches == [], f"instance_state_mismatch under stub cloud: {mismatches}"


def test_run_turn_without_begin_refuses(hf_tokenizer, fixture_entry) -> None:
    local = openvino_backend_stubbed_generate(hf_tokenizer)
    with pytest.raises(SystemExit, match="begin_entry"):
        local.run_turn(fixture_entry, 0, model="stub")


def test_lifecycle_smoke_cli_helper(hf_tokenizer) -> None:
    del hf_tokenizer  # ensures model dir present via fixture chain
    doc = run_turnwise_lifecycle_smoke(entry_index=0)
    assert doc["ok"] is True
    assert doc["policies"] == list(INTERLEAVE_POLICIES)
    assert len(doc["results"]) == 3
    for row in doc["results"]:
        assert "active session" not in str(row).lower()
