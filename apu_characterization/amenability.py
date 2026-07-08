"""APU hardware-amenability classification and per-task metrics.

The per-task "hardware amenable percentage" needs an explicit category
classification to be defensible. Tiers, with one-line rationale each:

  direct   fixed-function or parameterizable hardware block exists or is
           demonstrated (Phase 2 kernels, JSON parse engines, BPE encoders)
  partial  the mechanical core (copies, formatting, template fill) maps to
           a copy/DMA/format engine but irregular control stays on host
  overlap  offloadable, but an existing device class (NIC/DPU) already
           owns it; an APU block would duplicate, not create, the win
  none     application compute or interpreter runtime, out of APU scope

Two headline percentages per task:
  strict = direct / instrumented
  broad  = (direct + partial + overlap) / instrumented

Base is the task's instrumented CPU. GC and RESIDUAL are process-global
and cannot be attributed to a task honestly, so they are excluded from
per-task math (they appear in the run-level table).

This classification is an input assumption of the analysis, not a
measurement. The full scorecard (section 9) refines it with measured
interface economics; until then these tiers are the documented prior.
"""

from __future__ import annotations

from typing import Any

from .taxonomy import Category

TIER: dict[str, str] = {
    Category.ORCH_SETUP.value: "direct",
    Category.ORCH_DISPATCH.value: "direct",
    Category.TOKENIZATION.value: "direct",
    Category.SERIALIZATION.value: "direct",
    Category.HTTP_CLIENT.value: "overlap",
    Category.PROMPT_ASSEMBLY.value: "partial",
    Category.CONTEXT_MGMT.value: "partial",
    Category.LOGGING.value: "partial",
    Category.TOOL_COMPUTE.value: "none",
    Category.GC.value: "none",
    Category.CLIENT_HTTP.value: "overlap",
    Category.CLIENT_PARSE.value: "direct",
    Category.FRAMEWORK.value: "direct",
    Category.THREADPOOL.value: "partial",
    Category.EVENT_LOOP.value: "partial",
    Category.RESIDUAL_UNATTRIBUTED.value: "none",
}

RATIONALE: dict[str, str] = {
    Category.ORCH_SETUP.value: "graph-load/session-append kernel demonstrated in Phase 2",
    Category.ORCH_DISPATCH.value: "scatter-on-completion kernel demonstrated in Phase 2",
    Category.TOKENIZATION.value: "BPE encode/count is fixed-function friendly, table-driven",
    Category.SERIALIZATION.value: "JSON parse/serialize accelerators are an established block class",
    Category.HTTP_CLIENT.value: "NIC/DPU class devices already own HTTP/TLS envelope work",
    Category.PROMPT_ASSEMBLY.value: "template fill and concatenation map to copy engines; "
    "message-selection logic stays on host",
    Category.CONTEXT_MGMT.value: "state copies map to DMA/copy engines; "
    "structure traversal stays on host",
    Category.LOGGING.value: "format-and-ship maps to telemetry offload engines",
    Category.TOOL_COMPUTE.value: "application compute, not serving-harness work; "
    "out of APU scope by definition",
    Category.GC.value: "CPython runtime internals, not a separable block",
    Category.CLIENT_HTTP.value: "TLS/HTTP transport owned by NIC/DPU class devices",
    Category.CLIENT_PARSE.value: "JSON and schema validation map to parse engines",
    Category.FRAMEWORK.value: "LangGraph dispatch maps to Phase 2 orchestration kernels",
    Category.THREADPOOL.value: "executor dispatch is partial copy/scheduling offload",
    Category.EVENT_LOOP.value: "asyncio driver is partial overlap with runtime",
    Category.RESIDUAL_UNATTRIBUTED.value: "unattributed gap; must be driven to zero in v2",
}

STRICT_TIERS = ("direct",)
BROAD_TIERS = ("direct", "partial", "overlap")


