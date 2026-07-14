"""Independent CPU conservation for MCP endpoint and message ledgers."""

from __future__ import annotations

from typing import Any, Iterable

from .accum import McpMessageAccumulator, ScopeObservation
from .taxonomy import McpCategory

DEFAULT_RESIDUAL_LIMIT = 0.15
_MESSAGE_CATEGORIES = tuple(
    category
    for category in McpCategory
    if category not in (McpCategory.SESSION_SETUP, McpCategory.RESIDUAL)
)


def _coverage_summary(accumulator: McpMessageAccumulator) -> dict[str, Any]:
    registrations = list(accumulator.sdk_coverage)
    requested = sum(int(item.get("requested_hooks", 0)) for item in registrations)
    registered = sum(int(item.get("registered_hooks", 0)) for item in registrations)
    unavailable = sorted(
        {
            str(name)
            for item in registrations
            for name in item.get("unavailable_hooks", [])
        }
    )
    return {
        "registrations": registrations,
        "requested_hooks": requested,
        "registered_hooks": registered,
        "coverage_fraction": registered / requested if requested else None,
        "unavailable_hooks": unavailable,
        "category_hooks_enabled": accumulator.category_hooks_enabled,
    }


def _reconcile_cpu(
    *,
    measured_cpu_ns: int,
    category_cpu_ns: dict[str, int],
    residual_limit: float,
) -> dict[str, Any]:
    instrumented_cpu_ns = sum(category_cpu_ns.values())
    residual_cpu_ns = measured_cpu_ns - instrumented_cpu_ns
    reconstructed_cpu_ns = instrumented_cpu_ns + residual_cpu_ns
    conservation_error_ns = measured_cpu_ns - reconstructed_cpu_ns
    over_attributed = residual_cpu_ns < 0
    residual_fraction = (
        residual_cpu_ns / measured_cpu_ns
        if measured_cpu_ns > 0
        else (0.0 if residual_cpu_ns == 0 else -1.0)
    )
    return {
        "measured_cpu_ns": measured_cpu_ns,
        "categories": {
            **category_cpu_ns,
            McpCategory.RESIDUAL.value: residual_cpu_ns,
        },
        "instrumented_cpu_ns": instrumented_cpu_ns,
        "residual_cpu_ns": residual_cpu_ns,
        "residual_fraction": residual_fraction,
        "reconstructed_cpu_ns": reconstructed_cpu_ns,
        "conservation_error_ns": conservation_error_ns,
        "conserved": conservation_error_ns == 0,
        "over_attributed": over_attributed,
        "residual_gate_pass": (
            not over_attributed and residual_fraction <= residual_limit
        ),
        "residual_limit": residual_limit,
    }


def _wait_summary(
    accumulator: McpMessageAccumulator, message_id: str
) -> dict[str, Any]:
    cells = accumulator.waits_for_message(message_id)
    by_kind = {
        kind: {"cpu_ns": totals.cpu_ns, "wall_ns": totals.wall_ns, "count": totals.count}
        for kind, totals in sorted(cells.items())
    }
    return {
        "by_kind": by_kind,
        "cpu_ns": sum(value["cpu_ns"] for value in by_kind.values()),
        "wall_ns": sum(value["wall_ns"] for value in by_kind.values()),
    }


def reconcile_message(
    accumulator: McpMessageAccumulator,
    message_id: str,
    *,
    residual_limit: float = DEFAULT_RESIDUAL_LIMIT,
) -> dict[str, Any]:
    """Conserve one message against its endpoint process-clock delta."""

    mid = str(message_id)
    try:
        observation = accumulator.messages[mid]
    except KeyError as exc:
        raise ValueError(f"message {mid!r} has no process observation") from exc
    cells = accumulator.categories_for_message(mid)
    categories = {
        category.value: cells.get(category.value).cpu_ns
        if category.value in cells
        else 0
        for category in _MESSAGE_CATEGORIES
    }
    result = _reconcile_cpu(
        measured_cpu_ns=observation.process_cpu_ns,
        category_cpu_ns=categories,
        residual_limit=residual_limit,
    )
    result.update(
        {
            "scope": "message",
            "process_role": accumulator.process_role,
            "message_id": mid,
            "wall_ns": observation.wall_ns,
            "start_wall_ns": observation.start_wall_ns,
            "end_wall_ns": observation.end_wall_ns,
            "thread_schedstat_cpu_ns": observation.thread_schedstat_cpu_ns,
            "wait": _wait_summary(accumulator, mid),
            "sdk_coverage": _coverage_summary(accumulator),
        }
    )
    return result


