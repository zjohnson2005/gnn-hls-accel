"""Two-layer step labeling (mechanism + semantic) and PrefixSpan validation."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from apu_characterization.turntrace_v2.contracts import load_tool_manifest
from apu_characterization.turntrace_v2.schema import StepFeatures


@dataclass(frozen=True)
class RawTurnEvent:
    """Minimal event metadata for labeling (derivation step input)."""

    turn_index: int
    tool_names: tuple[str, ...]
    graph_node: str | None
    call_site_tag: str | None
    status: str = "ok"  # ok | error | timeout
    expected_horizon: int = 1


def tool_class_for(name: str | None, manifest: Mapping[str, Any] | None = None) -> str:
    if not name:
        return "none"
    manifest = manifest or load_tool_manifest()
    tools = manifest.get("tools") or {}
    return str(tools.get(name, "state_mutating"))


def semantic_label(event: RawTurnEvent) -> str:
    if event.tool_names:
        # One step = one model call; semantic label is primary tool or joined fanout.
        if len(event.tool_names) == 1:
            return event.tool_names[0]
        return "+".join(event.tool_names)
    if event.graph_node:
        return event.graph_node
    if event.call_site_tag:
        return event.call_site_tag
    return "generate"


def detect_loop_membership(
    semantic_seq: Sequence[str],
    *,
    window: int = 4,
) -> list[bool]:
    """Flag turns that participate in a tight alternating cycle (e.g. edit-verify)."""
    flags = [False] * len(semantic_seq)
    if len(semantic_seq) < 4:
        return flags
    for i in range(2, len(semantic_seq)):
        # Detect ABAB pattern ending at i.
        if (
            semantic_seq[i] == semantic_seq[i - 2]
            and semantic_seq[i - 1] == semantic_seq[i - 3]
            and semantic_seq[i] != semantic_seq[i - 1]
        ):
            flags[i] = True
            flags[i - 1] = True
            flags[i - 2] = True
            flags[i - 3] = True
    # Also mark dense repeats inside a short window.
    for i in range(len(semantic_seq)):
        lo = max(0, i - window + 1)
        window_vals = semantic_seq[lo : i + 1]
        if len(window_vals) >= 3 and window_vals.count(semantic_seq[i]) >= 3:
            flags[i] = True
    return flags


def label_trajectory(
    events: Sequence[RawTurnEvent],
    *,
    manifest: Mapping[str, Any] | None = None,
) -> list[tuple[str, StepFeatures]]:
    manifest = manifest or load_tool_manifest()
    semantics = [semantic_label(ev) for ev in events]
    loops = detect_loop_membership(semantics)
    counts: Counter[str] = Counter()
    horizon = max((ev.expected_horizon for ev in events), default=1)
    horizon = max(horizon, len(events), 1)
    labeled: list[tuple[str, StepFeatures]] = []
    for i, ev in enumerate(events):
        sem = semantics[i]
        counts[sem] += 1
        primary = ev.tool_names[0] if ev.tool_names else None
        features = StepFeatures(
            is_tool_call=bool(ev.tool_names),
            tool_class=tool_class_for(primary, manifest),  # type: ignore[arg-type]
            repeat_count=counts[sem],
            loop_membership=loops[i],
            fanout_siblings=max(0, len(ev.tool_names) - 1) if ev.tool_names else 0,
            trajectory_position=ev.turn_index / horizon,
        )
        features.validate()
        labeled.append((sem, features))
    return labeled


@dataclass
class TaxonomyValidation:
    assigned_types: list[str]
    mined_patterns: list[tuple[tuple[str, ...], int]]
    agreement_rate: float
    prefer_mined_for_layer1: bool
    notes: str


def _prefixspan(
    sequences: Sequence[Sequence[str]],
    *,
    min_support: int,
) -> list[tuple[tuple[str, ...], int]]:
    """Minimal PrefixSpan over event signatures for PASTE-style validation."""

    def _freq(prefix: tuple[str, ...], db: list[list[str]]) -> list[tuple[tuple[str, ...], int, list[list[str]]]]:
        counter: dict[str, int] = defaultdict(int)
        projected: dict[str, list[list[str]]] = defaultdict(list)
        for seq in db:
            seen: set[str] = set()
            for i, item in enumerate(seq):
                if item in seen:
                    continue
                seen.add(item)
                counter[item] += 1
                projected[item].append(seq[i + 1 :])
        out = []
        for item, support in sorted(counter.items()):
            if support >= min_support:
                out.append((prefix + (item,), support, projected[item]))
        return out

    results: list[tuple[tuple[str, ...], int]] = []
    db0 = [list(seq) for seq in sequences]

    def recurse(prefix: tuple[str, ...], db: list[list[str]]) -> None:
        for new_prefix, support, proj in _freq(prefix, db):
            results.append((new_prefix, support))
            if proj:
                recurse(new_prefix, proj)

    recurse((), db0)
    results.sort(key=lambda p: (-p[1], p[0]))
    return results


def validate_taxonomy(
    labeled_trajectories: Sequence[Sequence[tuple[str, StepFeatures, str]]],
    *,
    min_support: int = 2,
) -> TaxonomyValidation:
    """Compare assigned semantic labels against mined frequent subsequences.

    Each inner item is (semantic, features, status).
    """
    assigned: list[str] = []
    sequences: list[list[str]] = []
    for traj in labeled_trajectories:
        seq = []
        for semantic, features, status in traj:
            assigned.append(semantic)
            sig = f"{features.tool_class}/{semantic}:{status}"
            seq.append(sig)
        sequences.append(seq)
    mined = _prefixspan(sequences, min_support=min_support)
    # Agreement: fraction of assigned labels that appear as length-1 mined patterns.
    mined_singletons = {pat[0].split(":")[0].split("/", 1)[-1] for pat, _ in mined if len(pat) == 1}
    if not assigned:
        return TaxonomyValidation([], [], 1.0, False, "empty")
    hits = sum(1 for a in assigned if a in mined_singletons)
    rate = hits / len(assigned)
    prefer_mined = rate < 0.5
    notes = (
        "assigned taxonomy recovered by mining"
        if rate >= 0.5
        else "disagreement: prefer mined clusters for Layer 1 grouping"
    )
    return TaxonomyValidation(
        assigned_types=sorted(set(assigned)),
        mined_patterns=mined[:50],
        agreement_rate=rate,
        prefer_mined_for_layer1=prefer_mined,
        notes=notes,
    )


def event_signatures(
    labeled: Iterable[tuple[str, StepFeatures, str]],
) -> list[str]:
    return [f"{feat.tool_class}/{sem}:{status}" for sem, feat, status in labeled]
