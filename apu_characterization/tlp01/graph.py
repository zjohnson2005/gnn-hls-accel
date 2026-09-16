"""Dependence DAG construction and validation for TLP-01 (graph format v2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from apu_characterization.tlp01.contracts import TraceEvent
from apu_characterization.tlp01.dependence import (
    DependenceEdge,
    DependenceTierName,
    assert_bracket_invariant,
    edges_for_tier,
)
from apu_characterization.tlp01.edge_taxonomy import (
    GRAPH_FORMAT_V2,
    TypedEdge,
    conservation_of_ordering,
    generate_ho_edges,
    generate_structural_edges,
)


@dataclass
class DependenceGraph:
    session_id: str
    tier: DependenceTierName
    events: dict[int, TraceEvent]
    edges: set[DependenceEdge] = field(default_factory=set)
    graph_format: str = GRAPH_FORMAT_V2
    conservation: dict[str, object] = field(default_factory=dict)

    @property
    def nodes(self) -> list[int]:
        return sorted(self.events)

    def successors(self, seq: int) -> list[int]:
        return sorted({edge.dst_seq for edge in self.edges if edge.src_seq == seq})

    def predecessors(self, seq: int) -> list[int]:
        return sorted({edge.src_seq for edge in self.edges if edge.dst_seq == seq})

    def data_predecessors(self, seq: int) -> list[int]:
        return sorted(
            {
                edge.src_seq
                for edge in self.edges
                if edge.dst_seq == seq and edge.kind == "data"
            }
        )

    def control_predecessors(self, seq: int) -> list[int]:
        return sorted(
            {
                edge.src_seq
                for edge in self.edges
                if edge.dst_seq == seq and edge.kind == "control"
            }
        )

    def binding_predecessors(self, seq: int, *, breakable: frozenset[str]) -> list[int]:
        """Predecessors whose edge class the machine may NOT break."""
        return sorted(
            {
                edge.src_seq
                for edge in self.edges
                if edge.dst_seq == seq and edge.edge_class not in breakable
            }
        )

    def is_dag(self) -> bool:
        pending = {seq: len(self.predecessors(seq)) for seq in self.events}
        ready = [seq for seq, degree in pending.items() if degree == 0]
        seen = 0
        while ready:
            node = ready.pop()
            seen += 1
            for succ in self.successors(node):
                pending[succ] -= 1
                if pending[succ] == 0:
                    ready.append(succ)
        return seen == len(self.events)

    def topological_levels(self) -> list[list[int]]:
        if not self.is_dag():
            raise ValueError("graph has a cycle")
        remaining = {seq: set(self.predecessors(seq)) for seq in self.events}
        levels: list[list[int]] = []
        while remaining:
            ready = sorted(seq for seq, preds in remaining.items() if not preds)
            if not ready:
                raise ValueError("graph has a cycle")
            levels.append(ready)
            ready_set = set(ready)
            for seq in ready:
                del remaining[seq]
            for preds in remaining.values():
                preds -= ready_set
        return levels


def _typed_to_dep(
    edge: TypedEdge, *, tier: DependenceTierName
) -> DependenceEdge:
    return DependenceEdge(
        src_seq=edge.src_seq,
        dst_seq=edge.dst_seq,
        kind=edge.kind,
        tier=tier,
        reason=edge.reason or edge.edge_class,
        edge_class=edge.edge_class,
        derivation_ref=edge.derivation_ref,
    )


def assemble_typed_edges(
    events: Sequence[TraceEvent],
    tier: DependenceTierName,
) -> tuple[set[DependenceEdge], dict[str, object]]:
    """Structural + data(tier) + HO; run conservation gate."""
    structural = generate_structural_edges(events)
    data = edges_for_tier(events, tier)
    covered = {(e.src_seq, e.dst_seq) for e in structural} | {
        (e.src_seq, e.dst_seq) for e in data
    }
    ho = generate_ho_edges(events, covered_pairs=covered)
    typed: set[TypedEdge] = set(structural) | set(ho)
    merged: set[DependenceEdge] = {_typed_to_dep(e, tier=tier) for e in typed}
    merged |= set(data)
    conservation = conservation_of_ordering(
        events, list(structural) + list(ho) + [
            TypedEdge(
                src_seq=e.src_seq,
                dst_seq=e.dst_seq,
                edge_class=e.edge_class,  # type: ignore[arg-type]
                derivation_ref=e.derivation_ref or e.reason,
                kind=e.kind,
                reason=e.reason,
            )
            for e in data
        ]
    )
    return merged, conservation


def build_graph(
    events: Sequence[TraceEvent],
    tier: DependenceTierName,
    *,
    include_control: bool = True,
) -> DependenceGraph:
    assert_bracket_invariant(events)
    edges, conservation = assemble_typed_edges(events, tier)
    if not include_control:
        edges = {edge for edge in edges if edge.kind == "data"}
    if not conservation["pass"]:
        raise ValueError(
            f"taxonomy conservation hole in {events[0].session_id}: "
            f"{conservation['unexplained'][:5]}"
        )
    event_map = {event.seq: event for event in events}
    graph = DependenceGraph(
        session_id=events[0].session_id,
        tier=tier,
        events=event_map,
        edges=edges,
        conservation=conservation,
    )
    if not graph.is_dag():
        raise ValueError(f"{tier} graph for {graph.session_id} is cyclic")
    return graph


def event_conservation(
    events: Sequence[TraceEvent], graphs: Iterable[DependenceGraph]
) -> list[str]:
    errors: list[str] = []
    expected = {event.seq for event in events}
    for graph in graphs:
        got = set(graph.events)
        if got != expected:
            errors.append(
                f"{graph.tier}: node set mismatch "
                f"missing={sorted(expected - got)} extra={sorted(got - expected)}"
            )
        if graph.conservation and not graph.conservation.get("pass", True):
            errors.append(
                f"{graph.tier}: ordering conservation failed: "
                f"{graph.conservation.get('unexplained')}"
            )
    return errors
