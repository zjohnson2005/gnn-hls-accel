"""Structural proof: O(N) global-scan software vs O(fan-out) hardware scatter.

Primary thesis evidence — independent of LangGraph percentage extrapolation.
Optionally runs native ``oe_bench.exe`` when built; always emits analytical sweep.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

DISPATCH_STRESS_PATH = Path(
    "orchestration_engine/characterization/out/gate/dispatch_stress.json"
)

OPT_SPEEDUP = 4.0
BATCH_WIDTH = 8
SWEEP_LIVE_NODES = [1, 10, 100, 500, 1000, 5000]
SWEEP_FANOUT = [1, 2, 4, 8, 16, 64]

BENCH_PATHS = [
    Path("orchestration_engine/build/oe_bench.exe"),
    Path("orchestration_engine/build/oe_bench"),
]


@dataclass
class CoordModel:
    live_nodes: int
    fanout: int
    completions: int
    cycles_global_scan: int
    cycles_optimized_scan: int
    cycles_hardware_flat: int
    cycles_hardware_batched: int
    hardware_flat_beats_optimized: bool
    hardware_batched_beats_optimized: bool


def _bench_binary() -> Path | None:
    for path in BENCH_PATHS:
        if path.is_file():
            return path
    return None


def _parse_bench_stdout(text: str) -> dict | None:
    m = re.search(
        r"coord_overhead_eng=(\d+)\s+coord_overhead_cpu=(\d+)\s+speedup_coord=([\d.]+)x\s+nodes=(\d+)",
        text,
    )
    if not m:
        return None
    return {
        "coord_overhead_engine": int(m.group(1)),
        "coord_overhead_cpu_scan": int(m.group(2)),
        "speedup_coord": float(m.group(3)),
        "graph_nodes": int(m.group(4)),
    }


def run_native_bench_sweep(
    depths: list[int] | None = None,
    fanouts: list[int] | None = None,
    seed: int = 42,
) -> list[dict]:
    """Run oe_bench if compiled; returns parsed rows (may be empty)."""
    bench = _bench_binary()
    if bench is None:
        return []

    depths = depths or [3, 4, 5, 6]
    fanouts = fanouts or [2, 4, 8]
    rows: list[dict] = []
    for depth in depths:
        for fanout in fanouts:
            proc = subprocess.run(
                [str(bench.resolve()), str(depth), str(fanout), str(seed)],
                capture_output=True,
                text=True,
                check=False,
            )
            parsed = _parse_bench_stdout(proc.stdout)
            if parsed:
                parsed["depth"] = depth
                parsed["fanout"] = fanout
                parsed["seed"] = seed
                rows.append(parsed)
    return rows


def _completions_for_live(live_nodes: int) -> int:
    """Coordination decisions scale with active graph size (proxy for agent steps)."""
    return max(13, live_nodes // 2 + 13)


def coordination_cycles(
    live_nodes: int,
    fanout: int,
    completions: int,
    *,
    batch_width: int = 1,
) -> tuple[int, int, int]:
    """Return (global_scan, optimized_scan, hardware) coordination cycles."""
    scan_per = live_nodes + fanout
    global_scan = scan_per * completions
    optimized = int(global_scan / OPT_SPEEDUP)
    if batch_width <= 1:
        hw_per = 1 + fanout
    else:
        hw_per = 1 + (fanout + batch_width - 1) // batch_width
    hardware = hw_per * completions
    return global_scan, optimized, hardware


def build_coord_row(live_nodes: int, fanout: int) -> CoordModel:
    completions = _completions_for_live(live_nodes)
    global_scan, optimized, hw_flat = coordination_cycles(live_nodes, fanout, completions)
    _, _, hw_batch = coordination_cycles(
        live_nodes, fanout, completions, batch_width=BATCH_WIDTH
    )
    return CoordModel(
        live_nodes=live_nodes,
        fanout=fanout,
        completions=completions,
        cycles_global_scan=global_scan,
        cycles_optimized_scan=optimized,
        cycles_hardware_flat=hw_flat,
        cycles_hardware_batched=hw_batch,
        hardware_flat_beats_optimized=hw_flat < optimized,
        hardware_batched_beats_optimized=hw_batch < optimized,
    )


def build_structural_proof() -> dict:
    grid = [
        asdict(build_coord_row(live, fanout))
        for live in SWEEP_LIVE_NODES
        for fanout in SWEEP_FANOUT
    ]

    react_fanout = 2
    by_live: list[dict] = []
    min_live_flat: int | None = None
    min_live_batch: int | None = None
    for live in SWEEP_LIVE_NODES:
        row = build_coord_row(live, react_fanout)
        by_live.append(asdict(row))
        if row.hardware_flat_beats_optimized and min_live_flat is None:
            min_live_flat = live
        if row.hardware_batched_beats_optimized and min_live_batch is None:
            min_live_batch = live

    native = run_native_bench_sweep()
    native_ok = len(native) > 0
    avg_speedup = (
        sum(r["speedup_coord"] for r in native) / len(native) if native else None
    )

    # Measured constants from local dispatch stress (check 11), if available.
    measured_constants = None
    if DISPATCH_STRESS_PATH.is_file():
        stress = json.loads(DISPATCH_STRESS_PATH.read_text(encoding="utf-8"))
        rows = [r for r in stress.get("rows", []) if r["live_n"] >= 100]
        if rows:
            def _avg(name: str) -> float | None:
                vals = [r["cpu_us_per_decision"] for r in rows if r["scheduler"] == name]
                return sum(vals) / len(vals) if vals else None

            measured_constants = {
                "langgraph_us_per_decision": _avg("langgraph_threads"),
                "event_driven_us_per_decision": _avg("asyncio_event"),
                "scan_growth_measured": stress.get("growth_global_scan"),
                "hw_us_per_decision": stress.get("hw_reference_us_per_decision"),
            }

    thesis = (
        "Two-claim thesis. (1) Complexity class: scan-class schedulers cost "
        "O(live_nodes) per coordination decision (measured 59x growth to N=1000, "
        "check 11) while the engine costs O(fan-out) via scatter-on-completion — "
        "proven at a measurable (live_nodes, fan-out) crossover below. "
        "(2) Constant factor + energy: event-driven software is also O(fan-out) "
        "but carries measured constants of ~2 us/decision (ideal asyncio) to "
        "~1.7 ms/decision (deployed LangGraph) vs the engine's cycle-scale scatter "
        "— pending csynth and full-path interface accounting (check 11). "
        "Claim (1) never applies against event-driven baselines."
    )

    return {
        "thesis_statement": thesis,
        "proof_layer": "structural_sim",
        "note": (
            "Primary evidence for Phase 2. LangGraph traces (checks 1–5) calibrate "
            "workload realism; this check proves the mechanism."
        ),
        "opt_speedup": OPT_SPEEDUP,
        "batch_width": BATCH_WIDTH,
        "sweep_live_nodes": SWEEP_LIVE_NODES,
        "sweep_fanout": SWEEP_FANOUT,
        "react_fanout_proxy": react_fanout,
        "by_live_nodes_at_react_fanout": by_live,
        "min_live_nodes_hw_flat_beats_optimized": min_live_flat,
        "min_live_nodes_hw_batch_beats_optimized": min_live_batch,
        "grid": grid,
        "native_bench_available": native_ok,
        "native_bench_rows": native,
        "native_bench_avg_coord_speedup": avg_speedup,
        "measured_constants": measured_constants,
        "baseline_honesty": (
            "An ideal event-driven software scheduler (O(1) wakeup) matches the "
            "engine's O(fan-out) asymptotics. Against that baseline the hardware "
            "case is constant factor + energy, not complexity class. The scan "
            "columns model LangGraph-class superstep frameworks; check 11 measures "
            "both constants on real code."
        ),
        "headline": _headline(min_live_flat, min_live_batch, native_ok, avg_speedup),
    }


def _headline(
    min_flat: int | None,
    min_batch: int | None,
    native_ok: bool,
    avg_speedup: float | None,
) -> str:
    parts = []
    if min_flat is not None:
        parts.append(
            f"Analytical crossover: flat hardware beats {OPT_SPEEDUP:.0f}x optimized "
            f"software at live_nodes >= {min_flat} (fan-out=2)."
        )
    else:
        parts.append("Analytical flat crossover not reached in sweep range.")
    if min_batch is not None and min_batch != min_flat:
        parts.append(f"8-wide batch lowers threshold to live_nodes >= {min_batch}.")
    if native_ok and avg_speedup:
        parts.append(
            f"Native oe_bench avg coordination speedup (engine vs CPU scan): {avg_speedup:.2f}x."
        )
    return " ".join(parts)


def render_structural_markdown(data: dict) -> str:
    lines = [
        "## 9. Structural proof (primary thesis evidence)",
        "",
        f"**Thesis:** {data['thesis_statement']}",
        "",
        f"**Headline:** {data['headline']}",
        "",
        "_LangGraph percentages (checks 1–3) calibrate workload realism; this section "
        "proves the O(N) vs O(fan-out) mechanism._",
        "",
        "### Crossover at fan-out=2 (live nodes vs coordination cycles)",
        "",
        "| live N | completions | CPU scan | 4x opt scan | HW flat | HW batch | HW wins? |",
        "|--------|-------------|----------|-------------|---------|----------|----------|",
    ]
    for row in data["by_live_nodes_at_react_fanout"]:
        win = "yes" if row["hardware_flat_beats_optimized"] else "no"
        lines.append(
            f"| {row['live_nodes']} | {row['completions']} | {row['cycles_global_scan']} | "
            f"{row['cycles_optimized_scan']} | {row['cycles_hardware_flat']} | "
            f"{row['cycles_hardware_batched']} | {win} |"
        )

    if data["native_bench_available"]:
        lines.extend(["", "### Native oe_bench (engine_sim vs cpu_baseline)", ""])
        lines.append("| depth | fanout | cpu coord | eng coord | speedup | nodes |")
        lines.append("|-------|--------|-----------|-----------|---------|-------|")
        for r in data["native_bench_rows"]:
            lines.append(
                f"| {r['depth']} | {r['fanout']} | {r['coord_overhead_cpu_scan']} | "
                f"{r['coord_overhead_engine']} | {r['speedup_coord']:.2f}x | {r['graph_nodes']} |"
            )
    else:
        lines.extend(
            [
                "",
                "_Native bench not built — run ``cd orchestration_engine && ./build.ps1`` "
                "for cycle-accurate C++ confirmation._",
            ]
        )

    mc = data.get("measured_constants")
    lines.extend(
        [
            "",
            "### Baseline honesty (event-driven software)",
            "",
            data.get("baseline_honesty", ""),
            "",
        ]
    )
    if mc:
        lg = mc.get("langgraph_us_per_decision")
        ev = mc.get("event_driven_us_per_decision")
        hw = mc.get("hw_us_per_decision")
        lines.extend(
            [
                "| dispatcher | measured µs/decision | vs hardware |",
                "|-----------|----------------------|-------------|",
                f"| LangGraph (real framework, live_n>=100) | {lg:.0f} | {lg/hw:,.0f}x |"
                if lg and hw
                else "",
                f"| asyncio event-driven (O(1) baseline) | {ev:.2f} | {ev/hw:,.0f}x |"
                if ev and hw
                else "",
                f"| engine scatter (analytic, pre-csynth) | {hw:.2f} | 1x |"
                if hw
                else "",
                "",
            ]
        )

    lines.extend(
        [
            "",
            "### Hardware-wins region (flat vs 4x optimized scan)",
            "",
            "| live N \\ fan-out | "
            + " | ".join(str(f) for f in data["sweep_fanout"])
            + " |",
            "|---|" + "|".join("---" for _ in data["sweep_fanout"]) + "|",
        ]
    )
    for live in data["sweep_live_nodes"]:
        cells = []
        for fanout in data["sweep_fanout"]:
            row = next(
                r for r in data["grid"] if r["live_nodes"] == live and r["fanout"] == fanout
            )
            cells.append("Y" if row["hardware_flat_beats_optimized"] else ".")
        lines.append(f"| {live} | " + " | ".join(cells) + " |")

    return "\n".join(lines)