def reconcile_setup(
    accumulator: McpMessageAccumulator,
    *,
    residual_limit: float = DEFAULT_RESIDUAL_LIMIT,
) -> dict[str, Any] | None:
    """Conserve setup separately; it never receives a message identifier."""

    observation = accumulator.setup_observation
    if observation is None:
        return None
    setup_cpu_ns = accumulator.setup_totals().cpu_ns
    result = _reconcile_cpu(
        measured_cpu_ns=observation.process_cpu_ns,
        category_cpu_ns={McpCategory.SESSION_SETUP.value: setup_cpu_ns},
        residual_limit=residual_limit,
    )
    result.update(
        {
            "scope": "setup",
            "process_role": accumulator.process_role,
            "message_id": None,
            "wall_ns": observation.wall_ns,
            "start_wall_ns": observation.start_wall_ns,
            "end_wall_ns": observation.end_wall_ns,
            "thread_schedstat_cpu_ns": observation.thread_schedstat_cpu_ns,
        }
    )
    return result


def _derived_endpoint_observation(
    accumulator: McpMessageAccumulator,
) -> tuple[ScopeObservation, str]:
    if accumulator.endpoint_observation is not None:
        return accumulator.endpoint_observation, "endpoint_process_clock"
    observations: Iterable[ScopeObservation] = accumulator.messages.values()
    values = list(observations)
    if accumulator.setup_observation is not None:
        values.append(accumulator.setup_observation)
    if not values:
        raise ValueError("endpoint has no process observations")
    return (
        ScopeObservation(
            start_wall_ns=min(item.start_wall_ns for item in values),
            end_wall_ns=max(item.end_wall_ns for item in values),
            process_cpu_ns=sum(item.process_cpu_ns for item in values),
            wall_ns=sum(item.wall_ns for item in values),
            metadata={"derived_from_scopes": True},
        ),
        "sum_of_nonoverlapping_scopes",
    )


def reconcile_endpoint(
    accumulator: McpMessageAccumulator,
    *,
    residual_limit: float = DEFAULT_RESIDUAL_LIMIT,
) -> dict[str, Any]:
    """Reconcile a single client or server process without cross-endpoint math."""

    observation, total_source = _derived_endpoint_observation(accumulator)
    category_cpu_ns = {category.value: 0 for category in _MESSAGE_CATEGORIES}
    for (category, _message_id, role), totals in accumulator.by_key.items():
        if role != accumulator.process_role or category == McpCategory.RESIDUAL.value:
            continue
        category_cpu_ns[category] = category_cpu_ns.get(category, 0) + totals.cpu_ns
    category_cpu_ns[McpCategory.SESSION_SETUP.value] = accumulator.setup_totals().cpu_ns
    result = _reconcile_cpu(
        measured_cpu_ns=observation.process_cpu_ns,
        category_cpu_ns=category_cpu_ns,
        residual_limit=residual_limit,
    )
    messages = {
        message_id: reconcile_message(
            accumulator, message_id, residual_limit=residual_limit
        )
        for message_id in sorted(accumulator.messages)
    }
    total_wait_wall_ns = sum(
        totals.wall_ns for totals in accumulator.waits_by_key.values()
    )
    result.update(
        {
            "scope": "endpoint",
            "process_role": accumulator.process_role,
            "mode": accumulator.mode,
            "wall_ns": observation.wall_ns,
            "start_wall_ns": observation.start_wall_ns,
            "end_wall_ns": observation.end_wall_ns,
            "total_source": total_source,
            "messages": messages,
            "setup": reconcile_setup(accumulator, residual_limit=residual_limit),
            "wait_wall_ns": total_wait_wall_ns,
            "sdk_coverage": _coverage_summary(accumulator),
        }
    )
    return result


def reconcile_endpoints(
    *accumulators: McpMessageAccumulator,
    residual_limit: float = DEFAULT_RESIDUAL_LIMIT,
) -> dict[str, dict[str, Any]]:
    """Reconcile client/server ledgers independently.

    There is intentionally no combined CPU-to-wall equation: endpoint process
    CPU may overlap both remote waiting and CPU in the other endpoint.
    """

    result: dict[str, dict[str, Any]] = {}
    for accumulator in accumulators:
        if accumulator.process_role in result:
            raise ValueError(
                f"duplicate endpoint role {accumulator.process_role!r}"
            )
        result[accumulator.process_role] = reconcile_endpoint(
            accumulator, residual_limit=residual_limit
        )
    return result
