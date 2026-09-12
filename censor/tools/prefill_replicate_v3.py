#!/usr/bin/env python3
"""Item 1.0: replicate deep prefill points with thermal controls + verified JSON.

Harness must match original: llama-bench b10155 / 1cbfd1988, -n 0 -ngl 0 -t 8.
Writes analysis/characterization/v3/prefill_reps_v3.json after json.load verify.
"""

from __future__ import annotations

import json
import math
import random
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "characterization" / "v3"
BENCH = Path(r"C:\Users\zjohn\Downloads\llamacpp-bin\bin\llama-bench.exe")
CLI = Path(r"C:\Users\zjohn\Downloads\llamacpp-bin\bin\llama-cli.exe")
MODEL = Path(r"C:\Users\zjohn\Downloads\llamacpp-bin\qwen2.5-0.5b-instruct-q4_k_m.gguf")
EXPECTED_COMMIT = "1cbfd1988"
EXPECTED_BUILD = 10155

# Depths to re-measure at -r 3. 8192 replaces RECOVERED mean.
REPLICATE_DEPTHS = (8192, 32768, 65536)
REPS = 3
THREADS = 8
IDLE_BETWEEN_DEPTHS_S = 90.0
IDLE_BETWEEN_REPS_S = 45.0  # when interleaved
SEED = 20260728


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_harness_version() -> dict:
    if not BENCH.is_file():
        raise SystemExit(f"MISSING binary: {BENCH}")
    if not MODEL.is_file():
        raise SystemExit(f"MISSING model: {MODEL}")
    # llama-bench has no --version; sibling llama-cli reports the build.
    proc = subprocess.run(
        [str(CLI), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    ok = EXPECTED_COMMIT in blob and str(EXPECTED_BUILD) in blob
    return {
        "cli_version_blob": blob.strip().splitlines()[:8],
        "expected_commit": EXPECTED_COMMIT,
        "expected_build": EXPECTED_BUILD,
        "version_match": ok,
        "bench_path": str(BENCH),
        "model_path": str(MODEL),
    }


def _cim_power_mw() -> float | None:
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_PowerMeter -ErrorAction SilentlyContinue |"
                " Select-Object -First 1 -ExpandProperty CurrentReading)",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        s = (proc.stdout or "").strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def _proc_perf_pct() -> float | None:
    """Average % Processor Performance (effective clock proxy vs base)."""
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-Counter '\\Processor Information(*)\\% Processor Performance'"
                " -ErrorAction SilentlyContinue).CounterSamples |"
                " Where-Object { $_.InstanceName -notmatch '_Total|0,0' } |"
                " Measure-Object -Property CookedValue -Average |"
                " Select-Object -ExpandProperty Average",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        s = (proc.stdout or "").strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None


class TelemetrySampler:
    def __init__(self, interval_s: float = 5.0) -> None:
        self.interval_s = interval_s
        self.samples: list[dict] = []
        self._stop = threading.Event()
        self._thr: threading.Thread | None = None

    def start(self) -> None:
        self.samples = []
        self._stop.clear()
        self._thr = threading.Thread(target=self._run, daemon=True)
        self._thr.start()

    def stop(self) -> list[dict]:
        self._stop.set()
        if self._thr is not None:
            self._thr.join(timeout=30)
        return list(self.samples)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.samples.append(
                {
                    "t": utc_now(),
                    "power_mw": _cim_power_mw(),
                    "proc_perf_pct": _proc_perf_pct(),
                }
            )
            self._stop.wait(self.interval_s)


def run_one_depth(depth: int, reps: int, out_json: Path, stderr_path: Path) -> dict:
    """Run llama-bench for one depth; -o json written to disk, then verified."""
    cmd = [
        str(BENCH),
        "-m",
        str(MODEL),
        "-p",
        str(depth),
        "-n",
        "0",
        "-r",
        str(reps),
        "-t",
        str(THREADS),
        "-ngl",
        "0",
        "-o",
        "json",
    ]
    # Redirect JSON to file via Python (PowerShell UTF-16 trap).
    telem = TelemetrySampler(interval_s=5.0)
    idle_power_before = _cim_power_mw()
    idle_perf_before = _proc_perf_pct()
    t0 = time.perf_counter()
    telem.start()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=max(3600, int(depth / 30) * reps + 1800),
        )
    finally:
        samples_telem = telem.stop()
    wall_s = time.perf_counter() - t0
    stderr = proc.stderr.decode("utf-8", errors="replace")
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr_path.write_text(stderr, encoding="utf-8")
    # Prefer writing stdout JSON to disk, then parse FROM DISK.
    out_json.write_text(stdout, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(
            f"llama-bench rc={proc.returncode} depth={depth}: {stderr[-800:]}"
        )
    raw = out_json.read_text(encoding="utf-8-sig").strip()
    data = json.loads(raw)  # verify parse BEFORE moving on
    if isinstance(data, dict):
        data = [data]
    if not data:
        raise RuntimeError(f"empty JSON for depth {depth}")
    row = data[0]
    commit = row.get("build_commit")
    build = row.get("build_number")
    if commit != EXPECTED_COMMIT or int(build) != EXPECTED_BUILD:
        raise SystemExit(
            f"HARNESS MISMATCH at depth {depth}: got build {build} commit {commit}; "
            f"expected {EXPECTED_BUILD} / {EXPECTED_COMMIT}. STOP."
        )
    samples_ts = row.get("samples_ts") or []
    samples_ns = row.get("samples_ns") or []
    if len(samples_ts) != reps:
        raise RuntimeError(
            f"samples_ts length {len(samples_ts)} != {reps} at depth {depth}"
        )
    if len(samples_ns) != reps:
        raise RuntimeError(
            f"samples_ns length {len(samples_ns)} != {reps} at depth {depth}"
        )
    # Re-write pretty canonical single-object JSON after verify.
    out_json.write_text(json.dumps(row, indent=2), encoding="utf-8")
    idle_power_after = _cim_power_mw()
    idle_perf_after = _proc_perf_pct()
    return {
        "depth": depth,
        "row": row,
        "wall_s": wall_s,
        "idle_power_mw_before": idle_power_before,
        "idle_power_mw_after": idle_power_after,
        "idle_proc_perf_before": idle_perf_before,
        "idle_proc_perf_after": idle_perf_after,
        "telemetry": samples_telem,
        "cmd": cmd,
    }


def summarize_depth(depth: int, samples_ts: list[float], provenance: str) -> dict:
    n = len(samples_ts)
    mean = statistics.fmean(samples_ts)
    stdev = statistics.stdev(samples_ts) if n >= 2 else 0.0
    sem = stdev / math.sqrt(n) if n >= 1 else float("nan")
    rel_sem = (sem / mean) if mean else float("nan")
    # Monotone decline => throttling, not noise.
    diffs = [samples_ts[i + 1] - samples_ts[i] for i in range(n - 1)]
    monotone_down = n >= 3 and all(d < 0 for d in diffs)
    return {
        "depth": depth,
        "provenance": provenance,
        "n_reps": n,
        "samples_ts": samples_ts,
        "mean_ts": mean,
        "stdev_ts": stdev,
        "sem_ts": sem,
        "rel_sem": rel_sem,
        "monotone_decline": monotone_down,
        "throttle_invalidates_mean": monotone_down,
        "rep_deltas": diffs,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ver = check_harness_version()
    print("HARNESS:", json.dumps(ver, indent=2), flush=True)
    if not ver["version_match"]:
        print("STOP: harness version does not match expected b10155 / 1cbfd1988", flush=True)
        return 2

    # Interleave strategy: randomize depth ORDER (not ascending), each depth
    # still uses -r 3 in one invocation (same as original harness per depth).
    # Cool-down between depths. Within-depth throttle check on samples_ts.
    rng = random.Random(SEED)
    order = list(REPLICATE_DEPTHS)
    rng.shuffle(order)
    print(f"DEPTH ORDER (seed={SEED}): {order}", flush=True)

    # Procedural cool-down note start.
    protocol = {
        "seed": SEED,
        "depth_order": order,
        "reps_per_depth": REPS,
        "idle_between_depths_s": IDLE_BETWEEN_DEPTHS_S,
        "flags": {"n": 0, "ngl": 0, "t": THREADS, "r": REPS},
        "thermal_control": (
            "procedural + measured: randomized depth order (not ascending); "
            f"{IDLE_BETWEEN_DEPTHS_S}s idle between depth blocks; "
            "Win32_PowerMeter CurrentReading (mW) and % Processor Performance "
            "sampled every 5s during each block. Within-block monotone decline "
            "of samples_ts => throttle invalidates mean."
        ),
        "started_at": utc_now(),
    }

    results: list[dict] = []
    for i, depth in enumerate(order):
        if i > 0:
            print(f"IDLE cool-down {IDLE_BETWEEN_DEPTHS_S}s ...", flush=True)
            time.sleep(IDLE_BETWEEN_DEPTHS_S)
        print(f"=== pp{depth} r={REPS} ===", flush=True)
        raw_path = OUT / f"prefill_pp{depth}_raw.json"
        err_path = OUT / f"prefill_pp{depth}_stderr.txt"
        block = run_one_depth(depth, REPS, raw_path, err_path)
        row = block["row"]
        samples = [float(x) for x in row["samples_ts"]]
        summary = summarize_depth(depth, samples, "measured_r3")
        if summary["throttle_invalidates_mean"]:
            print(
                f"THROTTLE DETECTED at depth {depth}: samples={samples}. "
                "Mean INVALID per 1.0c.",
                flush=True,
            )
        print(
            f"  mean={summary['mean_ts']:.4f} stdev={summary['stdev_ts']:.4f} "
            f"SEM={summary['sem_ts']:.4f} relSEM={100*summary['rel_sem']:.2f}% "
            f"monotone_down={summary['monotone_decline']}",
            flush=True,
        )
        results.append({**block, "summary": summary})

    # Also attach original shallow points (512, 2048) from v2 for consolidated file.
    v2 = ROOT / "analysis" / "characterization" / "v2" / "prefill_bench_raw.json"
    shallow: list[dict] = []
    if v2.is_file():
        v2data = json.loads(v2.read_text(encoding="utf-8-sig"))
        for r in v2data:
            d = int(r.get("n_prompt") or 0)
            if d in (512, 2048) and r.get("samples_ts") and len(r["samples_ts"]) >= 3:
                samples = [float(x) for x in r["samples_ts"]]
                shallow.append(
                    {
                        "depth": d,
                        "row": r,
                        "summary": summarize_depth(d, samples, "measured_v2_r3"),
                        "note": "carried from v2 prefill_bench_raw.json; not re-run in 1.0",
                    }
                )

    # Recovered 8192 metadata (replaced if re-run succeeded).
    recovered_8192 = {
        "depth": 8192,
        "provenance": "RECOVERED",
        "mean_ts": 185.37,
        "stdev_ts": 6.53,
        "sem_ts": 6.53 / math.sqrt(3),
        "rel_sem": (6.53 / math.sqrt(3)) / 185.37,
        "note": (
            "First-run stderr markdown only; sample vector lost to mid-JSON-write kill. "
            "Superseded by measured_r3 in this artifact if present."
        ),
    }

    by_depth = {int(x["summary"]["depth"]): x for x in results}
    for s in shallow:
        by_depth[int(s["depth"])] = s

    # Throttle gate: if any replicated depth invalid, exit non-zero.
    invalid = [
        d
        for d, x in by_depth.items()
        if d in REPLICATE_DEPTHS and x["summary"].get("throttle_invalidates_mean")
    ]

    artifact = {
        "protocol": protocol,
        "harness": ver,
        "finished_at": utc_now(),
        "recovered_8192_metadata": recovered_8192,
        "depths": {
            str(d): {
                "summary": by_depth[d]["summary"],
                "build_commit": by_depth[d]["row"].get("build_commit"),
                "build_number": by_depth[d]["row"].get("build_number"),
                "samples_ns": by_depth[d]["row"].get("samples_ns"),
                "samples_ts": by_depth[d]["row"].get("samples_ts"),
                "avg_ts": by_depth[d]["row"].get("avg_ts"),
                "stddev_ts": by_depth[d]["row"].get("stddev_ts"),
                "wall_s": by_depth[d].get("wall_s"),
                "idle_power_mw_before": by_depth[d].get("idle_power_mw_before"),
                "idle_power_mw_after": by_depth[d].get("idle_power_mw_after"),
                "idle_proc_perf_before": by_depth[d].get("idle_proc_perf_before"),
                "idle_proc_perf_after": by_depth[d].get("idle_proc_perf_after"),
                "telemetry_n": len(by_depth[d].get("telemetry") or []),
                "telemetry": by_depth[d].get("telemetry"),
                "note": by_depth[d].get("note"),
            }
            for d in sorted(by_depth)
        },
        "throttle_invalid_depths": invalid,
        "parse_verified": True,
    }

    out_path = OUT / "prefill_reps_v3.json"
    out_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    # Verify the written artifact parses and samples length == 3 for replicates.
    check = json.loads(out_path.read_text(encoding="utf-8"))
    for d in REPLICATE_DEPTHS:
        entry = check["depths"][str(d)]
        st = entry["samples_ts"]
        assert isinstance(st, list) and len(st) == 3, (d, st)
        assert len(entry["samples_ns"]) == 3, d
    print(f"WROTE {out_path} (parse-verified)", flush=True)

    if invalid:
        print(f"STOP: throttle at depths {invalid}; do not average through it.", flush=True)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
