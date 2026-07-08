"""Confirm OpenBLAS native threads are visible in /proc with a comm name,
and show per-seed LH-01 wall vs host CPU correlation from the v3 artifact."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def list_threads() -> dict[int, str]:
    out = {}
    for entry in os.listdir("/proc/self/task"):
        try:
            tid = int(entry)
        except ValueError:
            continue
        try:
            comm = Path(f"/proc/self/task/{tid}/comm").read_text().strip()
        except OSError:
            comm = "?"
        out[tid] = comm
    return out


def main() -> None:
    import numpy as np

    print("threads before matmul:")
    for tid, comm in sorted(list_threads().items()):
        print(f"  {tid}: {comm}")

    mat = np.random.default_rng(0).standard_normal((100_000, 384)).astype(np.float32)
    q = np.random.default_rng(1).standard_normal(384).astype(np.float32)
    _ = mat @ q
    time.sleep(0.1)

    print("\nthreads after matmul:")
    for tid, comm in sorted(list_threads().items()):
        print(f"  {tid}: {comm}")

    # Per-seed LH-01 wall vs host CPU (spin hypothesis: host CPU ~ wall)
    art = Path("apu_characterization/out/replication_remote_search_v3.json")
    data = json.loads(art.read_text(encoding="utf-8"))
    print("\nLH-01 per seed (v3):")
    print(f"{'seed':>4} {'wall_s':>8} {'host_ms':>9} {'host/wall (cores)':>18}")
    for a in data["per_seed_artifacts"]:
        seed = a["config"]["seed"]
        for s in a["run"]["per_session"]:
            if s["task_id"] == "LH-01":
                w = s["wall_s"]
                h = s["process_cpu_ns"] / 1e6
                print(f"{seed:>4} {w:>8.1f} {h:>9.1f} {h / 1000 / w:>18.2f}")

    v1 = Path("apu_characterization/out/replication_remote_search.json")
    d1 = json.loads(v1.read_text(encoding="utf-8"))
    print("\nLH-01 per seed (v1):")
    for a in d1["per_seed_artifacts"]:
        seed = a["config"]["seed"]
        for s in a["run"]["per_session"]:
            if s["task_id"] == "LH-01":
                w = s["wall_s"]
                h = s["process_cpu_ns"] / 1e6
                print(f"{seed:>4} {w:>8.1f} {h:>9.1f} {h / 1000 / w:>18.2f}")


if __name__ == "__main__":
    main()
