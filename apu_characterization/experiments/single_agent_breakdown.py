"""Experiment 0: prove the per-category CPU breakdown on one instrumented agent.

**Validity:** DEBUG ONLY. Mock LLM + scripted task decisions. Verifies timers
and invariants; never cite as experimental results. See `validity.py`.
one ReAct agent session, every CPU-bearing region wrapped in an exclusive
category timer, mock LLM sleeps as I/O wait, and the accounting invariant
checked (sum of categories + residual = total thread CPU).

Run:
  python -m apu_characterization.experiments.single_agent_breakdown \
      --profile mixed --seed 0 --sessions 1 --out apu_characterization/out

Artifacts (every number in the .md comes from the .json, never hand-typed):
  out/single_agent_breakdown.json   raw measurement
  out/single_agent_breakdown.md     auto-generated setup + breakdown report
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..amenability import (
    BROAD_TIERS,
    RATIONALE,
    STRICT_TIERS,
    TIER,
    compute_category_averages,
    compute_per_task,
    compute_per_task_wall_cpu,
)
from ..capture_setup import _porcelain_path
from ..harness.runner import run_batch
from ..instr import measure_timer_overhead_ns
from ..tasks import assign_task
from ..validity import DEBUG_ONLY, validity_banner
from ..stats import batch_attribution_summary
from ..taxonomy import Category

RESIDUAL_LIMIT = 0.15
SETUP_JSON = Path("apu_characterization/out/setup.json")

HARNESS_APU_CATEGORIES = (
    "ORCH_SETUP",
    "ORCH_DISPATCH",
    "TOKENIZATION",
    "SERIALIZATION",
)

CATEGORY_REGIONS = {
    "ORCH_SETUP": "OrchEngine.setup_session: task-graph node/edge construction per session",
    "ORCH_DISPATCH": "OrchEngine.dispatch_ready + complete_node: readiness scan, scatter, handoff",
    "SERIALIZATION": "json.dumps/loads of LLM responses and tool results, response parse",
    "TOKENIZATION": "token counting of the full assembled prompt each turn plus the "
    "response body (tiktoken or len/4 fallback); models client-side context-window "
    "bookkeeping, so it scales with conversation length per turn",
    "PROMPT_ASSEMBLY": "message-list build + prompt text construction each turn",
    "CONTEXT_MGMT": "deepcopy of session state, history append, artifact tracking",
    "HTTP_CLIENT": "mock API envelopes: request build + response parse around the "
    "I/O-wait sleep (AH tasks); real HTTP session handling in live mode",
    "TOOL_COMPUTE": "tool bodies: regex corpus scan, exec'd snippet, numpy cosine top-k, sympy eval",
    "LOGGING": "logger formatting calls in the agent loop",
    "GC": "collector cycles via gc.callbacks (lower bound, excludes refcount frees)",
    "RESIDUAL": "computed: total thread CPU minus sum of instrumented categories",
    "CLIENT_HTTP": "httpx/OpenAI transport send path (v2 thread hooks)",
    "CLIENT_PARSE": "response body read, JSON decode, validation (v2)",
    "FRAMEWORK": "LangGraph/LangChain executor and graph internals (v2)",
    "THREADPOOL": "concurrent.futures worker dispatch wrapper (v2)",
    "EVENT_LOOP": "asyncio.run / loop driver overhead (v2)",
    "RESIDUAL_UNATTRIBUTED": "process_cpu minus all tagged categories (v2 session-end gap)",
}


def _repo_relative_posix(path: Path) -> str:
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return path.resolve().relative_to(root).as_posix()
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        return path.as_posix()


def _git_state(*, ignore_paths: tuple[str, ...] = ()) -> dict[str, str]:
    """Return HEAD commit and whether the working tree has uncommitted changes."""
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        porcelain = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        ).stdout
        ignore = {p.replace("\\", "/") for p in ignore_paths}
        dirty_lines: list[str] = []
        for line in porcelain.splitlines():
            if not line.strip():
                continue
            path = _porcelain_path(line)
            if not path or path in ignore:
                continue
            dirty_lines.append(line)
        dirty = "\n".join(dirty_lines)
        return {
            "commit": rev,
            "dirty": "yes" if dirty else "no",
            "dirty_paths": [_porcelain_path(ln) for ln in dirty_lines],
        }
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {"commit": "unknown", "dirty": "unknown", "dirty_paths": []}


def _env_info() -> dict[str, Any]:
    from ..env_pin import blas_pin_snapshot

    info: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu_model": platform.processor() or "unknown",
        "blas_pin": blas_pin_snapshot(),
    }
    try:
        import psutil

        info["cores_logical"] = psutil.cpu_count(logical=True)
        info["cores_physical"] = psutil.cpu_count(logical=False)
        info["ram_gb"] = round(psutil.virtual_memory().total / (1024**3), 2)
    except ImportError:
        import os

        info["cores_logical"] = os.cpu_count()
    return info


def _load_setup_digest() -> dict[str, str]:
    if not SETUP_JSON.is_file():
        raise SystemExit(
            "setup record missing: run `python -m apu_characterization.capture_setup` "
            "first so the environment is registered before measurement"
        )
    setup = json.loads(SETUP_JSON.read_text(encoding="utf-8"))
    return {
        "setup_digest": setup.get("setup_digest", "unknown"),
        "task_suite_digest": setup.get("task_suite", {}).get("digest", "unknown"),
        "cpu_model": setup.get("hardware", {}).get("cpu_model", "unknown"),
    }


def run_experiment(
    profile: str,
    seed: int,
    sessions: int,
    llm_median_scale: float,
    out_dir: Path,
) -> dict[str, Any]:
    setup_ref = _load_setup_digest()
    overhead_ns = measure_timer_overhead_ns(200_000)

    t0 = time.perf_counter()
    run = run_batch(
        concurrency=sessions,
        profile=profile,
        seed=seed,
        mode="asyncio",
        llm_median_scale=llm_median_scale,
    )
    batch_wall_s = time.perf_counter() - t0

    task_assignments = [
        assign_task(profile, seed, i).describe() for i in range(sessions)
    ]

    artifact = {
        "experiment": "single_agent_breakdown",
        "result_validity": DEBUG_ONLY,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "setup_ref": setup_ref,
        "task_assignments": task_assignments,
        "git": _git_state(),
        "env": _env_info(),
        "config": {
            "profile": profile,
            "seed": seed,
            "sessions": sessions,
            "mode": "asyncio",
            "llm_median_scale": llm_median_scale,
            "note_llm_scale": (
                "mock LLM latency is asyncio sleep (I/O wait, zero thread CPU); "
                "scaling it changes wall time only, never CPU shares"
            ),
        },
        "timer_overhead_ns_per_pair": overhead_ns,
        "batch_wall_s": batch_wall_s,
        "run": run,
    }

    artifact["per_task"] = compute_per_task(run)
    artifact["category_averages"] = compute_category_averages(
        artifact["per_task"], run["per_session"]
    )
    artifact["amenability_tiers"] = TIER

    total = run["totals"]["thread_cpu_ns"]
    artifact["invariant"] = {
        "total_thread_cpu_ns": total,
        "instrumented_cpu_ns": run["totals"]["instrumented_cpu_ns"],
        "residual_cpu_ns": run["residual_cpu_ns"],
        "residual_fraction": run["residual_fraction"],
        "limit": RESIDUAL_LIMIT,
        "pass": run["residual_fraction"] < RESIDUAL_LIMIT,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = artifact_stem("single_agent_breakdown", DEBUG_ONLY)
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    artifact["_report_stem"] = stem
    return artifact


def _category_cpu_share(run: dict[str, Any], category: str) -> float:
    total = run["totals"]["thread_cpu_ns"] or 1
    return run["per_category"].get(category, {}).get("cpu_ns", 0) / total


def _harness_apu_cpu_share(run: dict[str, Any]) -> float:
    total = run["totals"]["thread_cpu_ns"] or 1
    ns = sum(
        run["per_category"].get(cat, {}).get("cpu_ns", 0)
        for cat in HARNESS_APU_CATEGORIES
    )
    return ns / total


def _format_tool_calls(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{tool}×{n}" for tool, n in sorted(counts.items()))


def _tool_calls_by_task(per_session: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for session in per_session:
        task_id = session.get("task_id")
        if task_id:
            out[task_id] = session.get("tool_call_counts", {})
    return out


def _orch_attribution_lines(artifact: dict[str, Any]) -> list[str]:
    """ORCH measured vs reconcile headline (real-agent artifacts only)."""
    ba = artifact.get("batch_attribution")
    if not ba:
        run = artifact.get("run", {})
        total = artifact.get("invariant", {}).get("total_thread_cpu_ns", 0)
        if run and total:
            ba = batch_attribution_summary(run, total)
        else:
            return []
    audit_attr = (artifact.get("audit") or {}).get("attribution_summary") or {}
    lines = [
        "",
        "### ORCH attribution (measured vs reconcile)",
        "",
        "ORCH **measured** = LangGraph stream step residual. ORCH **reconcile** = "
        "session-end process CPU not caught by region tags, booked to ORCH_DISPATCH. "
        "See `ATTRIBUTION.md`.",
        "",
        f"- Pooled ORCH: {ba.get('pooled_orch_pct', 0):.1f}% of batch host CPU",
        f"- ORCH measured: {ba.get('pooled_orch_measured_pct', 0):.1f}% of host",
        f"- ORCH reconcile: {ba.get('pooled_orch_reconcile_pct', 0):.1f}% of host",
        f"- Reconcile as % of total ORCH: {ba.get('orch_reconcile_pct_of_orch', 0):.1f}%",
        f"- harness_strict (ORCH_SETUP+ORCH_DISPATCH+TOKENIZATION+SERIALIZATION): "
        f"{ba.get('pooled_harness_strict_pct', ba.get('pooled_harness_apu_pct', 0)):.1f}%",
        f"- harness_broad (strict + HTTP_CLIENT + PROMPT_ASSEMBLY + CONTEXT_MGMT + LOGGING): "
        f"{ba.get('pooled_harness_broad_pct', 0):.1f}%",
    ]
    if audit_attr:
        lines.append(
            f"- Audit rollup: reconcile {audit_attr.get('orch_reconcile_pct_of_host', 0):.1f}% "
            f"of host CPU"
        )
    return lines


def _deployment_reconciliation_lines(
    artifact: dict[str, Any], out_dir: Path
) -> list[str]:
    cfg = artifact.get("config", {})
    if cfg.get("search_locality") != "remote":
        return []

    baseline_path = out_dir / "real_agent_breakdown.json"
    if not baseline_path.is_file():
        return [
            "",
            "### Deployment model (remote search)",
            "",
            "Search tool uses mock hosted API (HTTP envelope + I/O wait) instead of "
            "in-process regex. Compare to `real_agent_breakdown.json` (local search) "
            "when available for pooled headline reconciliation.",
        ]

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    run = artifact["run"]
    base_run = baseline["run"]
    total_ms = artifact["invariant"]["total_thread_cpu_ns"] / 1e6
    base_total_ms = baseline["invariant"]["total_thread_cpu_ns"] / 1e6

    tool_pct = _category_cpu_share(run, "TOOL_COMPUTE") * 100
    base_tool_pct = _category_cpu_share(base_run, "TOOL_COMPUTE") * 100
    orch_pct = (
        _category_cpu_share(run, "ORCH_SETUP")
        + _category_cpu_share(run, "ORCH_DISPATCH")
    ) * 100
    base_orch_pct = (
        _category_cpu_share(base_run, "ORCH_SETUP")
        + _category_cpu_share(base_run, "ORCH_DISPATCH")
    ) * 100
    harness_pct = _harness_apu_cpu_share(run) * 100
    base_harness_pct = _harness_apu_cpu_share(base_run) * 100
    from ..stats import _pooled_shares_from_run

    shares = _pooled_shares_from_run(run, artifact["invariant"]["total_thread_cpu_ns"])
    base_shares = _pooled_shares_from_run(
        base_run, baseline["invariant"]["total_thread_cpu_ns"]
    )

    avgs = artifact.get("category_averages", {})
    base_avgs = baseline.get("category_averages", {})
    tool_eq = (
        avgs.get("overall", {})
        .get("categories", {})
        .get("TOOL_COMPUTE", {})
        .get("mean_cpu_share", 0)
        * 100
    )
    base_tool_eq = (
        base_avgs.get("overall", {})
        .get("categories", {})
        .get("TOOL_COMPUTE", {})
        .get("mean_cpu_share", 0)
        * 100
    )

    return [
        "",
        "### Deployment model and headline reconciliation",
        "",
        "This run models **production-shaped search** (remote API + I/O wait). "
        "The baseline `real_agent_breakdown.json` used **local in-process regex search**.",
        "",
        "**Corrected headline framing:** local-search runs looked TOOL-dominated "
        "because the mock search tool intentionally scans a 50 MB corpus on-host. "
        "Under remote search, TOOL_COMPUTE falls and orchestration/serialization/"
        "tokenization (APU-relevant harness work) become the dominant *on-host* categories — "
        "reconciling this breakdown with the Phase 0 concurrency experiment's "
        "orchestration-dominant picture.",
        "",
        "| Metric | Local search (baseline) | Remote search (this run) |",
        "|---|---|---|",
        f"| Batch host CPU | {base_total_ms:.1f} ms | {total_ms:.1f} ms |",
        f"| Pooled TOOL_COMPUTE share | {base_tool_pct:.1f}% | {tool_pct:.1f}% |",
        f"| Pooled ORCH share | {base_orch_pct:.1f}% | {orch_pct:.1f}% |",
        f"| ORCH measured (host %) | {base_shares.get('pooled_orch_measured_pct', 0):.1f}% | "
        f"{shares.get('pooled_orch_measured_pct', 0):.1f}% |",
        f"| ORCH reconcile (host %) | {base_shares.get('pooled_orch_reconcile_pct', 0):.1f}% | "
        f"{shares.get('pooled_orch_reconcile_pct', 0):.1f}% |",
        f"| Pooled harness_strict (ORCH_SETUP+ORCH_DISPATCH+TOKENIZATION+SERIALIZATION) | "
        f"{base_harness_pct:.1f}% | {harness_pct:.1f}% |",
        f"| Pooled harness_broad (strict + HTTP + PROMPT + CONTEXT + LOGGING) | "
        f"{base_shares.get('pooled_harness_broad_pct', 0):.1f}% | "
        f"{shares.get('pooled_harness_broad_pct', 0):.1f}% |",
        f"| Equal-weight TOOL_COMPUTE share | {base_tool_eq:.1f}% | {tool_eq:.1f}% |",
        "",
        "Sessions that invoked local search (SH, and CH-02 when the model chose search) "
        "move from the CPU-heavy cluster to I/O-dominated wall time; remaining TOOL_COMPUTE "
        "is code_exec and local retrieve only.",
    ]


def _headline_denominator_caption(artifact: dict[str, Any]) -> str:
    cfg = artifact.get("config", {})
    inv = artifact.get("invariant", {})
    run = artifact.get("run", {})
    total_ms = inv.get("total_thread_cpu_ns", 0) / 1e6
    seeds = cfg.get("seeds") or [cfg.get("seed", "?")]
    if isinstance(seeds, int):
        seeds = [seeds]
    n = len(seeds)
    loc = cfg.get("search_locality", "local")
    wall = artifact.get("batch_wall_s", 0)
    cpu_wall_pct = 0.0
    wcpu = artifact.get("per_task_wall_cpu", {})
    if wcpu.get("totals"):
        cpu_wall_pct = wcpu["totals"].get("host_cpu_pct_of_session_wall", 0)
    workers = cfg.get("workers", run.get("config", {}).get("workers", 1))
    sessions = cfg.get("sessions", run.get("config", {}).get("concurrency", "?"))
    exec_note = (
        f"workers={workers} ({sessions} sessions sequential one-at-a-time)"
        if workers == 1
        else f"workers={workers} ({sessions} sessions, up to {workers} parallel)"
    )
    return (
        f"n={n} seed(s)={seeds}, search={loc}, batch host CPU={total_ms:.0f} ms, "
        f"batch wall={wall:.1f} s, CPU% of wall≈{cpu_wall_pct:.2f}%, {exec_note}"
    )


def _audit_report_lines(artifact: dict[str, Any]) -> list[str]:
    audit = artifact.get("audit")
    if not audit:
        return []
    lines = [
        "",
        "### Accounting audit",
        "",
        f"- pass: **{'YES' if audit.get('pass') else 'NO'}**",
        f"- publishable_ok: **{'YES' if audit.get('publishable_ok') else 'NO'}**",
        f"- platform: `{audit.get('platform')}`",
    ]
    if audit.get("windows_tick_ms"):
        lines.append(f"- Windows tick: {audit['windows_tick_ms']} ms (footnote-only below 200 ms/session)")
    for v in audit.get("violations", []):
        lines.append(f"- **VIOLATION:** {v}")
    for w in audit.get("warnings", []):
        lines.append(f"- warning: {w}")
    return lines


def _behavior_bucket_lines(artifact: dict[str, Any]) -> list[str]:
    bb = artifact.get("behavior_buckets")
    if not bb:
        return []
    lines = [
        "",
        "### Behavioral buckets (realized workload, not task labels)",
        "",
        bb.get("note", ""),
        "",
        f"CPU floor for detailed per-task amenability: {bb.get('cpu_floor_ms', 200)} ms",
        "",
        "| Bucket | Label | Tasks | Mean host CPU ms | Mean strict amenable |",
        "|---|---|---|---|---|",
    ]
    for bid, stats in sorted(bb.get("buckets", {}).items()):
        strict = stats.get("mean_amenable_strict")
        strict_s = f"{strict * 100:.1f}%" if strict is not None else "n/a"
        lines.append(
            f"| {bid} | {stats.get('label', bid)} | {', '.join(stats.get('tasks', []))} "
            f"| {stats.get('mean_host_cpu_ms', 0):.1f} | {strict_s} |"
        )
    lines.extend(
        [
            "",
            "Task archetype labels (SH, RH, …) are prompt-intent only; use behavioral "
            "buckets for workload-ground-truth grouping.",
        ]
    )
    return lines


def write_report(
    artifact: dict[str, Any],
    out_dir: Path,
    stem: str = "single_agent_breakdown",
    title: str = "Experiment 0: single-agent CPU-time breakdown",
) -> Path:
    run = artifact["run"]
    inv = artifact["invariant"]
    total = max(1, inv["total_thread_cpu_ns"])
    cfg = artifact["config"]
    env = artifact["env"]
    git = artifact["git"]

    rows: list[tuple[str, dict[str, Any]]] = sorted(
        run["per_category"].items(), key=lambda kv: -kv[1]["cpu_ns"]
    )

    lines = [
        f"# {title}",
        "",
        validity_banner(artifact.get("result_validity", DEBUG_ONLY)),
        "",
        f"Generated: {artifact['generated_utc']} from `{stem}.json`.",
        "All numbers below are read from that artifact.",
        "",
        "## Setup",
        "",
        f"- setup record: digest `{artifact['setup_ref']['setup_digest']}`,"
        f" task suite `{artifact['setup_ref']['task_suite_digest']}`"
        " (see EXPERIMENT_SETUP.md)",
        f"- cpu (from setup record): {artifact['setup_ref']['cpu_model']}",
        f"- git commit: `{git['commit']}` (dirty tree: {git['dirty']})",
        f"- python: {env['python']}",
        f"- platform: {env['platform']}",
        f"- cpu: {env.get('cpu_model', 'unknown')}, logical cores: {env.get('cores_logical')}",
        f"- ram_gb: {env.get('ram_gb', 'n/a')}",
        "",
        "### Protocol",
        "",
        f"- profile: `{cfg['profile']}`, seed: {cfg['seed']}, sessions: {cfg['sessions']},"
        f" execution: {cfg['mode']}",
    ]
    if cfg.get("search_locality"):
        lines.append(f"- search locality: `{cfg['search_locality']}`")
    if cfg.get("payload_profile") and cfg.get("payload_profile") != cfg.get("profile"):
        lines.append(
            f"- payload profile: `{cfg['payload_profile']}` "
            "(synthetic tool-result padding; see tool-locality ablation note)"
        )
    lines.extend(
        [
            f"- total CPU basis: {cfg.get('total_cpu_basis', 'worker thread_time_ns sum')}",
            f"- mock LLM latency scale: {cfg['llm_median_scale']}"
            f" ({cfg['note_llm_scale']})",
            "- clocks: wall = perf_counter_ns; CPU = thread_time_ns per region; "
            "real-agent total CPU = process_time (all threads, including LangGraph "
            "tool executors)",
            "- nesting: exclusive self-time accounting; an inner region pauses its parent",
            f"- timer overhead: {artifact['timer_overhead_ns_per_pair']:.0f} ns per enter/exit pair",
            f"- batch wall time: {artifact['batch_wall_s']:.2f} s",
            "",
            "### What each category wraps in this harness",
            "",
        ]
    )
    regions = {**CATEGORY_REGIONS, **artifact.get("category_regions_override", {})}
    for cat in Category:
        if cat == Category.RESIDUAL:
            continue
        desc = regions.get(cat.value, "see METHODOLOGY.md")
        lines.append(f"- `{cat.value}`: {desc}")

    lines.extend(
        [
            "",
            "## Accounting invariant",
            "",
            "sum(category thread-CPU) + residual = total thread-CPU of the run:",
            "",
            f"- total thread CPU: {inv['total_thread_cpu_ns'] / 1e6:.2f} ms",
            f"- instrumented: {inv['instrumented_cpu_ns'] / 1e6:.2f} ms",
            f"- residual: {inv['residual_cpu_ns'] / 1e6:.2f} ms"
            f" ({inv['residual_fraction'] * 100:.1f}% of total)",
            f"- limit: {inv['limit'] * 100:.0f}%  ->  "
            + ("PASS" if inv["pass"] else "FAIL"),
            "",
            "## Breakdown (thread CPU, exclusive per category — pooled across all sessions)",
            "",
            f"*Denominators: {_headline_denominator_caption(artifact)}*",
            "",
            "| Category | CPU ms | Share of total | Wall ms | Count | Bytes in | Bytes out |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for cat, v in rows:
        lines.append(
            f"| {cat} | {v['cpu_ns'] / 1e6:.3f} | {v['cpu_ns'] / total * 100:.1f}% "
            f"| {v['wall_ns'] / 1e6:.3f} | {v['count']} | {v['bytes_in']} | {v['bytes_out']} |"
        )
    lines.append(
        f"| RESIDUAL | {inv['residual_cpu_ns'] / 1e6:.3f} "
        f"| {inv['residual_fraction'] * 100:.1f}% | n/a | n/a | n/a | n/a |"
    )

    # ---------------------------------------------------- per-task breakdown
    per_task = artifact.get("per_task", {})
    if per_task:
        tools_by_task = _tool_calls_by_task(run["per_session"])
        lines.extend(
            [
                "",
                "## Per-task breakdowns and hardware amenability",
                "",
                "The headline table sums all sessions. Sections here are per"
                " task, which is the grouping the archetype analysis uses.",
                "",
                "Amenability tiers (classification is a documented input"
                " assumption, refined later by the measured scorecard):",
                "",
            ]
        )
        for cat in Category:
            if cat == Category.RESIDUAL:
                continue
            tier = TIER.get(cat.value, "none")
            lines.append(f"- `{cat.value}` [{tier}]: {RATIONALE.get(cat.value, 'see METHODOLOGY.md')}")
        lines.extend(
            [
                "",
                f"strict = {' + '.join(STRICT_TIERS)} tiers;"
                f" broad = {' + '.join(BROAD_TIERS)} tiers."
                " Base is the task's instrumented CPU; GC and RESIDUAL are"
                " process-global and excluded from per-task math.",
                "",
                "### Summary",
                "",
                "| Task | Instrumented CPU ms | Amenable strict | Amenable broad |",
                "|---|---|---|---|",
            ]
        )
        for task_id in sorted(per_task):
            e = per_task[task_id]
            lines.append(
                f"| {task_id} | {e['instrumented_cpu_ns'] / 1e6:.1f} "
                f"| {e['amenable_strict_share'] * 100:.1f}% "
                f"| {e['amenable_broad_share'] * 100:.1f}% |"
            )

        if artifact.get("experiment") == "real_agent_breakdown":
            wall_cpu = artifact.get("per_task_wall_cpu") or compute_per_task_wall_cpu(
                per_task, run["per_session"]
            )
            lines.extend(
                [
                    "",
                    "### Per-task LLM I/O wait vs host CPU",
                    "",
                    "Each row is one session. **LLM I/O wait** = HTTP_CLIENT wall"
                    " (blocked on OpenAI). **Host CPU** = session process_time."
                    " I/O % and CPU % both divide by session wall; they are different"
                    " axes (wait vs compute), not additive category wall fractions.",
                    "",
                    "| Task | Session wall s | LLM I/O wait s | Non-LLM wall s | Host CPU ms | I/O % of wall | CPU % of wall | Tool CPU ms | Harness CPU ms | Tools |",
                    "|---|---|---|---|---|---|---|---|---|---|",
                ]
            )
            for task_id in sorted(wall_cpu["per_task"]):
                r = wall_cpu["per_task"][task_id]
                calls = ", ".join(
                    f"{k}×{v}" for k, v in sorted(r["tool_call_counts"].items())
                ) or "none"
                lines.append(
                    f"| {task_id} | {r['session_wall_s']:.2f} | {r['llm_io_wait_s']:.2f} "
                    f"| {r['non_llm_wall_s']:.2f} | {r['host_cpu_ms']:.1f} "
                    f"| {r['llm_io_pct_of_session_wall']:.1f}% "
                    f"| {r['host_cpu_pct_of_session_wall']:.2f}% "
                    f"| {r['tool_cpu_ms']:.1f} | {r['harness_cpu_ms']:.1f} | {calls} |"
                )
            t = wall_cpu["totals"]
            lines.append(
                f"| **Total** | {t['session_wall_s']:.2f} | {t['llm_io_wait_s']:.2f} "
                f"| {t['session_wall_s'] - t['llm_io_wait_s']:.2f} | {t['host_cpu_ms']:.1f} "
                f"| {t['llm_io_pct_of_session_wall']:.1f}% "
                f"| {t['host_cpu_pct_of_session_wall']:.2f}% | | | |"
            )
            lines.extend(
                [
                    "",
                    "#### Per-task CPU category breakdown",
                    "",
                ]
            )
            for task_id in sorted(wall_cpu["per_task"]):
                r = wall_cpu["per_task"][task_id]
                e = per_task[task_id]
                total = max(0.001, e["instrumented_cpu_ns"] / 1e6)
                calls = _format_tool_calls(tools_by_task.get(task_id, {}))
                lines.append(
                    f"**{task_id}** — {r['host_cpu_ms']:.1f} ms host CPU, "
                    f"{r['session_wall_s']:.2f} s session wall — tools: {calls}"
                )
                lines.append("")
                lines.append("| Category | CPU ms | Share of task CPU |")
                lines.append("|---|---|---|")
                for cat, ms in sorted(
                    r["cpu_by_category_ms"].items(), key=lambda kv: -kv[1]
                ):
                    share = 100 * ms / total if e["instrumented_cpu_ns"] else 0
                    lines.append(f"| {cat} | {ms:.1f} | {share:.1f}% |")
                if not r["cpu_by_category_ms"]:
                    lines.append("| (none above tick floor) | 0.0 | — |")
                lines.append("")

        avgs = artifact.get("category_averages")
        if avgs:

            def _wall_frac_cell(cat: str, st: dict[str, Any]) -> str:
                if st.get("wall_concurrent"):
                    return "concurrent†"
                frac = st.get("mean_wall_frac")
                if frac is None:
                    return "n/a"
                return f"{frac * 100:.1f}%"

            def _append_avg_group(
                title: str,
                group: dict[str, Any],
                *,
                caveat: str = "",
            ) -> None:
                lines.extend(
                    [
                        "",
                        f"#### {title}",
                        "",
                        f"- tasks ({group['task_count']}): {', '.join(group['tasks'])}",
                        f"- mean session wall: {group['mean_session_wall_s']:.2f} s",
                        f"- mean instrumented CPU: {group['mean_instrumented_cpu_ms']:.1f} ms",
                        f"- mean amenable strict: {group['mean_amenable_strict_share'] * 100:.1f}%",
                        f"- mean amenable broad: {group['mean_amenable_broad_share'] * 100:.1f}%",
                        f"- partition wall fractions sum: "
                        f"{group.get('mean_wall_frac_sum_partition', 0) * 100:.1f}%"
                        " (excludes TOOL_COMPUTE, GC, ORCH_SETUP; see wall integrity)",
                    ]
                )
                if caveat:
                    lines.append(f"- **Caveat:** {caveat}")
                lines.extend(
                    [
                        "",
                        "| Category | Tier | Mean CPU ms | Mean CPU share | Mean wall ms | Wall / session |",
                        "|---|---|---|---|---|---|",
                    ]
                )
                rows = sorted(
                    group["categories"].items(),
                    key=lambda kv: -kv[1]["mean_cpu_ms"],
                )
                for cat, v in rows:
                    lines.append(
                        f"| {cat} | {TIER.get(cat, 'none')} | {v['mean_cpu_ms']:.1f} "
                        f"| {v['mean_cpu_share'] * 100:.1f}% "
                        f"| {v['mean_wall_ms']:.1f} "
                        f"| {_wall_frac_cell(cat, v)} |"
                    )

            pooled_total = inv.get("total_thread_cpu_ns") or 1
            pooled_tool = run["per_category"].get("TOOL_COMPUTE", {}).get("cpu_ns", 0)
            pooled_tool_pct = 100 * pooled_tool / pooled_total
            overall = avgs["overall"]
            tool_avg = overall["categories"].get("TOOL_COMPUTE", {})
            tool_avg_pct = tool_avg.get("mean_cpu_share", 0) * 100
            lines.extend(
                [
                    "",
                    "### Pooled vs equal-weight (different questions)",
                    "",
                    f"*Denominators: {_headline_denominator_caption(artifact)}. "
                    "Comparison type: single-run sample unless replication_batch artifact.*",
                    "",
                    "| Metric | Pooled (headline table) | Equal-weight task average |",
                    "|---|---|---|",
                    f"| TOOL_COMPUTE CPU share | {pooled_tool_pct:.1f}% of batch CPU | "
                    f"{tool_avg_pct:.1f}% |",
                    "| Answers | What consumed this batch's total host capacity | "
                    "What a typical task of each type costs (one session per task here) |",
                    "",
                    "Use **pooled** for capacity planning (dominated by heavy outlier sessions)."
                    " Use **equal-weight per-archetype** rows below for archetype"
                    " characterization. Do not treat the overall equal-weight amenability"
                    " mean as a representative headline — it averages a bimodal distribution.",
                    "",
                    "### Archetype amenability (primary equal-weight table)",
                    "",
                    "| Archetype | Tasks | Mean CPU ms | Strict amenable | Broad amenable |",
                    "|---|---|---|---|---|",
                ]
            )
            small_base = {"RH", "LH"}
            for arch in sorted(avgs["by_archetype"]):
                g = avgs["by_archetype"][arch]
                note = ""
                if arch in small_base:
                    note = " ‡"
                lines.append(
                    f"| {arch} ({g['label']}) | {', '.join(g['tasks'])} "
                    f"| {g['mean_instrumented_cpu_ms']:.1f} "
                    f"| {g['mean_amenable_strict_share'] * 100:.1f}%{note} "
                    f"| {g['mean_amenable_broad_share'] * 100:.1f}%{note} |"
                )
            lines.extend(
                [
                    "",
                    "‡ **Small-base caution:** strict/broad percentages are of mean"
                    " instrumented CPU near the Windows thread-time tick floor (~15 ms)."
                    " High amenability % on RH/LH reflects sessions that barely ran local"
                    " work, not hardware-friendly archetypes. Do not quote without absolute"
                    " CPU ms; prefer Linux re-run for tick resolution.",
                    "",
                    "**CH blend:** the CH archetype row averages tasks that can land in"
                    " opposite behavior clusters — report CH-01 and CH-02 individually"
                    " alongside the CH row (see per-task sections).",
                ]
            )
            lines.extend(_deployment_reconciliation_lines(artifact, out_dir))
            lines.extend(_behavior_bucket_lines(artifact))
            if artifact.get("experiment") == "real_agent_breakdown":
                lines.extend(_orch_attribution_lines(artifact))
            lines.extend(_audit_report_lines(artifact))
            if artifact.get("experiment") == "real_agent_breakdown":
                lines.extend(
                    [
                        "",
                        "### Wall-time attribution integrity",
                        "",
                        "CPU category shares partition instrumented CPU (exclusive nesting;"
                        " invariant PASS). **Wall fractions are not a partition metric** in"
                        " real-agent mode: TOOL_COMPUTE/GC timers run on LangGraph tool-pool"
                        " threads while the stream thread's session clock is also advancing,"
                        " so summing all category wall fractions can exceed 100%. ORCH stream"
                        " steps now use perf_counter gaps minus tagged wall (not thread CPU).",
                        "",
                        "† TOOL_COMPUTE/GC: report mean wall ms; wall/session is marked"
                        " concurrent (same clock period as session wait, not additive).",
                        "",
                        "| Task | Session wall s | All-category coverage | Partition coverage |",
                        "|---|---|---|---|",
                    ]
                )
                wall_diag = avgs.get("wall_diagnostics", {}).get("per_task", {})
                for task_id in sorted(wall_diag):
                    d = wall_diag[task_id]
                    cov_all = d.get("coverage_all_categories")
                    cov_part = d.get("coverage_partition_categories")
                    all_s = f"{cov_all * 100:.1f}%" if cov_all is not None else "n/a"
                    part_s = f"{cov_part * 100:.1f}%" if cov_part is not None else "n/a"
                    lines.append(
                        f"| {task_id} | {d['session_wall_s']:.2f} | {all_s} | {part_s} |"
                    )
            lines.extend(
                [
                    "",
                    "### Equal-weight category breakdown by archetype",
                    "",
                    "Mean CPU share partitions instrumented CPU (~100% per task)."
                    " Wall/session excludes concurrent tool-pool categories (†).",
                ]
            )
            for arch in sorted(avgs["by_archetype"]):
                g = avgs["by_archetype"][arch]
                caveat = ""
                if arch == "CH":
                    caveat = (
                        "CH-01 and CH-02 landed in opposite behavior clusters;"
                        " see individual task sections below."
                    )
                _append_avg_group(f"{arch} ({g['label']})", g, caveat=caveat)

        for task_id in sorted(per_task):
            e = per_task[task_id]
            task_total = max(1, e["instrumented_cpu_ns"])
            calls = _format_tool_calls(tools_by_task.get(task_id, {}))
            lines.extend(
                [
                    "",
                    f"### {task_id}",
                    "",
                    f"- sessions: {', '.join(sorted(e['sessions']))}",
                    f"- tool invocations: {calls}",
                    f"- instrumented CPU: {e['instrumented_cpu_ns'] / 1e6:.1f} ms",
                    f"- hardware amenable: strict {e['amenable_strict_share'] * 100:.1f}%"
                    f" ({e['amenable_strict_ns'] / 1e6:.1f} ms),"
                    f" broad {e['amenable_broad_share'] * 100:.1f}%"
                    f" ({e['amenable_broad_ns'] / 1e6:.1f} ms)",
                    "",
                    "| Category | Tier | CPU ms | Share of task | Wall ms | Count | Bytes in | Bytes out |",
                    "|---|---|---|---|---|---|---|---|",
                ]
            )
            rows = sorted(
                e["categories"].items(), key=lambda kv: -kv[1]["cpu_ns"]
            )
            for cat, v in rows:
                lines.append(
                    f"| {cat} | {TIER.get(cat, 'none')} | {v['cpu_ns'] / 1e6:.1f} "
                    f"| {v['cpu_ns'] / task_total * 100:.1f}% "
                    f"| {v['wall_ns'] / 1e6:.1f} | {v['count']} "
                    f"| {v['bytes_in']} | {v['bytes_out']} |"
                )

    user_sys = run["os_times_user_sys"]
    lines.extend(
        [
            "",
            "## Process user/system split",
            "",
            f"- user: {user_sys['user']:.3f} s, system: {user_sys['system']:.3f} s",
            "- per-category kernel-time attribution is approximate; category timers"
            " are user-space, syscall-heavy regions surface partly as system time",
            "",
        "## Per-session summary",
        "",
        "| Session | Task | Turns | Tool calls | Graph nodes | Dispatches | Wall s | Thread CPU ms |",
        "|---|---|---|---|---|---|---|---|",
        ]
    )

    def _session_rows(sessions: list[dict[str, Any]]) -> None:
        for s in sessions:
            calls = ", ".join(f"{k}:{v}" for k, v in sorted(s.get("tool_call_counts", {}).items()))
            lines.append(
                f"| {s['session_id']} | {s.get('task_id', 'n/a')} | {s['turns']} "
                f"| {calls or 'none'} | {s.get('graph_nodes', 'n/a')} "
                f"| {s.get('dispatch_decisions', 'n/a')} "
                f"| {s['wall_s']:.2f} | {s['thread_cpu_ns'] / 1e6:.2f} |"
            )
            _session_rows(s.get("subagent_results", []))

    _session_rows(run["per_session"])

    # Aggregate tool usage across all sessions including sub-agents.
    tool_totals: dict[str, int] = {}
    tool_byte_totals: dict[str, int] = {}

    def _collect(sessions: list[dict[str, Any]]) -> None:
        for s in sessions:
            for k, v in s.get("tool_call_counts", {}).items():
                tool_totals[k] = tool_totals.get(k, 0) + v
            for k, v in s.get("tool_result_bytes", {}).items():
                tool_byte_totals[k] = tool_byte_totals.get(k, 0) + v
            _collect(s.get("subagent_results", []))

    _collect(run["per_session"])
    lines.extend(
        [
            "",
            "## Tool usage (all sessions including sub-agents)",
            "",
            "| Tool | Calls | Result bytes |",
            "|---|---|---|",
        ]
    )
    for tool in sorted(tool_totals):
        lines.append(
            f"| {tool} | {tool_totals[tool]} | {tool_byte_totals.get(tool, 0)} |"
        )

    lines.extend(["", "## Tasks executed", ""])
    for t in artifact["task_assignments"]:
        lines.append(f"### {t['task_id']} ({t['profile']})")
        lines.append("")
        lines.append(f"Goal: {t['goal']}")
        lines.append("")
        for i, turn in enumerate(t["turns"]):
            lines.append(f"- turn {i}: {turn}")
        lines.append("")

    reproduce = artifact.get(
        "reproduce_cmd",
        "python -m apu_characterization.experiments.single_agent_breakdown"
        f" --profile {cfg['profile']} --seed {cfg['seed']} --sessions {cfg['sessions']}"
        f" --llm-scale {cfg['llm_median_scale']}",
    )
    lines.extend(["", "## Reproduce", "", "```", reproduce, "```"])

    md_path = out_dir / f"{stem}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="mixed")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sessions", type=int, default=1)
    parser.add_argument("--llm-scale", type=float, default=0.05, dest="llm_scale")
    parser.add_argument("--out", type=Path, default=Path("apu_characterization/out"))
    args = parser.parse_args()

    artifact = run_experiment(args.profile, args.seed, args.sessions, args.llm_scale, args.out)
    stem = artifact.get("_report_stem", artifact_stem("single_agent_breakdown", DEBUG_ONLY))
    md = write_report(artifact, args.out, stem=stem)

    inv = artifact["invariant"]
    print(f"validity: {DEBUG_ONLY} (not publishable)")
    print(f"json: {args.out / (stem + '.json')}")
    print(f"md:   {md}")
    print(
        f"invariant: residual {inv['residual_fraction'] * 100:.1f}% "
        f"(limit {RESIDUAL_LIMIT * 100:.0f}%) -> {'PASS' if inv['pass'] else 'FAIL'}"
    )
    if not inv["pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
