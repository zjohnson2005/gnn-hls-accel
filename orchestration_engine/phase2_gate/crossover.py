"""Crossover analysis using measured csynth scatter + Phase 1 software constants."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from orchestration_engine.phase2_gate.csynth_parser import (
    DEFAULT_CLOCK_MHZ,
    load_or_parse,
)

OE_ROOT = Path(__file__).resolve().parents[1]
GATE_DIR = OE_ROOT / "characterization" / "out" / "gate"
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"

DELIVERY_US = {
    "sw_epoll": 3.5,
    "sw_kernel_bypass": 1.25,
    "hw_pcie": 0.75,
    "hw_cxl": 0.45,
    "hw_on_soc": 0.10,
}


@dataclass
class CrossoverRow:
    baseline: str
    per_completion_us: float
    vs_hw_pcie: float
    vs_hw_on_soc: float
    note: str


@dataclass
class CrossoverReport:
    hw_scatter_us_fanout2: float
    hw_scatter_cycles_fanout2: int
    clock_mhz: float
    csynth_source: str | None
    csynth_pending: bool
    rows: list[CrossoverRow]
    verdict: str
    headline: str


def _load_dispatch_stress() -> dict:
    path = GATE_DIR / "dispatch_stress.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_crossover(out_degree: int = 2, batch_width: int = 1) -> CrossoverReport:
    csynth = load_or_parse()
    stress = _load_dispatch_stress()

    if csynth:
        hw_scatter_us = csynth.scatter_us(out_degree, batch_width=batch_width)
        cycles = 1 + (out_degree + batch_width - 1) // batch_width
        clock_mhz = csynth.clock_mhz
        csynth_source = csynth.report_path
        csynth_pending = False
    else:
        cycles = 1 + (out_degree + batch_width - 1) // batch_width
        clock_mhz = DEFAULT_CLOCK_MHZ
        hw_scatter_us = cycles / clock_mhz
        csynth_source = None
        csynth_pending = True

    fp = stress.get("full_path_us_per_completion", {})
    asyncio_dispatch = 1.9
    ev_rows = [
        r
        for r in stress.get("rows", [])
        if r.get("scheduler") == "asyncio_event" and r.get("live_n", 0) >= 100
    ]
    if ev_rows:
        asyncio_dispatch = sum(r["cpu_us_per_decision"] for r in ev_rows) / len(ev_rows)

    langgraph = 1700.0
    lg_rows = [
        r
        for r in stress.get("rows", [])
        if r.get("scheduler") == "langgraph_threads" and r.get("live_n", 0) >= 100
    ]
    if lg_rows:
        langgraph = sum(r["cpu_us_per_decision"] for r in lg_rows) / len(lg_rows)

    def _row(name: str, dispatch_us: float, delivery_key: str, note: str) -> CrossoverRow:
        total = dispatch_us + DELIVERY_US[delivery_key]
        hw_pcie = total / (hw_scatter_us + DELIVERY_US["hw_pcie"])
        hw_soc = total / (hw_scatter_us + DELIVERY_US["hw_on_soc"])
        return CrossoverRow(name, round(total, 2), round(hw_pcie, 1), round(hw_soc, 1), note)

    rows = [
        _row(
            "LangGraph (deployed)",
            langgraph,
            "sw_epoll",
            "Claim 2: constant factor vs deployed framework",
        ),
        _row(
            "asyncio event (ideal, dispatch only)",
            asyncio_dispatch,
            "sw_epoll",
            "Claim 2: full-path vs ideal event-driven",
        ),
        _row(
            "asyncio + kernel-bypass delivery",
            asyncio_dispatch,
            "sw_kernel_bypass",
            "Strongest software full-path baseline",
        ),
    ]

    if fp:
        epoll_total = fp.get("sw_asyncio_epoll", rows[1].per_completion_us)
        kb_total = fp.get("sw_asyncio_kernel_bypass", rows[2].per_completion_us)
        hw_pcie_total = hw_scatter_us + DELIVERY_US["hw_pcie"]
        hw_soc_total = hw_scatter_us + DELIVERY_US["hw_on_soc"]
        rows[1] = CrossoverRow(
            "asyncio + epoll (measured full-path)",
            epoll_total,
            round(epoll_total / hw_pcie_total, 1),
            round(epoll_total / hw_soc_total, 1),
            rows[1].note,
        )
        rows[2] = CrossoverRow(
            "asyncio + kernel-bypass (measured full-path)",
            kb_total,
            round(kb_total / hw_pcie_total, 1),
            round(kb_total / hw_soc_total, 1),
            rows[2].note,
        )

    hw_pcie_total = hw_scatter_us + DELIVERY_US["hw_pcie"]
    kb_total = rows[2].per_completion_us
    if csynth_pending:
        verdict = "PENDING_CSYNTH"
        headline = (
            "Crossover table uses analytic scatter target; run run_hls_scatter.tcl "
            "on the Vitis box and re-run phase2_gate.gate_report."
        )
    elif kb_total / hw_pcie_total < 2.0:
        verdict = "FULL_PATH_NEAR_PARITY"
        headline = (
            f"Full-path vs kernel-bypass software is ~{kb_total / hw_pcie_total:.1f}x "
            "(throughput/energy/offload case at PCIe attach; on-SoC retains latency win)."
        )
    else:
        verdict = "FULL_PATH_ADVANTAGE"
        headline = (
            f"Measured scatter {hw_scatter_us:.4f} µs + PCIe delivery → "
            f"~{kb_total / hw_pcie_total:.1f}x vs kernel-bypass software."
        )

    return CrossoverReport(
        hw_scatter_us_fanout2=round(hw_scatter_us, 4),
        hw_scatter_cycles_fanout2=cycles,
        clock_mhz=round(clock_mhz, 1),
        csynth_source=csynth_source,
        csynth_pending=csynth_pending,
        rows=rows,
        verdict=verdict,
        headline=headline,
    )


def render_markdown(report: CrossoverReport) -> str:
    src = report.csynth_source or "analytic (pending csynth)"
    lines = [
        "## Phase 2 crossover (measured scatter + full-path delivery)",
        "",
        f"**Verdict:** `{report.verdict}`",
        "",
        report.headline,
        "",
        f"- Hardware scatter (fan-out=2): **{report.hw_scatter_cycles_fanout2} cycles** "
        f"= **{report.hw_scatter_us_fanout2} µs** @ {report.clock_mhz} MHz",
        f"- csynth source: `{src}`",
        "",
        "| baseline | µs/completion | vs engine+PCIe | vs engine+on-SoC |",
        "|----------|---------------|----------------|------------------|",
    ]
    for row in report.rows:
        lines.append(
            f"| {row.baseline} | {row.per_completion_us} | {row.vs_hw_pcie}x | "
            f"{row.vs_hw_on_soc}x |"
        )
    lines.extend(
        [
            "",
            "_Scan-class O(N) crossover remains in Phase 1 check 9; this table closes "
            "Claim 2 (constant factor + energy) against event-driven baselines._",
        ]
    )
    return "\n".join(lines)
