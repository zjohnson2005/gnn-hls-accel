"""Trace-replay locality ablation: same recorded tool-call trace, both localities.

Loads ``tool_call_sequence`` from a source real_agent_breakdown artifact and
replays it under local vs remote search on the real LangGraph path. This is a
**matched-pair** comparison (identical tool decisions); contrast with the full
remote rerun which is an independent sample subject to model drift.

Run (debug, no API key):
  python -m apu_characterization.experiments.trace_replay_ablation \\
      --trace apu_characterization/out/real_agent_breakdown_debug.json \\
      --tasks SH-01,SH-02

Publishable trace source must come from an OpenAI breakdown artifact recorded
on Linux with audit PASS; replay itself uses the deterministic replay model
(no live API during replay).

Artifacts: out/trace_replay_ablation.json / .md
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
from ..audit import apply_audit_to_artifact
from ..harness.runner import _os_times_delta, _os_times_snapshot, _warm_shared_state
from ..instr import RunAccumulator, install_gc_hooks, measure_timer_overhead_ns
from ..profiles import LOCALITY_ABLATION_PROFILE
from ..setup_validate import load_and_validate
from ..tasks import DEFAULT_LOCALITY_ABLATION_TASKS, task_by_id
from ..tools import LOCALITY_LOCAL, LOCALITY_REMOTE, reset_tool_locality, set_tool_locality
from ..validity import DEBUG_ONLY, PUBLISHABLE, artifact_stem, validity_banner
from .real_agent_breakdown import (
    RESIDUAL_LIMIT,
    _env_info,
    _git_state,
    _load_setup_digest,
    _require_langgraph,
    build_langchain_tools,
    load_trace_steps_from_artifact,
    run_real_session,
)
from .single_agent_breakdown import SETUP_JSON
from .tool_locality_ablation import (
    _comparison,
    _interpretation,
    _session_row,
    write_ablation_report,
)


def run_trace_replay(
    task_ids: list[str],
    trace_artifact: dict[str, Any],
    seed: int,
    llm_scale: float,
    retrieve_locality: str,
) -> dict[str, Any]:
    spec = LOCALITY_ABLATION_PROFILE
    install_gc_hooks()
    _warm_shared_state()
    tools = build_langchain_tools()
    acc = RunAccumulator(profile=spec.name)
    os_start = _os_times_snapshot()
    wall_start = time.perf_counter_ns()
    proc_start = time.process_time()
    per_session: list[dict[str, Any]] = []
    arms = (LOCALITY_LOCAL, LOCALITY_REMOTE)

    for task_id in task_ids:
        task = task_by_id(task_id)
        replay_steps = load_trace_steps_from_artifact(trace_artifact, task_id)
        for search_loc in arms:
            sid = f"{task_id}_replay_{search_loc}"
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
                    "scripted",
                    llm_scale,
                    tools,
                    replay_steps=replay_steps,
                )
                result["search_locality"] = search_loc
                result["retrieve_locality"] = retrieve_locality
                result["trace_source"] = trace_artifact.get("config", {})
                per_session.append(result)
            finally:
                reset_tool_locality(tok)

    wall_end = time.perf_counter_ns()
    os_end = _os_times_snapshot()
    proc_end = time.process_time()
    total_process_cpu_ns = sum(s.get("process_cpu_ns", 0) for s in per_session)
    if total_process_cpu_ns <= 0:
        total_process_cpu_ns = int((proc_end - proc_start) * 1e9)

    return acc.to_run_dict(
        env={},
        config={
            "profile": "trace_replay_ablation",
            "seed": seed,
            "mode": "sequential",
            "backend": "trace_replay",
            "llm_median_scale": llm_scale,
            "task_ids": task_ids,
            "retrieve_locality": retrieve_locality,
            "comparison_type": "matched_trace_replay",
            "trace_source_digest": trace_artifact.get("setup_ref", {}).get("setup_digest"),
            "trace_source_file": trace_artifact.get("_source_path"),
            "total_cpu_basis": "process_time_all_threads",
        },
        total_thread_cpu_ns=total_process_cpu_ns,
        total_wall_ns=wall_end - wall_start,
        os_times=_os_times_delta(os_start, os_end),
        per_session=sorted(per_session, key=lambda s: s["session_id"]),
    )


def main() -> None:
    import warnings

    warnings.filterwarnings("ignore", message=".*create_react_agent.*", category=DeprecationWarning)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trace",
        type=Path,
        required=True,
        help="Source real_agent_breakdown JSON with tool_call_sequence fields",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--tasks",
        default=",".join(DEFAULT_LOCALITY_ABLATION_TASKS),
        help="Comma-separated task IDs present in the trace artifact",
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

    if not args.trace.is_file():
        raise SystemExit(f"trace artifact not found: {args.trace}")

    load_and_validate(strict=not args.allow_dirty)
    _require_langgraph()

    trace_artifact = json.loads(args.trace.read_text(encoding="utf-8"))
    trace_artifact["_source_path"] = str(args.trace)
    task_ids = [t.strip() for t in args.tasks.split(",") if t.strip()]
    for tid in task_ids:
        task_by_id(tid)
        load_trace_steps_from_artifact(trace_artifact, tid)

    setup_ref = _load_setup_digest()
    t0 = time.perf_counter()
    run = run_trace_replay(
        task_ids,
        trace_artifact,
        args.seed,
        args.llm_scale,
        args.retrieve_locality,
    )
    batch_wall_s = time.perf_counter() - t0

    # Replay uses deterministic model; publishable when trace source is publishable.
    src_validity = trace_artifact.get("result_validity", DEBUG_ONLY)
    validity = PUBLISHABLE if src_validity == PUBLISHABLE else DEBUG_ONLY
    stem = artifact_stem("trace_replay_ablation", validity)
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
        "experiment": "trace_replay_ablation",
        "result_validity": validity,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "setup_ref": setup_ref,
        "git": _git_state(),
        "env": _env_info(),
        "config": {
            **run["config"],
            "trace_file": str(args.trace),
            "comparison_type": "matched_trace_replay",
        },
        "timer_overhead_ns_per_pair": measure_timer_overhead_ns(100_000),
        "batch_wall_s": batch_wall_s,
        "run": run,
        "per_task": per_task,
        "per_task_wall_cpu": per_task_wall,
        "session_rows": session_rows,
        "comparison": comparison,
        "interpretation": _interpretation(comparison),
        "reproduce_cmd": (
            "python -m apu_characterization.experiments.trace_replay_ablation"
            f" --trace {args.trace} --seed {args.seed}"
            f" --tasks {','.join(task_ids)}"
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
    print(f"validity: {artifact['result_validity']}")
    print(f"comparison_type: matched_trace_replay")
    print(f"audit pass: {audit.get('pass')}")
    print(f"json: {args.out / (stem + '.json')}")
    print(f"md:   {md}")
    print(f"interpretation: {artifact['interpretation']}")
    print(
        f"invariant: residual {inv['residual_fraction'] * 100:.1f}% "
        f"(limit {RESIDUAL_LIMIT * 100:.0f}%) -> {'PASS' if inv['pass'] else 'FAIL'}"
    )
    if audit.get("violations"):
        for v in audit["violations"][:5]:
            print(f"  AUDIT VIOLATION: {v}")
    if not inv["pass"] or not audit.get("pass"):
        sys.exit(1)


if __name__ == "__main__":
    main()
