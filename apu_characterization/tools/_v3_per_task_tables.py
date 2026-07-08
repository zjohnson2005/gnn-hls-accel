"""Emit one markdown table block per task from v3 replication artifact."""

from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

ART = Path("apu_characterization/out/replication_remote_search_v3.json")

SHOW = [
    ("TOOL_COMPUTE", "TOOL"),
    ("THREADPOOL", "THREADPOOL"),
    ("ORCH_SETUP", "ORCH_setup"),
    ("ORCH_DISPATCH", "ORCH_dispatch"),
    ("CLIENT_HTTP", "LLM_HTTP_CPU"),
    ("HTTP_CLIENT", "Remote_tool_IO_CPU"),
    ("FRAMEWORK", "FRAMEWORK"),
    ("TOKENIZATION", "TOKEN"),
    ("RESIDUAL_UNATTRIBUTED", "RESIDUAL"),
]


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


def fmt_call(call: dict) -> str:
    tool = call.get("tool") or "?"
    query = call.get("query") or ""
    for key in ("query", "expression"):
        m = re.search(rf'"{re.escape(key)}":\s*"((?:\\.|[^"\\])*)', query)
        if m:
            val = m.group(1).encode().decode("unicode_escape", errors="replace")
            val = val.replace("\\n", " ").strip()
            if len(val) > 55:
                val = val[:54] + "…"
            return f'{tool}("{val}")'
    return tool


def main() -> None:
    data = json.loads(ART.read_text(encoding="utf-8"))
    wall: dict[str, list[float]] = defaultdict(list)
    llm: dict[str, list[float]] = defaultdict(list)
    remote_io: dict[str, list[float]] = defaultdict(list)
    host: dict[str, list[float]] = defaultdict(list)
    cat_pct: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    res_pct: dict[str, list[float]] = defaultdict(list)
    tools: dict[str, list[str]] = defaultdict(list)
    seqs: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for art in data["per_seed_artifacts"]:
        seed = art["config"]["seed"]
        ptw = (art.get("per_task_wall_cpu") or {}).get("per_task") or {}
        for tid, row in ptw.items():
            wall[tid].append(row["session_wall_s"])
            llm[tid].append(row.get("llm_io_wait_s") or 0.0)
            remote_io[tid].append(row.get("remote_tool_io_wait_s") or 0.0)
            host[tid].append(row["host_cpu_ms"])
            h = row["host_cpu_ms"] or 1.0
            by = row.get("cpu_by_category_ms") or {}
            for cat, short in SHOW:
                cat_pct[tid][short].append(100 * by.get(cat, 0) / h)
            for sess in art["run"]["per_session"]:
                if sess.get("task_id") != tid:
                    continue
                host_ns = sess.get("process_cpu_ns") or 1
                res_pct[tid].append(
                    100 * (sess.get("provenance") or {}).get("residual", 0) / host_ns
                )
                counts = sess.get("tool_call_counts") or {}
                tools[tid].append(
                    ", ".join(f"{k}×{v}" for k, v in sorted(counts.items())) or "(none)"
                )
                seq = " → ".join(fmt_call(c) for c in (sess.get("tool_call_sequence") or []))
                seqs[tid].append((seed, seq))
                break

    order = sorted(wall.keys(), key=lambda t: (-med(host[t]), t))
    agg = data["aggregate"]
    b = agg["batch_host_cpu_ms"]
    print("# v3.1 per-task breakdown (n=5 seeds, audit PASS)\n")
    print("## Batch summary\n")
    print("| Metric | Median [IQR or range] |")
    print("|--------|------------------------|")
    batch_wall = [a["batch_wall_s"] for a in data["per_seed_artifacts"]]
    print(f"| Batch wall (s) | {med(batch_wall):.1f} [{min(batch_wall):.1f}–{max(batch_wall):.1f}] |")
    print(f"| Batch host CPU (ms) | {b['median']:.1f} [{b['q1']:.1f}–{b['q3']:.1f}] |")
    print(f"| Pooled TOOL % | {agg['pooled_tool_compute_pct']['median']:.1f}% |")
    print(f"| Pooled THREADPOOL % | {agg['pooled_threadpool_pct']['median']:.1f}% |")
    print(f"| Pooled ORCH % | {agg['pooled_orch_pct']['median']:.1f}% |")
    print(f"| Residual provenance % | {agg['pooled_residual_provenance_pct']['median']:.1f}% |")
    print()

    for tid in order:
        n = len(host[tid])
        print(f"---\n\n## {tid}\n")
        print(f"**Seeds:** n={n} · **Tools:** {tools[tid][0] if len(set(tools[tid])) == 1 else 'varies by seed'}\n")
        print("| Metric | Median [IQR] |")
        print("|--------|--------------|")
        print(f"| Session wall (s) | {iqr_str(wall[tid])} |")
        print(f"| LLM I/O wait (s) | {iqr_str(llm[tid])} |")
        print(f"| Remote-tool I/O wait (s) | {iqr_str(remote_io[tid])} |")
        print(f"| Host CPU (ms) | {iqr_str(host[tid])} |")
        print(f"| Residual (% of host) | {iqr_str(res_pct[tid])} |")
        print()
        print("| Category | % host CPU (median) |")
        print("|----------|---------------------|")
        rows = [(med(cat_pct[tid][short]), short) for _, short in SHOW if cat_pct[tid][short]]
        for m, short in sorted(rows, reverse=True):
            if m >= 0.05:
                print(f"| {short} | {m:.1f}% |")
        print()
        print("| Step | Tool call |")
        print("|------|-----------|")
        # Use median seed's sequence if multiple; else list all seeds
        if len(set(s for _, s in seqs[tid])) == 1:
            seq = seqs[tid][0][1]
            if not seq or seq == "":
                print("| — | (none) |")
            else:
                for i, call in enumerate(seq.split(" → "), 1):
                    print(f"| {i} | {call} |")
        else:
            for seed, seq in sorted(seqs[tid]):
                if not seq:
                    print(f"| seed {seed} | (none) |")
                    continue
                calls = seq.split(" → ")
                for i, call in enumerate(calls, 1):
                    label = f"seed {seed}, step {i}" if len(calls) > 1 else f"seed {seed}"
                    print(f"| {label} | {call} |")
        print()


if __name__ == "__main__":
    main()
