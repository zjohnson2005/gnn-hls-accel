"""Bare-metal comparison: WSL2 v3.1 baseline vs native-Linux validation subset.

Reads:
  out/replication_remote_search_v3.json           (baseline, platform wsl2)
  out/bare_metal_validation_<label>.json           (native subset)

Writes out/bare_metal_comparison.md with three tables and exactly one verdict:
  AGREEMENT        composition platform-robust; sweep may run on either platform
  SCHEDULING DELTA c=1 composition stands; sweep MUST run on native Linux
  DISAGREEMENT     stop and diagnose before any sweep planning continues

All numbers are computed from the two artifacts; nothing is hand-typed.

Run as a script (the tools package has a circular import under -m):
  python apu_characterization/tools/bare_metal_compare.py
      [--native apu_characterization/out/bare_metal_validation_native_linux.json]
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

BASELINE = Path("apu_characterization/out/replication_remote_search_v3.json")
OUT_MD = Path("apu_characterization/out/bare_metal_comparison.md")

SUBSET_TASKS = ("LH-01", "RH-01", "FO-01", "RE-01", "CH-01", "LH-02")
SHARE_CATEGORIES = (
    "TOOL_COMPUTE",
    "THREADPOOL",
    "ORCH_SETUP",
    "ORCH_DISPATCH",
    "CLIENT_HTTP",
    "HTTP_CLIENT",
    "FRAMEWORK",
    "TOKENIZATION",
    "RESIDUAL_UNATTRIBUTED",
)
SCHEDULING_CATEGORIES = ("THREADPOOL", "FRAMEWORK", "ORCH_DISPATCH")

MAJOR_SHARE_PP = 5.0
SHARE_TOLERANCE_PP = 10.0
HOST_CPU_TOLERANCE_REL = 0.30


def _default_native_path() -> Path:
    for label in ("native_linux", "native_vm"):
        p = Path(f"apu_characterization/out/bare_metal_validation_{label}.json")
        if p.is_file():
            return p
    raise SystemExit(
        "no native artifact found: run bare_metal_validation on the native box first"
    )


def extract_baseline(data: dict[str, Any]) -> dict[str, Any]:
    """Per-task medians (host CPU, LLM wait, category shares, residual) from v3.1."""
    per_task_vals: dict[str, dict[str, list[float]]] = {}
    residuals: dict[str, list[float]] = {}
    for art in data["per_seed_artifacts"]:
        ptw = (art.get("per_task_wall_cpu") or {}).get("per_task") or {}
        for tid, row in ptw.items():
            if tid not in SUBSET_TASKS:
                continue
            host = row["host_cpu_ms"] or 1.0
            d = per_task_vals.setdefault(
                tid, {"host_cpu_ms": [], "llm_wait_s": [], **{c: [] for c in SHARE_CATEGORIES}}
            )
            d["host_cpu_ms"].append(row["host_cpu_ms"])
            d["llm_wait_s"].append(row.get("llm_io_wait_s") or 0.0)
            by = row.get("cpu_by_category_ms") or {}
            for cat in SHARE_CATEGORIES:
                d[cat].append(100 * by.get(cat, 0) / host)
        for sess in art["run"]["per_session"]:
            tid = sess.get("task_id")
            if tid not in SUBSET_TASKS:
                continue
            host_ns = sess.get("process_cpu_ns") or 0
            res_ns = (sess.get("provenance") or {}).get("residual", 0)
            if host_ns:
                residuals.setdefault(tid, []).append(100 * res_ns / host_ns)

    out: dict[str, Any] = {}
    for tid, d in per_task_vals.items():
        out[tid] = {
            "n": len(d["host_cpu_ms"]),
            "host_cpu_ms": statistics.median(d["host_cpu_ms"]),
            "llm_wait_s": statistics.median(d["llm_wait_s"]),
            "share_pct_by_category": {
                cat: statistics.median(d[cat]) for cat in SHARE_CATEGORIES
            },
            "residual_provenance_pct": statistics.median(residuals.get(tid, [0.0])),
        }
    return out


def extract_native(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tid, e in data["per_task_medians"].items():
        out[tid] = {
            "n": e["n"],
            "host_cpu_ms": e["host_cpu_ms"],
            "llm_wait_s": e["llm_wait_s"],
            "share_pct_by_category": dict(e["share_pct_by_category"]),
            "residual_provenance_pct": e["residual_provenance_pct"],
        }
    return out


def compute_verdict(
    base: dict[str, Any], native: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    sched_violations: list[str] = []
    nonsched_violations: list[str] = []
    host_violations: list[str] = []
    max_delta_pp = 0.0
    tasks = [t for t in SUBSET_TASKS if t in base and t in native]

    for tid in tasks:
        b, n = base[tid], native[tid]
        b_host, n_host = b["host_cpu_ms"], n["host_cpu_ms"]
        if b_host > 0:
            rel = abs(n_host - b_host) / b_host
            if rel > HOST_CPU_TOLERANCE_REL:
                host_violations.append(
                    f"{tid}: host CPU {b_host:.1f} ms (wsl2) vs {n_host:.1f} ms "
                    f"(native), {100 * rel:.0f}% relative delta"
                )
        for cat in SHARE_CATEGORIES:
            if cat == "RESIDUAL_UNATTRIBUTED":
                continue
            bs = b["share_pct_by_category"].get(cat, 0.0)
            ns = n["share_pct_by_category"].get(cat, 0.0)
            if max(bs, ns) < MAJOR_SHARE_PP:
                continue
            delta = abs(ns - bs)
            max_delta_pp = max(max_delta_pp, delta)
            if delta > SHARE_TOLERANCE_PP:
                msg = f"{tid}/{cat}: {bs:.1f} pp (wsl2) vs {ns:.1f} pp (native)"
                if cat in SCHEDULING_CATEGORIES:
                    sched_violations.append(msg)
                else:
                    nonsched_violations.append(msg)

    if nonsched_violations:
        verdict = "DISAGREEMENT"
    elif sched_violations or host_violations:
        verdict = "SCHEDULING DELTA"
    else:
        verdict = "AGREEMENT"
    return verdict, {
        "tasks_compared": tasks,
        "max_major_share_delta_pp": round(max_delta_pp, 1),
        "scheduling_violations": sched_violations,
        "nonscheduling_violations": nonsched_violations,
        "host_cpu_violations": host_violations,
    }


def _verdict_block(verdict: str, detail: dict[str, Any], native_label: str) -> list[str]:
    lines = [f"## Verdict: {verdict}", ""]
    if verdict == "AGREEMENT":
        lines += [
            "Composition is platform-robust; WSL2 vs native deltas were "
            f"{detail['max_major_share_delta_pp']} pp max on major categories, "
            "and absolute host CPU agreed within 30% on every task.",
            "",
            "**Sweep platform decision:** the WSL2 caveat is retired for "
            "composition claims. The concurrency sweep may run on whichever "
            "machine is more practical, stated as validated.",
            "",
            "**Limitations sentence for the main report:** "
            "\"Platform validation on "
            f"{native_label} reproduced the WSL2 composition within "
            f"{detail['max_major_share_delta_pp']} pp on all major categories; "
            "the bare-metal caveat is retired for composition claims.\"",
        ]
    elif verdict == "SCHEDULING DELTA":
        lines += [
            "The c=1 composition stands, but scheduling-sensitive categories "
            "(THREADPOOL, FRAMEWORK, ORCH_DISPATCH) or absolute host CPU shifted "
            "materially between platforms:",
            "",
        ]
        for v in detail["scheduling_violations"] + detail["host_cpu_violations"]:
            lines.append(f"- {v}")
        lines += [
            "",
            "**Sweep platform decision:** the concurrency sweep MUST run on "
            "native Linux. WSL2-era contention numbers must be bounded using the "
            "direction of bias shown above.",
            "",
            "**Limitations sentence for the main report:** "
            "\"Platform validation showed WSL2 shifts scheduling-sensitive "
            "categories relative to native Linux (see bare_metal_comparison.md); "
            "c=1 composition claims stand, and the concurrency sweep runs on "
            "native Linux.\"",
            "",
            "**Sweep-spec update required:** add a platform requirement "
            "(native Linux) to the concurrency sweep before scheduling it.",
        ]
    else:
        lines += [
            "Broad composition shifts beyond 10 pp on non-scheduling categories:",
            "",
        ]
        for v in detail["nonscheduling_violations"]:
            lines.append(f"- {v}")
        lines += [
            "",
            "**Sweep platform decision:** STOP. Diagnose kernel timer "
            "granularity, Python build, and BLAS linkage before any sweep "
            "planning continues. Something other than the scheduler differs.",
        ]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, default=None)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    args = parser.parse_args()

    native_path = args.native or _default_native_path()
    base_data = json.loads(args.baseline.read_text(encoding="utf-8"))
    native_data = json.loads(native_path.read_text(encoding="utf-8"))

    if native_data.get("result_validity") != "publishable":
        print(
            f"WARNING: native artifact validity is "
            f"{native_data.get('result_validity')!r}; comparison is exploratory only"
        )

    native_label = native_data["config"]["platform_label"]
    base = extract_baseline(base_data)
    native = extract_native(native_data)
    verdict, detail = compute_verdict(base, native)

    lines = [
        "# Bare-metal validation: WSL2 v3.1 vs native comparison",
        "",
        f"- baseline: `{args.baseline.name}` "
        f"(platform wsl2, commit `{base_data['git']['commit'][:8]}`)",
        f"- native:   `{native_path.name}` "
        f"(platform {native_label}, commit `{native_data['git']['commit'][:8]}`, "
        f"kernel `{native_data['config']['kernel']}`)",
        f"- native validity: {native_data.get('result_validity')}",
        "",
        "## Table 1: per-task medians side by side",
        "",
        "| task | host CPU ms (wsl2 / native / rel delta) | "
        "LLM wait s (wsl2 / native) | category | share pp (wsl2 / native / abs delta) |",
        "|------|------------------------------------------|"
        "----------------------------|----------|----------------------------------------|",
    ]
    for tid in detail["tasks_compared"]:
        b, n = base[tid], native[tid]
        rel = (
            f"{100 * (n['host_cpu_ms'] - b['host_cpu_ms']) / b['host_cpu_ms']:+.0f}%"
            if b["host_cpu_ms"]
            else "n/a"
        )
        first = True
        for cat in SHARE_CATEGORIES:
            bs = b["share_pct_by_category"].get(cat, 0.0)
            ns = n["share_pct_by_category"].get(cat, 0.0)
            if max(bs, ns) < 1.0:
                continue
            host_cell = (
                f"{b['host_cpu_ms']:.1f} / {n['host_cpu_ms']:.1f} / {rel}"
                if first
                else ""
            )
            llm_cell = (
                f"{b['llm_wait_s']:.2f} / {n['llm_wait_s']:.2f}" if first else ""
            )
            lines.append(
                f"| {tid if first else ''} | {host_cell} | {llm_cell} | "
                f"{cat} | {bs:.1f} / {ns:.1f} / {abs(ns - bs):.1f} |"
            )
            first = False

    lines += [
        "",
        "## Table 2: scheduling-sensitive focus (THREADPOOL, FRAMEWORK, ORCH_DISPATCH)",
        "",
        "| task | category | wsl2 share pp | native share pp | delta pp |",
        "|------|----------|---------------|-----------------|----------|",
    ]
    for tid in detail["tasks_compared"]:
        for cat in SCHEDULING_CATEGORIES:
            bs = base[tid]["share_pct_by_category"].get(cat, 0.0)
            ns = native[tid]["share_pct_by_category"].get(cat, 0.0)
            mark = " **(headline)**" if tid == "RH-01" and cat == "THREADPOOL" else ""
            lines.append(
                f"| {tid}{mark} | {cat} | {bs:.1f} | {ns:.1f} | {ns - bs:+.1f} |"
            )

    lines += [
        "",
        "## Table 3: instrument health",
        "",
        "| task | wsl2 residual % | native residual % |",
        "|------|-----------------|-------------------|",
    ]
    for tid in detail["tasks_compared"]:
        lines.append(
            f"| {tid} | {base[tid]['residual_provenance_pct']:.1f} | "
            f"{native[tid]['residual_provenance_pct']:.1f} |"
        )
    lines += [
        "",
        f"- native timer overhead: "
        f"{native_data.get('timer_overhead_ns_per_pair')} ns per timed pair",
        f"- native loadavg (1-min) start {native_data.get('loadavg_start')}, "
        f"end {native_data.get('loadavg_end')}; per-session records in the "
        "native artifact",
        "- timer resolution self-test and instrumentation unit tests are "
        "run-gates on the native box; a native artifact exists only if they passed",
    ]
    if native_data.get("smoke_c5"):
        s = native_data["smoke_c5"]
        lines += [
            "",
            f"- smoke_c5 (excluded from statistics): batch host CPU "
            f"{s['batch_host_cpu_ms']} ms, residual fraction {s['residual_fraction']}",
        ]

    lines += [""] + _verdict_block(verdict, detail, native_label) + [""]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"md: {OUT_MD}")
    print(f"verdict: {verdict}")
    if detail["scheduling_violations"] or detail["nonscheduling_violations"]:
        for v in detail["scheduling_violations"] + detail["nonscheduling_violations"]:
            print(f"  violation: {v}")


if __name__ == "__main__":
    main()
