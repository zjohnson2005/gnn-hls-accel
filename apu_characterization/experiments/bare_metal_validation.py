"""Bare-metal validation: matched c=1 subset vs the WSL2 v3.1 baseline.

Runs a 6-task, n=3-seed subset of the v3.1 replication configuration on a
native-Linux box (or labeled VM) to measure how much of the v3.1 CPU
composition is WSL2-specific. Scheduling-sensitive categories (THREADPOOL,
FRAMEWORK, ORCH_DISPATCH) are the focus; the verdict gates which platform
the concurrency sweep runs on.

Task subset (spans the composition space):
  LH-01  highest CPU, retrieve + ORCH_dispatch mix
  RH-01  THREADPOOL-heavy, the key scheduling-sensitive row
  FO-01  fan-out residual canary
  RE-01  ORCH-dominated, retry-storm behavior check
  CH-01  light ORCH_setup-dominated control
  LH-02  no-tool floor, timer behavior at the small end

Load hygiene: refuses to start when 1-min loadavg exceeds 1.0; aborts if it
exceeds 2.0 mid-run; records loadavg before and after every session.

Run (native box, publishable):
  export OPENAI_API_KEY=sk-...
  python -m apu_characterization.experiments.bare_metal_validation \\
      --backend openai --seeds 0,1,2

Debug plumbing check (any platform, no API key):
  python -m apu_characterization.experiments.bare_metal_validation \\
      --backend scripted --seeds 0 --allow-dirty

Optional contention smoke signal (NOT a sweep point, excluded from stats):
  ... --smoke-c5

Artifacts: out/bare_metal_validation_<platform_label>.json / .md
Compare:   python apu_characterization/tools/bare_metal_compare.py
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..audit import apply_audit_to_artifact
from ..env_pin import assert_blas_pinned
from ..harness.runner import _os_times_delta, _os_times_snapshot, _warm_shared_state
from ..instr import RunAccumulator, install_gc_hooks, measure_timer_overhead_ns
from ..profiles import LOCALITY_ABLATION_PROFILE
from ..setup_validate import load_and_validate
from ..tasks import task_by_id
from ..tools import LOCALITY_REMOTE, reset_tool_locality, set_tool_locality
from ..validity import validity_banner, validity_for_real_agent_backend
from .real_agent_breakdown import (
    RESIDUAL_LIMIT,
    _env_info,
    _git_state,
    _load_setup_digest,
    _require_langgraph,
    build_langchain_tools,
    run_real_batch,
    run_real_session,
)

SUBSET_TASKS = ("LH-01", "RH-01", "FO-01", "RE-01", "CH-01", "LH-02")
OUT_DIR = Path("apu_characterization/out")
STEM = "bare_metal_validation"

LOAD_START_LIMIT = 1.0
LOAD_ABORT_LIMIT = 2.0

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


def _loadavg_1m() -> float | None:
    try:
        return round(os.getloadavg()[0], 3)
    except (AttributeError, OSError):
        return None


def detect_platform_label() -> str:
    """wsl2 | native_vm | native_linux, from kernel string and lscpu."""
    release = platform.release().lower()
    if "microsoft" in release or "wsl" in release:
        return "wsl2"
    try:
        out = subprocess.run(
            ["lscpu"], capture_output=True, text=True, check=True
        ).stdout
        if "Hypervisor vendor" in out:
            return "native_vm"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return "native_linux"


def _session_row(
    sess: dict[str, Any],
    cats: dict[str, dict[str, int]],
    task_id: str,
    seed: int,
) -> dict[str, Any]:
    host_ns = sess.get("process_cpu_ns") or 0
    host_ms = host_ns / 1e6
    prov = sess.get("provenance") or {}
    res_ns = prov.get("residual", 0)
    shares = {}
    cpu_ms = {}
    for cat in SHARE_CATEGORIES:
        cat_ns = cats.get(cat, {}).get("cpu_ns", 0)
        cpu_ms[cat] = round(cat_ns / 1e6, 2)
        shares[cat] = round(100 * cat_ns / host_ns, 2) if host_ns else 0.0
    return {
        "task_id": task_id,
        "seed": seed,
        "session_id": sess["session_id"],
        "wall_s": round(sess["wall_s"], 3),
        "host_cpu_ms": round(host_ms, 2),
        "llm_wait_s": round(cats.get("CLIENT_HTTP", {}).get("wall_ns", 0) / 1e9, 3),
        "remote_tool_io_wait_s": round(
            cats.get("HTTP_CLIENT", {}).get("wall_ns", 0) / 1e9, 3
        ),
        "cpu_ms_by_category": cpu_ms,
        "share_pct_by_category": shares,
        "residual_provenance_ms": round(res_ns / 1e6, 2),
        "residual_provenance_pct": round(100 * res_ns / host_ns, 2) if host_ns else 0.0,
        "residual_gate_pass": (res_ns / host_ns < RESIDUAL_LIMIT) if host_ns else True,
        "tool_call_counts": sess.get("tool_call_counts", {}),
        "turns": sess.get("turns"),
    }


def _per_task_medians(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tid in SUBSET_TASKS:
        trows = [r for r in rows if r["task_id"] == tid]
        if not trows:
            continue
        entry: dict[str, Any] = {
            "n": len(trows),
            "host_cpu_ms": round(statistics.median(r["host_cpu_ms"] for r in trows), 2),
            "llm_wait_s": round(statistics.median(r["llm_wait_s"] for r in trows), 3),
            "wall_s": round(statistics.median(r["wall_s"] for r in trows), 3),
            "residual_provenance_pct": round(
                statistics.median(r["residual_provenance_pct"] for r in trows), 2
            ),
        }
        entry["share_pct_by_category"] = {
            cat: round(
                statistics.median(r["share_pct_by_category"][cat] for r in trows), 2
            )
            for cat in SHARE_CATEGORIES
        }
        entry["cpu_ms_by_category"] = {
            cat: round(
                statistics.median(r["cpu_ms_by_category"][cat] for r in trows), 2
            )
            for cat in SHARE_CATEGORIES
        }
        out[tid] = entry
    return out


def run_subset(
    seeds: list[int], backend: str, llm_scale: float
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    assert_blas_pinned()
    install_gc_hooks()
    from ..thread_identity import get_thread_registry, install_thread_identity_hooks

    install_thread_identity_hooks()
    _warm_shared_state()
    get_thread_registry().snapshot()
    _require_langgraph()
    tools = build_langchain_tools()

    acc = RunAccumulator(profile=LOCALITY_ABLATION_PROFILE.name, instr_version=3)
    os_start = _os_times_snapshot()
    wall_start = time.perf_counter_ns()
    per_session: list[dict[str, Any]] = []
    load_records: list[dict[str, Any]] = []
    spec = LOCALITY_ABLATION_PROFILE

    for seed in seeds:
        for tid in SUBSET_TASKS:
            load_before = _loadavg_1m()
            if load_before is not None and load_before > LOAD_ABORT_LIMIT:
                raise SystemExit(
                    f"ABORT: 1-min loadavg {load_before} exceeds {LOAD_ABORT_LIMIT} "
                    f"mid-run (before {tid} seed {seed}); host is contended, "
                    "results would not be quotable"
                )
            task = task_by_id(tid)
            sid = f"{tid}_s{seed}"
            tok = set_tool_locality(search=LOCALITY_REMOTE)
            try:
                result = run_real_session(
                    acc, sid, task, spec, seed, backend, llm_scale, tools,
                    instr_version=3,
                )
                result["seed"] = seed
                result["search_locality"] = LOCALITY_REMOTE
                per_session.append(result)
            finally:
                reset_tool_locality(tok)
            load_records.append(
                {
                    "session_id": sid,
                    "loadavg_before": load_before,
                    "loadavg_after": _loadavg_1m(),
                }
            )

    wall_end = time.perf_counter_ns()
    os_end = _os_times_snapshot()
    total_process_cpu_ns = sum(s.get("process_cpu_ns", 0) for s in per_session)

    run = acc.to_run_dict(
        env=_env_info(),
        config={
            "profile": LOCALITY_ABLATION_PROFILE.name,
            "seeds": seeds,
            "task_ids": list(SUBSET_TASKS),
            "mode": "sequential",
            "backend": backend,
            "llm_median_scale": llm_scale,
            "search_locality": LOCALITY_REMOTE,
            "instr_version": 3,
            "total_cpu_basis": "process_time_all_threads",
        },
        total_thread_cpu_ns=total_process_cpu_ns,
        total_wall_ns=wall_end - wall_start,
        os_times=_os_times_delta(os_start, os_end),
        per_session=sorted(per_session, key=lambda s: s["session_id"]),
    )

    psc = run.get("per_session_category") or {}
    rows = [
        _session_row(s, psc.get(s["session_id"], {}), s["session_id"].split("_s")[0], s["seed"])
        for s in run["per_session"]
    ]
    return run, rows, load_records


def run_smoke_c5(seed: int, backend: str, llm_scale: float) -> dict[str, Any]:
    """One c=5 mixed mini-batch. Contention smoke signal only, never quotable."""
    run = run_real_batch(
        5,
        "mixed",
        seed,
        backend,
        llm_scale,
        workers=5,
        search_locality=LOCALITY_REMOTE,
        payload_profile=LOCALITY_ABLATION_PROFILE.name,
        instr_version=3,
    )
    return {
        "label": "smoke_c5",
        "excluded_from_statistics": True,
        "seed": seed,
        "workers": 5,
        "sessions": 5,
        "batch_host_cpu_ms": round(run["totals"]["thread_cpu_ns"] / 1e6, 1),
        "residual_fraction": run.get("residual_fraction"),
        "per_session": [
            {
                "session_id": s["session_id"],
                "task_id": s.get("task_id"),
                "wall_s": round(s["wall_s"], 3),
                "host_cpu_ms": round((s.get("process_cpu_ns") or 0) / 1e6, 2),
            }
            for s in run["per_session"]
        ],
    }


def write_markdown(artifact: dict[str, Any], md_path: Path) -> None:
    rows = artifact["session_rows"]
    per_task = artifact["per_task_medians"]
    label = artifact["config"]["platform_label"]
    lines = [
        validity_banner(artifact["result_validity"]),
        "",
        f"# Bare-metal validation subset (platform: {label})",
        "",
        f"Generated: {artifact['generated_utc']}",
        f"Git commit: `{artifact['git']['commit']}` (dirty: {artifact['git']['dirty']})",
        f"Kernel: `{artifact['config']['kernel']}`",
        "",
        "Matched c=1 subset of the v3.1 replication configuration. Compare with",
        "`python apu_characterization/tools/bare_metal_compare.py` which writes",
        "`out/bare_metal_comparison.md` with the verdict.",
        "",
        "## Per-task medians",
        "",
        "| task | n | host CPU ms | LLM wait s | TOOL % | TPOOL % | FRMW % | "
        "ORCH_d % | RESID % |",
        "|------|---|-------------|------------|--------|---------|--------|"
        "----------|---------|",
    ]
    for tid, e in per_task.items():
        sh = e["share_pct_by_category"]
        lines.append(
            f"| {tid} | {e['n']} | {e['host_cpu_ms']:.1f} | {e['llm_wait_s']:.2f} | "
            f"{sh['TOOL_COMPUTE']:.1f} | {sh['THREADPOOL']:.1f} | "
            f"{sh['FRAMEWORK']:.1f} | {sh['ORCH_DISPATCH']:.1f} | "
            f"{sh['RESIDUAL_UNATTRIBUTED']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Residual gate (15% per session)",
            "",
            "| session | residual ms | residual % | pass |",
            "|---------|-------------|------------|------|",
        ]
    )
    for r in rows:
        lines.append(
            f"| {r['session_id']} | {r['residual_provenance_ms']:.2f} | "
            f"{r['residual_provenance_pct']:.1f} | "
            f"{'PASS' if r['residual_gate_pass'] else 'FAIL'} |"
        )
    loads = artifact["load_records"]
    if loads and loads[0].get("loadavg_before") is not None:
        vals = [
            x
            for rec in loads
            for x in (rec.get("loadavg_before"), rec.get("loadavg_after"))
            if x is not None
        ]
        lines.extend(
            [
                "",
                "## Load hygiene",
                "",
                f"- 1-min loadavg range across run: {min(vals)} to {max(vals)} "
                f"(start limit {LOAD_START_LIMIT}, abort limit {LOAD_ABORT_LIMIT})",
            ]
        )
    if artifact.get("smoke_c5"):
        s = artifact["smoke_c5"]
        lines.extend(
            [
                "",
                "## smoke_c5 (contention smoke signal, excluded from all statistics)",
                "",
                f"- workers=5, sessions=5, seed={s['seed']}",
                f"- batch host CPU: {s['batch_host_cpu_ms']} ms",
                f"- residual fraction: {s['residual_fraction']}",
            ]
        )
    lines.extend(["", f"Reproduce: `{artifact['reproduce_cmd']}`", ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bare-metal validation subset")
    parser.add_argument("--backend", default="openai", choices=("scripted", "openai"))
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--llm-scale", type=float, default=1.0)
    parser.add_argument(
        "--platform-label",
        default=None,
        help="Override auto-detection: wsl2, native_linux, native_vm",
    )
    parser.add_argument("--smoke-c5", action="store_true", dest="smoke_c5")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()

    label = args.platform_label or detect_platform_label()
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]

    load0 = _loadavg_1m()
    if load0 is not None and load0 > LOAD_START_LIMIT:
        raise SystemExit(
            f"REFUSED: 1-min loadavg {load0} exceeds start limit {LOAD_START_LIMIT}. "
            "Wait for the host to quiesce, then retry."
        )
    if sys.platform == "win32":
        raise SystemExit("REFUSED: Linux only (WSL2 or native).")

    load_and_validate(strict=not args.allow_dirty)

    run, rows, load_records = run_subset(seeds, args.backend, args.llm_scale)

    artifact: dict[str, Any] = {
        "experiment": STEM,
        "result_validity": validity_for_real_agent_backend(args.backend),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "setup_ref": _load_setup_digest(),
        "git": _git_state(),
        "env": _env_info(),
        "config": {
            "platform_label": label,
            "kernel": platform.release(),
            "backend": args.backend,
            "seeds": seeds,
            "task_ids": list(SUBSET_TASKS),
            "sessions": len(rows),
            "search_locality": LOCALITY_REMOTE,
            "instr_version": 3,
            "comparison_type": "platform_validation_subset",
            "baseline_ref": "out/replication_remote_search_v3.json (platform wsl2)",
        },
        "run": run,
        "session_rows": rows,
        "per_task_medians": _per_task_medians(rows),
        "load_records": load_records,
        "loadavg_start": load0,
        "loadavg_end": _loadavg_1m(),
        "timer_overhead_ns_per_pair": measure_timer_overhead_ns(100_000),
        "reproduce_cmd": (
            "python -m apu_characterization.experiments.bare_metal_validation "
            f"--backend {args.backend} --seeds {','.join(str(s) for s in seeds)}"
            + (" --smoke-c5" if args.smoke_c5 else "")
        ),
    }
    total = run["totals"]["thread_cpu_ns"]
    artifact["invariant"] = {
        "total_thread_cpu_ns": total,
        "residual_fraction": run.get("residual_fraction", 0),
        "pass": run.get("residual_fraction", 0) < RESIDUAL_LIMIT,
        "limit": RESIDUAL_LIMIT,
    }

    if args.smoke_c5:
        print("running smoke_c5 (contention smoke signal) ...", flush=True)
        artifact["smoke_c5"] = run_smoke_c5(seeds[0], args.backend, args.llm_scale)

    apply_audit_to_artifact(artifact)

    gate_fail = [r["session_id"] for r in rows if not r["residual_gate_pass"]]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"{STEM}_{label}.json"
    json_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    md_path = OUT_DIR / f"{STEM}_{label}.md"
    write_markdown(artifact, md_path)

    print(f"json: {json_path}")
    print(f"md:   {md_path}")
    print(f"validity: {artifact['result_validity']}")
    print(f"platform: {label}  sessions: {len(rows)}")
    if gate_fail:
        print(f"FAIL: residual gate exceeded on {gate_fail}")
        sys.exit(1)
    print("all sessions PASS the residual gate")


if __name__ == "__main__":
    main()