def compute_per_task(run: dict[str, Any]) -> dict[str, Any]:
    """Group per-session category totals by task and score amenability.

    Returns {task_id: {"categories": {cat: {cpu_ns, wall_ns, bytes_in,
    bytes_out, count}}, "instrumented_cpu_ns", "amenable_strict_ns",
    "amenable_broad_ns", "amenable_strict_share", "amenable_broad_share",
    "sessions": [...]}}.
    """
    session_to_task: dict[str, str] = {}

    def _map(sessions: list[dict[str, Any]]) -> None:
        for s in sessions:
            session_to_task[s["session_id"]] = s.get("task_id", "unknown")
            _map(s.get("subagent_results", []))

    _map(run.get("per_session", []))

    per_task: dict[str, Any] = {}
    for sid, cats in run.get("per_session_category", {}).items():
        if sid not in session_to_task:
            continue  # e.g. "global" (GC), which is not attributable
        task_id = session_to_task[sid]
        entry = per_task.setdefault(
            task_id, {"categories": {}, "sessions": []}
        )
        if sid not in entry["sessions"]:
            entry["sessions"].append(sid)
        for cat, vals in cats.items():
            slot = entry["categories"].setdefault(
                cat,
                {"cpu_ns": 0, "wall_ns": 0, "bytes_in": 0, "bytes_out": 0, "count": 0},
            )
            for key in slot:
                slot[key] += vals.get(key, 0)

    for task_id, entry in per_task.items():
        total = sum(v["cpu_ns"] for v in entry["categories"].values())
        strict = sum(
            v["cpu_ns"]
            for cat, v in entry["categories"].items()
            if TIER.get(cat) in STRICT_TIERS
        )
        broad = sum(
            v["cpu_ns"]
            for cat, v in entry["categories"].items()
            if TIER.get(cat) in BROAD_TIERS
        )
        entry["instrumented_cpu_ns"] = total
        entry["amenable_strict_ns"] = strict
        entry["amenable_broad_ns"] = broad
        entry["amenable_strict_share"] = strict / total if total else 0.0
        entry["amenable_broad_share"] = broad / total if total else 0.0

    return per_task


# Categories whose wall timers run on LangGraph tool-pool threads while the
# stream thread is blocked on the same session clock. Summing their wall
# fractions against session wall double-counts those periods (CPU timers are
# exclusive; session wall is single-thread elapsed).
CONCURRENT_WALL_CATEGORIES: frozenset[str] = frozenset(
    {Category.TOOL_COMPUTE.value, Category.GC.value}
)

# ORCH_SETUP is timed before session wall starts in real-agent mode; exclude
# from session-wall fractions so numerator and denominator describe the same
# interval.
EXCLUDED_FROM_WALL_FRACTION: frozenset[str] = frozenset(
    {Category.ORCH_SETUP.value}
)

ARCHETYPE_LABELS: dict[str, str] = {
    "SH": "search_heavy",
    "CH": "code_heavy",
    "RH": "rag_heavy",
    "RE": "reasoning_heavy",
    "LH": "long_horizon",
    "FO": "fanout",
    "CN": "chain",
    "SW": "swarm",
    "SO": "structured_output",
    "AH": "api_heavy",
    "MX": "mixed",
}


def task_archetype(task_id: str) -> str:
    """Task prefix before the numeric suffix, e.g. SH-01 -> SH."""
    head, _, _tail = task_id.partition("-")
    return head or task_id


def _empty_category() -> dict[str, int]:
    return {"cpu_ns": 0, "wall_ns": 0, "bytes_in": 0, "bytes_out": 0, "count": 0}


def _wall_fraction(
    wall_ns: int,
    session_wall_s: float,
    category: str,
) -> float | None:
    """Category wall as a fraction of session wall, or None if not applicable."""
    if session_wall_s <= 0:
        return None
    if category in EXCLUDED_FROM_WALL_FRACTION:
        return None
    return (wall_ns / 1e9) / session_wall_s


