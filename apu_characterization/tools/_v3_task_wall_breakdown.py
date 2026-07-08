"""Print per-task wall + CPU breakdown from v3 replication artifact."""

from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

ART = Path("apu_characterization/out/replication_remote_search_v3.json")

# Roll-up for table (v3 measured categories)
SHOW = (
    ("TOOL_COMPUTE", "TOOL"),
    ("THREADPOOL", "THREADPOOL"),
    ("ORCH_SETUP", "ORCH_setup"),
    ("ORCH_DISPATCH", "ORCH_dispatch"),
    ("CLIENT_HTTP", "HTTP"),
    ("FRAMEWORK", "FRAMEWORK"),
    ("TOKENIZATION", "TOKEN"),
    ("RESIDUAL_UNATTRIBUTED", "RESIDUAL"),
)


def med(vals: list[float]) -> float:
    return statistics.median(vals) if vals else 0.0


def iqr_str(vals: list[float]) -> str:
    if not vals:
        return "—"
    if len(vals) == 1:
        return f"{vals[0]:.1f}"
    s = sorted(vals)
    q1, q3 = statistics.quantiles(s, n=4)[0], statistics.quantiles(s, n=4)[2]
    return f"{statistics.median(s):.1f} [{q1:.1f}–{q3:.1f}]"


def _extract_arg(query: str, key: str, max_len: int = 48) -> str | None:
    m = re.search(rf'"{re.escape(key)}":\s*"((?:\\.|[^"\\])*)', query)
    if not m:
        return None
    val = m.group(1).encode().decode("unicode_escape", errors="replace")
    val = val.replace("\\n", " ").strip()
    if len(val) > max_len:
        return val[: max_len - 1] + "…"
    return val


def fmt_tool_call(call: dict) -> str:
    tool = call.get("tool") or "?"
    query = call.get("query") or ""
    for key in ("query", "expression", "code"):
        arg = _extract_arg(query, key)
        if arg:
            return f'{tool}("{arg}")'
    step = call.get("llm_step")
    if step is not None:
        return f"{tool}(step {step})"
    return tool


def fmt_tool_sequence(seq: list[dict]) -> str:
    if not seq:
        return "(none)"
    return " → ".join(fmt_tool_call(c) for c in seq)


