"""Print per-task host CPU breakdown with category percentages and tools."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TASK_ORDER = [
    "SH-01", "SH-02", "CH-01", "CH-02",
    "RH-01", "RH-02", "RE-01", "RE-02", "LH-01", "LH-02",
]

GROUP = {
    "ORCH_SETUP": "ORCH",
    "ORCH_DISPATCH": "ORCH",
    "PROMPT_ASSEMBLY": "ORCH*",
    "CONTEXT_MGMT": "ORCH*",
    "TOKENIZATION": "TOKEN",
    "SERIALIZATION": "SER",
    "HTTP_CLIENT": "HTTP",
    "TOOL_COMPUTE": "TOOL",
    "GC": "GC",
    "LOGGING": "LOG",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def session_by_task(run: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for s in run.get("per_session", []):
        out[s["task_id"]] = s
    return out


def pct(cpu_ns: int, denom: int) -> float:
    return 100.0 * cpu_ns / denom if denom else 0.0


def fmt_tools(counts: dict) -> str:
    if not counts:
        return "(none — LLM-only answer)"
    return ", ".join(f"{k}×{v}" for k, v in sorted(counts.items()))


def print_run(label: str, data: dict) -> None:
    run = data["run"]
    sessions = session_by_task(run)
    per_task = data["per_task"]
    locality = run.get("per_session", [{}])[0].get("search_locality", "?")

    print(f"\n{'=' * 72}")
    print(f"{label}")
    print(f"search_locality={locality}  seed={run.get('seed')}  backend={run.get('backend')}")
    print(f"{'=' * 72}")

    for tid in TASK_ORDER:
        if tid not in per_task:
            continue
        task = per_task[tid]
        sess = sessions.get(tid, {})
        host_ns = int(sess.get("process_cpu_ns") or 0)
        instr_ns = int(task.get("instrumented_cpu_ns") or host_ns)
        denom = host_ns if host_ns > 0 else instr_ns
        denom_label = "process" if host_ns > 0 else "instrumented"

        cats = task.get("categories", {})
        rows: list[tuple[str, int, float]] = []
        for name, c in sorted(cats.items(), key=lambda x: -x[1].get("cpu_ns", 0)):
            cpu = int(c.get("cpu_ns") or 0)
            if cpu <= 0:
                continue
            rows.append((name, cpu, pct(cpu, denom)))

        pooled: dict[str, int] = {}
        for name, cpu, _ in rows:
            g = GROUP.get(name, name)
            pooled[g] = pooled.get(g, 0) + cpu

        print(f"\n### {tid}")
        print(f"Host CPU: {host_ns / 1e6:.2f} ms  |  Instrumented: {instr_ns / 1e6:.2f} ms")
        print(f"Tools: {fmt_tools(sess.get('tool_call_counts') or {})}")
        print(f"Turns: {sess.get('turns', '?')}  Wall: {sess.get('wall_s', 0):.1f}s")
        print(f"Category CPU (% of {denom_label} {denom / 1e6:.2f} ms):")

        for name, cpu, p in rows:
            print(f"  {name:18s}  {cpu / 1e6:8.2f} ms  {p:6.1f}%")

        if pooled:
            print("Pooled:")
            for g, cpu in sorted(pooled.items(), key=lambda x: -x[1]):
                print(f"  {g:6s}  {cpu / 1e6:8.2f} ms  {pct(cpu, denom):6.1f}%")


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "out"
    files = [
        ("LOCAL SEARCH (Windows footnote)", root / "real_agent_breakdown.json"),
        ("REMOTE SEARCH (Windows footnote)", root / "real_agent_breakdown_remote_search.json"),
    ]
    for label, path in files:
        if not path.exists():
            print(f"Missing {path}", file=sys.stderr)
            continue
        print_run(label, load(path))


if __name__ == "__main__":
    main()
