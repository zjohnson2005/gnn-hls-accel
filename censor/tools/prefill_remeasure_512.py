"""Re-measure L=512 at -r 3 so the five-point set shares one thermal regime."""
from __future__ import annotations

import json
import math
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "analysis" / "characterization" / "v3"
BENCH = Path(r"C:\Users\zjohn\Downloads\llamacpp-bin\bin\llama-bench.exe")
MODEL = Path(r"C:\Users\zjohn\Downloads\llamacpp-bin\qwen2.5-0.5b-instruct-q4_k_m.gguf")
EXPECTED_COMMIT = "1cbfd1988"
EXPECTED_BUILD = 10155


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def summarize(depth: int, samples: list[float]) -> dict:
    n = len(samples)
    mean = statistics.fmean(samples)
    stdev = statistics.stdev(samples) if n >= 2 else 0.0
    sem = stdev / math.sqrt(n)
    diffs = [samples[i + 1] - samples[i] for i in range(n - 1)]
    mono = n >= 3 and all(d < 0 for d in diffs)
    return {
        "depth": depth,
        "provenance": "measured_r3",
        "n_reps": n,
        "samples_ts": samples,
        "mean_ts": mean,
        "stdev_ts": stdev,
        "sem_ts": sem,
        "rel_sem": sem / mean,
        "monotone_decline": mono,
        "throttle_invalidates_mean": mono,
        "rep_deltas": diffs,
    }


def main() -> int:
    raw_path = OUT / "prefill_pp512_raw.json"
    err_path = OUT / "prefill_pp512_stderr.txt"
    cmd = [
        str(BENCH), "-m", str(MODEL),
        "-p", "512", "-n", "0", "-r", "3", "-t", "8", "-ngl", "0", "-o", "json",
    ]
    print("IDLE 30s before pp512...", flush=True)
    time.sleep(30)
    print("=== pp512 r=3 ===", flush=True)
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    err_path.write_text(proc.stderr.decode("utf-8", errors="replace"), encoding="utf-8")
    raw_path.write_text(proc.stdout.decode("utf-8", errors="replace"), encoding="utf-8")
    if proc.returncode != 0:
        return 1
    data = json.loads(raw_path.read_text(encoding="utf-8-sig").strip())
    if isinstance(data, dict):
        data = [data]
    row = data[0]
    if row.get("build_commit") != EXPECTED_COMMIT or int(row.get("build_number")) != EXPECTED_BUILD:
        print("HARNESS MISMATCH", flush=True)
        return 2
    samples = [float(x) for x in row["samples_ts"]]
    assert len(samples) == 3
    raw_path.write_text(json.dumps(row, indent=2), encoding="utf-8")
    summary = summarize(512, samples)
    print(summary, flush=True)

    art_path = OUT / "prefill_reps_v3.json"
    art = json.loads(art_path.read_text(encoding="utf-8"))
    art["depths"]["512"] = {
        "summary": summary,
        "build_commit": row.get("build_commit"),
        "build_number": row.get("build_number"),
        "samples_ns": row.get("samples_ns"),
        "samples_ts": row.get("samples_ts"),
        "avg_ts": row.get("avg_ts"),
        "stddev_ts": row.get("stddev_ts"),
        "wall_s": None,
        "idle_power_mw_before": None,
        "idle_power_mw_after": None,
        "idle_proc_perf_before": None,
        "idle_proc_perf_after": None,
        "telemetry_n": 0,
        "telemetry": None,
        "note": (
            "Re-measured after L=2048 remeasure (345 t/s) inverted vs stale v2 "
            "L=512 (280 t/s). Same cool-session regime required for a coherent set."
        ),
        "replaced_v2_samples_ts": [272.869, 281.745, 286.535],
        "remeasured_at": utc_now(),
    }
    invalid = [
        int(d)
        for d, e in art["depths"].items()
        if e["summary"].get("throttle_invalidates_mean")
    ]
    art["throttle_invalid_depths"] = invalid
    art["finished_at"] = utc_now()
    art_path.write_text(json.dumps(art, indent=2), encoding="utf-8")
    json.loads(art_path.read_text(encoding="utf-8"))
    print("updated", art_path, "throttle_invalid", invalid, flush=True)
    return 3 if summary["throttle_invalidates_mean"] else 0


if __name__ == "__main__":
    sys.exit(main())
