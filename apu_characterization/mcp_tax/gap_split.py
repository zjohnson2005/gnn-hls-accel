"""v9 gap-split conservation and pre-registered diffuseness verdicts.

Diffuseness working definition (eight words): cost smeared between named
instrumented regions. Confirm/refute thresholds live in protocol_v1.json and
OPEN_QUESTIONS §4; do not invent a post-hoc call after seeing the split.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .gap_measure import (
    ALL_MECHANISM_KEYS,
    GAP_SYSCALL_ADJACENT,
    GAP_SYSCALL_MEASURED,
    GAP_SYSCALL_RETURN,
    GAP_UNATTRIBUTED,
    NAMED_MECHANISMS,
)

GAP_PARENT_PROVENANCE = "client_call_inter_region_gaps"
GAP_DECOMPOSITION_KEY = "gap_decomposition"

# Canonical mechanism IDs. Legacy a_* aliases accepted on read.
MECHANISM_IDS = ALL_MECHANISM_KEYS

_LEGACY_ALIASES = {
    "a_event_loop": "gap_event_loop",
    "b_observer": "gap_instrumentation",
    "c_gc_allocator": "gap_gc",
    "d_syscall_return": "gap_syscall_return",
}


def _limit(value: float, *, floor: float, fraction: float) -> float:
    return max(float(floor), float(fraction) * float(value))


def normalize_mechanisms(mechanisms: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, amount in mechanisms.items():
        key = _LEGACY_ALIASES.get(str(name), str(name))
        out[key] = out.get(key, 0.0) + float(amount or 0)
    return out


def gap_decomposition_for_message(
    endpoint: Mapping[str, Any], message_id: str
) -> Mapping[str, Any] | None:
    diagnostics = (endpoint.get("message_diagnostics") or {}).get(message_id) or {}
    if not isinstance(diagnostics, Mapping):
        return None
    decomp = diagnostics.get(GAP_DECOMPOSITION_KEY)
    return decomp if isinstance(decomp, Mapping) else None


def evaluate_diffuseness_verdict(
    decomposition: Mapping[str, Any],
    *,
    cfg: Mapping[str, Any],
) -> dict[str, Any]:
    """Return one of the pre-written verdicts: confirmed, refuted, inconclusive.

    v1.5 amendment (OPEN_QUESTIONS): confirm/refute evaluate over named
    mechanisms (a)–(d) only. ``gap_unattributed`` (e) above
    ``unattributed_forces_inconclusive_share`` (default 20%) forces
    inconclusive — a large residual is unmeasured, not concentrated-in-a-
    known-fixable place, and must not trigger ``refuted``.
    """
    verdict_cfg = cfg.get("diffuseness_verdict") or {}
    max_single = float(verdict_cfg.get("confirm_max_single_mechanism_share", 0.50))
    refute_single = float(verdict_cfg.get("refute_single_mechanism_share", 0.50))
    min_mechs = int(verdict_cfg.get("confirm_min_mechanisms", 3))
    min_bounds = int(verdict_cfg.get("confirm_min_boundaries", 2))
    min_share = float(verdict_cfg.get("mechanism_count_min_share", 0.0))
    e_bound = float(verdict_cfg.get("unattributed_forces_inconclusive_share", 0.20))

    parent_ns = float(decomposition.get("parent_cpu_ns") or 0)
    mechanisms = normalize_mechanisms(decomposition.get("mechanisms") or {})
    boundaries = decomposition.get("boundaries") or []
    if not mechanisms or parent_ns <= 0:
        return {
            "verdict": "inconclusive",
            "reason": "missing parent_cpu_ns or mechanisms",
            "parent_cpu_ns": parent_ns,
        }
    if not isinstance(boundaries, Sequence) or isinstance(boundaries, (str, bytes)):
        boundaries = []

    e_ns = float(mechanisms.get(GAP_UNATTRIBUTED, 0) or 0)
    e_share = e_ns / parent_ns
    named_shares = {
        str(name): float(amount) / parent_ns
        for name, amount in mechanisms.items()
        if name in NAMED_MECHANISMS and float(amount or 0) > 0
    }
    all_shares = {
        str(name): float(amount) / parent_ns
        for name, amount in mechanisms.items()
        if float(amount or 0) > 0
    }
    boundary_ids = sorted({str(item) for item in boundaries if str(item)})
    contributing_named = [
        name for name, share in named_shares.items() if share > min_share
    ]

    detail = {
        "parent_cpu_ns": parent_ns,
        "mechanism_shares": dict(sorted(all_shares.items())),
        "named_mechanism_shares": dict(sorted(named_shares.items())),
        "unattributed_share": e_share,
        "boundaries": boundary_ids,
        "contributing_mechanisms": contributing_named,
        "thresholds": {
            "confirm_max_single_mechanism_share": max_single,
            "refute_single_mechanism_share": refute_single,
            "confirm_min_mechanisms": min_mechs,
            "confirm_min_boundaries": min_bounds,
            "unattributed_forces_inconclusive_share": e_bound,
        },
    }

    if e_share > e_bound:
        return {
            "verdict": "inconclusive",
            "reason": (
                f"{GAP_UNATTRIBUTED} holds {100 * e_share:.1f}% of parent gap "
                f"(> {100 * e_bound:.0f}% bound); residual is unmeasured, not a "
                "named mechanism, so confirm/refute cannot fire — large (e) feeds "
                "inconclusive per v1.5 amendment"
            ),
            "dominant_mechanism": GAP_UNATTRIBUTED,
            "dominant_share": e_share,
            **detail,
        }

    if not named_shares:
        return {
            "verdict": "inconclusive",
            "reason": "no positive named mechanism amounts (a)–(d)",
            "dominant_mechanism": None,
            "dominant_share": 0.0,
            **detail,
        }

    dominant_name = max(named_shares, key=named_shares.get)
    dominant_share = named_shares[dominant_name]
    detail["dominant_mechanism"] = dominant_name
    detail["dominant_share"] = dominant_share

    if dominant_share > refute_single:
        return {
            "verdict": "refuted",
            "reason": (
                f"{dominant_name} holds {100 * dominant_share:.1f}% of gap time "
                f"(> {100 * refute_single:.0f}%); concentrated named mechanism is "
                "fixable, not diffuse under 'cost smeared between named "
                "instrumented regions'"
            ),
            **detail,
        }

    if (
        dominant_share <= max_single
        and len(contributing_named) >= min_mechs
        and len(boundary_ids) >= min_bounds
    ):
        return {
            "verdict": "confirmed",
            "reason": (
                f"no named mechanism > {100 * max_single:.0f}% "
                f"({dominant_name}={100 * dominant_share:.1f}%); "
                f"{len(contributing_named)} named mechanisms across "
                f"{len(boundary_ids)} boundaries; "
                f"{GAP_UNATTRIBUTED}={100 * e_share:.1f}% ≤ {100 * e_bound:.0f}%"
            ),
            **detail,
        }

    return {
        "verdict": "inconclusive",
        "reason": (
            "named distribution does not meet confirm criteria and is not "
            "concentrated enough to refute; widen instrumentation or increase "
            "seed n before calling"
        ),
        **detail,
    }


def population_meets_verdict_floor(
    *,
    measured_messages: int,
    seed_count: int,
    cfg: Mapping[str, Any],
) -> bool:
    floor = cfg.get("verdict_min_population") or {}
    min_messages = int(floor.get("min_measured_messages", 20))
    min_seeds = int(floor.get("min_seeds", 3))
    return int(measured_messages) >= min_messages and int(seed_count) >= min_seeds


def classify_with_population_gate(
    decomposition: Mapping[str, Any],
    *,
    cfg: Mapping[str, Any],
    measured_messages: int,
    seed_count: int,
) -> dict[str, Any]:
    """Binding verdict only when population floor holds; else deferred + advisory."""
    advisory = evaluate_diffuseness_verdict(decomposition, cfg=cfg)
    if population_meets_verdict_floor(
        measured_messages=measured_messages, seed_count=seed_count, cfg=cfg
    ):
        return {
            "verdict": advisory["verdict"],
            "binding": True,
            "advisory_only": None,
            **{k: v for k, v in advisory.items() if k != "verdict"},
        }
    return {
        "verdict": "deferred_insufficient_population",
        "binding": False,
        "advisory_only": advisory,
        "population": {
            "measured_messages": int(measured_messages),
            "seed_count": int(seed_count),
            "floor": dict(cfg.get("verdict_min_population") or {}),
        },
        "reason": (
            "diffuseness verdict deferred: need "
            f">={int((cfg.get('verdict_min_population') or {}).get('min_measured_messages', 20))} "
            "measured messages and "
            f">={int((cfg.get('verdict_min_population') or {}).get('min_seeds', 3))} "
            "seeds; WSL seed-0 smoke cannot return a binding verdict"
        ),
    }


def audit_gap_split_conservation(
    endpoint: Mapping[str, Any],
    *,
    cfg: Mapping[str, Any],
    role: str = "client",
    measured_messages: int | None = None,
    seed_count: int = 1,
) -> tuple[list[str], dict[str, Any]]:
    """G7: when a gap decomposition is present, Σ(sub) ≈ parent within G3 slack."""
    errors: list[str] = []
    details: dict[str, Any] = {
        "role": role,
        "messages": [],
        "g7_live": False,
        "evaluated_count": 0,
    }
    messages = endpoint.get("messages") or {}
    if not isinstance(messages, Mapping):
        return errors, details

    floor = float(cfg.get("conservation_floor_ns", 500_000))
    fraction = float(cfg.get("conservation_fraction", 0.05))
    msg_count = (
        int(measured_messages)
        if measured_messages is not None
        else len(messages)
    )

    for message_id in sorted(str(key) for key in messages.keys()):
        decomp = gap_decomposition_for_message(endpoint, message_id)
        if decomp is None:
            continue
        details["g7_live"] = True
        details["evaluated_count"] += 1
        parent_ns = float(decomp.get("parent_cpu_ns") or 0)
        mechanisms = normalize_mechanisms(decomp.get("mechanisms") or {})
        if GAP_UNATTRIBUTED not in mechanisms and mechanisms:
            # Require explicit (e) bucket when any split is present.
            errors.append(
                f"{role} message {message_id} gap_decomposition missing "
                f"{GAP_UNATTRIBUTED}"
            )
        child_sum = sum(float(amount or 0) for amount in mechanisms.values())
        limit = _limit(parent_ns, floor=floor, fraction=fraction)
        error_ns = abs(child_sum - parent_ns)
        classification = classify_with_population_gate(
            decomp,
            cfg=cfg,
            measured_messages=msg_count,
            seed_count=seed_count,
        )
        per_message = {
            "message_id": message_id,
            "parent_cpu_ns": parent_ns,
            "mechanisms_sum_ns": child_sum,
            "conservation_error_ns": error_ns,
            "conservation_limit_ns": limit,
            "mechanisms": mechanisms,
            "diffuseness": classification,
        }
        details["messages"].append(per_message)
        if parent_ns <= 0:
            if child_sum == 0:
                continue
            errors.append(
                f"{role} message {message_id} gap_decomposition has "
                "non-positive parent_cpu_ns with non-zero mechanisms"
            )
            continue
        if error_ns > limit:
            errors.append(
                f"{role} message {message_id} gap split conservation error "
                f"{error_ns:.0f} ns exceeds {limit:.0f} ns "
                f"(Σ mechanisms={child_sum:.0f}, parent={parent_ns:.0f})"
            )
        if float(mechanisms.get(GAP_UNATTRIBUTED, 0)) < 0:
            errors.append(
                f"{role} message {message_id} {GAP_UNATTRIBUTED} is negative"
            )
    return errors, details


def observer_instrumentation_crosscheck(
    throttle_cell: Mapping[str, Any],
    stripped_cell: Mapping[str, Any],
    *,
    cfg: Mapping[str, Any],
) -> dict[str, Any]:
    """Task 3: booked gap_instrumentation must not exceed throttle−stripped bracket."""
    from .analyze import cell_steady_cpu_ns_per_message
    from .gap_measure import GAP_INSTRUMENTATION

    floor = float(cfg.get("conservation_floor_ns", 500_000))
    fraction = float(cfg.get("conservation_fraction", 0.05))
    throttle_ns = float(cell_steady_cpu_ns_per_message(throttle_cell))
    stripped_ns = float(cell_steady_cpu_ns_per_message(stripped_cell))
    bracket = throttle_ns - stripped_ns
    coordinates = throttle_cell.get("coordinates") or {}
    booked_b = 0.0
    for mid, diagnostics in (throttle_cell.get("message_diagnostics") or {}).items():
        if not isinstance(diagnostics, Mapping):
            # cell-level aggregate may nest differently — try provenance path
            continue
        decomp = diagnostics.get(GAP_DECOMPOSITION_KEY) or {}
        mechs = normalize_mechanisms((decomp or {}).get("mechanisms") or {})
        booked_b += float(mechs.get(GAP_INSTRUMENTATION, 0))
    # Prefer per-message medians from cell summary if present
    gap_summary = throttle_cell.get("gap_decomposition_ns_per_message") or {}
    if gap_summary:
        raw_b = gap_summary.get(GAP_INSTRUMENTATION, booked_b)
        if isinstance(raw_b, Mapping):
            booked_b = float(raw_b.get("median", raw_b.get("mean", 0)))
        else:
            booked_b = float(raw_b or 0)

    result: dict[str, Any] = {
        "transport": coordinates.get("transport"),
        "implementation": coordinates.get("implementation"),
        "throttle_ns_per_message": throttle_ns,
        "stripped_ns_per_message": stripped_ns,
        "observer_bracket_delta_ns": bracket,
        "booked_gap_instrumentation_ns": booked_b,
        "flag": None,
        "usable": True,
    }
    if bracket < 0:
        result["usable"] = False
        result["flag"] = "OBSERVER_BRACKET_NEGATIVE"
        result["diagnosis"] = (
            "stripped > throttle; pair unusable for instrumentation cross-check "
            "(stdio-class ghost)"
        )
        return result
    limit = _limit(max(bracket, booked_b), floor=floor, fraction=fraction)
    if booked_b > bracket + limit:
        result["flag"] = "OBSERVER_ATTRIBUTION_SUSPECT"
        result["diagnosis"] = (
            f"booked gap_instrumentation {booked_b:.0f} ns exceeds "
            f"observer bracket {bracket:.0f} ns by more than G3 slack {limit:.0f} ns"
        )
    else:
        result["flag"] = "OBSERVER_ATTRIBUTION_OK"
        result["diagnosis"] = "booked instrumentation within observer bracket"
    return result
