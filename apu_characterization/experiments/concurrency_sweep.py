"""Concurrency sweep: host CPU breakdown vs concurrent agent sessions (workers).

Characterizes how pooled TOOL / ORCH / harness-APU shares and batch host CPU
scale when multiple LangGraph ReAct sessions run in parallel. Uses the same
deployment as the Linux replication baseline: OpenAI backend, remote search,
``locality_ablation`` payload profile, mixed task suite, 10 sessions per batch.

**Baseline c=1** in the replication and real-agent breakdown runs means
``workers=1``: all 10 sessions execute sequentially one-at-a-time in a single
thread pool slot. This sweep varies ``--workers`` while holding sessions=10.

Run (publishable, Linux/WSL recommended):
  python -m apu_characterization.experiments.concurrency_sweep \\
      --backend openai --seeds 0 --workers 1,2,4,8 \\
      --search-locality remote --allow-dirty

Debug smoke (no API key):
  python -m apu_characterization.experiments.concurrency_sweep \\
      --backend scripted --workers 1,2 --sessions 2 --seed 0

Artifacts: out/concurrency_sweep.json / .md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..audit import apply_audit_to_artifact, apply_audit_to_concurrency_sweep
from ..profiles import LOCALITY_ABLATION_PROFILE
from ..setup_validate import load_and_validate
from ..stats import aggregate_concurrency_by_workers, batch_attribution_summary, summarize_concurrency_run
from ..validity import DEBUG_ONLY, PUBLISHABLE, validity_banner
from .real_agent_breakdown import (
    CATEGORY_OVERRIDE_REMOTE_SEARCH,
    RESIDUAL_LIMIT,
    _env_info,
    _git_state,
    _load_setup_digest,
    _require_langgraph,
    run_real_batch,
)
from ..amenability import compute_category_averages, compute_per_task, compute_per_task_wall_cpu
from ..behavior import summarize_behavior_buckets
from ..instr import measure_timer_overhead_ns
from ..tasks import assign_task
from ..validity import validity_for_real_agent_backend


def _run_one(
    workers: int,
    seed: int,
    profile: str,
    backend: str,
    search_locality: str,
    sessions: int,
    llm_scale: float,
    payload_profile: str | None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    run = run_real_batch(
        sessions,
        profile,
        seed,
        backend,
        llm_scale,
        workers=workers,
        search_locality=search_locality,
        payload_profile=payload_profile,
    )
    batch_wall_s = time.perf_counter() - t0
    pp = payload_profile or (
        LOCALITY_ABLATION_PROFILE.name if search_locality == "remote" else profile
    )

    per_task = compute_per_task(run)
    artifact: dict[str, Any] = {
        "experiment": "real_agent_breakdown",
        "result_validity": validity_for_real_agent_backend(backend),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "setup_ref": _load_setup_digest(),
        "config": {
            "profile": profile,
            "payload_profile": pp,
            "search_locality": search_locality,
            "seed": seed,
            "sessions": sessions,
            "workers": workers,
            "mode": f"threads/{backend}",
            "llm_median_scale": llm_scale,
        },
        "batch_wall_s": batch_wall_s,
        "run": run,
        "per_task": per_task,
        "per_task_wall_cpu": compute_per_task_wall_cpu(per_task, run["per_session"]),
        "category_averages": compute_category_averages(per_task, run["per_session"]),
        "behavior_buckets": summarize_behavior_buckets(run["per_session"], per_task),
        "timer_overhead_ns_per_pair": measure_timer_overhead_ns(100_000),
        "task_assignments": [
            assign_task(profile, seed, i).describe() for i in range(sessions)
        ],
        "category_regions_override": CATEGORY_OVERRIDE_REMOTE_SEARCH,
    }
    total = run["totals"]["thread_cpu_ns"]
    artifact["invariant"] = {
        "total_thread_cpu_ns": total,
        "instrumented_cpu_ns": run["totals"]["instrumented_cpu_ns"],
        "residual_cpu_ns": run["residual_cpu_ns"],
        "residual_fraction": run["residual_fraction"],
        "limit": RESIDUAL_LIMIT,
        "pass": run["residual_fraction"] < RESIDUAL_LIMIT,
    }
    artifact["batch_attribution"] = batch_attribution_summary(run, total)
    apply_audit_to_artifact(artifact)
    return artifact


def _reproduce_cmd(args: argparse.Namespace, workers: str, seeds: str) -> str:
    parts = [
        "python -m apu_characterization.experiments.concurrency_sweep",
        f"--backend {args.backend}",
        f"--profile {args.profile}",
        f"--seeds {seeds}",
        f"--workers {workers}",
        f"--sessions {args.sessions}",
        f"--search-locality {args.search_locality}",
    ]
    if args.payload_profile:
        parts.append(f"--payload-profile {args.payload_profile}")
    if args.allow_dirty:
        parts.append("--allow-dirty")
    return " ".join(parts)


def _write_markdown(
    combined: dict[str, Any],
    by_workers: dict[str, Any],
    out_path: Path,
) -> None:
    cfg = combined["config"]
    audit = combined.get("audit", {})
    lines = [
        validity_banner(combined["result_validity"]),
        "",
        "# Concurrency sweep (workers × remote search)",
        "",
        f"- audit pass: **{'YES' if audit.get('pass') else 'NO'}**",
        f"- publishable_ok: **{'YES' if audit.get('publishable_ok') else 'NO'}**",
        f"- platform: `{audit.get('platform')}`",
        "",
        "## Configuration",
        "",
        f"- Backend: `{cfg['backend']}`",
        f"- Profile: `{cfg['profile']}` (payload: `{cfg['payload_profile']}`)",
        f"- Search locality: `{cfg['search_locality']}`",
        f"- Sessions per batch: **{cfg['sessions']}**",
        f"- Workers sweep: `{cfg['workers_sweep']}`",
        f"- Seeds: `{cfg['seeds']}`",
        "",
        "**Baseline note:** replication and real-agent breakdown at c=1 use "
        "`workers=1` — 10 sessions run **sequentially** one-at-a-time. "
        "Higher workers values run that many sessions in parallel (up to 10).",
        "",
        "## Results by workers (median [IQR] over seeds)",
        "",
        "| workers | batch host CPU ms | batch wall s | TOOL % | ORCH % | ORCH meas | ORCH recon | harness strict % |",
        "|--------:|------------------:|-------------:|-------:|-------:|----------:|-----------:|-----------------:|",
    ]
    for key in sorted(by_workers, key=lambda k: int(k)):
        row = by_workers[key]
        cpu = row["batch_host_cpu_ms"]
        wall = row["batch_wall_s"]
        tool = row["pooled_tool_compute_pct"]
        orch = row["pooled_orch_pct"]
        orch_m = row["pooled_orch_measured_pct"]
        orch_r = row["pooled_orch_reconcile_pct"]
        harness = row["pooled_harness_strict_pct"]
        lines.append(
            f"| {row['workers']} | "
            f"{cpu['median']:.1f} [{cpu['q1']:.1f}–{cpu['q3']:.1f}] | "
            f"{wall['median']:.1f} [{wall['q1']:.1f}–{wall['q3']:.1f}] | "
            f"{tool['median']:.1f} | {orch['median']:.1f} | "
            f"{orch_m['median']:.1f} | {orch_r['median']:.1f} | {harness['median']:.1f} |"
        )
    lines.extend(
        [
            "",
            "Comparison type: **workers sweep** with optional distribution over seeds.",
            "Denominators: batch host CPU ms = sum(session process_time); "
            "pooled % = category CPU / batch host CPU.",
            "",
        ]
    )
    for v in audit.get("violations", [])[:10]:
        lines.append(f"- **VIOLATION:** {v}")
    if len(audit.get("violations", [])) > 10:
        lines.append(f"- ... and {len(audit['violations']) - 10} more violations")
    lines.extend(
        [
            "",
            f"Full data: `{out_path.name}`",
            f"Reproduce: `{combined['reproduce_cmd']}`",
        ]
    )
    md_path = out_path.with_suffix(".md")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("scripted", "openai"), default="openai")
    parser.add_argument("--profile", default="mixed")
    parser.add_argument("--seed", type=int, default=None, help="Single seed (alias for --seeds)")
    parser.add_argument("--seeds", default="0", help="Comma-separated seeds (default: 0)")
    parser.add_argument(
        "--workers",
        default="1,2,4,8",
        help="Comma-separated ThreadPoolExecutor max_workers values",
    )
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--search-locality", default="remote", dest="search_locality")
    parser.add_argument("--payload-profile", default=None, dest="payload_profile")
    parser.add_argument("--llm-scale", type=float, default=0.05, dest="llm_scale")
    parser.add_argument("--out", type=Path, default=Path("apu_characterization/out"))
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()

    if args.seed is not None:
        seeds = [args.seed]
    else:
        seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    workers_list = [int(w.strip()) for w in args.workers.split(",") if w.strip()]

    load_and_validate(strict=not args.allow_dirty)
    _require_langgraph()

    if args.backend == "openai" and not seeds:
        raise SystemExit("at least one seed required")
    if len(seeds) < 5 and args.backend == "openai":
        print(f"WARNING: only {len(seeds)} seed(s); replication standard is n≥5")

    payload_profile = args.payload_profile
    if payload_profile is None and args.search_locality == "remote":
        payload_profile = LOCALITY_ABLATION_PROFILE.name

    per_run_artifacts: list[dict[str, Any]] = []
    for workers in workers_list:
        for seed in seeds:
            print(f"running workers={workers} seed={seed} ...", flush=True)
            per_run_artifacts.append(
                _run_one(
                    workers,
                    seed,
                    args.profile,
                    args.backend,
                    args.search_locality,
                    args.sessions,
                    args.llm_scale,
                    payload_profile,
                )
            )

    per_run = [summarize_concurrency_run(art) for art in per_run_artifacts]
    by_workers = aggregate_concurrency_by_workers(per_run)

    validity = DEBUG_ONLY if args.backend != "openai" else PUBLISHABLE
    workers_str = ",".join(str(w) for w in workers_list)
    seeds_str = ",".join(str(s) for s in seeds)

    combined: dict[str, Any] = {
        "experiment": "concurrency_sweep",
        "result_validity": validity,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "setup_ref": _load_setup_digest(),
        "git": _git_state(),
        "env": _env_info(),
        "config": {
            "profile": args.profile,
            "payload_profile": payload_profile or args.profile,
            "search_locality": args.search_locality,
            "sessions": args.sessions,
            "workers_sweep": workers_list,
            "seeds": seeds,
            "backend": args.backend,
            "baseline_note": (
                "c=1 baseline (replication, real_agent_breakdown) uses workers=1: "
                f"{args.sessions} sessions run sequentially one-at-a-time"
            ),
            "comparison_type": "workers_sweep",
        },
        "by_workers": by_workers,
        "per_run": per_run,
        "per_run_artifacts": per_run_artifacts,
        "reproduce_cmd": _reproduce_cmd(args, workers_str, seeds_str),
    }

    all_pass = all(r.get("invariant_pass") for r in per_run)
    all_audit = all(r.get("audit_pass") for r in per_run)
    combined["sweep_summary"] = {
        "n_runs": len(per_run),
        "all_invariant_pass": all_pass,
        "all_audit_pass": all_audit,
    }

    apply_audit_to_concurrency_sweep(combined)

    stem = "concurrency_sweep"
    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / f"{stem}.json"
    json_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    _write_markdown(combined, by_workers, json_path)

    print(f"json: {json_path}")
    print(f"md:   {json_path.with_suffix('.md')}")
    print(f"validity: {validity}")
    print(f"runs: {len(per_run)} ({len(workers_list)} workers × {len(seeds)} seeds)")
    for key in sorted(by_workers, key=lambda k: int(k)):
        row = by_workers[key]
        print(
            f"  workers={row['workers']}: "
            f"host CPU {row['batch_host_cpu_ms']['median']:.1f} ms, "
            f"harness strict {row['pooled_harness_strict_pct']['median']:.1f}%"
        )
    if not all_pass:
        print("FAIL: one or more runs exceeded residual limit")
        sys.exit(1)
    if not all_audit and args.backend == "openai":
        print("WARN: one or more runs failed audit (check platform / tick resolution)")


if __name__ == "__main__":
    main()