def compute_wall_diagnostics(
    per_task: dict[str, Any],
    per_session: list[dict[str, Any]],
) -> dict[str, Any]:
    """Per-task wall coverage checks (sum of category walls vs session wall).

    CPU category timers are exclusive and sum to instrumented CPU. Wall timers
    use the same exclusive nesting on each thread, but category walls are
    summed across threads while session wall is stream-thread elapsed, so
    coverage can exceed 1.0 when tool-pool work overlaps session clock time.
    """
    session_wall = {s["session_id"]: s["wall_s"] for s in per_session}
    per_task_diag: dict[str, Any] = {}
    for task_id, entry in per_task.items():
        sid = entry["sessions"][0]
        sw = session_wall.get(sid, 0.0)
        sw_ns = int(sw * 1e9)
        cats = entry["categories"]
        total_wall_ns = sum(v["wall_ns"] for v in cats.values())
        partition_wall_ns = sum(
            v["wall_ns"]
            for cat, v in cats.items()
            if cat not in CONCURRENT_WALL_CATEGORIES
            and cat not in EXCLUDED_FROM_WALL_FRACTION
        )
        concurrent_wall_ns = sum(
            v["wall_ns"]
            for cat, v in cats.items()
            if cat in CONCURRENT_WALL_CATEGORIES
        )
        per_task_diag[task_id] = {
            "session_wall_s": sw,
            "total_category_wall_s": total_wall_ns / 1e9,
            "coverage_all_categories": (
                (total_wall_ns / sw_ns) if sw_ns > 0 else None
            ),
            "coverage_partition_categories": (
                (partition_wall_ns / sw_ns) if sw_ns > 0 else None
            ),
            "concurrent_category_wall_s": concurrent_wall_ns / 1e9,
        }
    return {"per_task": per_task_diag}


def compute_per_task_wall_cpu(
    per_task: dict[str, Any],
    per_session: list[dict[str, Any]],
) -> dict[str, Any]:
    """Per-task session wall, LLM I/O wait (HTTP wall), and CPU breakdown.

    I/O % and CPU % both use session wall as denominator. They sum to at most
    ~100% because HTTP wall and host CPU measure different axes (blocked wait
    vs thread compute), not overlapping category wall fractions.
    """
    session_by_id = {s["session_id"]: s for s in per_session}
    rows: dict[str, Any] = {}
    for task_id in sorted(per_task):
        entry = per_task[task_id]
        sid = entry["sessions"][0]
        s = session_by_id[sid]
        sw = s["wall_s"]
        cpu_ms = s["process_cpu_ns"] / 1e6
        cats = entry["categories"]
        http_s = cats.get("HTTP_CLIENT", {}).get("wall_ns", 0) / 1e9
        tool_cpu = cats.get("TOOL_COMPUTE", {}).get("cpu_ns", 0) / 1e6
        orch_cpu = (
            cats.get("ORCH_SETUP", {}).get("cpu_ns", 0)
            + cats.get("ORCH_DISPATCH", {}).get("cpu_ns", 0)
        ) / 1e6
        token_cpu = cats.get("TOKENIZATION", {}).get("cpu_ns", 0) / 1e6
        http_cpu = cats.get("HTTP_CLIENT", {}).get("cpu_ns", 0) / 1e6
        gc_cpu = cats.get("GC", {}).get("cpu_ns", 0) / 1e6
        serial_cpu = cats.get("SERIALIZATION", {}).get("cpu_ns", 0) / 1e6
        harness_cpu = orch_cpu + token_cpu + http_cpu + gc_cpu + serial_cpu
        cpu_by_category = {
            cat: vals["cpu_ns"] / 1e6
            for cat, vals in cats.items()
            if vals.get("cpu_ns", 0) > 0
        }
        rows[task_id] = {
            "session_id": sid,
            "session_wall_s": sw,
            "llm_io_wait_s": http_s,
            "non_llm_wall_s": max(0.0, sw - http_s),
            "host_cpu_ms": cpu_ms,
            "llm_io_pct_of_session_wall": (http_s / sw * 100) if sw else None,
            "host_cpu_pct_of_session_wall": (cpu_ms / 1000 / sw * 100) if sw else None,
            "tool_cpu_ms": tool_cpu,
            "harness_cpu_ms": harness_cpu,
            "cpu_by_category_ms": cpu_by_category,
            "tool_call_counts": s.get("tool_call_counts", {}),
        }

    total_wall = sum(r["session_wall_s"] for r in rows.values())
    total_io = sum(r["llm_io_wait_s"] for r in rows.values())
    total_cpu = sum(r["host_cpu_ms"] for r in rows.values())
    return {
        "per_task": rows,
        "totals": {
            "session_wall_s": total_wall,
            "llm_io_wait_s": total_io,
            "host_cpu_ms": total_cpu,
            "llm_io_pct_of_session_wall": (total_io / total_wall * 100) if total_wall else None,
            "host_cpu_pct_of_session_wall": (total_cpu / 1000 / total_wall * 100)
            if total_wall
            else None,
        },
    }


