"""R2C-TURNWISE equivalence gate: compositor vs session turn-by-turn.

Local-only paths (no bounce). Fail loud on:
  - prompt_render_sha256 or per-step token-ID divergence
  - BFCL tool *environment* divergence after any turn (same comparison the
    official multi_turn_checker uses for instance_state_mismatch)

A prompt-equivalent path that produces different world state is not equivalent.
"""

from __future__ import annotations

import copy
import hashlib
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
    MultiTurnAgentSession,
    encode_execute_calls_as_qwen_tool_text,
    run_multi_turn_agent_entry,
    select_multi_turn_entries,
    snapshot_bfcl_tool_instances,
)


class _FakeGenResult:
    def __init__(self, text: str) -> None:
        self.texts = [text]
        self.perf_metrics = None


class _FakePipe:
    """Deterministic generate for local-only equivalence (no OpenVINO device)."""

    def __init__(self, text: str = "I cannot help with that.") -> None:
        self._text = text
        self._n_generate = 0

    def generate(self, prompts: Any, cfg: Any = None, streamer: Any = None) -> _FakeGenResult:
        del prompts, cfg, streamer
        self._n_generate += 1
        return _FakeGenResult(self._text)

    def finish_chat(self) -> None:
        return None

    def get_tokenizer(self) -> None:
        return None


class _GoldToolPipe:
    """Emit gold BFCL execute strings as Qwen <tool_call> text, then stop.

    Per user turn: one tool-call generation (if gold non-empty), then a plain
    text generation so the step loop exits. Exercises real execute_multi_turn
    and instance mutation - the prior hash-only gate missed that axis.
    """

    def __init__(self, entry: dict[str, Any]) -> None:
        self._queue: list[str] = []
        for turn in entry.get("reference") or []:
            if turn:
                self._queue.append(encode_execute_calls_as_qwen_tool_text(list(turn)))
            self._queue.append("Task complete.")
        self._n_generate = 0

    def generate(self, prompts: Any, cfg: Any = None, streamer: Any = None) -> _FakeGenResult:
        del prompts, cfg, streamer
        self._n_generate += 1
        text = self._queue.pop(0) if self._queue else "Task complete."
        return _FakeGenResult(text)

    def finish_chat(self) -> None:
        return None

    def get_tokenizer(self) -> None:
        return None


class _FakeCfg:
    max_new_tokens = 512
    do_sample = False
    apply_chat_template = False


