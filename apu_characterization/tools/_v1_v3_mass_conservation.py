"""v1 <-> v3 mass-conservation table: where did each CPU category's mass go?

Compares per-category CPU totals (pooled across sessions, per seed, then
median across seeds) between the v1-era replication artifact and the v3
thread-identity artifact. Answers: does v1 reconcile mass reappear as v3
THREADPOOL, and what owns the +delta in total host CPU?
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

OUT = Path("apu_characterization/out")
V1 = OUT / "replication_remote_search.json"
V3 = OUT / "replication_remote_search_v3.json"


def med(vals):
    return statistics.median(vals) if vals else 0.0


def per_seed_category_ms(data) -> tuple[dict[str, list[float]], list[float], list[float]]:
    """Per-category pooled CPU ms per seed + batch host CPU ms per seed."""
    cat_ms: dict[str, list[float]] = defaultdict(list)
    host_ms: list[float] = []
    recon_ms: list[float] = []
    for art in data["per_seed_artifacts"]:
        run = art["run"]
        pc = run.get("per_category", {})
        for k, v in pc.items():
            cat_ms[k].append(v.get("cpu_ns", 0) / 1e6)
        host_ms.append(sum(s.get("process_cpu_ns", 0) for s in run["per_session"]) / 1e6)
        recon_ms.append(sum(s.get("reconcile_cpu_ns", 0) for s in run["per_session"]) / 1e6)
    return cat_ms, host_ms, recon_ms


def main() -> None:
    v1 = json.loads(V1.read_text(encoding="utf-8"))
    v3 = json.loads(V3.read_text(encoding="utf-8"))

    v1_iv = v1["per_seed_artifacts"][0]["config"].get("instr_version")
    v3_iv = v3["per_seed_artifacts"][0]["config"].get("instr_version")
    print(f"v1 artifact: {V1.name}  instr_version={v1_iv}  validity={v1.get('result_validity')}")
    print(f"v3 artifact: {V3.name}  instr_version={v3_iv}  validity={v3.get('result_validity')}")

    c1, h1, r1 = per_seed_category_ms(v1)
    c3, h3, r3 = per_seed_category_ms(v3)

    print(f"\nBatch host CPU ms (median): v1={med(h1):.1f}  v3={med(h3):.1f}  "
          f"delta={med(h3) - med(h1):+.1f} ({100 * (med(h3) / med(h1) - 1):+.1f}%)")
    print(f"Session reconcile ms (median): v1={med(r1):.1f}  v3={med(r3):.1f}")

    cats = sorted(set(c1) | set(c3), key=lambda k: -(med(c3.get(k, [])) or 0))
    print(f"\n{'Category':<24} {'v1 ms':>10} {'v3 ms':>10} {'delta':>10}")
    print("-" * 58)
    tot1 = tot3 = 0.0
    for k in cats:
        m1, m3 = med(c1.get(k, [])), med(c3.get(k, []))
        if m1 < 0.5 and m3 < 0.5:
            continue
        tot1 += m1
        tot3 += m3
        print(f"{k:<24} {m1:>10.1f} {m3:>10.1f} {m3 - m1:>+10.1f}")
    print("-" * 58)
    print(f"{'sum shown':<24} {tot1:>10.1f} {tot3:>10.1f} {tot3 - tot1:>+10.1f}")

    # v1 mass that lived outside categories (reconcile gap booked to session):
    print("\nConservation check:")
    v1_accounted = tot1 + med(r1)
    print(f"  v1 categories + reconcile = {tot1:.1f} + {med(r1):.1f} = {v1_accounted:.1f} ms"
          f"  (vs host {med(h1):.1f})")
    print(f"  v3 categories             = {tot3:.1f} ms  (vs host {med(h3):.1f})")
    print(f"  unexplained new CPU in v3 vs v1-accounted: {med(h3) - v1_accounted:+.1f} ms")

    # Workload drift check: per-task host CPU + tool call volume.
    def per_task(data):
        host: dict[str, list[float]] = defaultdict(list)
        wall: dict[str, list[float]] = defaultdict(list)
        calls: dict[str, list[int]] = defaultdict(list)
        trim: dict[str, list[float]] = defaultdict(list)
        for art in data["per_seed_artifacts"]:
            for s in art["run"]["per_session"]:
                tid = s["task_id"]
                host[tid].append(s.get("process_cpu_ns", 0) / 1e6)
                wall[tid].append(s.get("wall_s", 0.0))
                calls[tid].append(sum((s.get("tool_call_counts") or {}).values()))
                trim[tid].append(s.get("parallel_cpu_trim_ns", 0) / 1e6)
        return host, wall, calls, trim

    ht1, w1, tc1, tr1 = per_task(v1)
    ht3, w3, tc3, tr3 = per_task(v3)
    tasks = sorted(set(ht1) | set(ht3), key=lambda t: -(med(ht3.get(t, [])) or 0))
    print(f"\n{'Task':<8} {'v1 host ms':>11} {'v3 host ms':>11} {'delta':>9} "
          f"{'v1 calls':>8} {'v3 calls':>8} {'v1 wall':>8} {'v3 wall':>8} {'v3 trim ms':>11}")
    print("-" * 96)
    for t in tasks:
        print(f"{t:<8} {med(ht1.get(t, [])):>11.1f} {med(ht3.get(t, [])):>11.1f} "
              f"{med(ht3.get(t, [])) - med(ht1.get(t, [])):>+9.1f} "
              f"{med(tc1.get(t, [])):>8.1f} {med(tc3.get(t, [])):>8.1f} "
              f"{med(w1.get(t, [])):>8.1f} {med(w3.get(t, [])):>8.1f} "
              f"{med(tr3.get(t, [])):>11.1f}")


if __name__ == "__main__":
    main()
