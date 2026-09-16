"""Next-dispatch predictor sub-study for M4 (secondary result)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Sequence

from apu_characterization.tlp01.contracts import TraceEvent, load_protocol


def tool_sequence(events: Sequence[TraceEvent]) -> list[str]:
    return [
        event.tool_name or f"turn:{event.seq}"
        for event in sorted(events, key=lambda item: item.seq)
        if event.event_type == "tool_call" and event.tool_name
    ]


def train_markov(
    sessions: Sequence[Sequence[TraceEvent]],
) -> dict[str, dict[str, Counter[str]]]:
    """Per task-class bigram counts: history tool -> next tool."""
    models: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    for events in sessions:
        if not events:
            continue
        task_class = events[0].task_class or "UNKNOWN"
        seq = tool_sequence(events)
        for left, right in zip(seq, seq[1:]):
            models[task_class][left][right] += 1
        if seq:
            models[task_class]["__start__"][seq[0]] += 1
    return models


def predict_next(
    model: dict[str, Counter[str]],
    history: str,
    *,
    top_k: int = 3,
) -> list[str]:
    counts = model.get(history) or model.get("__start__") or Counter()
    return [tool for tool, _ in counts.most_common(top_k)]


def evaluate_predictor(
    train: Sequence[Sequence[TraceEvent]],
    test: Sequence[Sequence[TraceEvent]],
) -> dict[str, dict[str, float]]:
    models = train_markov(train)
    hits_top1: dict[str, list[int]] = defaultdict(list)
    hits_top3: dict[str, list[int]] = defaultdict(list)
    for events in test:
        if not events:
            continue
        task_class = events[0].task_class or "UNKNOWN"
        model = models.get(task_class) or {}
        seq = tool_sequence(events)
        if len(seq) < 2:
            continue
        for left, right in zip(seq, seq[1:]):
            ranked = predict_next(model, left, top_k=3)
            hits_top1[task_class].append(int(bool(ranked) and ranked[0] == right))
            hits_top3[task_class].append(int(right in ranked))
    protocol = load_protocol()
    favorable = float(protocol["predictor_substudy"]["pre_registered_favorable_top1"])
    out: dict[str, dict[str, float]] = {}
    for task_class in sorted(set(hits_top1) | set(hits_top3)):
        t1 = hits_top1.get(task_class) or []
        t3 = hits_top3.get(task_class) or []
        top1 = sum(t1) / len(t1) if t1 else 0.0
        top3 = sum(t3) / len(t3) if t3 else 0.0
        out[task_class] = {
            "top1_accuracy": top1,
            "top3_accuracy": top3,
            "favorable_vs_preregistered": float(top1 >= favorable),
        }
    return out


def split_sessions(
    sessions: Sequence[Sequence[TraceEvent]],
    *,
    train_fraction: float | None = None,
) -> tuple[list[Sequence[TraceEvent]], list[Sequence[TraceEvent]]]:
    protocol = load_protocol()
    frac = (
        float(protocol["predictor_substudy"]["train_fraction"])
        if train_fraction is None
        else train_fraction
    )
    by_class: dict[str, list[Sequence[TraceEvent]]] = defaultdict(list)
    for events in sessions:
        if events:
            by_class[events[0].task_class or "UNKNOWN"].append(events)
    train: list[Sequence[TraceEvent]] = []
    test: list[Sequence[TraceEvent]] = []
    for items in by_class.values():
        cut = max(1, int(len(items) * frac)) if len(items) > 1 else len(items)
        # Keep at least one test item when possible.
        if len(items) > 1 and cut >= len(items):
            cut = len(items) - 1
        train.extend(items[:cut])
        test.extend(items[cut:])
    return train, test
