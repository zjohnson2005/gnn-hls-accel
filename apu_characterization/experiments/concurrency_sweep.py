"""Concurrency sweep: host CPU breakdown vs concurrent agent sessions.

Two modes:

**c-ladder mode (primary, ``--levels``):** each level c runs c sessions in a
batch with workers = c (true concurrent sessions). Tasks are sampled with
replacement from the 14-task main pool (mixed suite minus AH-01, MX-01) with a
deterministic per-(level, seed) RNG. Each batch is wrapped in a
``BatchSampler`` (1 s CPU utilization series, context switches, loadavg).
The c=1 anchor is NOT rerun: the v3.1 replication artifact
(``out/replication_remote_search_v3.json``: 10 sessions, workers=1, n=5 seeds)
is ingested and injected as level 1, marked ``source: v3.1 replication
(ingested anchor)``.

Saturation criterion (evaluated per level, ladder stops when tripped):
median CPU utilization over the batch window > 85%, or throughput
(sessions/min) stops increasing vs the previous level. N_max is the highest
level before the criterion trips. Capacity uplift k is computed analytically:
k = 1 / (1 - f) where f is the pooled harness fraction of host CPU at N_max
(strict and broad variants); N_max_counterfactual = N_max_measured * k.

**workers mode (legacy, ``--workers``):** sessions fixed (default 10), sweep
ThreadPoolExecutor max_workers. Kept for backward compatibility.

**Per-level audit:** at c=1 the standard 15% per-session residual gate applies.
At c>1 overlapping session clocks make per-session gates meaningless; the
batch-level gate uses ``batch_process_cpu_ns`` (single process_time delta for
the whole batch) with the same 15% residual-provenance limit, plus a 12%
fan-out canary on FO-01 or any session with >= 4 parallel tool calls
(``apply_audit_to_concurrency_sweep``). Canary warnings do not fail the
sweep.

Run (publishable c-ladder, Linux/WSL):
  python -m apu_characterization.experiments.concurrency_sweep \\
      --backend openai --levels 5,10,25,50,100 --seeds 0,1,2 \\
      --search-locality remote

Debug smoke (no API key):
  python -m apu_characterization.experiments.concurrency_sweep \\
      --backend scripted --levels 2,3 --seeds 0 --llm-scale 0.05 --allow-dirty

Artifacts: out/concurrency_sweep.json / .md
Figures:   python apu_characterization/tools/sweep_figures.py
Report:    python apu_characterization/tools/sweep_report.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..audit import apply_audit_to_artifact, apply_audit_to_concurrency_sweep
from ..env_pin import assert_blas_pinned
from ..profiles import LOCALITY_ABLATION_PROFILE
from ..setup_validate import load_and_validate
from ..stats import (
    aggregate_concurrency_by_level,
    aggregate_concurrency_by_workers,
    batch_attribution_summary,
    median_iqr,
    summarize_concurrency_run,
)
from ..sysmon import BatchSampler
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
from ..tasks import assign_task, sample_tasks_with_replacement, task_by_id
from ..validity import validity_for_real_agent_backend

ANCHOR_PATH_DEFAULT = Path("apu_characterization/out/replication_remote_search_v3.json")
ANCHOR_SOURCE_LABEL = "v3.1 replication (ingested anchor)"
SATURATION_UTIL_PCT = 85.0


def _run_one(
    workers: int,
    seed: int,
    profile: str,
    backend: str,
    search_locality: str,
    sessions: int,
    llm_scale: float,
    payload_profile: str | None,
    *,
    level: int | None = None,
    task_ids: list[str] | None = None,
    instr_version: int = 1,
) -> dict[str, Any]:
    # BatchSampler wraps the whole batch window: 1 s CPU utilization series,
    # context-switch delta, loadavg start/end (B2 instrumentation).
    sampler = BatchSampler()
    sampler.start()
    t0 = time.perf_counter()
    try:
        run = run_real_batch(
            sessions,
            profile,
            seed,
            backend,
            llm_scale,
            workers=workers,
            search_locality=search_locality,
            payload_profile=payload_profile,
            instr_version=instr_version,
            task_ids=task_ids,
        )
    finally:
        sysmon = sampler.stop()
    batch_wall_s = time.perf_counter() - t0
    pp = payload_profile or (
        LOCALITY_ABLATION_PROFILE.name if search_locality == "remote" else profile
    )

    if task_ids is not None:
        task_assignments = [task_by_id(t).describe() for t in task_ids]
        task_sampling = "with_replacement (14-task main pool, rng sweep-{level}-{seed})"
    else:
        task_assignments = [
            assign_task(profile, seed, i).describe() for i in range(sessions)
        ]
        task_sampling = "rotation (pool[(seed + i) % len])"

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
            "level": level,
            "sampled_task_ids": task_ids,
            "task_sampling": task_sampling,
            "mode": f"threads/{backend}",
            "llm_median_scale": llm_scale,
            "instr_version": instr_version,
        },
        "batch_wall_s": batch_wall_s,
        "sysmon": sysmon,
        "run": run,
        "per_task": per_task,
        "per_task_wall_cpu": compute_per_task_wall_cpu(per_task, run["per_session"]),
        "category_averages": compute_category_averages(per_task, run["per_session"]),
        "behavior_buckets": summarize_behavior_buckets(run["per_session"], per_task),
        "timer_overhead_ns_per_pair": measure_timer_overhead_ns(100_000),
        "task_assignments": task_assignments,
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


def _ingest_anchor(path: Path) -> dict[str, Any] | None:
    """Load the v3.1 replication artifact and build the level-1 anchor row.

    The anchor batch runs 10 sessions with workers=1 (sequential, one at a
    time), so per-session host CPU and pooled shares anchor c=1. Never rerun
    by the sweep.
    """
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    agg = data.get("aggregate") or {}
    per_seed = data.get("per_seed_artifacts") or []
    sessions = int((data.get("config") or {}).get("sessions") or 10)

    walls: list[float] = []
    throughputs: list[float] = []
    per_session_cpu: list[float] = []
    cat_ms: dict[str, list[float]] = {}
    for art in per_seed:
        wall = art.get("batch_wall_s")
        total_ns = (art.get("invariant") or {}).get("total_thread_cpu_ns", 0)
        if wall:
            walls.append(wall)
            throughputs.append(sessions / (wall / 60.0))
        if total_ns:
            per_session_cpu.append(total_ns / 1e6 / sessions)
        for cat, vals in (art.get("run") or {}).get("per_category", {}).items():
            cat_ms.setdefault(cat, []).append(vals.get("cpu_ns", 0) / 1e6)

    row: dict[str, Any] = {
        "level": 1,
        "workers": 1,
        "sessions_per_batch": sessions,
        "source": ANCHOR_SOURCE_LABEL,
        "anchor_artifact": path.as_posix(),
        "anchor_validity": data.get("result_validity"),
        "n_seeds": agg.get("n_seeds", len(per_seed)),
        "seeds": agg.get("seeds"),
        "batch_host_cpu_ms": agg.get("batch_host_cpu_ms"),
        "batch_wall_s": median_iqr(walls) if walls else None,
        "host_cpu_ms_per_session": median_iqr(per_session_cpu)
        if per_session_cpu
        else None,
        "throughput_sessions_per_min": median_iqr(throughputs) if throughputs else None,
        "category_cpu_ms": {cat: median_iqr(v) for cat, v in sorted(cat_ms.items())},
        "note": (
            f"{sessions} sessions run sequentially (workers=1); per-session host "
            "CPU anchors c=1. Ingested from the v3.1 replication, not rerun."
        ),
        "comparison_type": "distribution_over_seeds",
    }
    for key, val in agg.items():
        if key.startswith("pooled_"):
            row[key] = val
    return row


def _saturation_reason(
    level_row: dict[str, Any], prev_throughput: float | None
) -> str | None:
    """B3 saturation criterion for one aggregated level row."""
    util = (level_row.get("cpu_pct_median") or {}).get("median")
    if util is not None and util > SATURATION_UTIL_PCT:
        return (
            f"median CPU utilization {util:.1f}% > {SATURATION_UTIL_PCT:.0f}% "
            "over batch window"
        )
    tp = (level_row.get("throughput_sessions_per_min") or {}).get("median")
    if prev_throughput is not None and tp is not None and tp <= prev_throughput:
        return (
            f"throughput {tp:.2f} sessions/min did not increase vs previous "
            f"level ({prev_throughput:.2f} sessions/min)"
        )
    return None


def _capacity_uplift(n_max: int, n_max_row: dict[str, Any]) -> dict[str, Any]:
    """Analytic capacity uplift k from measured harness budgets at N_max.

    Formula: a harness component consuming fraction f of the CPU-bound
    per-session budget, once removed, frees f of host CPU per session; on the
    same CPU headroom the sustainable session count scales by k = 1 / (1 - f).
    So N_max_counterfactual = N_max_measured * k, computed analytically from
    the pooled harness share at the N_max level (median over seeds), with no
    counterfactual run. k_strict removes harness_strict
    (ORCH_SETUP + ORCH_DISPATCH + TOKENIZATION + SERIALIZATION); k_broad
    removes harness_broad (strict + HTTP/framework/threadpool client buckets).
    """
    strict_f = ((n_max_row.get("pooled_harness_strict_pct") or {}).get("median") or 0.0) / 100.0
    broad_f = ((n_max_row.get("pooled_harness_broad_pct") or {}).get("median") or 0.0) / 100.0
    host_per_sess = (n_max_row.get("host_cpu_ms_per_session") or {}).get("median")

    def _k(f: float) -> float | None:
        return 1.0 / (1.0 - f) if 0.0 <= f < 1.0 else None

    k_strict = _k(strict_f)
    k_broad = _k(broad_f)
    return {
        "n_max_measured": n_max,
        "harness_strict_fraction": strict_f,
        "harness_broad_fraction": broad_f,
        "k_strict": k_strict,
        "k_broad": k_broad,
        "n_max_counterfactual_strict": (n_max * k_strict) if k_strict else None,
        "n_max_counterfactual_broad": (n_max * k_broad) if k_broad else None,
        "host_cpu_ms_per_session_measured": host_per_sess,
        "host_cpu_ms_per_session_strict_removed": (
            host_per_sess * (1.0 - strict_f) if host_per_sess is not None else None
        ),
        "host_cpu_ms_per_session_broad_removed": (
            host_per_sess * (1.0 - broad_f) if host_per_sess is not None else None
        ),
        "formula": (
            "k = 1 / (1 - f), f = pooled harness fraction of host CPU at N_max; "
            "N_max_counterfactual = N_max_measured * k (applied to CPU-bound headroom)"
        ),
    }


def _reproduce_cmd_workers(args: argparse.Namespace, workers: str, seeds: str) -> str:
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


def _reproduce_cmd_levels(args: argparse.Namespace, levels: str, seeds: str) -> str:
    parts = [
        "python -m apu_characterization.experiments.concurrency_sweep",
        f"--backend {args.backend}",
        f"--profile {args.profile}",
        f"--seeds {seeds}",
        f"--levels {levels}",
        f"--search-locality {args.search_locality}",
    ]
    if args.payload_profile:
        parts.append(f"--payload-profile {args.payload_profile}")
    if args.llm_scale != 0.05:
        parts.append(f"--llm-scale {args.llm_scale}")
    if args.allow_dirty:
        parts.append("--allow-dirty")
    return " ".join(parts)


def _fmt_mi(mi: dict[str, Any] | None, digits: int = 1) -> str:
    if not mi:
        return "n/a"
    return f"{mi['median']:.{digits}f} [{mi['q1']:.{digits}f}-{mi['q3']:.{digits}f}]"


def _write_markdown_levels(combined: dict[str, Any], out_path: Path) -> None:
    cfg = combined["config"]
    audit = combined.get("audit", {})
    by_level = combined.get("by_level", {})
    sat = combined.get("saturation")
    cap = combined.get("capacity") or {}
    lines = [
        validity_banner(combined["result_validity"]),
        "",
        "# Concurrency sweep (c-ladder, remote search)",
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
        f"- Levels (c = concurrent sessions = workers): `{cfg['levels']}`",
        f"- Levels completed: `{cfg['levels_run']}`",
        f"- Seeds per level: `{cfg['seeds']}`",
        f"- Task sampling: {cfg['task_sampling']}",
        f"- instr_version: {cfg['instr_version']}",
        "",
        "**Anchor note:** level 1 is ingested from the v3.1 replication "
        "(10 sessions, workers=1, sequential; n=5 seeds), not rerun. "
        "Marked `source: v3.1 replication (ingested anchor)`.",
        "",
        "## Results by level (median [IQR] over seeds)",
        "",
        "| c | n | host CPU ms/session | throughput (sess/min) | util % | TOOL % | ORCH % | harness strict % | harness broad % | p99 turn ms | source |",
        "|--:|--:|--------------------:|----------------------:|-------:|-------:|-------:|-----------------:|----------------:|------------:|--------|",
    ]
    for key in sorted(by_level, key=lambda k: int(k)):
        row = by_level[key]
        src = row.get("source", "sweep run")
        n = row.get("n_seeds", 0)
        n_label = f"{n} (n=1!)" if n == 1 else str(n)
        lines.append(
            f"| {row['level']} | {n_label} | "
            f"{_fmt_mi(row.get('host_cpu_ms_per_session'))} | "
            f"{_fmt_mi(row.get('throughput_sessions_per_min'), 2)} | "
            f"{_fmt_mi(row.get('cpu_pct_median'))} | "
            f"{_fmt_mi(row.get('pooled_tool_compute_pct'))} | "
            f"{_fmt_mi(row.get('pooled_orch_pct'))} | "
            f"{_fmt_mi(row.get('pooled_harness_strict_pct'))} | "
            f"{_fmt_mi(row.get('pooled_harness_broad_pct'))} | "
            f"{_fmt_mi(row.get('turn_transition_p99_ms'))} | {src} |"
        )
    lines.extend(
        [
            "",
            "Denominators: c=1 host CPU ms/session = batch host / 10 (sequential "
            "sessions); c>1 = batch process_time delta / c (not sum of overlapping "
            "session clocks). Pooled % = category CPU / batch host CPU. util % = "
            "1 s psutil samples over the batch window.",
            "",
            "## Saturation and capacity (B3)",
            "",
        ]
    )
    if sat:
        lines.append(f"- **saturation:** level {sat['level']}: {sat['reason']}")
    else:
        lines.append("- **saturation:** not reached within the ladder")
    lines.extend(
        [
            f"- N_max (measured): **{cap.get('n_max_measured')}**",
            f"- k_strict = {cap.get('k_strict'):.3f} -> N_max counterfactual "
            f"{cap.get('n_max_counterfactual_strict'):.1f}"
            if cap.get("k_strict")
            else "- k_strict: n/a",
            f"- k_broad = {cap.get('k_broad'):.3f} -> N_max counterfactual "
            f"{cap.get('n_max_counterfactual_broad'):.1f}"
            if cap.get("k_broad")
            else "- k_broad: n/a",
            f"- formula: {cap.get('formula')}",
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
            f"Report: `concurrency_sweep_report.md` (tools/sweep_report.py)",
            f"Reproduce: `{combined['reproduce_cmd']}`",
        ]
    )
    md_path = out_path.with_suffix(".md")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_markdown_workers(
    combined: dict[str, Any],
    by_workers: dict[str, Any],
    out_path: Path,
) -> None:
    cfg = combined["config"]
    audit = combined.get("audit", {})
    lines = [
        validity_banner(combined["result_validity"]),
        "",
        "# Concurrency sweep (workers x remote search)",
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
        "`workers=1`: 10 sessions run **sequentially** one-at-a-time. "
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
            f"{cpu['median']:.1f} [{cpu['q1']:.1f}-{cpu['q3']:.1f}] | "
            f"{wall['median']:.1f} [{wall['q1']:.1f}-{wall['q3']:.1f}] | "
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


def _finalize(combined: dict[str, Any], args: argparse.Namespace) -> Path:
    apply_audit_to_concurrency_sweep(combined)
    stem = "concurrency_sweep"
    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / f"{stem}.json"
    json_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    return json_path


def _run_levels_mode(args: argparse.Namespace, seeds: list[int], levels: list[int]) -> None:
    instr_version = args.instr_version if args.instr_version is not None else 3

    payload_profile = args.payload_profile
    if payload_profile is None and args.search_locality == "remote":
        payload_profile = LOCALITY_ABLATION_PROFILE.name

    anchor = _ingest_anchor(args.anchor)
    if anchor is None:
        print(
            f"WARNING: anchor artifact not found at {args.anchor}; level 1 will be "
            "missing from the combined artifact (run the v3 replication first)"
        )

    by_level: dict[str, Any] = {}
    prev_throughput: float | None = None
    if anchor is not None:
        by_level["1"] = anchor
        tp = (anchor.get("throughput_sessions_per_min") or {}).get("median")
        if tp is not None:
            prev_throughput = tp

    per_run_artifacts: list[dict[str, Any]] = []
    per_run: list[dict[str, Any]] = []
    levels_run: list[int] = []
    saturation: dict[str, Any] | None = None

    for level in sorted(levels):
        level_artifacts: list[dict[str, Any]] = []
        for seed in seeds:
            task_ids = sample_tasks_with_replacement(level, seed)
            print(
                f"running level c={level} seed={seed} "
                f"(sessions={level}, workers={level}) ...",
                flush=True,
            )
            art = _run_one(
                level,
                seed,
                args.profile,
                args.backend,
                args.search_locality,
                level,
                args.llm_scale,
                payload_profile,
                level=level,
                task_ids=task_ids,
                instr_version=instr_version,
            )
            level_artifacts.append(art)
            per_run_artifacts.append(art)
        rows = [summarize_concurrency_run(a) for a in level_artifacts]
        per_run.extend(rows)
        level_agg = aggregate_concurrency_by_level(rows)[str(level)]
        by_level[str(level)] = level_agg
        levels_run.append(level)

        reason = _saturation_reason(level_agg, prev_throughput)
        if reason and not args.no_saturate_stop:
            saturation = {"level": level, "reason": reason}
            print(f"SATURATION at c={level}: {reason}; stopping ladder", flush=True)
            break
        if reason and args.no_saturate_stop:
            print(
                f"SATURATION would trip at c={level}: {reason}; "
                "--no-saturate-stop — continuing",
                flush=True,
            )
        tp = (level_agg.get("throughput_sessions_per_min") or {}).get("median")
        if tp is not None:
            prev_throughput = tp

    # N_max = highest level BEFORE the saturation criterion trips. If nothing
    # tripped, N_max is the highest level actually run (saturation not reached).
    completed = sorted(int(k) for k in by_level)
    if saturation is not None:
        below = [lv for lv in completed if lv < saturation["level"]]
        n_max = max(below) if below else saturation["level"]
    else:
        n_max = max(completed) if completed else 0
    capacity = (
        _capacity_uplift(n_max, by_level[str(n_max)]) if str(n_max) in by_level else {}
    )

    validity = DEBUG_ONLY if args.backend != "openai" else PUBLISHABLE
    levels_str = ",".join(str(v) for v in levels)
    seeds_str = ",".join(str(s) for s in seeds)

    combined: dict[str, Any] = {
        "experiment": "concurrency_sweep",
        "mode": "levels",
        "result_validity": validity,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "setup_ref": _load_setup_digest(),
        "git": _git_state(),
        "env": _env_info(),
        "config": {
            "profile": args.profile,
            "payload_profile": payload_profile or args.profile,
            "search_locality": args.search_locality,
            "levels": levels,
            "levels_run": levels_run,
            "sessions": "per level (sessions = workers = c)",
            "seeds": seeds,
            "backend": args.backend,
            "model": (
                os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                if args.backend == "openai"
                else "scripted (synthetic LLM, debug only)"
            ),
            "instr_version": instr_version,
            "task_sampling": (
                "with replacement from the 14-task main pool "
                "(mixed suite minus AH-01, MX-01), rng random.Random(f'sweep-{c}-{s}')"
            ),
            "anchor": {
                "path": args.anchor.as_posix(),
                "source": ANCHOR_SOURCE_LABEL,
                "ingested": anchor is not None,
            },
            "baseline_note": (
                "c=1 anchor ingested from v3.1 replication (10 sessions, workers=1, "
                "sequential, n=5 seeds); not rerun by this sweep"
            ),
            "comparison_type": "c_ladder_sweep",
        },
        "anchor": anchor,
        "by_level": by_level,
        "saturation": saturation,
        "capacity": capacity,
        "per_run": per_run,
        "per_run_artifacts": per_run_artifacts,
        "reproduce_cmd": _reproduce_cmd_levels(args, levels_str, seeds_str),
    }

    all_pass = all(r.get("invariant_pass") for r in per_run)
    all_audit = all(r.get("audit_pass") for r in per_run)
    combined["sweep_summary"] = {
        "n_runs": len(per_run),
        "all_invariant_pass": all_pass,
        "all_audit_pass": all_audit,
        "n_max_measured": n_max,
        "saturation": saturation,
    }

    json_path = _finalize(combined, args)
    _write_markdown_levels(combined, json_path)

    print(f"json: {json_path}")
    print(f"md:   {json_path.with_suffix('.md')}")
    print(f"validity: {combined['result_validity']}")
    print(f"runs: {len(per_run)} ({len(levels_run)} levels x {len(seeds)} seeds)")
    for key in sorted(by_level, key=lambda k: int(k)):
        row = by_level[key]
        hps = (row.get("host_cpu_ms_per_session") or {}).get("median")
        tp = (row.get("throughput_sessions_per_min") or {}).get("median")
        print(
            f"  c={row['level']}: host CPU/session "
            f"{hps:.1f} ms, throughput {tp:.2f} sess/min"
            if hps is not None and tp is not None
            else f"  c={row['level']}: (partial data)"
        )
    print(f"N_max: {n_max}" + (f" (saturation: {saturation['reason']})" if saturation else " (saturation not reached)"))
    if not all_pass:
        print("FAIL: one or more runs exceeded residual limit")
        sys.exit(1)
    if not all_audit and args.backend == "openai":
        print("FAIL: one or more runs failed audit (check platform / tick resolution)")
        sys.exit(1)


def _run_workers_mode(args: argparse.Namespace, seeds: list[int]) -> None:
    workers_list = [int(w.strip()) for w in args.workers.split(",") if w.strip()]
    instr_version = args.instr_version if args.instr_version is not None else 1

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
                    instr_version=instr_version,
                )
            )

    per_run = [summarize_concurrency_run(art) for art in per_run_artifacts]
    by_workers = aggregate_concurrency_by_workers(per_run)

    validity = DEBUG_ONLY if args.backend != "openai" else PUBLISHABLE
    workers_str = ",".join(str(w) for w in workers_list)
    seeds_str = ",".join(str(s) for s in seeds)

    combined: dict[str, Any] = {
        "experiment": "concurrency_sweep",
        "mode": "workers",
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
            "instr_version": instr_version,
            "baseline_note": (
                "c=1 baseline (replication, real_agent_breakdown) uses workers=1: "
                f"{args.sessions} sessions run sequentially one-at-a-time"
            ),
            "comparison_type": "workers_sweep",
        },
        "by_workers": by_workers,
        "per_run": per_run,
        "per_run_artifacts": per_run_artifacts,
        "reproduce_cmd": _reproduce_cmd_workers(args, workers_str, seeds_str),
    }

    all_pass = all(r.get("invariant_pass") for r in per_run)
    all_audit = all(r.get("audit_pass") for r in per_run)
    combined["sweep_summary"] = {
        "n_runs": len(per_run),
        "all_invariant_pass": all_pass,
        "all_audit_pass": all_audit,
    }

    json_path = _finalize(combined, args)
    _write_markdown_workers(combined, by_workers, json_path)

    print(f"json: {json_path}")
    print(f"md:   {json_path.with_suffix('.md')}")
    print(f"validity: {combined['result_validity']}")
    print(f"runs: {len(per_run)} ({len(workers_list)} workers x {len(seeds)} seeds)")
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
        print("FAIL: one or more runs failed audit (check platform / tick resolution)")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("scripted", "openai"), default="openai")
    parser.add_argument("--profile", default="mixed")
    parser.add_argument("--seed", type=int, default=None, help="Single seed (alias for --seeds)")
    parser.add_argument("--seeds", default="0", help="Comma-separated seeds (default: 0)")
    parser.add_argument(
        "--levels",
        default=None,
        help="Comma-separated concurrency levels (c-ladder mode: "
        "sessions = workers = c per level; primary mode)",
    )
    parser.add_argument(
        "--workers",
        default="1,2,4,8",
        help="Comma-separated ThreadPoolExecutor max_workers values "
        "(legacy workers mode; ignored when --levels is given)",
    )
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument(
        "--anchor",
        type=Path,
        default=ANCHOR_PATH_DEFAULT,
        help="v3.1 replication artifact ingested as the c=1 anchor (levels mode)",
    )
    parser.add_argument(
        "--instr-version",
        type=int,
        default=None,
        dest="instr_version",
        help="Instrumentation version (default: 3 in levels mode, 1 in workers mode)",
    )
    parser.add_argument("--search-locality", default="remote", dest="search_locality")
    parser.add_argument("--payload-profile", default=None, dest="payload_profile")
    parser.add_argument("--llm-scale", type=float, default=0.05, dest="llm_scale")
    parser.add_argument("--out", type=Path, default=Path("apu_characterization/out"))
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument(
        "--no-saturate-stop",
        action="store_true",
        dest="no_saturate_stop",
        help="Do not stop the c-ladder when the saturation criterion trips "
        "(smoke/debug; throughput may be API-bound at low c)",
    )
    args = parser.parse_args()

    if args.seed is not None:
        seeds = [args.seed]
    else:
        seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]

    load_and_validate(strict=not args.allow_dirty)
    assert_blas_pinned()
    _require_langgraph()

    if args.backend == "openai" and not seeds:
        raise SystemExit("at least one seed required")
    if len(seeds) < 5 and args.backend == "openai":
        print(f"WARNING: only {len(seeds)} seed(s); replication standard is n>=5")

    if args.levels:
        levels = [int(v.strip()) for v in args.levels.split(",") if v.strip()]
        bad = [v for v in levels if v < 2]
        if bad:
            raise SystemExit(
                f"levels must be >= 2 (c=1 is the ingested v3.1 anchor, never rerun): {bad}"
            )
        _run_levels_mode(args, seeds, levels)
    else:
        _run_workers_mode(args, seeds)


if __name__ == "__main__":
    main()
