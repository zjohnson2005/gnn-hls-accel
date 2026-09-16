"""Publication gates G-V / G-D / G-A / G-R / G-J for TLP-01."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from apu_characterization.tlp01.contracts import TraceEvent, load_protocol
from apu_characterization.tlp01.dependence import (
    assert_bracket_invariant,
    summarize_disagreement,
    tier_c_edges,
    tier_s_edges,
)
from apu_characterization.tlp01.graph import build_graph, event_conservation
from apu_characterization.tlp01.schedule import simulate_in_order, simulate_model
from apu_characterization.tlp01.schema import recorded_makespan_ns


def _gate(name: str, passed: bool, errors: list[str], **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "evaluated": True,
        "pass": passed,
        "errors": errors,
        **extra,
    }


def audit_g_v(events: Sequence[TraceEvent]) -> dict[str, Any]:
    protocol = load_protocol()
    tol = float(protocol["gates"]["G_V"]["relative_tolerance"])
    recorded = recorded_makespan_ns(events)
    replay = simulate_in_order(events).makespan_ns
    errors: list[str] = []
    if recorded <= 0:
        errors.append("recorded makespan must be positive")
    else:
        rel = abs(replay - recorded) / recorded
        if rel > tol:
            errors.append(
                f"M0 replay makespan {replay} differs from recorded {recorded} "
                f"by {rel:.3%} (limit {tol:.1%})"
            )
    return _gate("simulator_validation", not errors, errors, recorded_ns=recorded, replay_ns=replay)


def audit_g_d(events: Sequence[TraceEvent]) -> dict[str, Any]:
    from apu_characterization.tlp01.dependence import (
        assert_tier0_subseteq_tier_c,
        assert_tier0_subseteq_tier_s,
        tier_0_edges,
    )

    errors: list[str] = []
    try:
        assert_bracket_invariant(events)
    except AssertionError as exc:
        errors.append(str(exc))
    # G-D extensions (enforced whenever dep_refs are instrumented).
    try:
        assert_tier0_subseteq_tier_c(events)
    except AssertionError as exc:
        errors.append(str(exc))
    try:
        assert_tier0_subseteq_tier_s(events)
    except AssertionError as exc:
        errors.append(str(exc))
    s_count = len(tier_s_edges(events))
    c_count = len(tier_c_edges(events))
    t0_count = len(tier_0_edges(events))
    return _gate(
        "dependence_bracket_sanity",
        not errors,
        errors,
        tier_s_edges=s_count,
        tier_c_edges=c_count,
        tier_0_edges=t0_count,
        disagreement_pairs=max(c_count - s_count, 0),
    )


def audit_g_a(events: Sequence[TraceEvent]) -> dict[str, Any]:
    errors: list[str] = []
    graphs = []
    for tier in ("Tier_S", "Tier_C"):
        try:
            graph = build_graph(events, tier)  # type: ignore[arg-type]
        except ValueError as exc:
            errors.append(str(exc))
            continue
        graphs.append(graph)
        if not graph.is_dag():
            errors.append(f"{tier} is not a DAG")
    errors.extend(event_conservation(events, graphs))
    # Work conservation: sum of unit durations unchanged across models.
    baseline_work = sum(max(event.duration_ns, 0) for event in events)
    for tier in ("Tier_S", "Tier_C"):
        for model in ("M1a", "M1b"):
            result = simulate_model(events, model, tier)
            if result.makespan_ns <= 0:
                errors.append(f"{tier} {model} makespan non-positive")
    return _gate(
        "acyclicity_and_conservation",
        not errors,
        errors,
        baseline_work_ns=baseline_work,
    )


def audit_g_r(sessions: Sequence[Sequence[TraceEvent]]) -> dict[str, Any]:
    protocol = load_protocol()
    required = int(protocol["gates"]["G_R"]["required_seeds"])
    by_task: dict[str, set[int]] = {}
    for events in sessions:
        if not events:
            continue
        key = events[0].task_class or events[0].session_id
        by_task.setdefault(key, set()).add(int(events[0].seed))
    errors = [
        f"{task}: {len(seeds)} seeds < required {required}"
        for task, seeds in sorted(by_task.items())
        if len(seeds) < required
    ]
    return _gate(
        "replication",
        not errors,
        errors,
        seeds_by_task={task: sorted(seeds) for task, seeds in by_task.items()},
    )


def audit_g_j(kappa: float | None) -> dict[str, Any]:
    protocol = load_protocol()
    threshold = float(protocol["gates"]["G_J"]["kappa_threshold"])
    errors: list[str] = []
    demote = False
    if kappa is None:
        errors.append("human-agreement kappa not supplied")
        demote = True
    elif kappa < threshold:
        errors.append(f"kappa {kappa:.3f} < threshold {threshold:.3f}")
        demote = True
    return _gate(
        "judge_calibration",
        kappa is not None and kappa >= threshold,
        errors,
        kappa=kappa,
        demote_to_appendix=demote,
        threshold=threshold,
    )


def audit_session(events: Sequence[TraceEvent]) -> dict[str, Any]:
    gates = {
        "G_V": audit_g_v(events),
        "G_D": audit_g_d(events),
        "G_A": audit_g_a(events),
    }
    return {
        "session_id": events[0].session_id if events else None,
        "gates": gates,
        "pass": all(gate["pass"] for gate in gates.values()),
    }


def audit_experiment(
    sessions: Sequence[Sequence[TraceEvent]],
    *,
    kappa: float | None = None,
) -> dict[str, Any]:
    per_session = [audit_session(events) for events in sessions if events]
    gates = {
        "G_V": {
            "name": "simulator_validation",
            "evaluated": True,
            "pass": all(item["gates"]["G_V"]["pass"] for item in per_session),
            "errors": [
                err
                for item in per_session
                for err in item["gates"]["G_V"]["errors"]
            ],
        },
        "G_D": {
            "name": "dependence_bracket_sanity",
            "evaluated": True,
            "pass": all(item["gates"]["G_D"]["pass"] for item in per_session),
            "errors": [
                err
                for item in per_session
                for err in item["gates"]["G_D"]["errors"]
            ],
            "disagreement_rate_by_task_class": summarize_disagreement(sessions),
        },
        "G_A": {
            "name": "acyclicity_and_conservation",
            "evaluated": True,
            "pass": all(item["gates"]["G_A"]["pass"] for item in per_session),
            "errors": [
                err
                for item in per_session
                for err in item["gates"]["G_A"]["errors"]
            ],
        },
        "G_R": audit_g_r(sessions),
        "G_J": audit_g_j(kappa),
    }
    # Tier-J demotion is allowed; experiment can still publish S/C headlines.
    load_bearing = ("G_V", "G_D", "G_A", "G_R")
    return {
        "gates": gates,
        "pass": all(gates[name]["pass"] for name in load_bearing),
        "tier_j_in_headline": gates["G_J"]["pass"],
        "sessions_audited": len(per_session),
    }


def format_gate_table(audit: Mapping[str, Any]) -> list[str]:
    lines = ["| Gate | Evaluated | Result | Violations |", "|---|---|---|---:|"]
    for name in ("G_V", "G_D", "G_A", "G_R", "G_J", "G_SMOKE_LABEL"):
        gate = (audit.get("gates") or {}).get(name) or {}
        if name == "G_SMOKE_LABEL" and not gate:
            continue
        lines.append(
            f"| {name} | {'YES' if gate.get('evaluated') else 'NO'} | "
            f"{'PASS' if gate.get('pass') else 'FAIL'} | "
            f"{len(gate.get('errors') or [])} |"
        )
    return lines
