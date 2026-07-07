"""Per-task CPU category medians across replication seeds."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

GROUP = {
    "ORCH_SETUP": "ORCH",
    "ORCH_DISPATCH": "ORCH",
    "TOKENIZATION": "TOKEN",
    "SERIALIZATION": "SER",
    "HTTP_CLIENT": "HTTP",
    "TOOL_COMPUTE": "TOOL",
    "GC": "GC",
}


def iqr(vals: list[float]) -> tuple[float, float, float]:
    if not vals:
        return 0.0, 0.0, 0.0
    s = sorted(vals)
    n = len(s)
    if n == 1:
        return s[0], s[0], s[0]
    q1 = statistics.quantiles(s, n=4)[0]
    med = statistics.median(s)
    q3 = statistics.quantiles(s, n=4)[2]
    return med, q1, q3


def fmt_tools(counts: dict) -> str:
    if not counts:
        return "(none)"
    return ", ".join(f"{k}×{v}" for k, v in sorted(counts.items()))


def main() -> None:
    path = Path(__file__).resolve().parents[1] / "out" / "replication_remote_search.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    agg = data["aggregate"]

    print("=== Publishable replication (Linux, remote search, n=5 seeds) ===")
    print(f"validity: {data['result_validity']}")
    print(f"audit pass: {data['audit']['pass']}")
    b = agg["batch_host_cpu_ms"]
    print(f"Batch host CPU ms: {b['median']:.1f} [{b['q1']:.1f}–{b['q3']:.1f}]")
    for key, label in [
        ("pooled_tool_compute_pct", "Pooled TOOL %"),
        ("pooled_orch_pct", "Pooled ORCH %"),
        ("pooled_harness_strict_pct", "Pooled harness strict % (ORCH+TOKEN+SER)"),
        ("pooled_orch_measured_pct", "Pooled ORCH measured %"),
        ("pooled_orch_reconcile_pct", "Pooled ORCH reconcile %"),
    ]:
        if key not in agg:
            continue
        x = agg[key]
        print(f"{label}: {x['median']:.1f} [{x['q1']:.1f}–{x['q3']:.1f}]")

    # Collect per-task per-seed rows
    host_ms: dict[str, list[float]] = defaultdict(list)
    pool_pct: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    tools: dict[str, list[str]] = defaultdict(list)

    for art in data["per_seed_artifacts"]:
        for sess in art["run"]["per_session"]:
            tid = sess["task_id"]
            host_ns = sess.get("process_cpu_ns") or 0
            if host_ns <= 0:
                continue
            host = host_ns / 1e6
            host_ms[tid].append(host)
            tools[tid].append(fmt_tools(sess.get("tool_call_counts") or {}))

            pt = art.get("per_task", {}).get(tid)
            if not pt:
                continue
            pooled: dict[str, float] = defaultdict(float)
            for name, c in pt.get("categories", {}).items():
                cpu = c.get("cpu_ns") or 0
                if cpu <= 0:
                    continue
                g = GROUP.get(name, name)
                pooled[g] += 100.0 * cpu / host_ns
            for g, p in pooled.items():
                pool_pct[tid][g].append(p)

    print("\n=== Per-task host CPU ms (median [IQR]) ===")
    task_order = sorted(host_ms.keys())
    for tid in task_order:
        med, q1, q3 = iqr(host_ms[tid])
        n = len(host_ms[tid])
        tool_modes = sorted(set(tools[tid]), key=tools[tid].count, reverse=True)
        print(f"\n{tid}  n={n} seeds  host CPU {med:.1f} ms [{q1:.1f}–{q3:.1f}]")
        print(f"  tools seen: {' | '.join(tool_modes[:3])}")

        if tid not in pool_pct:
            continue
        print("  Pooled CPU % (median):")
        rows = []
        for g, vals in pool_pct[tid].items():
            m, _, _ = iqr(vals)
            rows.append((m, g, len(vals)))
        for m, g, nv in sorted(rows, reverse=True):
            print(f"    {g:6s}  {m:5.1f}%  (n={nv})")


if __name__ == "__main__":
    main()
