"""Software scheduler cost models vs measured LangGraph orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from orchestration_engine.characterization.langgraph_react.timing import (
    PRESETS,
    timing_for_preset,
)
from orchestration_engine.characterization.phase1_gate.metrics import (
    orchestration_decisions,
    orchestration_us,
)
from orchestration_engine.characterization.taxonomy import WorkloadProfile


@dataclass
class SchedulerModel:
    name: str
    total_orchestration_us: int
    per_decision_us: float
    notes: str


def _langgraph_measured(profile: WorkloadProfile) -> SchedulerModel:
    total = orchestration_us(profile)
    decisions = max(1, orchestration_decisions(profile))
    return SchedulerModel(
        name="langgraph_measured",
        total_orchestration_us=total,
        per_decision_us=total / decisions,
        notes="From instrumented trace spans (cpu_orchestration bucket).",
    )


def _naive_global_scan(
    preset: str,
    concurrency: int,
    decisions: int,
    calibrated: bool = True,
) -> SchedulerModel:
    """O(live tasks) scan per coordination decision — thread-pool baseline."""
    t = timing_for_preset(preset, calibrated=calibrated)
    live = max(1, concurrency)
    per = (
        t.orchestration_per_step_us
        + t.orchestration_live_task_penalty_us * live
        + 8 * live  # explicit scan penalty beyond LangGraph model
    )
    total = int(per * decisions)
    return SchedulerModel(
        name="naive_global_scan",
        total_orchestration_us=total,
        per_decision_us=per,
        notes=f"O(N) scan with N={live} live tasks per decision.",
    )


def hardware_scatter_us(
    preset: str,
    decisions: int,
    avg_out_degree: float,
    *,
    calibrated: bool = True,
    batch_width: int = 1,
) -> int:
    """Microseconds for O(out-degree) scatter; optional pipelined batching."""
    t = timing_for_preset(preset, calibrated=calibrated)
    if batch_width <= 1:
        edge_cost = avg_out_degree
    else:
        edge_cost = (avg_out_degree + batch_width - 1) // batch_width
    per = t.orchestration_per_step_us + int(t.orchestration_live_task_penalty_us * edge_cost)
    return int(per * decisions)


def optimized_software_us(measured_us: int, speedup: float) -> int:
    return int(measured_us / speedup)


def _hardware_scatter_model(
    preset: str,
    decisions: int,
    avg_out_degree: float,
    calibrated: bool = True,
    batch_width: int = 1,
) -> SchedulerModel:
    """O(out-degree) scatter per completion — proposed engine target."""
    total = hardware_scatter_us(
        preset, decisions, avg_out_degree, calibrated=calibrated, batch_width=batch_width
    )
    per = total / max(1, decisions)
    label = "hardware_scatter_o_out_degree"
    if batch_width > 1:
        label = f"hardware_scatter_batch_w{batch_width}"
    return SchedulerModel(
        name=label,
        total_orchestration_us=total,
        per_decision_us=per,
        notes=f"O(out-degree) avg={avg_out_degree:.1f}, batch_width={batch_width}.",
    )


def _optimized_software(measured: SchedulerModel, speedup: float, label: str) -> SchedulerModel:
    total = optimized_software_us(measured.total_orchestration_us, speedup)
    return SchedulerModel(
        name=label,
        total_orchestration_us=total,
        per_decision_us=measured.per_decision_us / speedup,
        notes=f"LangGraph cost / {speedup:.0f}x (literature-style optimized scheduler).",
    )


def compare_schedulers(
    profile: WorkloadProfile,
    preset: str,
    *,
    avg_out_degree: float = 1.5,
    calibrated: bool = True,
) -> list[SchedulerModel]:
    measured = _langgraph_measured(profile)
    decisions = max(1, orchestration_decisions(profile))
    conc = max(1, profile.concurrency)
    return [
        measured,
        _naive_global_scan(preset, conc, decisions, calibrated=calibrated),
        _hardware_scatter_model(preset, decisions, avg_out_degree, calibrated=calibrated),
        _optimized_software(measured, 4.0, "optimized_software_4x"),
        _optimized_software(measured, 15.0, "optimized_software_15x"),
    ]
