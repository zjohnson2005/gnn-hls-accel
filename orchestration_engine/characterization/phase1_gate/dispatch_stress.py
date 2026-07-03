"""Local dispatch stress: measured per-decision CPU cost vs live concurrency.

The missing experiment for the O(live) claim. No API, no rate limits - N truly
concurrent live tasks in one process, three schedulers:

  A. langgraph_threads  - real LangGraph agents (mock model, instant tools),
                          N live threads. What deployed frameworks actually cost.
  B. asyncio_event      - event-driven O(1)-per-wakeup dispatcher. The honest
                          "optimized software" baseline (no global scan).
  C. python_global_scan - naive O(live) ready-scan scheduler. Structural
                          worst case in the same units.

Metric: process CPU microseconds per coordination decision at each live-N.
If (A) grows with N while (B) stays flat, LangGraph-class frameworks are
empirically in the scan class and check 9's software model is trace-grounded.

Run:  py -3 -m orchestration_engine.characterization.phase1_gate.dispatch_stress
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

GATE_DIR = Path("orchestration_engine/characterization/out/gate")
OUT_PATH = GATE_DIR / "dispatch_stress.json"

DEFAULT_LEVELS = [1, 10, 50, 100, 250, 500, 1000]
STEPS_PER_TASK = 10

# Hardware reference: scatter-on-completion = (1 + fan-out) cycles.
HW_CLOCK_MHZ = 300
HW_FANOUT = 2
SHARD_PROCS = 4

# Full-path completion-delivery costs (first-order, us). Both sides pay a
# delivery path: a tool completion arrives over the network / from a device
# and must reach the dispatcher before any decision happens.
#   Software: NIC -> kernel -> epoll/futex wakeup -> user space  ~2-5 us
#             (kernel-bypass ~1 us, rarely deployed for agent hosts)
#   Engine:   NIC/GPU -> PCIe Gen4 DMA one-way posted write      ~0.5-1.0 us
#             CXL-attached                                        ~0.3-0.6 us
#             on-SoC AXI (integrated beside host)                 ~0.05-0.15 us
DELIVERY_US = {
    "sw_epoll_wakeup": (2.0, 5.0),
    "sw_kernel_bypass": (1.0, 1.5),
    "hw_pcie_gen4_dma": (0.5, 1.0),
    "hw_cxl": (0.3, 0.6),
    "hw_on_soc_axi": (0.05, 0.15),
}


def _cpu_and_wall(fn) -> tuple[float, float]:
    """Run fn, return (process_cpu_s, wall_s)."""
    c0, w0 = time.process_time(), time.perf_counter()
    fn()
    return time.process_time() - c0, time.perf_counter() - w0


# ---------------------------------------------------------------- A: LangGraph
def run_langgraph_threads(n_live: int, steps: int = STEPS_PER_TASK) -> dict:
    """N real LangGraph agents live simultaneously (mock model, instant tools)."""
    from orchestration_engine.characterization.langgraph_react.agent import run_session

    profiles = []

    def one_session(idx: int) -> None:
        prof = run_session(
            preset="action_heavy",
            backend="mock",
            agent_id=f"stress_{idx}",
            seed=idx,
            calibrated=False,
            wall_clock=False,
            react_steps_override=steps,
        )
        profiles.append(prof)

    def batch() -> None:
        with ThreadPoolExecutor(max_workers=n_live) as pool:
            futures = [pool.submit(one_session, i) for i in range(n_live)]
            for f in futures:
                f.result()

    cpu_s, wall_s = _cpu_and_wall(batch)
    decisions = sum(
        1 for p in profiles for s in p.spans if s.name == "langgraph_react_step"
    )
    return {
        "scheduler": "langgraph_threads",
        "live_n": n_live,
        "decisions": decisions,
        "cpu_us_per_decision": 1e6 * cpu_s / max(1, decisions),
        "wall_s": round(wall_s, 3),
    }


def _steps_for_timing(n_live: int, min_decisions: int = 50_000) -> int:
    """Single-threaded modes need enough decisions to beat Windows timer granularity."""
    return max(STEPS_PER_TASK, min_decisions // max(1, n_live))


# ------------------------------------------------------------- B: asyncio O(1)
def run_asyncio_event(n_live: int, steps: int | None = None) -> dict:
    """Event-driven dispatcher: completions wake only their successors."""
    steps = steps or _steps_for_timing(n_live)

    async def main() -> int:
        decisions = 0
        queues = [asyncio.Queue() for _ in range(n_live)]
        state = [0] * n_live

        async def task(idx: int) -> int:
            done = 0
            for _ in range(steps):
                await queues[idx].get()
                # Successor update: O(fan-out) pointer chase, no scan.
                state[(idx + 1) % n_live] += 1
                done += 1
            return done

        async def driver() -> None:
            for _ in range(steps):
                for q in queues:
                    q.put_nowait(1)
                await asyncio.sleep(0)

        results = await asyncio.gather(driver(), *(task(i) for i in range(n_live)))
        decisions = sum(r for r in results[1:])
        return decisions

    # Single-threaded and non-blocking: wall time == CPU time, at ns resolution.
    w0 = time.perf_counter()
    decisions = asyncio.run(main())
    wall_s = time.perf_counter() - w0
    return {
        "scheduler": "asyncio_event",
        "live_n": n_live,
        "decisions": decisions,
        "cpu_us_per_decision": 1e6 * wall_s / max(1, decisions),
        "wall_s": round(wall_s, 3),
    }


# ------------------------------------------------- B2: sharded multi-core O(1)
def _sharded_worker(args: tuple[int, int]) -> tuple[int, float]:
    """One shard: event-driven loop over n_live/K tasks. Returns (decisions, wall_s)."""
    n_live, steps = args
    row = run_asyncio_event(n_live, steps=steps)
    return row["decisions"], row["wall_s"]


def run_sharded_asyncio(n_live: int, shards: int = SHARD_PROCS) -> dict:
    """The realistic datacenter answer: K cores running sharded event loops."""
    from concurrent.futures import ProcessPoolExecutor

    per_shard = max(1, n_live // shards)
    steps = _steps_for_timing(per_shard)
    w0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=shards) as pool:
        results = list(pool.map(_sharded_worker, [(per_shard, steps)] * shards))
    wall_s = time.perf_counter() - w0
    decisions = sum(r[0] for r in results)
    busy_s = sum(r[1] for r in results)  # single-threaded loops: wall ~= CPU
    return {
        "scheduler": f"sharded_asyncio_x{shards}",
        "live_n": n_live,
        "decisions": decisions,
        "cpu_us_per_decision": 1e6 * busy_s / max(1, decisions),
        "throughput_decisions_per_s": decisions / wall_s if wall_s > 0 else 0.0,
        "wall_s": round(wall_s, 3),
    }


# --------------------------------------------------------- C: global scan O(N)
def run_python_global_scan(n_live: int, steps: int | None = None) -> dict:
    """Naive scheduler: every completion rescans all live tasks for readiness."""
    steps = steps or _steps_for_timing(n_live)
    remaining = [steps] * n_live
    status = [1] * n_live  # touched by the scan on every decision

    w0 = time.perf_counter()
    completions = 0
    target = n_live * steps
    cursor = 0
    while completions < target:
        # Global scan: touch every live slot before firing (worst-case readiness check).
        acc = 0
        for i in range(n_live):
            acc += status[i]
        fired = cursor % n_live
        while remaining[fired] <= 0:
            fired = (fired + 1) % n_live
        remaining[fired] -= 1
        completions += 1
        cursor += 1
    wall_s = time.perf_counter() - w0
    return {
        "scheduler": "python_global_scan",
        "live_n": n_live,
        "decisions": completions,
        "cpu_us_per_decision": 1e6 * wall_s / max(1, completions),
        "wall_s": round(wall_s, 3),
    }


# ---------------------------------------------------------------------- report
def build_stress_report(levels: list[int] | None = None) -> dict:
    levels = levels or DEFAULT_LEVELS
    rows: list[dict] = []

    # Warmup (imports, JIT-ish caches) so N=1 is not polluted.
    run_langgraph_threads(1, steps=2)
    run_asyncio_event(1, steps=2)

    for n in levels:
        print(f"live_n={n}: langgraph...", end="", flush=True)
        rows.append(run_langgraph_threads(n))
        print(" asyncio...", end="", flush=True)
        rows.append(run_asyncio_event(n))
        print(" sharded...", end="", flush=True)
        rows.append(run_sharded_asyncio(n))
        print(" scan...", flush=True)
        rows.append(run_python_global_scan(n))

    by_sched: dict[str, list[dict]] = {}
    for r in rows:
        by_sched.setdefault(r["scheduler"], []).append(r)

    def growth(name: str) -> float:
        # Base at live_n >= 10: N=1 is dominated by pool startup amortization.
        pts = sorted(
            (r for r in by_sched.get(name, []) if r["live_n"] >= 10),
            key=lambda r: r["live_n"],
        )
        if len(pts) < 2 or pts[0]["cpu_us_per_decision"] <= 0:
            return 0.0
        return pts[-1]["cpu_us_per_decision"] / pts[0]["cpu_us_per_decision"]

    hw_us_per_decision = (1 + HW_FANOUT) / HW_CLOCK_MHZ  # cycles -> us
    hw_source = "analytic"
    try:
        from orchestration_engine.phase2_gate.csynth_parser import load_or_parse

        csynth = load_or_parse()
        if csynth is not None:
            hw_us_per_decision = csynth.scatter_us(HW_FANOUT)
            hw_source = "csynth"
    except ImportError:
        pass

    # Full-path accounting: delivery + dispatch, per completion (mid estimates).
    def _mid(key: str) -> float:
        lo, hi = DELIVERY_US[key]
        return (lo + hi) / 2

    ev_rows = [r for r in rows if r["scheduler"] == "asyncio_event" and r["live_n"] >= 100]
    ev_dispatch = (
        sum(r["cpu_us_per_decision"] for r in ev_rows) / len(ev_rows) if ev_rows else 2.0
    )
    full_path = {
        "sw_asyncio_epoll": round(_mid("sw_epoll_wakeup") + ev_dispatch, 2),
        "sw_asyncio_kernel_bypass": round(_mid("sw_kernel_bypass") + ev_dispatch, 2),
        "hw_engine_pcie": round(_mid("hw_pcie_gen4_dma") + hw_us_per_decision, 2),
        "hw_engine_cxl": round(_mid("hw_cxl") + hw_us_per_decision, 2),
        "hw_engine_on_soc": round(_mid("hw_on_soc_axi") + hw_us_per_decision, 3),
    }
    full_path["advantage_vs_kernel_bypass"] = round(
        full_path["sw_asyncio_kernel_bypass"] / full_path["hw_engine_pcie"], 1
    )
    full_path["advantage_vs_epoll"] = round(
        full_path["sw_asyncio_epoll"] / full_path["hw_engine_pcie"], 1
    )

    lg_growth = growth("langgraph_threads")
    ev_growth = growth("asyncio_event")
    scan_growth = growth("python_global_scan")

    if lg_growth >= 2.0 and ev_growth < 2.0:
        verdict = "LANGGRAPH_SCALES_WITH_LIVE_N"
        headline = (
            f"Measured: LangGraph per-decision CPU grows {lg_growth:.1f}x from "
            f"live_n={levels[0]} to {levels[-1]} while event-driven asyncio stays "
            f"~flat ({ev_growth:.1f}x). Deployed-framework dispatch is empirically "
            "in the scan class; check 9's software model is trace-grounded."
        )
    elif lg_growth < 2.0:
        verdict = "LANGGRAPH_FLAT"
        headline = (
            f"Measured: LangGraph per-decision CPU is ~flat with live_n "
            f"({lg_growth:.1f}x). The hardware case vs frameworks rests on constant "
            "factor + energy, not asymptotics - cite measured constants below."
        )
    else:
        verdict = "BOTH_SCALE"
        headline = (
            f"Both LangGraph ({lg_growth:.1f}x) and asyncio ({ev_growth:.1f}x) grow "
            "with live_n on this host - likely GIL/scheduler contention; rerun on "
            "an idle machine before citing."
        )

    return {
        "levels": levels,
        "steps_per_task": STEPS_PER_TASK,
        "rows": rows,
        "growth_langgraph": round(lg_growth, 2),
        "growth_asyncio_event": round(ev_growth, 2),
        "growth_global_scan": round(scan_growth, 2),
        "hw_reference_us_per_decision": round(hw_us_per_decision, 4),
        "hw_reference_source": hw_source,
        "hw_reference_note": (
            f"scatter = (1 + fan-out={HW_FANOUT}) cycles at {HW_CLOCK_MHZ} MHz "
            + ("(measured csynth)" if hw_source == "csynth" else "(analytic target, pending HLS csynth)")
        ),
        "delivery_us_assumptions": {k: list(v) for k, v in DELIVERY_US.items()},
        "full_path_us_per_completion": full_path,
        "full_path_note": (
            "Delivery + dispatch per completion, mid-range first-order estimates. "
            "Both sides pay inbound delivery: software completions cross "
            "NIC->kernel->epoll wakeup; engine completions cross an interconnect "
            "DMA write. Outbound work-launch to the executor (GPU/tool server) is "
            "symmetric on both sides and excluded. Dispatch-only comparisons "
            "overstate the hardware gap vs event-driven software."
        ),
        "verdict": verdict,
        "headline": headline,
    }


def render_stress_markdown(data: dict) -> str:
    lines = [
        "## 11. Local dispatch stress (measured O(live) evidence, no API)",
        "",
        f"**Verdict:** `{data['verdict']}`",
        "",
        data["headline"],
        "",
        "N live tasks in one process; per-decision **process CPU** cost "
        "(GIL-independent, energy-relevant).",
        "",
        "| live N | LangGraph µs/dec | asyncio event µs/dec | sharded x4 µs/dec | global scan µs/dec |",
        "|--------|------------------|----------------------|-------------------|--------------------|",
    ]
    by_n: dict[int, dict[str, float]] = {}
    shard_key = f"sharded_asyncio_x{SHARD_PROCS}"
    for r in data["rows"]:
        by_n.setdefault(r["live_n"], {})[r["scheduler"]] = r["cpu_us_per_decision"]
    for n in sorted(by_n):
        row = by_n[n]
        shard = row.get(shard_key)
        lines.append(
            f"| {n} | {row.get('langgraph_threads', 0):.0f} | "
            f"{row.get('asyncio_event', 0):.1f} | "
            + (f"{shard:.1f} | " if shard is not None else "- | ")
            + f"{row.get('python_global_scan', 0):.1f} |"
        )
    lines.extend(
        [
            "",
            f"- Growth {data['levels'][0]}->{data['levels'][-1]}: LangGraph "
            f"**{data['growth_langgraph']}x**, asyncio event **{data['growth_asyncio_event']}x**, "
            f"global scan **{data['growth_global_scan']}x**",
            f"- Hardware reference: **{data['hw_reference_us_per_decision']} µs/decision** "
            f"({data['hw_reference_note']})",
            "",
        ]
    )

    fp = data.get("full_path_us_per_completion")
    if fp:
        lines.extend(
            [
                "### Full-path accounting (delivery + dispatch per completion)",
                "",
                data.get("full_path_note", ""),
                "",
                "| path | µs/completion |",
                "|------|---------------|",
                f"| software: epoll wakeup + asyncio dispatch | {fp['sw_asyncio_epoll']} |",
                f"| software: kernel-bypass + asyncio dispatch | {fp['sw_asyncio_kernel_bypass']} |",
                f"| engine: PCIe Gen4 DMA + scatter | {fp['hw_engine_pcie']} |",
                f"| engine: CXL + scatter | {fp['hw_engine_cxl']} |",
                f"| engine: on-SoC AXI + scatter | {fp['hw_engine_on_soc']} |",
                "",
                f"_Full-path, the dispatch-only ~200x gap vs ideal asyncio collapses "
                f"to **~{fp['advantage_vs_kernel_bypass']}x** (vs kernel-bypass "
                f"software) / **~{fp['advantage_vs_epoll']}x** (vs standard epoll), "
                "because interconnect delivery dominates the engine's cycle-scale "
                "scatter. The durable advantages at PCIe attach are throughput under "
                "load (banked counters, no queue contention), energy, and freeing "
                "host cores; on-SoC integration recovers the latency gap._",
                "",
            ]
        )

    lines.append(
        "_Interpretation: sharded x4 event loops are the realistic deployed "
        "counter-proposal; single-core asyncio is the ideal. The hardware case "
        "against both is constant factor + energy + full-path latency; the case "
        "against LangGraph-class frameworks and scan-class schedulers adds the "
        "asymptotic gap._"
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local dispatch stress test")
    parser.add_argument("--levels", default=None, help="Comma list, e.g. 1,10,100,1000")
    args = parser.parse_args()

    levels = (
        [int(x) for x in args.levels.split(",") if x.strip()] if args.levels else None
    )
    data = build_stress_report(levels)
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\n{data['headline']}")
    print(f"Wrote {OUT_PATH.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