def _first_mismatch(a: list[int], b: list[int]) -> int | None:
    for i, (x, y) in enumerate(zip(a, b, strict=False)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def _public_attrs(inst: Any) -> dict[str, Any]:
    return {k: v for k, v in vars(inst).items() if not k.startswith("_")}


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
    # Prefer a short question entry to keep the gate cheap.
    entry = min(entries, key=lambda e: len(e.get("question") or []))
    assert entry.get("raw_entry") and entry.get("question")
    return entry


@pytest.fixture(scope="module")
def fixture_entry_with_tools(fixture_entry):
    """Require at least one gold tool call so the state gate is non-vacuous."""
    entry = fixture_entry
    n_calls = sum(len(t) for t in (entry.get("reference") or []))
    if n_calls < 1:
        pytest.skip("fixture entry has no gold tool calls")
    return entry


def test_turnwise_compositor_matches_session_hashes_and_token_ids(
    hf_tokenizer, fixture_entry
) -> None:
    """Path A (compositor) vs Path B (begin->run_user_turn*N->finish) must match.

    Bounce paths are out of scope for equality.
    """
    entry = fixture_entry
    pipe_a = _FakePipe()
    pipe_b = _FakePipe()
    cfg = _FakeCfg()

    # Path A: thin compositor (W-3 call-site shape).
    row_a = run_multi_turn_agent_entry(
        pipe=pipe_a,
        tokenizer=hf_tokenizer,
        cfg=cfg,
        entry=entry,
        residency_mode=None,
    )

    # Path B: explicit session turn-by-turn (hybrid outer-loop shape).
    session = MultiTurnAgentSession(
        pipe=pipe_b,
        tokenizer=hf_tokenizer,
        cfg=cfg,
        residency_mode=None,
    )
    session.begin(entry)
    for turn_idx in range(len(entry["question"])):
        session.run_user_turn(turn_idx)
        if session.force_quit:
            break
    row_b = session.finish()

    sha_a = row_a.get("prompt_render_sha256")
    sha_b = row_b.get("prompt_render_sha256")
    if sha_a != sha_b:
        raise AssertionError(
            "FATAL: prompt_render_sha256 diverged compositor vs session "
            f"entry={entry['id']!r} compositor={sha_a} session={sha_b} "
            f"n_a={row_a.get('prompt_render_n')} n_b={row_b.get('prompt_render_n')}"
        )
    assert sha_a is not None and len(sha_a) == 64
    assert row_a.get("prompt_render_n") == row_b.get("prompt_render_n")
    assert row_a.get("prompt_render_n", 0) >= 1

    ids_a = row_a.get("prompt_input_ids_all_steps") or []
    ids_b = row_b.get("prompt_input_ids_all_steps") or []
    if len(ids_a) != len(ids_b):
        raise AssertionError(
            "FATAL: prompt_input_ids_all_steps length diverged "
            f"entry={entry['id']!r} compositor_n={len(ids_a)} session_n={len(ids_b)}"
        )
    for step_i, (a, b) in enumerate(zip(ids_a, ids_b, strict=True)):
        if list(a) != list(b):
            mm = _first_mismatch(list(a), list(b))
            raise AssertionError(
                "FATAL: prompt token IDs diverged at step "
                f"{step_i} entry={entry['id']!r} first_mismatch={mm} "
                f"len_a={len(a)} len_b={len(b)} "
                f"sha_step_a={hashlib.sha256(str(a).encode()).hexdigest()[:16]} "
                f"sha_step_b={hashlib.sha256(str(b).encode()).hexdigest()[:16]}"
            )

    # Per-turn first-step token IDs (bounce excluded - local-only fixture).
    growth_a = [g for g in (row_a.get("context_growth") or []) if g.get("step") == 0]
    growth_b = [g for g in (row_b.get("context_growth") or []) if g.get("step") == 0]
    assert len(growth_a) == len(growth_b)
    for turn_i, (ga, gb) in enumerate(zip(growth_a, growth_b, strict=True)):
        if ga.get("prompt_tokens") != gb.get("prompt_tokens"):
            raise AssertionError(
                "FATAL: per-turn prompt_tokens diverged "
                f"entry={entry['id']!r} turn={turn_i} "
                f"compositor={ga.get('prompt_tokens')} session={gb.get('prompt_tokens')}"
            )


def test_turnwise_tool_state_matches_after_every_turn(
    hf_tokenizer, fixture_entry_with_tools
) -> None:
    """Compositor vs session: BFCL world state identical after every user turn.

    Uses real gold tool calls (not the no-tool FakePipe). Comparison is the
    official multi_turn_checker state_checker (instance_state_mismatch axis).
    """
    entry = fixture_entry_with_tools
    cfg = _FakeCfg()

    # Path A: compositor - snapshot after finish via its session model_name is
    # inaccessible; drive an explicit session whose generate queue matches A.
    pipe_a = _GoldToolPipe(entry)
    session_a = MultiTurnAgentSession(
        pipe=pipe_a,
        tokenizer=hf_tokenizer,
        cfg=cfg,
        residency_mode=None,
    )
    session_a.begin(entry)
    states_a: list[dict[str, Any]] = []
    for turn_idx in range(len(entry["question"])):
        session_a.run_user_turn(turn_idx)
        states_a.append(
            {k: copy.deepcopy(_public_attrs(v)) for k, v in session_a.tool_instances().items()}
        )
        if session_a.force_quit:
            break
    row_a = session_a.finish()

    pipe_b = _GoldToolPipe(entry)
    session_b = MultiTurnAgentSession(
        pipe=pipe_b,
        tokenizer=hf_tokenizer,
        cfg=cfg,
        residency_mode=None,
    )
    session_b.begin(entry)
    states_b: list[dict[str, Any]] = []
    for turn_idx in range(len(entry["question"])):
        session_b.run_user_turn(turn_idx)
        states_b.append(
            {k: copy.deepcopy(_public_attrs(v)) for k, v in session_b.tool_instances().items()}
        )
        if session_b.force_quit:
            break
    row_b = session_b.finish()

    if len(states_a) != len(states_b):
        raise AssertionError(
            "FATAL: tool-state snapshot count diverged "
            f"entry={entry['id']!r} n_a={len(states_a)} n_b={len(states_b)}"
        )
    for turn_i, (sa, sb) in enumerate(zip(states_a, states_b, strict=True)):
        if set(sa.keys()) != set(sb.keys()):
            raise AssertionError(
                "FATAL: involved class keys diverged after turn "
                f"{turn_i} entry={entry['id']!r} a={sorted(sa)} b={sorted(sb)}"
            )
        for cls in sa:
            if sa[cls] != sb[cls]:
                raise AssertionError(
                    "FATAL: BFCL tool environment diverged after turn "
                    f"{turn_i} class={cls!r} entry={entry['id']!r} "
                    f"(prompt hashes alone are insufficient)"
                )

    assert row_a.get("score", {}).get("valid") is True, row_a.get("score")
    assert row_b.get("score", {}).get("valid") is True, row_b.get("score")
    assert (row_a.get("score") or {}).get("error_type") != ("multi_turn:instance_state_mismatch")
    assert (row_b.get("score") or {}).get("error_type") != ("multi_turn:instance_state_mismatch")


def test_begin_resets_bfcl_instances_across_reentry(hf_tokenizer, fixture_entry_with_tools) -> None:
    """Second begin on the same entry_id must not inherit mutated tool state.

    This is the interleaved-policy failure mode voided as 6c7f88f1: stable
    model_name + BFCL globals() reuse skipped _load_scenario on re-begin.
    """
    entry = fixture_entry_with_tools
    cfg = _FakeCfg()
    raw = entry["raw_entry"]
    initial_config = raw.get("initial_config") or {}
    involved = list(raw.get("involved_classes") or [])
    test_id = str(raw["id"])
    category = entry["category"]

    session1 = MultiTurnAgentSession(
        pipe=_GoldToolPipe(entry),
        tokenizer=hf_tokenizer,
        cfg=cfg,
        residency_mode=None,
    )
    session1.begin(entry)
    for turn_idx in range(len(entry["question"])):
        session1.run_user_turn(turn_idx)
        if session1.force_quit:
            break
    mutated = {k: copy.deepcopy(_public_attrs(v)) for k, v in session1.tool_instances().items()}
    session1.finish()

    session2 = MultiTurnAgentSession(
        pipe=_FakePipe("I cannot help with that."),
        tokenizer=hf_tokenizer,
        cfg=cfg,
        residency_mode=None,
    )
    session2.begin(entry)
    fresh = {k: copy.deepcopy(_public_attrs(v)) for k, v in session2.tool_instances().items()}
    # Reference: brand-new instances under a throwaway model_name.
    ref_name = "gate_fresh_ref_" + hashlib.sha256(test_id.encode()).hexdigest()[:8]
    ref_inst = snapshot_bfcl_tool_instances(
        model_name=ref_name,
        test_entry_id=test_id,
        initial_config=initial_config,
        involved_classes=involved,
        test_category=category,
    )
    ref = {k: copy.deepcopy(_public_attrs(v)) for k, v in ref_inst.items()}

    for cls in involved:
        if cls not in fresh or cls not in ref:
            continue
        if fresh[cls] != ref[cls]:
            raise AssertionError(
                "FATAL: begin() did not reset BFCL instance to initial_config "
                f"class={cls!r} entry={entry['id']!r}"
            )
        if mutated.get(cls) == fresh[cls] and mutated.get(cls) != ref[cls]:
            raise AssertionError(
                "FATAL: re-begin inherited mutated state from prior session "
                f"class={cls!r} entry={entry['id']!r} (6c7f88f1 class bug)"
            )
    session2.finish()
