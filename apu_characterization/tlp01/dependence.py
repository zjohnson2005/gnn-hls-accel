"""Three-tier dependence oracles for TLP-01 Phase T1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

from apu_characterization.tlp01.contracts import TraceEvent, load_protocol

EdgeKind = Literal["data", "control"]
DependenceTierName = Literal["Tier_0", "Tier_S", "Tier_C", "Tier_J"]


@dataclass(frozen=True)
class DependenceEdge:
    src_seq: int
    dst_seq: int
    kind: EdgeKind
    tier: DependenceTierName
    reason: str
    edge_class: str = "DS"
    derivation_ref: str = ""

    def as_tuple(self) -> tuple[int, int, EdgeKind]:
        return (self.src_seq, self.dst_seq, self.kind)


_TOKEN_RE = re.compile(r"[A-Za-z0-9_./:\\-]+")


def _tokens(text: str) -> set[str]:
    return {match.group(0) for match in _TOKEN_RE.finditer(text) if len(match.group(0)) >= 3}


def _ngrams(text: str, n: int) -> set[str]:
    tokens = [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]
    if len(tokens) < n:
        return set()
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def _event_output_payload(event: TraceEvent) -> str:
    parts = [event.output_text]
    parts.extend(event.produced_paths)
    parts.extend(event.result_ids)
    if event.result_ref:
        parts.append(event.result_ref)
    return "\n".join(part for part in parts if part)


def _event_input_payload(event: TraceEvent) -> str:
    parts = [event.input_text]
    if event.args_ref:
        parts.append(event.args_ref)
    return "\n".join(part for part in parts if part)


def _tool_namespace(event: TraceEvent) -> str | None:
    if not event.tool_name:
        return None
    return event.tool_name.split(".", 1)[0]


def tier_0_edges(events: Sequence[TraceEvent]) -> set[DependenceEdge]:
    """Structured dep_refs: ground truth by construction (S2 harness).

    Null dep_refs (S1) contribute no Tier-0 edges — silence, not independence.
    """
    edges: set[DependenceEdge] = set()
    seqs = {event.seq for event in events}
    for event in events:
        if event.dep_refs is None:
            continue
        for src in event.dep_refs:
            if src not in seqs:
                raise ValueError(
                    f"dep_refs seq {src} missing in session {event.session_id}"
                )
            if src >= event.seq:
                raise ValueError(
                    f"dep_refs must reference prior seqs: {src} -> {event.seq}"
                )
            edges.add(
                DependenceEdge(
                    src_seq=src,
                    dst_seq=event.seq,
                    kind="data",
                    tier="Tier_0",
                    reason="dep_refs",
                    edge_class="D0",
                    derivation_ref=f"dep_refs:{src}->{event.seq}",
                )
            )
    return edges


def assert_tier0_subseteq_tier_c(events: Sequence[TraceEvent]) -> None:
    """G-D extension (T1): every Tier-0 edge must appear in Tier-C."""
    if all(event.dep_refs is None for event in events):
        return
    t0 = {(e.src_seq, e.dst_seq, e.kind) for e in tier_0_edges(events)}
    tc = {(e.src_seq, e.dst_seq, e.kind) for e in tier_c_edges(events)}
    if not t0.issubset(tc):
        leaked = sorted(t0 - tc)
        raise AssertionError(
            f"Tier-0 not subset of Tier-C (G-D extension): {leaked[:10]}"
        )


def assert_tier0_subseteq_tier_s(events: Sequence[TraceEvent]) -> None:
    """G-D extension: every Tier-0 edge must appear in Tier-S.

    Structured dep_refs are Tier-S-class evidence by construction. Omitting this
    clause allowed the conceptual hole that Tier-S could discard harness-proven
    edges (see ser02_diagnosis.md / died-ledger #8). On the frozen S2 corpus the
    edges were already recovered via result_id_ref string match; the gate makes
    that recovery structural.
    """
    if all(event.dep_refs is None for event in events):
        return
    t0 = {(e.src_seq, e.dst_seq, e.kind) for e in tier_0_edges(events)}
    ts = {(e.src_seq, e.dst_seq, e.kind) for e in tier_s_edges(events)}
    if not t0.issubset(ts):
        leaked = sorted(t0 - ts)
        raise AssertionError(
            f"Tier-0 not subset of Tier-S (G-D extension): {leaked[:10]}"
        )


def tier_s_edges(events: Sequence[TraceEvent]) -> set[DependenceEdge]:
    """Syntactic data oracle (DS). Control/ordering live in the structural layer.

    Envelope exclusion: turn outputs are constant framing — they never mint DS
    edges. SC-EMIT covers turn→tool emission structurally.
    """
    ordered = sorted(events, key=lambda event: event.seq)
    edges: set[DependenceEdge] = set()
    for index, later in enumerate(ordered):
        later_input = _event_input_payload(later)
        later_tokens = _tokens(later_input)
        for earlier in ordered[:index]:
            # Envelope exclusion + structural ownership of turn→tool.
            if earlier.event_type == "turn":
                continue
            reasons: list[str] = []
            earlier_output = _event_output_payload(earlier)
            if earlier.result_ids and any(
                result_id and result_id in later_input for result_id in earlier.result_ids
            ):
                reasons.append("result_id_ref")
            if earlier.produced_paths and any(
                path and path in later_input for path in earlier.produced_paths
            ):
                reasons.append("path_consume")
            if earlier.result_ref and earlier.result_ref in later_input:
                reasons.append("result_ref")
            for token in _tokens(earlier_output):
                if len(token) >= 8 and token in later_tokens:
                    reasons.append(f"span:{token[:32]}")
                    break
            if earlier.event_type == "delegation" and later.control_parent_seq == earlier.seq:
                reasons.append("delegation_parent_child")
            if reasons:
                reason = "+".join(sorted(set(reasons)))
                edges.add(
                    DependenceEdge(
                        src_seq=earlier.seq,
                        dst_seq=later.seq,
                        kind="data",
                        tier="Tier_S",
                        reason=reason,
                        edge_class="DS",
                        derivation_ref=f"tier_s:{earlier.seq}->{later.seq}:{reason}",
                    )
                )
    for edge in tier_0_edges(events):
        edges.add(
            DependenceEdge(
                src_seq=edge.src_seq,
                dst_seq=edge.dst_seq,
                kind=edge.kind,
                tier="Tier_S",
                reason="dep_refs",
                edge_class="DS",
                derivation_ref=edge.derivation_ref or f"dep_refs:{edge.src_seq}->{edge.dst_seq}",
            )
        )
    return edges


def tier_c_edges(events: Sequence[TraceEvent]) -> set[DependenceEdge]:
    """Conservative-complete data oracle (DC). No positional/order heuristics.

    Ordering that is not content dependence is SC-* / HO in the structural layer.
    """
    protocol = load_protocol()
    cfg = protocol["dependence_oracles"]["Tier_C"]
    n = int(cfg["ngram_n"])
    threshold = int(cfg["ngram_overlap_threshold"])
    ordered = sorted(events, key=lambda event: event.seq)
    edges: set[DependenceEdge] = set()
    for index, later in enumerate(ordered):
        later_input = _event_input_payload(later)
        later_ngrams = _ngrams(later_input, n)
        later_ns = _tool_namespace(later)
        for earlier in ordered[:index]:
            if earlier.event_type == "turn":
                continue
            earlier_output = _event_output_payload(earlier)
            earlier_ngrams = _ngrams(earlier_output, n)
            overlap = len(later_ngrams & earlier_ngrams)
            earlier_ns = _tool_namespace(earlier)
            namespaces_disjoint = (
                earlier_ns is None
                or later_ns is None
                or earlier_ns != later_ns
            )
            independent = (
                overlap <= threshold
                and namespaces_disjoint
                and not (
                    earlier.produced_paths
                    and any(path in later_input for path in earlier.produced_paths)
                )
                and not (
                    earlier.result_ids
                    and any(rid in later_input for rid in earlier.result_ids)
                )
            )
            if not independent:
                reason = (
                    f"ngram_overlap={overlap}"
                    if overlap > threshold
                    else "namespace_or_ref"
                )
                edges.add(
                    DependenceEdge(
                        src_seq=earlier.seq,
                        dst_seq=later.seq,
                        kind="data",
                        tier="Tier_C",
                        reason=reason,
                        edge_class="DC",
                        derivation_ref=f"tier_c:{earlier.seq}->{later.seq}:{reason}",
                    )
                )
    for edge in tier_s_edges(events):
        edges.add(
            DependenceEdge(
                src_seq=edge.src_seq,
                dst_seq=edge.dst_seq,
                kind=edge.kind,
                tier="Tier_C",
                reason=f"includes_S:{edge.reason}",
                edge_class="DC",
                derivation_ref=edge.derivation_ref
                or f"includes_S:{edge.src_seq}->{edge.dst_seq}",
            )
        )
    return edges


def disagreement_pairs(
    events: Sequence[TraceEvent],
) -> list[tuple[int, int]]:
    s_pairs = {(e.src_seq, e.dst_seq) for e in tier_s_edges(events) if e.kind == "data"}
    c_pairs = {(e.src_seq, e.dst_seq) for e in tier_c_edges(events) if e.kind == "data"}
    return sorted(c_pairs - s_pairs)


def assert_bracket_invariant(events: Sequence[TraceEvent]) -> None:
    s_pairs = {(e.src_seq, e.dst_seq, e.kind) for e in tier_s_edges(events)}
    c_pairs = {(e.src_seq, e.dst_seq, e.kind) for e in tier_c_edges(events)}
    if not s_pairs.issubset(c_pairs):
        leaked = sorted(s_pairs - c_pairs)
        raise AssertionError(f"Tier-S not subset of Tier-C: {leaked[:10]}")


def edges_for_tier(
    events: Sequence[TraceEvent], tier: DependenceTierName
) -> set[DependenceEdge]:
    if tier == "Tier_0":
        return tier_0_edges(events)
    if tier == "Tier_S":
        return tier_s_edges(events)
    if tier == "Tier_C":
        return tier_c_edges(events)
    raise ValueError("Tier_J edges are not produced by the deterministic oracle")


def summarize_disagreement(
    sessions: Iterable[Sequence[TraceEvent]],
) -> dict[str, float]:
    by_class: dict[str, list[float]] = {}
    for events in sessions:
        if not events:
            continue
        task_class = events[0].task_class or "UNKNOWN"
        ordered = list(events)
        pairs = len(ordered) * (len(ordered) - 1) // 2
        if pairs == 0:
            rate = 0.0
        else:
            rate = len(disagreement_pairs(ordered)) / pairs
        by_class.setdefault(task_class, []).append(rate)
    return {
        task_class: sum(rates) / len(rates)
        for task_class, rates in sorted(by_class.items())
    }
