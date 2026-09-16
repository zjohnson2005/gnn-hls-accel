"""Trace-driven scheduling simulation across the TLP-01 machine-model ladder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from apu_characterization.tlp01.contracts import TraceEvent, load_protocol
from apu_characterization.tlp01.edge_taxonomy import breakable_classes_for
from apu_characterization.tlp01.graph import DependenceGraph, build_graph
from apu_characterization.tlp01.schema import recorded_makespan_ns

PenaltyVariant = Literal["software", "praetor"]


@dataclass(frozen=True)
class ScheduleResult:
    model: str
    tier: str
    makespan_ns: int
    baseline_makespan_ns: int
    speedup: float
    max_in_flight: int
    width: int | None
    penalty_variant: str | None = None
    notes: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "tier": self.tier,
            "makespan_ns": self.makespan_ns,
            "baseline_makespan_ns": self.baseline_makespan_ns,
            "speedup": self.speedup,
            "max_in_flight": self.max_in_flight,
            "width": self.width,
            "penalty_variant": self.penalty_variant,
            "notes": self.notes,
        }


def _unit_cost_ns(event: TraceEvent, *, charge_orch: bool) -> int:
    body = event.duration_ns
    if not charge_orch:
        return max(body, 1)
    return max(body + event.orch_ns, 1)


def simulate_in_order(events: Sequence[TraceEvent]) -> ScheduleResult:
    """M0: recorded wall-clock makespan (G-V denominator / validation only)."""
    ordered = sorted(events, key=lambda event: event.harness_order_index)
    time_ns = 0
    for event in ordered:
        time_ns = max(time_ns, event.t_complete_ns - ordered[0].t_issue_ns)
    baseline = recorded_makespan_ns(ordered)
    makespan = baseline if baseline > 0 else time_ns
    return ScheduleResult(
        model="M0",
        tier="recorded",
        makespan_ns=makespan,
        baseline_makespan_ns=baseline,
        speedup=1.0,
        max_in_flight=1,
        width=1,
        notes="in-order harness replay (recorded wall)",
    )


def simulate_in_order_work(
    events: Sequence[TraceEvent],
    *,
    charge_orch: bool = False,
) -> ScheduleResult:
    """Work-serial denominator for M1a+ speedups (matched unit costs)."""
    ordered = sorted(events, key=lambda event: event.harness_order_index)
    time_ns = 0
    for event in ordered:
        time_ns += _unit_cost_ns(event, charge_orch=charge_orch)
    makespan = max(time_ns, 1)
    return ScheduleResult(
        model="M0_work",
        tier="work_serial",
        makespan_ns=makespan,
        baseline_makespan_ns=makespan,
        speedup=1.0,
        max_in_flight=1,
        width=1,
        notes="in-order work schedule (M1a+ speedup denominator)",
    )


def _list_scheduling(
    graph: DependenceGraph,
    *,
    model: str,
    width: int | None,
    charge_orch: bool,
    breakable: frozenset[str],
    misprediction_penalty_ns: int = 0,
    misprediction_rate: float = 0.0,
    rate_limit_cap: int | None = None,
    penalty_variant: str | None = None,
    baseline_makespan_ns: int,
) -> ScheduleResult:
    effective_width = width
    if rate_limit_cap is not None:
        if effective_width is None:
            effective_width = rate_limit_cap
        else:
            effective_width = min(effective_width, rate_limit_cap)

    remaining_preds: dict[int, set[int]] = {}
    binding_edges: dict[int, list] = {seq: [] for seq in graph.events}
    for edge in graph.edges:
        if edge.edge_class in breakable:
            continue
        binding_edges[edge.dst_seq].append(edge)
        remaining_preds.setdefault(edge.dst_seq, set()).add(edge.src_seq)
    for seq in graph.events:
        remaining_preds.setdefault(seq, set())

    ready = sorted(seq for seq, preds in remaining_preds.items() if not preds)
    in_flight: list[tuple[int, int]] = []
    now = 0
    done_nodes: set[int] = set()
    scheduled: set[int] = set()
    max_in_flight = 0
    speculative_tax = 0
    event_count = len(graph.events)
    # Contract: every binding edge class must be outside breakable.
    for seq, edges in binding_edges.items():
        for edge in edges:
            if edge.edge_class in breakable:
                raise AssertionError(
                    f"{model} contract: attempted to bind breakable class "
                    f"{edge.edge_class} on {edge.src_seq}->{edge.dst_seq}"
                )

    while len(done_nodes) < event_count:
        slots = (
            effective_width
            if effective_width is not None
            else max(len(ready), 1)
        )
        free = max(slots - len(in_flight), 0)
        launch = [seq for seq in ready[:free] if seq not in scheduled]
        ready = [seq for seq in ready if seq not in launch]
        for seq in launch:
            scheduled.add(seq)
            cost = _unit_cost_ns(graph.events[seq], charge_orch=charge_orch)
            if misprediction_penalty_ns and misprediction_rate > 0:
                speculative_tax += int(misprediction_penalty_ns * misprediction_rate)
            in_flight.append((now + cost, seq))
        max_in_flight = max(max_in_flight, len(in_flight))
        if not in_flight:
            break
        now = min(done for done, _ in in_flight)
        finished = [seq for done, seq in in_flight if done == now]
        in_flight = [(done, seq) for done, seq in in_flight if done != now]
        for seq in finished:
            done_nodes.add(seq)
            for succ in graph.successors(seq):
                if succ in scheduled:
                    continue
                if seq in remaining_preds[succ]:
                    remaining_preds[succ].remove(seq)
                if not remaining_preds[succ]:
                    ready.append(succ)
            ready = sorted(set(ready))

    # Contract: no unfinished node that still waits on a breakable-only edge.
    if len(done_nodes) != event_count:
        raise AssertionError(
            f"{model} schedule stuck: done={len(done_nodes)}/{event_count} "
            f"remaining={ {s: sorted(p) for s, p in remaining_preds.items() if p} }"
        )

    makespan = now + speculative_tax
    speedup = (
        baseline_makespan_ns / makespan if makespan > 0 else float("inf")
    )
    return ScheduleResult(
        model=model,
        tier=graph.tier,
        makespan_ns=makespan,
        baseline_makespan_ns=baseline_makespan_ns,
        speedup=speedup,
        max_in_flight=max_in_flight,
        width=effective_width,
        penalty_variant=penalty_variant,
        notes=f"breakable={sorted(breakable)}",
    )


def simulate_model(
    events: Sequence[TraceEvent],
    model: str,
    tier: str,
    *,
    width: int | None = None,
    penalty_variant: PenaltyVariant = "software",
    misprediction_rate: float = 0.3,
) -> ScheduleResult:
    if model == "M1":
        raise ValueError(
            "unqualified M1 is forbidden after edge taxonomy v2; use M1a or M1b"
        )
    recorded = simulate_in_order(events)
    if model == "M0":
        return recorded

    graph = build_graph(events, tier)  # type: ignore[arg-type]
    protocol = load_protocol()
    frontier = protocol.get("speculation_frontier") or {}
    axis = frontier.get("penalty_axis_ns") or {}
    if axis:
        penalties = {
            "software_ns": int(axis.get("10ms_software", 10_000_000)),
            "praetor_ns": int(axis.get("20us_praetor_tier_d", 20_000)),
        }
    else:
        penalties = protocol["machine_models"]["M4"]["misprediction_penalty"]
    rate_cap = int(protocol["machine_models"]["M5"]["rate_limit_concurrency_cap"])

    work_no_orch = simulate_in_order_work(events, charge_orch=False)
    work_orch = simulate_in_order_work(events, charge_orch=True)
    breakable = breakable_classes_for(model)

    if model == "M1a":
        return _list_scheduling(
            graph,
            model="M1a",
            width=None,
            charge_orch=False,
            breakable=breakable,
            baseline_makespan_ns=work_no_orch.makespan_ns,
        )
    if model == "M1b":
        return _list_scheduling(
            graph,
            model="M1b",
            width=None,
            charge_orch=False,
            breakable=breakable,
            baseline_makespan_ns=work_no_orch.makespan_ns,
        )
    if model == "M2":
        return _list_scheduling(
            graph,
            model="M2",
            width=None,
            charge_orch=True,
            breakable=breakable,
            baseline_makespan_ns=work_orch.makespan_ns,
        )
    if model == "M3":
        return _list_scheduling(
            graph,
            model="M3",
            width=width,
            charge_orch=True,
            breakable=breakable,
            baseline_makespan_ns=work_orch.makespan_ns,
        )
    if model == "M4":
        penalty = (
            int(penalties["software_ns"])
            if penalty_variant == "software"
            else int(penalties["praetor_ns"])
        )
        return _list_scheduling(
            graph,
            model="M4",
            width=width if width is not None else 8,
            charge_orch=True,
            breakable=breakable,
            misprediction_penalty_ns=penalty,
            misprediction_rate=misprediction_rate,
            penalty_variant=penalty_variant,
            baseline_makespan_ns=work_orch.makespan_ns,
        )
    if model == "M5":
        penalty = (
            int(penalties["software_ns"])
            if penalty_variant == "software"
            else int(penalties["praetor_ns"])
        )
        return _list_scheduling(
            graph,
            model="M5",
            width=width if width is not None else 8,
            charge_orch=True,
            breakable=breakable,
            misprediction_penalty_ns=penalty,
            misprediction_rate=misprediction_rate,
            rate_limit_cap=rate_cap,
            penalty_variant=penalty_variant,
            baseline_makespan_ns=work_orch.makespan_ns,
        )
    raise ValueError(f"unknown machine model: {model}")


def simulate_ladder(
    events: Sequence[TraceEvent],
    *,
    tiers: Sequence[str] = ("Tier_S", "Tier_C"),
    widths: Sequence[int | None] | None = None,
) -> list[ScheduleResult]:
    protocol = load_protocol()
    if widths is None:
        widths = list(protocol["machine_models"]["M3"]["widths"])
    results = [simulate_in_order(events)]
    for tier in tiers:
        results.append(simulate_model(events, "M1a", tier))
        results.append(simulate_model(events, "M1b", tier))
        results.append(simulate_model(events, "M2", tier))
        for width in widths:
            results.append(simulate_model(events, "M3", tier, width=width))
        results.append(
            simulate_model(events, "M4", tier, width=8, penalty_variant="software")
        )
        results.append(
            simulate_model(events, "M4", tier, width=8, penalty_variant="praetor")
        )
        results.append(
            simulate_model(events, "M5", tier, width=8, penalty_variant="software")
        )
    return results


def speculation_headroom(
    events: Sequence[TraceEvent], tier: str
) -> dict[str, float]:
    """M1b/M1a speedup ratio — reported, not a claim rung."""
    a = simulate_model(events, "M1a", tier)
    b = simulate_model(events, "M1b", tier)
    ratio = b.speedup / a.speedup if a.speedup > 0 else float("inf")
    return {
        "m1a_speedup": a.speedup,
        "m1b_speedup": b.speedup,
        "headroom": ratio,
    }
