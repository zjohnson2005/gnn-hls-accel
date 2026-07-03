"""Crossover analysis using measured csynth scatter + Phase 1 software constants."""

import json
from pathlib import Path

from orchestration_engine.phase2_gate.csynth_parser import DEFAULT_CLOCK_MHZ, load_or_parse

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"
GATE_DIR = OE_ROOT / "characterization" / "out" / "gate"

DELIVERY_US = {
    "sw_epoll": 3.5,
    "sw_kernel_bypass": 1.25,
    "hw_pcie": 0.75,
    "hw_cxl": 0.45,
    "hw_on_soc": 0.10,
}


class CrossoverRow(object):
    def __init__(self, baseline, per_completion_us, vs_hw_pcie, vs_hw_on_soc, note):
        self.baseline = baseline
        self.per_completion_us = per_completion_us
        self.vs_hw_pcie = vs_hw_pcie
        self.vs_hw_on_soc = vs_hw_on_soc
        self.note = note


class CrossoverReport(object):
    def __init__(
        self,
        hw_scatter_us_fanout2,
        hw_scatter_cycles_fanout2,
        clock_mhz,
        csynth_source,
        csynth_pending,
        cosim_source,
        cosim_verified,
        rows,
        verdict,
        headline,
    ):
        self.hw_scatter_us_fanout2 = hw_scatter_us_fanout2
        self.hw_scatter_cycles_fanout2 = hw_scatter_cycles_fanout2
        self.clock_mhz = clock_mhz
        self.csynth_source = csynth_source
        self.csynth_pending = csynth_pending
        self.cosim_source = cosim_source
        self.cosim_verified = cosim_verified
        self.rows = rows
        self.verdict = verdict
        self.headline = headline

    def to_dict(self):
        return {
            "hw_scatter_us_fanout2": self.hw_scatter_us_fanout2,
            "hw_scatter_cycles_fanout2": self.hw_scatter_cycles_fanout2,
            "clock_mhz": self.clock_mhz,
            "csynth_source": self.csynth_source,
            "csynth_pending": self.csynth_pending,
            "cosim_source": self.cosim_source,
            "cosim_verified": self.cosim_verified,
            "rows": [
                {
                    "baseline": r.baseline,
                    "per_completion_us": r.per_completion_us,
                    "vs_hw_pcie": r.vs_hw_pcie,
                    "vs_hw_on_soc": r.vs_hw_on_soc,
                    "note": r.note,
                }
                for r in self.rows
            ],
            "verdict": self.verdict,
            "headline": self.headline,
        }


def _load_dispatch_stress():
    path = GATE_DIR / "dispatch_stress.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_cosim_scatter():
    path = OUT_DIR / "cosim_scatter.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_crossover(out_degree=2, batch_width=1):
    csynth = load_or_parse()
    cosim = _load_cosim_scatter()
    stress = _load_dispatch_stress()

    cycles = 1 + (out_degree + batch_width - 1) // batch_width
    cosim_source = None
    cosim_verified = False

    if csynth and csynth.is_measured:
        clock_mhz = csynth.clock_mhz
        csynth_source = csynth.report_path
        csynth_pending = False
    elif csynth:
        clock_mhz = csynth.clock_mhz
        csynth_source = csynth.report_path
        csynth_pending = True
    else:
        clock_mhz = DEFAULT_CLOCK_MHZ
        csynth_source = None
        csynth_pending = True

    if (
        cosim
        and cosim.get("passed")
        and cosim.get("latency_cycles") is not None
        and cosim.get("fan_out", out_degree) == out_degree
    ):
        cycles = int(cosim["latency_cycles"])
        hw_scatter_us = cycles / clock_mhz
        cosim_source = cosim.get("report_path")
        cosim_verified = True
    elif csynth:
        hw_scatter_us = csynth.scatter_us(out_degree, batch_width=batch_width)
    else:
        hw_scatter_us = cycles / clock_mhz

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

    def _row(name, dispatch_us, delivery_key, note):
        total = dispatch_us + DELIVERY_US[delivery_key]
        hw_pcie = total / (hw_scatter_us + DELIVERY_US["hw_pcie"])
        hw_soc = total / (hw_scatter_us + DELIVERY_US["hw_on_soc"])
        return CrossoverRow(name, round(total, 2), round(hw_pcie, 1), round(hw_soc, 1), note)

    rows = [
        _row("LangGraph (deployed)", langgraph, "sw_epoll", "Claim 2: constant factor vs deployed framework"),
        _row("asyncio event (ideal, dispatch only)", asyncio_dispatch, "sw_epoll", "Claim 2: full-path vs ideal event-driven"),
        _row("asyncio + kernel-bypass delivery", asyncio_dispatch, "sw_kernel_bypass", "Strongest software full-path baseline"),
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
    elif cosim_verified:
        verdict = "FULL_PATH_ADVANTAGE"
        headline = (
            "Cosim-verified scatter {0} cycles ({1:.4f} us) + PCIe delivery -> "
            "~{2:.1f}x vs kernel-bypass software."
        ).format(cycles, hw_scatter_us, kb_total / hw_pcie_total)
    elif kb_total / hw_pcie_total < 2.0:
        verdict = "FULL_PATH_NEAR_PARITY"
        headline = (
            "Full-path vs kernel-bypass software is ~{0:.1f}x "
            "(throughput/energy/offload case at PCIe attach; on-SoC retains latency win)."
        ).format(kb_total / hw_pcie_total)
    else:
        verdict = "FULL_PATH_ADVANTAGE"
        headline = (
            "Measured scatter {0:.4f} us + PCIe delivery -> "
            "~{1:.1f}x vs kernel-bypass software."
        ).format(hw_scatter_us, kb_total / hw_pcie_total)

    return CrossoverReport(
        hw_scatter_us_fanout2=round(hw_scatter_us, 4),
        hw_scatter_cycles_fanout2=cycles,
        clock_mhz=round(clock_mhz, 1),
        csynth_source=csynth_source,
        csynth_pending=csynth_pending,
        cosim_source=cosim_source,
        cosim_verified=cosim_verified,
        rows=rows,
        verdict=verdict,
        headline=headline,
    )


def render_markdown(report):
    src = report.csynth_source or "analytic (pending csynth)"
    cycle_note = "cosim-verified" if report.cosim_verified else "csynth/analytic"
    lines = [
        "## Phase 2 crossover (measured scatter + full-path delivery)",
        "",
        "**Verdict:** `{0}`".format(report.verdict),
        "",
        report.headline,
        "",
        "- Hardware scatter (fan-out=2): **{0} cycles** = **{1} us** @ {2} MHz ({3})".format(
            report.hw_scatter_cycles_fanout2,
            report.hw_scatter_us_fanout2,
            report.clock_mhz,
            cycle_note,
        ),
        "- csynth source: `{0}`".format(src),
    ]
    if report.cosim_source:
        lines.append("- cosim source: `{0}`".format(report.cosim_source))
    lines.extend(
        [
            "",
            "| baseline | us/completion | vs engine+PCIe | vs engine+on-SoC |",
            "|----------|---------------|----------------|------------------|",
        ]
    )
    for row in report.rows:
        lines.append(
            "| {0} | {1} | {2}x | {3}x |".format(
                row.baseline, row.per_completion_us, row.vs_hw_pcie, row.vs_hw_on_soc
            )
        )
    lines.extend(
        [
            "",
            "_Scan-class O(N) crossover remains in Phase 1 check 9; this table closes "
            "Claim 2 (constant factor + energy) against event-driven baselines._",
        ]
    )
    return "\n".join(lines)
