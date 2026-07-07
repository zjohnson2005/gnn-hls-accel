"""Tool-locality ablation: local in-process search vs mock remote search.

The publishable real-agent run showed CPU-heavy sessions when the model
invoked **local** search (50 MB regex scan). Production search is usually
remote; this experiment holds task goals and agent framework fixed while
swapping only the search tool's locality (and optionally retrieve).

Each task runs twice: search=local (baseline) and search=remote (seeded
HTTP envelope + I/O wait, same model as mock API). Compare host CPU,
TOOL_COMPUTE, and HTTP_CLIENT to see whether search CPU is fundamental or
an artifact of the mock tool implementation.

Run (debug, no API key):
  python -m apu_characterization.experiments.tool_locality_ablation \\
      --backend scripted --seed 0

Publishable:
  python -m apu_characterization.experiments.tool_locality_ablation \\
      --backend openai --seed 0

Artifacts: out/tool_locality_ablation.json / .md (publishable with openai)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..amenability import compute_per_task, compute_per_task_wall_cpu
from ..harness.runner import _os_times_delta, _os_times_snapshot, _warm_shared_state
from ..instr import RunAccumulator, install_gc_hooks, measure_timer_overhead_ns
from ..profiles import LOCALITY_ABLATION_PROFILE
from ..tasks import DEFAULT_LOCALITY_ABLATION_TASKS, task_by_id
from ..tools import LOCALITY_LOCAL, LOCALITY_REMOTE, reset_tool_locality, set_tool_locality
from ..audit import apply_audit_to_artifact
from ..setup_validate import load_and_validate
from ..validity import (
    DEBUG_ONLY,
    PUBLISHABLE,
    artifact_stem,
    validity_banner,
    validity_for_real_agent_backend,
)
from .real_agent_breakdown import (
    RESIDUAL_LIMIT,
    _env_info,
    _git_state,
    _load_setup_digest,
    _require_langgraph,
    build_langchain_tools,
    run_real_session,
)


def _session_row(
    per_session_category: dict[str, dict[str, dict[str, int]]],
    per_session: list[dict[str, Any]],
    session_id: str,
    task_id: str,
    search_locality: str,
    retrieve_locality: str,
) -> dict[str, Any]:
    cats = per_session_category.get(session_id, {})
    sess = next(s for s in per_session if s["session_id"] == session_id)
    wall_s = sess["wall_s"]
    cpu_ms = sess["process_cpu_ns"] / 1e6
    tool_cpu = cats.get("TOOL_COMPUTE", {}).get("cpu_ns", 0) / 1e6
    http_cpu = cats.get("HTTP_CLIENT", {}).get("cpu_ns", 0) / 1e6
    http_wall_s = cats.get("HTTP_CLIENT", {}).get("wall_ns", 0) / 1e9
    orch_cpu = (
        cats.get("ORCH_SETUP", {}).get("cpu_ns", 0)
        + cats.get("ORCH_DISPATCH", {}).get("cpu_ns", 0)
    ) / 1e6
    io_pct = (http_wall_s / wall_s * 100) if wall_s > 0 else 0.0
    cpu_pct = (cpu_ms / 1000 / wall_s * 100) if wall_s > 0 else 0.0
    return {
        "session_id": session_id,
        "task_id": task_id,
        "search_locality": search_locality,
        "retrieve_locality": retrieve_locality,
        "session_wall_s": round(wall_s, 3),
        "host_cpu_ms": round(cpu_ms, 1),
        "tool_compute_cpu_ms": round(tool_cpu, 1),
        "http_client_cpu_ms": round(http_cpu, 1),
        "orch_cpu_ms": round(orch_cpu, 1),
        "llm_io_wait_s": round(http_wall_s, 3),
        "io_pct_of_wall": round(io_pct, 1),
        "cpu_pct_of_wall": round(cpu_pct, 1),
        "tool_call_counts": sess.get("tool_call_counts", {}),
        "search_calls": sess.get("tool_call_counts", {}).get("search", 0),
    }


def _comparison(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_task: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_task.setdefault(row["task_id"], {})[row["search_locality"]] = row

    out: list[dict[str, Any]] = []
    for task_id in sorted(by_task):
        arms = by_task[task_id]
        local = arms.get(LOCALITY_LOCAL)
        remote = arms.get(LOCALITY_REMOTE)
        if not local or not remote:
            continue
        tool_delta = remote["tool_compute_cpu_ms"] - local["tool_compute_cpu_ms"]
        cpu_delta = remote["host_cpu_ms"] - local["host_cpu_ms"]
        io_delta = remote["io_pct_of_wall"] - local["io_pct_of_wall"]
        cpu_wall_delta = remote["cpu_pct_of_wall"] - local["cpu_pct_of_wall"]
        out.append(
            {
                "task_id": task_id,
                "matched_pair": (
                    local["search_calls"] == remote["search_calls"]
                    and local["search_calls"] > 0
                ),
                "local_host_cpu_ms": local["host_cpu_ms"],
                "remote_host_cpu_ms": remote["host_cpu_ms"],
                "host_cpu_delta_ms": round(cpu_delta, 1),
                "local_tool_compute_ms": local["tool_compute_cpu_ms"],
                "remote_tool_compute_ms": remote["tool_compute_cpu_ms"],
                "tool_compute_delta_ms": round(tool_delta, 1),
                "local_io_pct": local["io_pct_of_wall"],
                "remote_io_pct": remote["io_pct_of_wall"],
                "io_pct_delta": round(io_delta, 1),
                "local_cpu_pct_wall": local["cpu_pct_of_wall"],
                "remote_cpu_pct_wall": remote["cpu_pct_of_wall"],
                "cpu_pct_wall_delta": round(cpu_wall_delta, 1),
                "local_search_calls": local["search_calls"],
                "remote_search_calls": remote["search_calls"],
            }
        )
    return out


def _interpretation(comparison: list[dict[str, Any]]) -> str:
    if not comparison:
        return "No paired local/remote rows to compare."

    matched = [c for c in comparison if c.get("matched_pair")]
    sh_matched = [c for c in matched if c["task_id"].startswith("SH-")]

    lines = [
        "Remote search moves tool body work from TOOL_COMPUTE (local regex scan) "
        "into HTTP_CLIENT envelope CPU plus I/O wait (time.sleep round trip).",
    ]
    if sh_matched:
        sh_cpu_drop = sum(c["cpu_pct_wall_delta"] for c in sh_matched) / len(sh_matched)
        sh_tool_drop = sum(c["tool_compute_delta_ms"] for c in sh_matched) / len(sh_matched)
        lines.append(
            f"Matched search pairs (identical search call counts, SH-* only): "
            f"mean CPU% of wall delta {sh_cpu_drop:.1f} pp; "
            f"mean TOOL_COMPUTE delta {sh_tool_drop:.1f} ms (n={len(sh_matched)})."
        )
        if sh_tool_drop < -500 and sh_cpu_drop < -5:
            lines.append(
                "Interpretation: in-process search CPU is a harness artifact; "
                "remote search is the production-representative instrument."
            )
    else:
        lines.append(
            "No matched search pairs (same search call count in both arms); "
            "do not quote cross-arm deltas as causal."
        )

    unmatched = [c for c in comparison if not c.get("matched_pair")]
    if unmatched:
        lines.append(
            f"Unmatched context rows (different tool counts or no search): "
            f"{', '.join(c['task_id'] for c in unmatched)} — directional only."
        )
    return " ".join(lines)


def write_ablation_report(artifact: dict[str, Any], out_dir: Path, stem: str) -> Path:
    validity = artifact["result_validity"]
    rows = artifact["session_rows"]
    comparison = artifact["comparison"]
    md_path = out_dir / f"{stem}.md"

    lines = [
        validity_banner(validity),
        "",
        "# Tool-locality ablation (search local vs remote)",
        "",
        f"Generated: {artifact['generated_utc']}",
        f"Setup digest: `{artifact['setup_ref'].get('setup_digest', 'unknown')}`",
        "",
        "## Question",
        "",
        "Does search push sessions into the CPU-heavy regime because search is "
        "inherently local compute, or because this harness implements search as an "
        "in-process 50 MB regex scan?",
        "",
        "## Configuration",
        "",
        f"- Backend: `{artifact['config']['backend']}`",
        f"- Seed: {artifact['config']['seed']}",
        f"- Tasks: {', '.join(artifact['config']['task_ids'])}",
        f"- Search locality arms: local (regex corpus) vs remote (mock HTTP + sleep)",
        f"- Retrieve locality: `{artifact['config']['retrieve_locality']}`",
        f"- Payload profile: `{artifact['config']['payload_profile']}` "
        f"(tool results padded to {artifact['config']['tool_result_kb_max']} KB max; "
        "identical across local/remote arms, does not affect TOOL_COMPUTE comparison)",
        "",
        f"- Comparison type: **{artifact['config'].get('comparison_type', 'matched_pair')}**",
        "",
        "## Per-session results",
        "",
        "| task | search | wall (s) | host CPU (ms) | TOOL_COMPUTE (ms) | "
        "HTTP_CLIENT (ms) | I/O % wall | CPU % wall | search calls |",
        "|------|--------|----------|---------------|-------------------|"
        "------------------|------------|------------|--------------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['task_id']} | {r['search_locality']} | {r['session_wall_s']} | "
            f"{r['host_cpu_ms']} | {r['tool_compute_cpu_ms']} | "
            f"{r['http_client_cpu_ms']} | {r['io_pct_of_wall']} | "
            f"{r['cpu_pct_of_wall']} | {r['search_calls']} |"
        )

    lines.extend(
        [
            "",
            "## Local vs remote (paired delta)",
            "",
            "Rows with **matched** = identical search call counts in both arms. "
            "Only matched SH-* rows support causal search-locality claims.",
            "",
            "| task | matched | local CPU ms | remote CPU ms | Δ CPU ms | local TOOL ms | "
            "remote TOOL ms | Δ TOOL ms | local CPU% wall | remote CPU% wall | "
            "Δ CPU% wall |",
            "|------|---------|--------------|---------------|----------|---------------|"
            "----------------|------------|-----------------|------------------|"
            "-------------|",
        ]
    )
    for c in comparison:
        lines.append(
            f"| {c['task_id']} | {'yes' if c.get('matched_pair') else 'no'} | "
            f"{c['local_host_cpu_ms']} | {c['remote_host_cpu_ms']} | "
            f"{c['host_cpu_delta_ms']} | {c['local_tool_compute_ms']} | "
            f"{c['remote_tool_compute_ms']} | {c['tool_compute_delta_ms']} | "
            f"{c['local_cpu_pct_wall']} | {c['remote_cpu_pct_wall']} | "
            f"{c['cpu_pct_wall_delta']} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            artifact["interpretation"],
            "",
            "## Reproduce",
            "",
            f"```\n{artifact['reproduce_cmd']}\n```",
            "",
            "## Invariant",
            "",
            f"Residual {artifact['invariant']['residual_fraction'] * 100:.1f}% "
            f"(limit {RESIDUAL_LIMIT * 100:.0f}%) → "
            f"{'PASS' if artifact['invariant']['pass'] else 'FAIL'}",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def run_ablation(
    task_ids: list[str],
    seed: int,
    backend: str,
    llm_scale: float,
    retrieve_locality: str,
) -> dict[str, Any]:
    install_gc_hooks()
    _warm_shared_state()
    _require_langgraph()
    tools = build_langchain_tools()

    acc = RunAccumulator(profile="tool_locality_ablation")
    os_start = _os_times_snapshot()
    wall_start = time.perf_counter_ns()
    proc_start = time.process_time()
    per_session: list[dict[str, Any]] = []
    arms = (LOCALITY_LOCAL, LOCALITY_REMOTE)

    for task_id in task_ids:
        task = task_by_id(task_id)
        spec = LOCALITY_ABLATION_PROFILE
        for search_loc in arms:
            sid = f"{task_id}_search_{search_loc}"
            overrides: dict[str, str] = {"search": search_loc}
            if retrieve_locality == LOCALITY_REMOTE:
                overrides["retrieve"] = LOCALITY_REMOTE
            tok = set_tool_locality(**overrides)
            try:
                result = run_real_session(
                    acc,
                    sid,
                    task,
                    spec,
                    seed,
                    backend,
                    llm_scale,
                    tools,
                )
                result["search_locality"] = search_loc
                result["retrieve_locality"] = retrieve_locality
                per_session.append(result)
            finally:
                reset_tool_locality(tok)

    wall_end = time.perf_counter_ns()
    os_end = _os_times_snapshot()
    proc_end = time.process_time()
    total_process_cpu_ns = sum(s.get("process_cpu_ns", 0) for s in per_session)
    if total_process_cpu_ns <= 0:
        total_process_cpu_ns = int((proc_end - proc_start) * 1e9)

    run = acc.to_run_dict(
        env={},
        config={
            "profile": "tool_locality_ablation",
            "seed": seed,
            "mode": "sequential",
            "backend": backend,
            "llm_median_scale": llm_scale,
            "task_ids": task_ids,
            "retrieve_locality": retrieve_locality,
            "total_cpu_basis": "process_time_all_threads",
        },
        total_thread_cpu_ns=total_process_cpu_ns,
        total_wall_ns=wall_end - wall_start,
        os_times=_os_times_delta(os_start, os_end),
        per_session=sorted(per_session, key=lambda s: s["session_id"]),
    )
    return run


def main() -> None:
    import warnings

    warnings.filterwarnings("ignore", message=".*create_react_agent.*", category=DeprecationWarning)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("scripted", "openai"), default="scripted")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--tasks",
        default=",".join(DEFAULT_LOCALITY_ABLATION_TASKS),
        help="Comma-separated task IDs (default: SH-01,SH-02,CH-02,RE-02,RH-01)",
    )
    parser.add_argument("--llm-scale", type=float, default=0.05, dest="llm_scale")
    parser.add_argument(
        "--retrieve-locality",
        choices=(LOCALITY_LOCAL, LOCALITY_REMOTE),
        default=LOCALITY_LOCAL,
        dest="retrieve_locality",
    )
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("apu_characterization/out"))
    args = parser.parse_args()

    load_and_validate(strict=args.backend == "openai" and not args.allow_dirty)
    _require_langgraph()

    task_ids = [t.strip() for t in args.tasks.split(",") if t.strip()]
    for tid in task_ids:
        task_by_id(tid)

    if args.backend == "openai" and len(task_ids) * 2 > 24:
        raise SystemExit("openai backend: at most 12 tasks (24 sessions) per run")

    setup_ref = _load_setup_digest()
    t0 = time.perf_counter()
    run = run_ablation(
        task_ids,
        args.seed,
        args.backend,
        args.llm_scale,
        args.retrieve_locality,
    )
    batch_wall_s = time.perf_counter() - t0

    validity = validity_for_real_agent_backend(args.backend)
    stem = artifact_stem("tool_locality_ablation", validity)
    per_task = compute_per_task(run)
    per_task_wall = compute_per_task_wall_cpu(per_task, run["per_session"])

    session_rows = [
        _session_row(
            run["per_session_category"],
            run["per_session"],
            s["session_id"],
            s["task_id"],
            s.get("search_locality", LOCALITY_LOCAL),
            s.get("retrieve_locality", LOCALITY_LOCAL),
        )
        for s in run["per_session"]
    ]
    comparison = _comparison(session_rows)

    artifact: dict[str, Any] = {
        "experiment": "tool_locality_ablation",
        "result_validity": validity,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "setup_ref": setup_ref,
        "git": _git_state(),
        "env": _env_info(),
        "config": {
            "backend": args.backend,
            "seed": args.seed,
            "task_ids": task_ids,
            "retrieve_locality": args.retrieve_locality,
            "llm_median_scale": args.llm_scale,
            "payload_profile": LOCALITY_ABLATION_PROFILE.name,
            "tool_result_kb_max": LOCALITY_ABLATION_PROFILE.tool_result_kb_max,
            "comparison_type": "local_vs_remote_paired_arms",
            "matched_pair_definition": (
                "matched_pair=true when local and remote arms have the same "
                "search call count and search_calls>0; headline deltas use SH-* "
                "matched rows only (methods validation, not APU sizing)."
            ),
            "payload_note": (
                "Synthetic tool-result padding capped at 4 KB so multi-tool "
                "OpenAI sessions stay under 128k context. Padding is identical "
                "across local/remote search arms."
            ),
        },
        "timer_overhead_ns_per_pair": measure_timer_overhead_ns(100_000),
        "batch_wall_s": batch_wall_s,
        "run": run,
        "per_task": per_task,
        "per_task_wall_cpu": per_task_wall,
        "session_rows": session_rows,
        "comparison": comparison,
        "comparison_matched": [c for c in comparison if c.get("matched_pair")],
        "interpretation": _interpretation(comparison),
        "reproduce_cmd": (
            "python -m apu_characterization.experiments.tool_locality_ablation"
            f" --backend {args.backend} --seed {args.seed}"
            f" --tasks {','.join(task_ids)}"
            f" --retrieve-locality {args.retrieve_locality}"
        ),
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

    apply_audit_to_artifact(artifact)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{stem}.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    md = write_ablation_report(artifact, args.out, stem)

    inv = artifact["invariant"]
    audit = artifact.get("audit", {})
    print(f"validity: {validity}")
    print(f"audit pass: {audit.get('pass')}")
    print(f"json: {args.out / (stem + '.json')}")
    print(f"md:   {md}")
    if validity == DEBUG_ONLY:
        print("NOTE: debug artifact — re-run with --backend openai for publishable data")
    print(f"interpretation: {artifact['interpretation']}")
    print(
        f"invariant: residual {inv['residual_fraction'] * 100:.1f}% "
        f"(limit {RESIDUAL_LIMIT * 100:.0f}%) -> {'PASS' if inv['pass'] else 'FAIL'}"
    )
    if audit.get("violations"):
        for v in audit["violations"][:5]:
            print(f"  AUDIT VIOLATION: {v}")
    if not inv["pass"] or (validity == PUBLISHABLE and not audit.get("pass")):
        sys.exit(1)


if __name__ == "__main__":
    main()
