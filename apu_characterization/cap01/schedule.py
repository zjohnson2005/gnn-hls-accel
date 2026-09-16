"""P2-measured serial matrix sizing for CAP-01 v2."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def estimate_matrix_hours(
    protocol: Mapping[str, Any],
    *,
    setup_ms: float,
    cooldown_ms: float,
    tasks_per_domain: Mapping[str, int] | None = None,
    drop_off_tier_domains: Sequence[str] = (),
) -> dict[str, Any]:
    if setup_ms < 0 or cooldown_ms < 0:
        raise ValueError("setup and cooldown measurements cannot be negative")
    domains = protocol["corpus"]["domains"]
    task_counts = dict(
        tasks_per_domain
        or {
            domain: int(protocol["corpus"]["tasks_per_domain"])
            for domain in domains
        }
    )
    if set(task_counts) != set(domains):
        raise ValueError("task counts must cover every protocol domain exactly")
    if any(int(value) < 1 for value in task_counts.values()):
        raise ValueError("every domain must contain at least one task")
    dropped = set(drop_off_tier_domains)
    unknown = dropped - set(domains)
    if unknown:
        raise ValueError(f"unknown domains in descoping request: {sorted(unknown)}")

    scales = len(protocol["latency_backend"]["median_scales_ms"])
    seeds = len(protocol["matrix"]["seeds"])
    harnesses = len(protocol["matrix"]["harnesses"])
    budgets = [int(value) for value in protocol["matrix"]["wall_budgets_ms"]]
    primary_tiers = {
        domain: int(value)
        for domain, value in protocol["matrix"]["domain_primary_tiers_ms"].items()
    }
    by_tier_ms = {str(budget): 0.0 for budget in budgets}
    by_domain_ms: dict[str, float] = {}
    for domain in domains:
        domain_total = 0.0
        for budget in budgets:
            if domain in dropped and budget != primary_tiers[domain]:
                continue
            per_task_ms = budget + setup_ms + cooldown_ms
            cell_ms = (
                per_task_ms
                * int(task_counts[domain])
                * scales
                * seeds
                * harnesses
            )
            by_tier_ms[str(budget)] += cell_ms
            domain_total += cell_ms
        by_domain_ms[domain] = domain_total
    total_ms = sum(by_tier_ms.values())
    return {
        "formula": (
            "sum((tier_budget_ms + measured_setup_ms + measured_cooldown_ms) * "
            "tasks_per_cell) over domain, scale, tier, seed, harness"
        ),
        "measured_setup_ms": setup_ms,
        "measured_cooldown_ms": cooldown_ms,
        "tasks_per_domain": task_counts,
        "drop_off_tier_domains": sorted(dropped),
        "serial_hours_by_tier": {
            tier: value / 3_600_000.0 for tier, value in by_tier_ms.items()
        },
        "serial_hours_by_domain": {
            domain: value / 3_600_000.0 for domain, value in by_domain_ms.items()
        },
        "serial_hours_total": total_ms / 3_600_000.0,
        "primary_cells_preserved": True,
        "positive_controls_preserved": True,
    }
