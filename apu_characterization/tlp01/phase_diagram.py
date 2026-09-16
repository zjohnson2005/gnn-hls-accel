"""M4 speculation-economics phase diagram (TLP-01 v2 flagship)."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from apu_characterization.tlp01.contracts import TraceEvent, load_protocol
from apu_characterization.tlp01.predictor import (
    split_sessions,
    tool_sequence,
    train_markov,
)
from apu_characterization.tlp01.schedule import simulate_model

AGGRESSIVE_POLICIES = frozenset(
    {"always_top1", "breadth_2", "breadth_3", "breadth_5"}
)
CONSERVATIVE_POLICIES = frozenset({"confidence_gated", "no_speculation"})


@dataclass(frozen=True)
class SpecCellResult:
    policy: str
    penalty_key: str
    penalty_ns: int
    accuracy_target: float
    useful_work_ns: int
    wall_ns: int
    effective_throughput: float
    wasted_ns: int
    praetor_tier_d: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "penalty_key": self.penalty_key,
            "penalty_ns": self.penalty_ns,
            "accuracy_target": self.accuracy_target,
            "useful_work_ns": self.useful_work_ns,
            "wall_ns": self.wall_ns,
            "effective_throughput": self.effective_throughput,
            "wasted_ns": self.wasted_ns,
            "praetor_tier_d": self.praetor_tier_d,
        }


def _ranked_with_confidence(
    model: Mapping[str, Counter[str]], history: str, *, top_k: int
) -> list[tuple[str, float]]:
    counts = model.get(history) or model.get("__start__") or Counter()
    total = sum(counts.values()) or 1
    return [
        (tool, count / total) for tool, count in counts.most_common(top_k)
    ]


def _corrupt_to_accuracy(
    ranked: Sequence[tuple[str, float]],
    actual: str,
    *,
    target_accuracy: float,
    rng: random.Random,
) -> list[tuple[str, float]]:
    """Force top-1 hit rate toward target_accuracy while preserving rank shape."""
    if not ranked:
        return [(actual, 1.0)]
    hit = rng.random() < target_accuracy
    if hit:
        rest = [item for item in ranked if item[0] != actual]
        return [(actual, max(ranked[0][1], 0.51))] + rest
    # Miss: ensure actual is not top-1.
    if ranked[0][0] != actual:
        return list(ranked)
    if len(ranked) == 1:
        return [("__wrong__", ranked[0][1]), (actual, 0.0)]
    swapped = list(ranked)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    return swapped


def _select_speculative_set(
    policy: str,
    ranked: Sequence[tuple[str, float]],
    *,
    confidence_threshold: float,
) -> list[str]:
    if policy == "no_speculation" or not ranked:
        return []
    if policy == "always_top1":
        return [ranked[0][0]]
    if policy == "confidence_gated":
        tool, conf = ranked[0]
        return [tool] if conf >= confidence_threshold else []
    if policy.startswith("breadth_"):
        k = int(policy.split("_", 1)[1])
        return [tool for tool, _ in ranked[:k]]
    raise ValueError(f"unknown policy: {policy}")


def _event_durations(events: Sequence[TraceEvent]) -> dict[str, int]:
    """Mean duration per tool name in the session (fallback: median unit)."""
    by_tool: dict[str, list[int]] = defaultdict(list)
    for event in events:
        if event.event_type == "tool_call" and event.tool_name:
            by_tool[event.tool_name].append(max(event.duration_ns, 1))
    return {
        tool: int(sum(vals) / len(vals)) for tool, vals in by_tool.items()
    }


def hit_path_wall_ns(
    *,
    duration_ns: int,
    penalty_ns: int,
    extras: int,
    credit_overlap: bool,
) -> int:
    """Wall contribution on a *correct* speculative prediction.

    GENERAL correctness (not dataset-tuned):
    - Pre-fix bug (`credit_overlap=False`): still charged ``duration_ns`` as
      serial wall on a hit, so overlap credit was structurally absent for every
      policy and every dataset. Comment claimed overlap hid the cost; code did not.
    - Post-fix (`credit_overlap=True`): hit pays only waste for extra wrong
      speculative siblings; the correctly predicted unit is not re-counted as
      serial wall (perfect early-issue overlap credit).

    This is independent of FO/CN synthetic shape and of any penalty threshold.
    """
    waste = penalty_ns * max(extras, 0)
    if credit_overlap:
        return waste
    return duration_ns + waste


def replay_speculation_policy(
    events: Sequence[TraceEvent],
    model: Mapping[str, Counter[str]],
    *,
    policy: str,
    penalty_ns: int,
    accuracy_target: float,
    confidence_threshold: float,
    rng: random.Random,
) -> SpecCellResult:
    seq = tool_sequence(events)
    durations = _event_durations(events)
    default_dur = (
        int(sum(durations.values()) / len(durations)) if durations else 1_000_000
    )
    useful = 0
    wall = 0
    waste = 0
    if len(seq) < 2:
        # Degenerate: fall back to M3-equivalent useful/wall from durations.
        useful = sum(max(e.duration_ns, 1) for e in events)
        wall = max(useful, 1)
        return SpecCellResult(
            policy=policy,
            penalty_key="",
            penalty_ns=penalty_ns,
            accuracy_target=accuracy_target,
            useful_work_ns=useful,
            wall_ns=wall,
            effective_throughput=useful / wall,
            wasted_ns=0,
            praetor_tier_d=False,
        )

    # Primary path always executes every tool once.
    for tool in seq:
        useful += durations.get(tool, default_dur)

    if policy == "no_speculation":
        # Zero point = M3-style serial issue of the tool sequence body.
        wall = useful
        waste = 0
    else:
        wall = 0
        history = "__start__"
        for actual in seq:
            dur = durations.get(actual, default_dur)
            ranked = _ranked_with_confidence(model, history, top_k=5)
            ranked = _corrupt_to_accuracy(
                ranked, actual, target_accuracy=accuracy_target, rng=rng
            )
            speculative = _select_speculative_set(
                policy, ranked, confidence_threshold=confidence_threshold
            )
            if actual in speculative:
                # Hit: see hit_path_wall_ns(credit_overlap=True) — general fix.
                extras = [tool for tool in speculative if tool != actual]
                waste += penalty_ns * len(extras)
                wall += hit_path_wall_ns(
                    duration_ns=dur,
                    penalty_ns=penalty_ns,
                    extras=len(extras),
                    credit_overlap=True,
                )
            elif speculative:
                # Miss: primary still runs; each wrong speculative issue pays penalty.
                waste += penalty_ns * len(speculative)
                wall += dur + penalty_ns * len(speculative)
            else:
                # No speculation issued this step.
                wall += dur
            history = actual
        wall = max(wall, 1)

    return SpecCellResult(
        policy=policy,
        penalty_key="",
        penalty_ns=penalty_ns,
        accuracy_target=accuracy_target,
        useful_work_ns=useful,
        wall_ns=wall,
        effective_throughput=useful / max(wall, 1),
        wasted_ns=waste,
        praetor_tier_d=False,
    )


def _stable_rng(*parts: object) -> random.Random:
    material = "\0".join(str(p) for p in parts).encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    return random.Random(seed)


def sweep_phase_diagram(
    sessions: Sequence[Sequence[TraceEvent]],
    *,
    accuracy_grid: Sequence[float] | None = None,
) -> dict[str, Any]:
    protocol = load_protocol()
    frontier = protocol["speculation_frontier"]
    penalties: dict[str, int] = {
        str(k): int(v) for k, v in frontier["penalty_axis_ns"].items()
    }
    policies: list[str] = list(frontier["policies"])
    threshold = float(frontier["confidence_gate_default_threshold"])
    grid = list(accuracy_grid or frontier["accuracy_grid"])
    praetor_key = str(frontier["praetor_penalty_key"])
    floor_ns = int(protocol["timer_resolution"]["sub_ms_absolute_floor_ns"])

    train, test = split_sessions(sessions)
    models = train_markov(train)
    eval_sessions = test or train

    cells: list[dict[str, Any]] = []
    # Aggregate throughput across sessions per (policy, penalty, accuracy).
    agg: dict[tuple[str, str, float], list[float]] = defaultdict(list)

    for events in eval_sessions:
        if not events:
            continue
        task_class = events[0].task_class or "UNKNOWN"
        model = models.get(task_class) or {}
        rng = _stable_rng(events[0].session_id, "phase")
        for accuracy in grid:
            for penalty_key, penalty_ns in penalties.items():
                quote_penalty = max(penalty_ns, floor_ns) if penalty_ns < 1_000_000 else penalty_ns
                for policy in policies:
                    result = replay_speculation_policy(
                        events,
                        model,
                        policy=policy,
                        penalty_ns=quote_penalty,
                        accuracy_target=float(accuracy),
                        confidence_threshold=threshold,
                        rng=rng,
                    )
                    cell = result.as_dict()
                    cell["penalty_key"] = penalty_key
                    cell["praetor_tier_d"] = penalty_key == praetor_key
                    cell["task_class"] = task_class
                    cell["session_id"] = events[0].session_id
                    cells.append(cell)
                    agg[(policy, penalty_key, float(accuracy))].append(
                        result.effective_throughput
                    )

    # Optimal policy per (penalty, accuracy).
    optimal: list[dict[str, Any]] = []
    region_map: dict[str, dict[str, str]] = defaultdict(dict)
    for accuracy in grid:
        for penalty_key in penalties:
            scored = []
            for policy in policies:
                values = agg.get((policy, penalty_key, float(accuracy))) or []
                mean_tp = sum(values) / len(values) if values else 0.0
                scored.append((mean_tp, policy))
            scored.sort(reverse=True)
            best_tp, best_policy = scored[0]
            optimal.append(
                {
                    "penalty_key": penalty_key,
                    "penalty_ns": penalties[penalty_key],
                    "accuracy_target": float(accuracy),
                    "optimal_policy": best_policy,
                    "effective_throughput": best_tp,
                    "praetor_tier_d": penalty_key == praetor_key,
                    "praetor_label": frontier["praetor_label"]
                    if penalty_key == praetor_key
                    else None,
                }
            )
            region_map[penalty_key][f"{float(accuracy):.1f}"] = best_policy

    # Boundary detection: does optimal policy change across the penalty axis
    # at the measured/natural accuracy band (use 0.6 and neighbors)?
    boundary = _detect_boundary(optimal, policies)
    praetor_region = _praetor_region(optimal, praetor_key)

    # Natural accuracy evaluation (no corruption target — use model as-is ~1.0 proxy via measured).
    natural = evaluate_predictor_natural(eval_sessions, models)

    return {
        "cells": cells,
        "optimal_by_penalty_accuracy": optimal,
        "region_map": dict(region_map),
        "boundary": boundary,
        "praetor_region": praetor_region,
        "natural_predictor_accuracy": natural,
        "penalties_ns": penalties,
        "policies": policies,
        "accuracy_grid": list(grid),
        "praetor_penalty_key": praetor_key,
        "praetor_label": frontier["praetor_label"],
        "pre_registered_hypothesis": frontier["pre_registered_hypothesis"],
        "m3_zero_point_note": "no_speculation policy is the M3 zero point",
    }


def evaluate_predictor_natural(
    sessions: Sequence[Sequence[TraceEvent]],
    models: Mapping[str, Mapping[str, Counter[str]]],
) -> dict[str, float]:
    hits = 0
    total = 0
    for events in sessions:
        if not events:
            continue
        model = models.get(events[0].task_class or "UNKNOWN") or {}
        seq = tool_sequence(events)
        history = "__start__"
        for actual in seq:
            ranked = _ranked_with_confidence(model, history, top_k=1)
            if ranked and ranked[0][0] == actual:
                hits += 1
            total += 1
            history = actual
    return {
        "top1_accuracy": (hits / total) if total else 0.0,
        "n_predictions": float(total),
    }


def _detect_boundary(
    optimal: Sequence[Mapping[str, Any]], policies: Sequence[str]
) -> dict[str, Any]:
    # Group by accuracy; look for policy changes along increasing penalty severity
    # (sort penalties ascending ns = harsher software -> cheaper silicon).
    by_acc: dict[float, list[Mapping[str, Any]]] = defaultdict(list)
    for row in optimal:
        by_acc[float(row["accuracy_target"])].append(row)
    transitions = []
    for accuracy, rows in sorted(by_acc.items()):
        ordered = sorted(rows, key=lambda r: int(r["penalty_ns"]), reverse=True)
        policies_along = [str(r["optimal_policy"]) for r in ordered]
        changed = len(set(policies_along)) > 1
        if changed:
            # Find first transition from conservative-ish to aggressive as penalty drops.
            for left, right in zip(ordered, ordered[1:]):
                if left["optimal_policy"] != right["optimal_policy"]:
                    transitions.append(
                        {
                            "accuracy_target": accuracy,
                            "from_penalty_key": left["penalty_key"],
                            "to_penalty_key": right["penalty_key"],
                            "from_policy": left["optimal_policy"],
                            "to_policy": right["optimal_policy"],
                            "boundary_penalty_ns": right["penalty_ns"],
                        }
                    )
                    break
    exists = len(transitions) >= max(1, len(by_acc) // 3)
    return {
        "exists": exists,
        "transitions": transitions,
        "policy_invariant": not exists and len({r["optimal_policy"] for r in optimal}) == 1,
    }


def _praetor_region(
    optimal: Sequence[Mapping[str, Any]], praetor_key: str
) -> dict[str, Any]:
    praetor_rows = [r for r in optimal if r["penalty_key"] == praetor_key]
    if not praetor_rows:
        return {
            "aggressive": False,
            "policies": [],
            "label": load_protocol()["speculation_frontier"]["praetor_label"],
        }
    policies = [str(r["optimal_policy"]) for r in praetor_rows]
    # Aggressive if majority of accuracy bands prefer breadth/always over gated/none.
    aggressive_frac = sum(1 for p in policies if p in AGGRESSIVE_POLICIES) / len(policies)
    return {
        "aggressive": aggressive_frac >= 0.5,
        "aggressive_fraction": aggressive_frac,
        "policies": policies,
        "label": load_protocol()["speculation_frontier"]["praetor_label"],
        "tier": "D",
    }


def select_frontier_rung(
    phase: Mapping[str, Any],
    *,
    data_source: str = "synthetic_smoke",
) -> dict[str, Any]:
    from apu_characterization.tlp01.labels import finalize_claim_label

    protocol = load_protocol()
    track = protocol["claim_ladder"]["frontier_track"]
    boundary = phase.get("boundary") or {}
    praetor = phase.get("praetor_region") or {}
    if boundary.get("policy_invariant"):
        key = "rung_3b"
    elif boundary.get("exists") and praetor.get("aggressive"):
        key = "rung_1b"
    elif boundary.get("exists"):
        key = "rung_2b"
    else:
        key = "rung_3b"
    entry = track[key]
    raw = {
        "track": "frontier",
        "rung": key,
        "name": entry["name"],
        "language": entry["language"],
        "criterion": entry["criterion"],
        "boundary_exists": bool(boundary.get("exists")),
        "praetor_aggressive": bool(praetor.get("aggressive")),
        "praetor_label": praetor.get("label"),
    }
    return finalize_claim_label(raw, data_source=data_source)


def m5_at_optimal_policy(
    sessions: Sequence[Sequence[TraceEvent]],
    phase: Mapping[str, Any],
    *,
    tier: str = "Tier_C",
) -> dict[str, Any]:
    """Evaluate M5 at the optimal policy implied per penalty regime (v2 Step 1)."""
    protocol = load_protocol()
    praetor_key = protocol["speculation_frontier"]["praetor_penalty_key"]
    # Use natural-accuracy optimal policies along the penalty axis.
    natural_acc = float(
        (phase.get("natural_predictor_accuracy") or {}).get("top1_accuracy") or 0.6
    )
    grid = phase.get("accuracy_grid") or [0.6]
    nearest = min(grid, key=lambda a: abs(float(a) - natural_acc))
    per_penalty = {}
    for row in phase.get("optimal_by_penalty_accuracy") or []:
        if float(row["accuracy_target"]) != float(nearest):
            continue
        # M5 speedup band under Tier-C with width capped by rate limit.
        speedups = []
        for events in sessions:
            if not events:
                continue
            # Anchor: M5 schedule still uses width/rate-limit; policy choice
            # modulates misprediction rate proxy.
            mis_rate = 0.1 if row["optimal_policy"] in AGGRESSIVE_POLICIES else 0.35
            result = simulate_model(
                events,
                "M5",
                tier,
                width=8,
                penalty_variant="praetor"
                if row["penalty_key"] == praetor_key
                else "software",
                misprediction_rate=mis_rate,
            )
            speedups.append(result.speedup)
        per_penalty[row["penalty_key"]] = {
            "optimal_policy": row["optimal_policy"],
            "m5_speedup_median": (
                sorted(speedups)[len(speedups) // 2] if speedups else float("nan")
            ),
            "praetor_tier_d": row["penalty_key"] == praetor_key,
        }
    return {
        "accuracy_band_used": float(nearest),
        "per_penalty": per_penalty,
    }


def render_phase_diagram_markdown(phase: Mapping[str, Any]) -> list[str]:
    """ASCII/markdown phase diagram: rows=accuracy, cols=penalty (log-ish order)."""
    penalties = list((phase.get("penalties_ns") or {}).items())
    penalties.sort(key=lambda kv: kv[1], reverse=True)
    grid = list(phase.get("accuracy_grid") or [])
    region = phase.get("region_map") or {}
    abbrev = {
        "no_speculation": "none",
        "always_top1": "top1",
        "confidence_gated": "gate",
        "breadth_2": "K2",
        "breadth_3": "K3",
        "breadth_5": "K5",
    }
    header = (
        "| top-1 acc \\ penalty | "
        + " | ".join(
            (
                f"{key}†"
                if key == phase.get("praetor_penalty_key")
                else key
            )
            for key, _ in penalties
        )
        + " |"
    )
    sep = "|---|" + "|".join(["---:" for _ in penalties]) + "|"
    lines = [
        "### Speculation-economics phase diagram",
        "",
        "Cells show throughput-maximizing policy. "
        "† = Praetor 20 µs position ("
        + str(phase.get("praetor_label"))
        + "). Boundary location is Tier A/B; only Praetor position is Tier D.",
        "",
        header,
        sep,
    ]
    for accuracy in sorted(grid):
        cells = []
        for key, _ in penalties:
            policy = (region.get(key) or {}).get(f"{float(accuracy):.1f}", "?")
            cells.append(abbrev.get(policy, policy))
        lines.append(f"| {float(accuracy):.1f} | " + " | ".join(cells) + " |")
    lines.append("")
    boundary = phase.get("boundary") or {}
    lines.append(
        f"- Boundary exists: **{'YES' if boundary.get('exists') else 'NO'}**"
    )
    if boundary.get("transitions"):
        t0 = boundary["transitions"][0]
        lines.append(
            f"- Example transition @ acc={t0['accuracy_target']}: "
            f"{t0['from_policy']} @ {t0['from_penalty_key']} → "
            f"{t0['to_policy']} @ {t0['to_penalty_key']}"
        )
    praetor = phase.get("praetor_region") or {}
    lines.append(
        f"- Praetor Tier-D region aggressive: "
        f"**{'YES' if praetor.get('aggressive') else 'NO'}** "
        f"(label: {praetor.get('label')})"
    )
    lines.append("")
    return lines


def write_phase_diagram_artifact(
    phase: Mapping[str, Any], output_dir: Path
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "phase_diagram.json"
    # Drop per-cell session blowup for the summary artifact if huge.
    summary = {
        key: value
        for key, value in phase.items()
        if key != "cells"
    }
    summary["cell_count"] = len(phase.get("cells") or [])
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "phase_diagram.md").write_text(
        "\n".join(render_phase_diagram_markdown(phase)), encoding="utf-8"
    )
    return path
