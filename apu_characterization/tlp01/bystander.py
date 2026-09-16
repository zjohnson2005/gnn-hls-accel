"""Bystander-contention (observer-effect) measurement for software-side speculation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from apu_characterization.tlp01.contracts import TraceEvent, load_protocol
from apu_characterization.tlp01.phase_diagram import (
    _corrupt_to_accuracy,
    _ranked_with_confidence,
    _select_speculative_set,
    _stable_rng,
)
from apu_characterization.tlp01.predictor import tool_sequence, train_markov
from apu_characterization.tlp01.predictor import split_sessions

# Primary-path slowdown per concurrent speculative issue (software observer effect).
# Frozen methodological constant for the secondary measurement; not a silicon claim.
CONTENTION_TAX_PER_INFLIGHT = 0.08


def measure_bystander_contention(
    sessions: Sequence[Sequence[TraceEvent]],
    *,
    accuracy_target: float = 0.6,
) -> dict[str, Any]:
    """Compare primary-path wall with vs without in-flight speculative siblings.

    Software-side policies only. Reports relative slowdown of the primary path
    when speculative work shares the host — observer-effect methodology pointed
    at speculation.
    """
    protocol = load_protocol()
    frontier = protocol["speculation_frontier"]
    threshold = float(frontier["confidence_gate_default_threshold"])
    software_policies = [
        p
        for p in frontier["policies"]
        if p != "no_speculation"
    ]
    train, test = split_sessions(sessions)
    models = train_markov(train)
    eval_sessions = test or train

    per_policy: dict[str, list[float]] = defaultdict(list)

    for events in eval_sessions:
        if not events:
            continue
        model = models.get(events[0].task_class or "UNKNOWN") or {}
        seq = tool_sequence(events)
        if len(seq) < 2:
            continue
        rng = _stable_rng(events[0].session_id, "bystander")
        # Baseline primary path: sum of tool durations, no contention.
        baseline = sum(
            max(e.duration_ns, 1)
            for e in events
            if e.event_type == "tool_call"
        )
        if baseline <= 0:
            continue
        for policy in software_policies:
            history = "__start__"
            contended = 0
            for actual in seq:
                ranked = _ranked_with_confidence(model, history, top_k=5)
                ranked = _corrupt_to_accuracy(
                    ranked, actual, target_accuracy=accuracy_target, rng=rng
                )
                speculative = _select_speculative_set(
                    policy, ranked, confidence_threshold=threshold
                )
                inflight = len(speculative)
                # Duration of this primary step under contention.
                # Find matching event duration.
                dur = next(
                    (
                        max(e.duration_ns, 1)
                        for e in events
                        if e.tool_name == actual
                    ),
                    1_000_000,
                )
                contended += int(dur * (1.0 + CONTENTION_TAX_PER_INFLIGHT * inflight))
                history = actual
            slowdown = (contended - baseline) / baseline
            per_policy[policy].append(slowdown)

    summary = {}
    for policy, values in sorted(per_policy.items()):
        summary[policy] = {
            "median_primary_slowdown": sorted(values)[len(values) // 2]
            if values
            else 0.0,
            "mean_primary_slowdown": sum(values) / len(values) if values else 0.0,
            "n": len(values),
            "contention_tax_per_inflight": CONTENTION_TAX_PER_INFLIGHT,
        }
    return {
        "secondary": True,
        "scope": "software_side_policies",
        "method": frontier["bystander_contention"]["method"],
        "per_policy": summary,
    }
