"""R2C-TURNWISE equivalence gate: compositor vs session turn-by-turn.

Local-only paths (no bounce). Fail loud on prompt_render_sha256 or per-step
token-ID divergence - do not absorb.
"""

from __future__ import annotations

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
    run_multi_turn_agent_entry,
    select_multi_turn_entries,
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


class _FakeCfg:
    max_new_tokens = 512
    do_sample = False
    apply_chat_template = False


def _first_mismatch(a: list[int], b: list[int]) -> int | None:
    for i, (x, y) in enumerate(zip(a, b, strict=False)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


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
