"""Regression: correct speculative hits must credit overlap into wall time.

Item 1 (smoke integrity): this was a GENERAL throughput-formula bug, not
tuning. Pre-fix hit path still charged ``duration_ns`` as serial wall
(``hit_path_wall_ns(..., credit_overlap=False)``), so a correct prediction
could not beat no-speculation for any policy or dataset. Post-fix uses
``credit_overlap=True``.

This test fails on the pre-fix formula and passes on the post-fix formula.
"""

from __future__ import annotations

from collections import Counter

from apu_characterization.tlp01.extract import make_synthetic_parallel_session
from apu_characterization.tlp01.phase_diagram import (
    hit_path_wall_ns,
    replay_speculation_policy,
)


def test_pre_fix_hit_path_does_not_reduce_wall() -> None:
    """Document the bug: without overlap credit, hit wall == dur (+ extras)."""
    dur = 10_000_000
    buggy = hit_path_wall_ns(
        duration_ns=dur, penalty_ns=0, extras=0, credit_overlap=False
    )
    assert buggy == dur


def test_post_fix_hit_path_credits_full_overlap() -> None:
    dur = 10_000_000
    fixed = hit_path_wall_ns(
        duration_ns=dur, penalty_ns=0, extras=0, credit_overlap=True
    )
    assert fixed == 0
    assert fixed < hit_path_wall_ns(
        duration_ns=dur, penalty_ns=0, extras=0, credit_overlap=False
    )


def test_one_correct_hit_beats_no_speculation_baseline() -> None:
    """Minimal trace: perfect always-top1 must lower wall vs no_speculation.

    Would fail under the pre-fix formula where hits still added ``dur`` to wall.
    """
    events = make_synthetic_parallel_session(
        session_id="overlap-credit-unit",
        seed=0,
        width=2,
        unit_ns=10_000_000,
        orch_ns=0,
    )
    # Perfect bigram model over the session's own tool sequence.
    tools = [
        e.tool_name
        for e in events
        if e.event_type == "tool_call" and e.tool_name
    ]
    model: dict[str, Counter[str]] = {"__start__": Counter({tools[0]: 1})}
    for left, right in zip(tools, tools[1:]):
        model.setdefault(left, Counter())[right] += 1

    class _AlwaysHit:
        def random(self) -> float:
            return 0.0  # always below any accuracy target → forced hits

    nospec = replay_speculation_policy(
        events,
        model,
        policy="no_speculation",
        penalty_ns=0,
        accuracy_target=1.0,
        confidence_threshold=0.0,
        rng=_AlwaysHit(),  # type: ignore[arg-type]
    )
    top1 = replay_speculation_policy(
        events,
        model,
        policy="always_top1",
        penalty_ns=0,
        accuracy_target=1.0,
        confidence_threshold=0.0,
        rng=_AlwaysHit(),  # type: ignore[arg-type]
    )
    assert top1.wall_ns < nospec.wall_ns, (
        f"correct hits must credit overlap: top1 wall={top1.wall_ns} "
        f"nospec wall={nospec.wall_ns} (pre-fix would keep them equal)"
    )
    assert top1.effective_throughput > nospec.effective_throughput
