"""Disaggregation analysis — publishable breakdown of the CPU-side bucket."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .taxonomy import (
    ACCELERABLE_CPU_BUCKETS,
    BUCKET_TO_CPU_LABEL,
    CPU_TOOL_BUCKETS,
    COORDINATION_BUCKET,
    Bucket,
    WorkloadProfile,
)


def _pct(num: float, denom: float) -> float:
    if denom <= 0:
        return 0.0
    return 100.0 * num / denom


@dataclass
class DisaggregationReport:
    workload_name: str
    concurrency: int

    e2e_us: int
    gpu_inference_us: int
    cpu_tool_phase_us: int

    bucket_us: dict[str, int]
    bucket_pct_of_e2e: dict[str, float]
    bucket_pct_of_cpu_tool: dict[str, float]

    io_wait_us: int
    accelerable_cpu_us: int
    orchestration_us: int

    orchestration_pct_of_cpu_tool: float
    orchestration_pct_of_accelerable_cpu: float
    orchestration_pct_of_e2e: float
    cpu_tool_pct_of_e2e: float
    accelerable_cpu_pct_of_e2e: float

    gt_style_cpu_tool_pct_of_e2e: float
    aggregate_cpu_us: int
    aggregate_orchestration_us: int
    aggregate_orchestration_pct_of_accelerable: float
    headline: str
    meta: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workload_name": self.workload_name,
            "concurrency": self.concurrency,
            "e2e_us": self.e2e_us,
            "gpu_inference_us": self.gpu_inference_us,
            "cpu_tool_phase_us": self.cpu_tool_phase_us,
            "bucket_us": self.bucket_us,
            "bucket_pct_of_e2e": self.bucket_pct_of_e2e,
            "bucket_pct_of_cpu_tool": self.bucket_pct_of_cpu_tool,
            "io_wait_us": self.io_wait_us,
            "accelerable_cpu_us": self.accelerable_cpu_us,
            "orchestration_us": self.orchestration_us,
            "orchestration_pct_of_cpu_tool": round(self.orchestration_pct_of_cpu_tool, 2),
            "orchestration_pct_of_accelerable_cpu": round(
                self.orchestration_pct_of_accelerable_cpu, 2
            ),
            "orchestration_pct_of_e2e": round(self.orchestration_pct_of_e2e, 2),
            "cpu_tool_pct_of_e2e": round(self.cpu_tool_pct_of_e2e, 2),
            "accelerable_cpu_pct_of_e2e": round(self.accelerable_cpu_pct_of_e2e, 2),
            "gt_style_cpu_tool_pct_of_e2e": round(self.gt_style_cpu_tool_pct_of_e2e, 2),
            "aggregate_cpu_us": self.aggregate_cpu_us,
            "aggregate_orchestration_us": self.aggregate_orchestration_us,
            "aggregate_orchestration_pct_of_accelerable": round(
                self.aggregate_orchestration_pct_of_accelerable, 2
            ),
            "headline": self.headline,
            "meta": self.meta,
        }


def analyze_profile(profile: WorkloadProfile) -> DisaggregationReport:
    totals = profile.bucket_totals_us()
    agg_total = profile.total_us()
    conc = max(1, profile.concurrency)
    gpu = totals[Bucket.GPU_INFERENCE]
    cpu_tool = profile.cpu_tool_phase_us()
    io_wait = totals[Bucket.CPU_IO_WAIT]
    orch = totals[COORDINATION_BUCKET]
    accelerable = sum(totals[b] for b in ACCELERABLE_CPU_BUCKETS)

    # Per-agent equivalent E2E denominator (symmetric agents). Avoids broken GT ratios
    # when concurrent traces use staggered simulated timestamps.
    if conc <= 1:
        e2e_denom = agg_total if agg_total > 0 else profile.e2e_us()
    else:
        e2e_denom = max(1, agg_total // conc)

    wall_e2e = profile.e2e_us()

    bucket_us = {}
    bucket_pct_e2e = {}
    bucket_pct_cpu = {}
    for b in Bucket:
        key = b.value
        bucket_us[key] = totals[b]
        per_agent_bucket = totals[b] // conc if conc > 1 else totals[b]
        bucket_pct_e2e[key] = round(_pct(per_agent_bucket, e2e_denom), 3)
    for b in CPU_TOOL_BUCKETS:
        bucket_pct_cpu[b.value] = round(_pct(totals[b], cpu_tool), 3)

    agg_orch = orch
    agg_accel = accelerable
    agg_orch_pct = _pct(agg_orch, agg_accel)

    orch_pct_accel = _pct(orch, accelerable)
    orch_pct_cpu_tool = _pct(orch, cpu_tool)
    cpu_tool_pct_e2e = _pct(cpu_tool, agg_total) if conc > 1 else _pct(cpu_tool, e2e_denom)
    gpu_pct_e2e = _pct(gpu, agg_total) if conc > 1 else _pct(gpu, e2e_denom)
    orch_pct_e2e = _pct(orch // conc if conc > 1 else orch, e2e_denom)
    accel_pct_e2e = _pct(accelerable // conc if conc > 1 else accelerable, e2e_denom)

    headline = (
        f"Coordination is {orch_pct_accel:.1f}% of hardware-amenable CPU time "
        f"(after removing I/O wait)."
    )
    if conc <= 1:
        headline += f" Per-agent orchestration is {orch_pct_e2e:.2f}% of E2E."
    else:
        headline += (
            f" Per-agent-equivalent CPU tool / E2E is {cpu_tool_pct_e2e:.1f}%. "
            f"At concurrency={conc}, aggregate coordination is {agg_orch_pct:.1f}% "
            f"of aggregate accelerable CPU ({agg_orch:,} us of {agg_accel:,} us)."
        )
    if orch_pct_accel < 5.0:
        headline += " WARNING: coordination slice may be too small to justify silicon."
    elif orch_pct_accel >= 15.0:
        headline += " Coordination is a sizeable, non-rounding-error slice."

    if profile.meta.get("source", "").lower().find("example") >= 0 or profile.meta.get(
        "source", ""
    ).lower().find("manual") >= 0:
        headline = (
            "[FORMAT DEMO — not publishable] This trace validates JSON import only. "
            + headline
        )

    return DisaggregationReport(
        workload_name=profile.name,
        concurrency=profile.concurrency,
        e2e_us=wall_e2e,
        gpu_inference_us=gpu,
        cpu_tool_phase_us=cpu_tool,
        bucket_us=bucket_us,
        bucket_pct_of_e2e=bucket_pct_e2e,
        bucket_pct_of_cpu_tool=bucket_pct_cpu,
        io_wait_us=io_wait,
        accelerable_cpu_us=accelerable,
        orchestration_us=orch,
        orchestration_pct_of_cpu_tool=orch_pct_cpu_tool,
        orchestration_pct_of_accelerable_cpu=orch_pct_accel,
        orchestration_pct_of_e2e=orch_pct_e2e,
        cpu_tool_pct_of_e2e=cpu_tool_pct_e2e,
        accelerable_cpu_pct_of_e2e=accel_pct_e2e,
        gt_style_cpu_tool_pct_of_e2e=cpu_tool_pct_e2e,
        aggregate_cpu_us=agg_total,
        aggregate_orchestration_us=agg_orch,
        aggregate_orchestration_pct_of_accelerable=agg_orch_pct,
        headline=headline,
        meta=dict(profile.meta),
    )


def analyze_many(profiles: list[WorkloadProfile]) -> list[DisaggregationReport]:
    return [analyze_profile(p) for p in profiles]


def format_markdown_table(reports: list[DisaggregationReport]) -> str:
    lines = [
        "| Workload | Concurrency | CPU tool / E2E | I/O wait / CPU tool | "
        "Orch / CPU tool | Orch / (CPU-IO) | Orch / E2E (per-agent) |",
        "|----------|-------------|----------------|---------------------|"
        "-----------------|------------------|------------|",
    ]
    for r in reports:
        io_pct = _pct(r.io_wait_us, r.cpu_tool_phase_us)
        lines.append(
            f"| {r.workload_name} | {r.concurrency} | "
            f"{r.cpu_tool_pct_of_e2e:.1f}% | {io_pct:.1f}% | "
            f"{r.orchestration_pct_of_cpu_tool:.3f}% | "
            f"{r.orchestration_pct_of_accelerable_cpu:.1f}% | "
            f"{r.orchestration_pct_of_e2e:.2f}% |"
        )
    return "\n".join(lines)


def format_publishable_summary(report: DisaggregationReport) -> str:
    lines = [
        f"# Disaggregation: {report.workload_name}",
        "",
        f"**Concurrency:** {report.concurrency}",
        "",
        "## GT/Intel-style headline",
        "",
    ]
    if report.concurrency > 1:
        lines.append(
            f"- Per-agent-equivalent CPU tool / E2E: **{report.cpu_tool_pct_of_e2e:.1f}%** "
            f"(use this for GT comparison, not wall-clock batch time)"
        )
    else:
        lines.append(
            f"- CPU-side tool processing: **{report.cpu_tool_pct_of_e2e:.1f}%** of end-to-end latency"
        )
    lines.append(
        f"- GPU inference (per-agent equiv.): **{report.bucket_pct_of_e2e.get('gpu_inference', 0):.1f}%** of E2E"
    )
    if report.concurrency > 1:
        lines.extend(
            [
                "",
                "## Datacenter aggregate",
                "",
                f"- Aggregate CPU tool time: **{report.cpu_tool_phase_us:,} us**",
                f"- Aggregate orchestration: **{report.orchestration_us:,} us**",
                f"- Orchestration / accelerable CPU: **{report.orchestration_pct_of_accelerable_cpu:.1f}%**",
                "",
            ]
        )
    lines.extend(
        [
            "",
            "## CPU tool-phase breakdown (% of CPU tool time)",
            "",
            "| Slice | % of CPU tool | us | Accelerable? |",
            "|-------|---------------|-----|--------------|",
        ]
    )
    for b in CPU_TOOL_BUCKETS:
        label = BUCKET_TO_CPU_LABEL[b]
        accel = "No" if b == Bucket.CPU_IO_WAIT else "Partly" if b == Bucket.CPU_STATE else "Yes"
        lines.append(
            f"| {label.value if label else b.value} | "
            f"{report.bucket_pct_of_cpu_tool.get(b.value, 0):.2f}% | "
            f"{report.bucket_us.get(b.value, 0):,} us | {accel} |"
        )

    lines.extend(
        [
            "",
            "## Key numbers (the publishable floor)",
            "",
            f"- I/O wait (unaccelerable): **{_pct(report.io_wait_us, report.cpu_tool_phase_us):.1f}%** "
            f"of CPU tool phase",
            f"- Hardware-amenable CPU (CPU tool - I/O): **{report.accelerable_cpu_pct_of_e2e:.1f}%** of E2E",
            f"- **Orchestration: {report.orchestration_pct_of_accelerable_cpu:.1f}%** of hardware-amenable CPU",
            f"- Orchestration: **{report.orchestration_pct_of_e2e:.1f}%** of E2E",
            "",
            f"## Headline",
            "",
            report.headline,
            "",
        ]
    )
    return "\n".join(lines)