def _mean_category_stats(
    task_ids: list[str],
    per_task: dict[str, Any],
    session_wall: dict[str, float],
) -> dict[str, Any]:
    """Equal-weight mean CPU/wall per category across the given tasks."""
    n = len(task_ids)
    if n == 0:
        return {"task_count": 0, "tasks": [], "categories": {}}

    categories: set[str] = set()
    for task_id in task_ids:
        categories.update(per_task[task_id]["categories"].keys())

    cat_stats: dict[str, dict[str, float]] = {}
    for cat in sorted(categories):
        cpu_ms: list[float] = []
        cpu_share: list[float] = []
        wall_ms: list[float] = []
        wall_frac: list[float] = []
        for task_id in task_ids:
            entry = per_task[task_id]
            total_cpu = entry["instrumented_cpu_ns"]
            vals = entry["categories"].get(cat, _empty_category())
            sid = entry["sessions"][0]
            sw = session_wall.get(sid, 0.0)
            cpu_ms.append(vals["cpu_ns"] / 1e6)
            cpu_share.append(vals["cpu_ns"] / total_cpu if total_cpu else 0.0)
            wall_ms.append(vals["wall_ns"] / 1e6)
            frac = _wall_fraction(vals["wall_ns"], sw, cat)
            if frac is not None:
                wall_frac.append(frac)
        cat_stats[cat] = {
            "mean_cpu_ms": sum(cpu_ms) / n,
            "mean_cpu_share": sum(cpu_share) / n,
            "mean_wall_ms": sum(wall_ms) / n,
            "mean_wall_frac": (
                sum(wall_frac) / len(wall_frac) if wall_frac else None
            ),
            "in_wall_partition": cat not in CONCURRENT_WALL_CATEGORIES
            and cat not in EXCLUDED_FROM_WALL_FRACTION,
            "wall_concurrent": cat in CONCURRENT_WALL_CATEGORIES,
        }

    instr_cpu_ms = [
        per_task[t]["instrumented_cpu_ns"] / 1e6 for t in task_ids
    ]
    strict_share = [per_task[t]["amenable_strict_share"] for t in task_ids]
    broad_share = [per_task[t]["amenable_broad_share"] for t in task_ids]
    wall_s = [
        session_wall.get(per_task[t]["sessions"][0], 0.0) for t in task_ids
    ]
    partition_frac_sum = 0.0
    for cat, st in cat_stats.items():
        if st.get("in_wall_partition") and st.get("mean_wall_frac") is not None:
            partition_frac_sum += st["mean_wall_frac"]

    return {
        "task_count": n,
        "tasks": sorted(task_ids),
        "mean_instrumented_cpu_ms": sum(instr_cpu_ms) / n,
        "mean_session_wall_s": sum(wall_s) / n,
        "mean_amenable_strict_share": sum(strict_share) / n,
        "mean_amenable_broad_share": sum(broad_share) / n,
        "mean_wall_frac_sum_partition": partition_frac_sum,
        "categories": cat_stats,
    }


def compute_category_averages(
    per_task: dict[str, Any],
    per_session: list[dict[str, Any]],
) -> dict[str, Any]:
    """Equal-weight means per instrumentation category, overall and by archetype.

    Unlike the headline pooled table, each task contributes equally regardless
    of how much CPU or wall it consumed.
    """
    session_wall = {s["session_id"]: s["wall_s"] for s in per_session}
    by_arch: dict[str, list[str]] = {}
    for task_id in per_task:
        arch = task_archetype(task_id)
        by_arch.setdefault(arch, []).append(task_id)

    return {
        "overall": _mean_category_stats(sorted(per_task), per_task, session_wall),
        "by_archetype": {
            arch: {
                "label": ARCHETYPE_LABELS.get(arch, arch),
                **_mean_category_stats(sorted(tids), per_task, session_wall),
            }
            for arch, tids in sorted(by_arch.items())
        },
        "wall_diagnostics": compute_wall_diagnostics(per_task, per_session),
    }
