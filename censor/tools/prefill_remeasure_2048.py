"""Re-measure L=2048 at -r 3 after v2 carry-forward failed throttle check."""
from __future__ import annotations

import json
import math
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "characterization" / "v3"
BENCH = Path(r"C:\Users\zjohn\Downloads\llamacpp-bin\bin\llama-bench.exe")
MODEL = Path(r"C:\Users\zjohn\Downloads\llamacpp-bin\qwen2.5-0.5b-instruct-q4_k_m.gguf")
EXPECTED_COMMIT = "1cbfd1988"
EXPECTED_BUILD = 10155


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def summarize(samples: list[float]) -> dict:
    n = len(samples)
    mean = statistics.fmean(samples)
    stdev = statistics.stdev(samples) if n >= 2 else 0.0
    sem = stdev / math.sqrt(n)
    diffs = [samples[i + 1] - samples[i] for i in range(n - 1)]
    mono = n >= 3 and all(d < 0 for d in diffs)
    return {
        "depth": 2048,
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
    raw_path = OUT / "prefill_pp2048_raw.json"
    err_path = OUT / "prefill_pp2048_stderr.txt"
    cmd = [
        str(BENCH), "-m", str(MODEL),
        "-p", "2048", "-n", "0", "-r", "3", "-t", "8", "-ngl", "0", "-o", "json",
    ]
    print("IDLE cool-down 45s before pp2048 remeasure...", flush=True)
    time.sleep(45)
    print("=== pp2048 r=3 ===", flush=True)
    proc = subprocess.run(cmd, capture_output=True, timeout=600)
    err_path.write_text(proc.stderr.decode("utf-8", errors="replace"), encoding="utf-8")
    raw_path.write_text(proc.stdout.decode("utf-8", errors="replace"), encoding="utf-8")
    if proc.returncode != 0:
        print("FAIL", proc.returncode, flush=True)
        return 1
    data = json.loads(raw_path.read_text(encoding="utf-8-sig").strip())
    if isinstance(data, dict):
        data = [data]
    row = data[0]
    if row.get("build_commit") != EXPECTED_COMMIT or int(row.get("build_number")) != EXPECTED_BUILD:
        print("HARNESS MISMATCH", row.get("build_commit"), row.get("build_number"), flush=True)
        return 2
    samples = [float(x) for x in row["samples_ts"]]
    assert len(samples) == 3
    raw_path.write_text(json.dumps(row, indent=2), encoding="utf-8")
    summary = summarize(samples)
    print(summary, flush=True)

    art_path = OUT / "prefill_reps_v3.json"
    art = json.loads(art_path.read_text(encoding="utf-8"))
    art["depths"]["2048"] = {
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
            "Re-measured 2026-07-28 after v2 carry-forward samples failed "
            "monotone-decline throttle check."
        ),
        "replaced_v2_samples_ts": [262.912, 255.589, 247.183],
        "remeasured_at": utc_now(),
    }
    # Keep throttle list honest for all depths in artifact.
    invalid = [
        int(d)
        for d, e in art["depths"].items()
        if e["summary"].get("throttle_invalidates_mean")
    ]
    art["throttle_invalid_depths"] = invalid
    art["finished_at"] = utc_now()
    art_path.write_text(json.dumps(art, indent=2), encoding="utf-8")
    check = json.loads(art_path.read_text(encoding="utf-8"))
    assert len(check["depths"]["2048"]["samples_ts"]) == 3
    print("updated", art_path, "throttle_invalid", invalid, flush=True)
    return 3 if summary["throttle_invalidates_mean"] else 0


if __name__ == "__main__":
    sys.exit(main())
