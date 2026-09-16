"""Claim-rung selection and bracket aggregation for TLP-01 v2 (two tracks)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Sequence

from apu_characterization.tlp01.bystander import measure_bystander_contention
from apu_characterization.tlp01.contracts import (
    MULTI_TOOL_TASK_CLASSES,
    TraceEvent,
    load_protocol,
)
from apu_characterization.tlp01.labels import (
    DATA_SOURCE_SYNTHETIC,
    finalize_claim_label,
)
from apu_characterization.tlp01.phase_diagram import (
    m5_at_optimal_policy,
    select_frontier_rung,
    sweep_phase_diagram,
)
from apu_characterization.tlp01.replication_floor import (
    assert_no_sparse_in_bands,
    infer_source,
    infer_task_id,
    partition_by_replication_floor,
    required_replication_seeds,
)
from apu_characterization.tlp01.schedule import simulate_model, speculation_headroom


def _median(values: Sequence[float]) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2)


def _band(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"min": float("nan"), "median": float("nan"), "max": float("nan")}
    return {
        "min": float(min(values)),
        "median": _median(values),
        "max": float(max(values)),
    }


def speedup_bands(
    sessions: Sequence[Sequence[TraceEvent]],
    *,
    model: str = "M1a",
    width: int | None = None,
    group_by: str = "task_id",
    min_seeds: int | None = None,
    enforce_replication_floor: bool = True,
) -> dict[str, dict[str, dict[str, float]]]:
    """Compute min/median/max speedup bands.

    When ``enforce_replication_floor`` is True (default), task_ids with fewer
    than G-R required seeds are **excluded** from the returned map (behavior a).
    Callers must route those sessions via ``sparse_descriptive_observations``.
    """
    floor = (
        min_seeds if min_seeds is not None else required_replication_seeds()
    )
    # values + seed sets per group key
    collected: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    seeds_seen: dict[str, set[int]] = defaultdict(set)
    for events in sessions:
        if not events:
            continue
        if group_by == "task_class":
            key = events[0].task_class or "UNKNOWN"
        else:
            key = infer_task_id(events)
        seeds_seen[key].add(int(events[0].seed))
        for tier in ("Tier_S", "Tier_C"):
            result = simulate_model(events, model, tier, width=width)
            collected[key][tier].append(result.speedup)

    bands: dict[str, dict[str, dict[str, float]]] = {}
    for key, tiers in sorted(collected.items()):
        if enforce_replication_floor and len(seeds_seen[key]) < floor:
            continue
        bands[key] = {
            tier: _band(values) for tier, values in sorted(tiers.items())
        }
    return bands


def sparse_descriptive_observations(
    sessions: Sequence[Sequence[TraceEvent]],
    *,
    model: str = "M1a",
) -> list[dict[str, Any]]:
    """Single-seed (or n<floor) observations — never banded."""
    rows: list[dict[str, Any]] = []
    for events in sessions:
        if not events:
            continue
        row: dict[str, Any] = {
            "task_id": infer_task_id(events),
            "source": infer_source(events),
            "seed": int(events[0].seed),
            "session_id": events[0].session_id,
            "banded": False,
            "tag": "sparse: below replication floor, not banded",
            "model": model,
            "speedups": {},
        }
        for tier in ("Tier_S", "Tier_C"):
            result = simulate_model(events, model, tier)
            row["speedups"][tier] = float(result.speedup)
        rows.append(row)
    return rows


def floor_tax_gap(
    sessions: Sequence[Sequence[TraceEvent]],
    *,
    enforce_replication_floor: bool = True,
) -> dict[str, dict[str, float]]:
    floor = required_replication_seeds()
    gaps: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    seeds_seen: dict[str, set[int]] = defaultdict(set)
    for events in sessions:
        if not events:
            continue
        task_id = infer_task_id(events)
        seeds_seen[task_id].add(int(events[0].seed))
        for tier in ("Tier_S", "Tier_C"):
            m1b = simulate_model(events, "M1b", tier).speedup
            m2 = simulate_model(events, "M2", tier).speedup
            gaps[task_id][tier].append(m1b - m2)
    out: dict[str, dict[str, float]] = {}
    for task_id, tiers in sorted(gaps.items()):
        if enforce_replication_floor and len(seeds_seen[task_id]) < floor:
            continue
        out[task_id] = {
            tier: _median(values) for tier, values in sorted(tiers.items())
        }
    return out


def _multi_tool_bands(
    bands: dict[str, dict[str, dict[str, float]]],
) -> dict[str, dict[str, dict[str, float]]]:
    multi = {
        task_id: tiers
        for task_id, tiers in bands.items()
        if task_id in MULTI_TOOL_TASK_CLASSES
        or task_id.startswith(MULTI_TOOL_TASK_CLASSES)
        or any(task_id.startswith(f"{p}-") for p in MULTI_TOOL_TASK_CLASSES)
        or task_id.startswith("MT-")
    }
    if not multi:
        multi = {
            task_id: tiers
            for task_id, tiers in bands.items()
            if any(
                task_id.startswith(prefix) for prefix in MULTI_TOOL_TASK_CLASSES
            )
        }
    return multi


def select_ceiling_rung(
    bands: dict[str, dict[str, dict[str, float]]],
    *,
    data_source: str = DATA_SOURCE_SYNTHETIC,
) -> dict[str, Any]:
    protocol = load_protocol()
    ladder = protocol["claim_ladder"]["ceiling_track"]
    multi = _multi_tool_bands(bands)

    def floor_median(task_tiers: dict[str, dict[str, float]]) -> float:
        return float((task_tiers.get("Tier_C") or {}).get("median") or 0.0)

    multi_floors = [floor_median(tiers) for tiers in multi.values()]
    all_floors = [floor_median(tiers) for tiers in bands.values()]

    if multi_floors and min(multi_floors) >= 3.0:
        key = "rung_1a"
    elif multi_floors and max(multi_floors) >= 2.0 and min(all_floors or [0]) < 2.0:
        key = "rung_2a"
    elif all_floors and max(all_floors) < 1.5:
        key = "rung_3a"
    elif multi_floors and _median(multi_floors) >= 3.0:
        key = "rung_1a"
    elif multi_floors and max(multi_floors) >= 2.0:
        key = "rung_2a"
    else:
        key = "rung_3a"

    entry = ladder[key]
    raw = {
        "track": "ceiling",
        "name": entry["name"],
        "rung": key,
        "language": entry["language"],
        "criterion": entry["criterion"],
        "multi_tool_tier_c_m1_bands": {
            task_id: tiers.get("Tier_C") for task_id, tiers in multi.items()
        },
    }
    return finalize_claim_label(raw, data_source=data_source)


# Back-compat alias used by older tests; maps to ceiling track.
def select_claim_rung(
    bands: dict[str, dict[str, dict[str, float]]],
    *,
    data_source: str = DATA_SOURCE_SYNTHETIC,
) -> dict[str, Any]:
    return select_ceiling_rung(bands, data_source=data_source)


def analyze_experiment(
    sessions: Sequence[Sequence[TraceEvent]],
    *,
    include_frontier: bool = True,
    data_source: str = DATA_SOURCE_SYNTHETIC,
) -> dict[str, Any]:
    partition = partition_by_replication_floor(sessions)
    eligible = partition["eligible_sessions"]
    sparse = partition["sparse_sessions"]
    sparse_ids = [row["task_id"] for row in partition["sparse_task_ids"]]

    m1a_bands = speedup_bands(eligible, model="M1a")
    m1b_bands = speedup_bands(eligible, model="M1b")
    m2_bands = speedup_bands(eligible, model="M2")
    m3_bands = {
        ("inf" if width is None else str(width)): speedup_bands(
            eligible, model="M3", width=width
        )
        for width in (2, 4, 8, None)
    }
    assert_no_sparse_in_bands(m1a_bands, sparse_ids)
    assert_no_sparse_in_bands(m1b_bands, sparse_ids)
    assert_no_sparse_in_bands(m2_bands, sparse_ids)
    for width_bands in m3_bands.values():
        assert_no_sparse_in_bands(width_bands, sparse_ids)

    ceiling = select_ceiling_rung(m1a_bands, data_source=data_source)
    headroom_rows: list[dict[str, Any]] = []
    by_task: dict[str, list] = defaultdict(list)
    for events in eligible:
        by_task[infer_task_id(events)].append(events)
    for task_id, group in sorted(by_task.items()):
        for tier in ("Tier_S", "Tier_C"):
            ratios = [speculation_headroom(ev, tier)["headroom"] for ev in group]
            headroom_rows.append(
                {
                    "task_id": task_id,
                    "tier": tier,
                    "n": len(ratios),
                    "median_headroom": _median(ratios),
                    "min_headroom": float(min(ratios)) if ratios else float("nan"),
                    "max_headroom": float(max(ratios)) if ratios else float("nan"),
                    "verdict": "reported_unverdicted",
                }
            )

    result: dict[str, Any] = {
        "validity_class": "turn_level_parallelism",
        "protocol_version": load_protocol()["protocol_version"],
        "data_source": data_source,
        "headline_form": "S_C_bracket_never_point",
        "replication_floor": {
            "required_seeds": partition["required_seeds"],
            "behavior": partition["behavior"],
            "eligible_task_ids": partition["eligible_task_ids"],
            "sparse_task_ids": partition["sparse_task_ids"],
            "eligible_session_count": len(eligible),
            "sparse_session_count": len(sparse),
        },
        "m1a_speedup_bands": m1a_bands,
        "m1b_speedup_bands": m1b_bands,
        "m2_speedup_bands": m2_bands,
        "m3_speedup_bands": m3_bands,
        "floor_tax_m2_minus_m1b": floor_tax_gap(eligible),
        "speculation_headroom": {
            "definition": "M1b_speedup / M1a_speedup per session; median by task_id×tier",
            "verdict_status": "reported_unverdicted",
            "rows": headroom_rows,
        },
        "sparse_descriptive": {
            "section": "single_seed_descriptive_not_banded",
            "tag": "sparse: below replication floor, not banded",
            "task_ids": partition["sparse_task_ids"],
            "m1a_observations": sparse_descriptive_observations(sparse, model="M1a"),
            "m1b_observations": sparse_descriptive_observations(sparse, model="M1b"),
        },
        "ceiling_claim": ceiling,
        "claim": ceiling,  # back-compat
        "blocked_claims": list(load_protocol()["blocked_claims"]),
        "ownable_firsts": list(load_protocol().get("ownable_firsts") or []),
        "session_count": len(sessions),
        "banded_session_count": len(eligible),
    }
    if include_frontier:
        # Predictor / phase diagram / M5 / bystander: eligible sessions only.
        phase = sweep_phase_diagram(eligible)
        frontier = select_frontier_rung(phase, data_source=data_source)
        bystander = measure_bystander_contention(eligible)
        m5 = m5_at_optimal_policy(eligible, phase)
        result.update(
            {
                "phase_diagram": phase,
                "frontier_claim": frontier,
                "bystander_contention": bystander,
                "m5_at_optimal_policy": m5,
            }
        )
    return result


def bracket_line(tier_s: float, tier_c: float) -> str:
    """Render an honest S/C bracket, never a point."""
    low = min(tier_c, tier_s)
    high = max(tier_c, tier_s)
    return f"[{low:.2f}x, {high:.2f}x] (Tier-C floor … Tier-S ceiling)"
