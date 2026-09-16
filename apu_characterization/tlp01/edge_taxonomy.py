"""TLP-01 edge taxonomy v2: structural / harness-order / data classes.

Structural edges are derived mechanically from trace schema (no content analysis).
Data edges come from Tier-0/S/C oracles (scoped to true data flow).
HO edges explain residual in-order serialization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

from apu_characterization.tlp01.contracts import TraceEvent

EdgeClass = Literal[
    "SC-EMIT",
    "SD-RESULT",
    "SC-SPAWN",
    "SD-JOIN",
    "HO",
    "D0",
    "DS",
    "DC",
]

# Machines may break only these classes (see MACHINE_BREAKABLE).
STRUCTURAL_CONTROL = frozenset({"SC-EMIT", "SC-SPAWN"})
STRUCTURAL_DATA = frozenset({"SD-RESULT", "SD-JOIN"})
DATA_DISCOVERED = frozenset({"D0", "DS", "DC"})
UNBREAKABLE_DEFAULT = STRUCTURAL_DATA | DATA_DISCOVERED

MACHINE_BREAKABLE: dict[str, frozenset[str]] = {
    "M0": frozenset(),  # recorded reality — no counterfactual breaks
    "M1a": frozenset({"HO"}),
    "M1b": frozenset({"HO", "SC-EMIT", "SC-SPAWN"}),
    "M2": frozenset({"HO", "SC-EMIT", "SC-SPAWN"}),
    "M3": frozenset({"HO"}),  # width-limited non-speculative (as M1a)
    "M4": frozenset({"HO", "SC-EMIT", "SC-SPAWN"}),  # SC break cost via penalty
    "M5": frozenset({"HO", "SC-EMIT", "SC-SPAWN"}),
}

GRAPH_FORMAT_V2 = "tlp01_graph_v2"


@dataclass(frozen=True)
class TypedEdge:
    src_seq: int
    dst_seq: int
    edge_class: EdgeClass
    derivation_ref: str
    kind: Literal["data", "control"]
    reason: str = ""

    def as_pair(self) -> tuple[int, int]:
        return (self.src_seq, self.dst_seq)


def _harness_ordered(events: Sequence[TraceEvent]) -> list[TraceEvent]:
    return sorted(events, key=lambda e: (e.harness_order_index, e.seq))


def _by_seq(events: Sequence[TraceEvent]) -> dict[int, TraceEvent]:
    return {e.seq: e for e in events}


def parent_turn_seq(event: TraceEvent, events: Sequence[TraceEvent]) -> int | None:
    """Resolve the emitting turn for a tool_call / child session.

    Prefers explicit control_parent_seq when it points at a turn; otherwise
    infers the most recent preceding turn in harness order (S2 freeze often
    left control_parent_seq null).
    """
    by = _by_seq(events)
    if event.control_parent_seq is not None:
        parent = by.get(event.control_parent_seq)
        if parent is not None and parent.event_type == "turn":
            return parent.seq
    ordered = _harness_ordered(events)
    prior_turn: int | None = None
    for ev in ordered:
        if ev.seq == event.seq:
            return prior_turn
        if ev.event_type == "turn":
            prior_turn = ev.seq
    return prior_turn


def generate_structural_edges(events: Sequence[TraceEvent]) -> set[TypedEdge]:
    """Pure structural edges — zero content analysis."""
    edges: set[TypedEdge] = set()
    by = _by_seq(events)
    ordered = _harness_ordered(events)

    for ev in ordered:
        if ev.event_type == "tool_call":
            parent = parent_turn_seq(ev, events)
            if parent is None:
                continue
            edges.add(
                TypedEdge(
                    src_seq=parent,
                    dst_seq=ev.seq,
                    edge_class="SC-EMIT",
                    derivation_ref=f"parent_turn:{parent}->tool_call:{ev.seq}",
                    kind="control",
                    reason="SC-EMIT",
                )
            )
        if ev.event_type == "delegation":
            parent = parent_turn_seq(ev, events)
            if parent is not None:
                edges.add(
                    TypedEdge(
                        src_seq=parent,
                        dst_seq=ev.seq,
                        edge_class="SC-SPAWN",
                        derivation_ref=f"parent_turn:{parent}->delegation:{ev.seq}",
                        kind="control",
                        reason="SC-SPAWN",
                    )
                )

    # SD-RESULT: tool_call → next turn that follows it in harness order
    # (result delivery into subsequent model context). Envelope-only sessions
    # with a single leading turn produce no SD-RESULT edges.
    for index, ev in enumerate(ordered):
        if ev.event_type != "tool_call":
            continue
        for later in ordered[index + 1 :]:
            if later.event_type == "turn":
                edges.add(
                    TypedEdge(
                        src_seq=ev.seq,
                        dst_seq=later.seq,
                        edge_class="SD-RESULT",
                        derivation_ref=(
                            f"result_delivery:tool_call:{ev.seq}->turn:{later.seq}"
                        ),
                        kind="data",
                        reason="SD-RESULT",
                    )
                )
                break

    # SD-JOIN / SC-SPAWN child→join: when a turn has control_parent pointing
    # at a delegation, treat as join consumer.
    for ev in ordered:
        if ev.event_type != "turn" or ev.control_parent_seq is None:
            continue
        parent = by.get(ev.control_parent_seq)
        if parent is None:
            continue
        if parent.event_type == "delegation":
            edges.add(
                TypedEdge(
                    src_seq=parent.seq,
                    dst_seq=ev.seq,
                    edge_class="SD-JOIN",
                    derivation_ref=(
                        f"delegation_join:{parent.seq}->turn:{ev.seq}"
                    ),
                    kind="data",
                    reason="SD-JOIN",
                )
            )
    return edges


def generate_ho_edges(
    events: Sequence[TraceEvent],
    *,
    covered_pairs: Iterable[tuple[int, int]],
) -> set[TypedEdge]:
    """HO: consecutive harness-order pairs with no other edge between them."""
    covered = set(covered_pairs)
    ordered = _harness_ordered(events)
    edges: set[TypedEdge] = set()
    for earlier, later in zip(ordered, ordered[1:]):
        pair = (earlier.seq, later.seq)
        if pair in covered:
            continue
        edges.add(
            TypedEdge(
                src_seq=earlier.seq,
                dst_seq=later.seq,
                edge_class="HO",
                derivation_ref=(
                    f"harness_order:{earlier.harness_order_index}"
                    f"->{later.harness_order_index}"
                    f"(seq {earlier.seq}->{later.seq})"
                ),
                kind="control",
                reason="HO",
            )
        )
    return edges


def conservation_of_ordering(
    events: Sequence[TraceEvent],
    edges: Iterable[TypedEdge],
) -> dict[str, object]:
    """Every harness-adjacent pair must be explained by some edge.

    Returns pass/fail plus any unexplained ordered pairs (taxonomy holes).
    """
    ordered = _harness_ordered(events)
    explained = {(e.src_seq, e.dst_seq) for e in edges}
    unexplained: list[dict[str, object]] = []
    for earlier, later in zip(ordered, ordered[1:]):
        if (earlier.seq, later.seq) not in explained:
            unexplained.append(
                {
                    "src_seq": earlier.seq,
                    "dst_seq": later.seq,
                    "src_type": earlier.event_type,
                    "dst_type": later.event_type,
                    "harness_order": (
                        earlier.harness_order_index,
                        later.harness_order_index,
                    ),
                }
            )
    return {
        "pass": not unexplained,
        "unexplained": unexplained,
        "adjacent_pairs": len(ordered) - 1 if ordered else 0,
        "explained_pairs": len(ordered) - 1 - len(unexplained) if ordered else 0,
    }


def breakable_classes_for(model: str) -> frozenset[str]:
    if model not in MACHINE_BREAKABLE:
        raise ValueError(f"unknown machine model for taxonomy: {model!r}")
    return MACHINE_BREAKABLE[model]


def assert_no_bare_m1(blob: str, *, context: str) -> None:
    """Grep-gate: unqualified M1 model tokens forbidden after M1a/M1b split."""
    import re

    patterns = (
        r'"model"\s*:\s*"M1"',
        r"model\s*=\s*[\"']M1[\"']",
        r"\bM1 oracle\b",
        r"\bm1_speedup_bands\b",
        r"floor_tax_m2_minus_m1\b",
        r"## M1(?![ab])\b",
    )
    hits: list[str] = []
    for pat in patterns:
        hits.extend(re.findall(pat, blob))
    # Also catch simulate_model(..., "M1", ...)
    hits.extend(re.findall(r"simulate_model\([^)]*[\"']M1[\"']", blob))
    if hits:
        raise AssertionError(
            f"{context}: unqualified M1 labels forbidden after taxonomy v2 "
            f"(use M1a/M1b): {sorted(set(hits))[:10]}"
        )