def main() -> None:
    data = json.loads(ART.read_text(encoding="utf-8"))
    agg = data["aggregate"]

    print("=== Batch (n=5 seeds) ===")
    b = agg["batch_host_cpu_ms"]
    print(f"Host CPU ms: {b['median']:.1f} [{b['q1']:.1f}–{b['q3']:.1f}]")
    batch_wall = [a["batch_wall_s"] for a in data["per_seed_artifacts"]]
    print(f"Batch wall s: {med(batch_wall):.1f} [{min(batch_wall):.1f}–{max(batch_wall):.1f}]")
    for key, label in [
        ("pooled_tool_compute_pct", "TOOL %"),
        ("pooled_threadpool_pct", "THREADPOOL %"),
        ("pooled_orch_pct", "ORCH %"),
        ("pooled_framework_pct", "FRAMEWORK %"),
        ("pooled_client_http_pct", "CLIENT_HTTP %"),
        ("pooled_measured_pct", "measured %"),
        ("pooled_residual_provenance_pct", "residual %"),
    ]:
        if key in agg:
            x = agg[key]
            print(f"  {label}: {x['median']:.1f} [{x['q1']:.1f}–{x['q3']:.1f}]")

    # Collect per-task across seeds
    wall_s: dict[str, list[float]] = defaultdict(list)
    llm_wait_s: dict[str, list[float]] = defaultdict(list)
    host_ms: dict[str, list[float]] = defaultdict(list)
    cat_pct: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    tools: dict[str, list[str]] = defaultdict(list)
    tool_seqs: dict[str, list[str]] = defaultdict(list)
    tool_seqs_by_seed: dict[str, list[tuple[int, str]]] = defaultdict(list)
    residual_pct: dict[str, list[float]] = defaultdict(list)

    for art in data["per_seed_artifacts"]:
        seed = art["config"]["seed"]
        ptw = (art.get("per_task_wall_cpu") or {}).get("per_task") or {}
        for tid, row in ptw.items():
            wall_s[tid].append(row["session_wall_s"])
            llm_wait_s[tid].append(row.get("llm_io_wait_s") or 0.0)
            host_ms[tid].append(row["host_cpu_ms"])
            for sess in art["run"]["per_session"]:
                if sess.get("task_id") == tid:
                    host_ns = sess.get("process_cpu_ns") or 1
                    res = (sess.get("provenance") or {}).get("residual", 0)
                    residual_pct[tid].append(100 * res / host_ns)
                    counts = sess.get("tool_call_counts") or {}
                    tools[tid].append(
                        ", ".join(f"{k}×{v}" for k, v in sorted(counts.items()))
                        or "(none)"
                    )
                    seq_str = fmt_tool_sequence(sess.get("tool_call_sequence") or [])
                    tool_seqs[tid].append(seq_str)
                    tool_seqs_by_seed[tid].append((seed, seq_str))
                    break
            by = row.get("cpu_by_category_ms") or {}
            h = row["host_cpu_ms"] or 1.0
            for cat, short in SHOW:
                cat_pct[tid][short].append(100 * by.get(cat, 0) / h)

    # Task order from batch profile (10 per seed typical)
    task_order = sorted(
        wall_s.keys(),
        key=lambda t: (-med(host_ms[t]), t),
    )

    print("\n=== Per task (median across seeds where task appeared) ===")
    print(
        f"{'Task':<8} {'n':>2} {'Wall s':>12} {'LLM wait s':>12} {'Host ms':>12} "
        f"{'TOOL%':>6} {'TPool%':>6} {'ORCH%':>6} {'FRMW%':>6} {'RES%':>5}  Tools"
    )
    print("-" * 105)
    for tid in task_order:
        n = len(host_ms[tid])
        orch = med(cat_pct[tid]["ORCH_setup"]) + med(cat_pct[tid]["ORCH_dispatch"])
        tool_str = tools[tid][0] if len(set(tools[tid])) == 1 else f"varies ({n})"
        print(
            f"{tid:<8} {n:>2} {iqr_str(wall_s[tid]):>12} {iqr_str(llm_wait_s[tid]):>12} "
            f"{iqr_str(host_ms[tid]):>12} "
            f"{med(cat_pct[tid]['TOOL']):>6.1f} {med(cat_pct[tid]['THREADPOOL']):>6.1f} "
            f"{orch:>6.1f} {med(cat_pct[tid]['FRAMEWORK']):>6.1f} "
            f"{med(residual_pct[tid]):>5.1f}  {tool_str}"
        )

    print("\n=== Per task category detail (% of host CPU, median across seeds) ===")
    for tid in task_order:
        n = len(host_ms[tid])
        parts = [f"{tid} (n={n})"]
        for cat, short in SHOW:
            if cat_pct[tid][short]:
                parts.append(f"{short}={med(cat_pct[tid][short]):.1f}%")
        print("  " + ", ".join(parts))

    print("\n=== Tool call sequences (specific queries per task) ===")
    for tid in task_order:
        n = len(host_ms[tid])
        unique = sorted(set(tool_seqs[tid]))
        print(f"\n{tid}  (n={n} seeds, counts: {tools[tid][0] if len(set(tools[tid])) == 1 else 'varies'})")
        if len(unique) == 1:
            print(f"  {unique[0]}")
        else:
            for seed, seq in sorted(tool_seqs_by_seed[tid], key=lambda x: x[0]):
                print(f"  seed {seed}: {seq}")


if __name__ == "__main__":
    main()
