"""Retrieve-locality ablation: LH-01 local matmul vs mock-remote retrieve.

Minimum viable matched pair for the caption: local retrieve TOOL mass converts
to remote I/O wait, consistent with the search-locality ablation precedent.

Run (publishable):
  export OPENAI_API_KEY=sk-...
  python -m apu_characterization.experiments.retrieve_locality_ablation \\
      --backend openai --seeds 0,1

Debug (no API key):
  python -m apu_characterization.experiments.retrieve_locality_ablation \\
      --backend scripted --seeds 0

Artifacts: out/retrieve_locality_ablation.json / .md
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
from ..env_pin import assert_blas_pinned
from ..harness.runner import _os_times_delta, _os_times_snapshot, _warm_shared_state
from ..instr import RunAccumulator, install_gc_hooks, measure_timer_overhead_ns
from ..profiles import LOCALITY_ABLATION_PROFILE
from ..setup_validate import load_and_validate
from ..tasks import task_by_id
from ..tools import LOCALITY_LOCAL, LOCALITY_REMOTE, reset_tool_locality, set_tool_locality
from ..validity import PUBLISHABLE, artifact_stem, validity_banner, validity_for_real_agent_backend
from .real_agent_breakdown import (
    RESIDUAL_LIMIT,
    _env_info,
    _git_state,
    _load_setup_digest,
    _require_langgraph,
    build_langchain_tools,
    run_real_session,
)

TASK_ID = "LH-01"
OUT_DIR = Path("apu_characterization/out")
STEM = "retrieve_locality_ablation"


def _row(
    per_session_category: dict[str, dict[str, dict[str, int]]],
    per_session: list[dict[str, Any]],
    session_id: str,
    retrieve_locality: str,
) -> dict[str, Any]:
    cats = per_session_category.get(session_id, {})
    sess = next(s for s in per_session if s["session_id"] == session_id)
    wall_s = sess["wall_s"]
    cpu_ms = sess["process_cpu_ns"] / 1e6
    tool_cpu = cats.get("TOOL_COMPUTE", {}).get("cpu_ns", 0) / 1e6
    http_wall_s = cats.get("HTTP_CLIENT", {}).get("wall_ns", 0) / 1e9
    llm_wall_s = cats.get("CLIENT_HTTP", {}).get("wall_ns", 0) / 1e9
    retrieve_calls = sess.get("tool_call_counts", {}).get("retrieve", 0)
    return {
        "session_id": session_id,
        "task_id": TASK_ID,
        "seed": sess.get("seed"),
        "retrieve_locality": retrieve_locality,
        "session_wall_s": round(wall_s, 3),
        "host_cpu_ms": round(cpu_ms, 1),
        "tool_compute_cpu_ms": round(tool_cpu, 1),
        "remote_retrieve_io_wait_s": round(http_wall_s, 3),
        "llm_io_wait_s": round(llm_wall_s, 3),
        "io_pct_of_wall": round((http_wall_s / wall_s * 100) if wall_s else 0, 1),
        "cpu_pct_of_wall": round((cpu_ms / 1000 / wall_s * 100) if wall_s else 0, 1),
        "retrieve_calls": retrieve_calls,
    }


def _comparison(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_seed: dict[int, dict[str, dict[str, Any]]] = {}
    for row in rows:
        seed = int(row["seed"])
        by_seed.setdefault(seed, {})[row["retrieve_locality"]] = row

    out: list[dict[str, Any]] = []
    for seed in sorted(by_seed):
        arms = by_seed[seed]
        local = arms.get(LOCALITY_LOCAL)
        remote = arms.get(LOCALITY_REMOTE)
        if not local or not remote:
            continue
        matched = local["retrieve_calls"] == remote["retrieve_calls"] and local["retrieve_calls"] > 0
        out.append(
            {
                "seed": seed,
                "matched_pair": matched,
                "local_host_cpu_ms": local["host_cpu_ms"],
                "remote_host_cpu_ms": remote["host_cpu_ms"],
                "host_cpu_delta_ms": round(remote["host_cpu_ms"] - local["host_cpu_ms"], 1),
                "local_tool_compute_ms": local["tool_compute_cpu_ms"],
                "remote_tool_compute_ms": remote["tool_compute_cpu_ms"],
                "tool_compute_delta_ms": round(
                    remote["tool_compute_cpu_ms"] - local["tool_compute_cpu_ms"], 1
                ),
                "local_io_pct": local["io_pct_of_wall"],
                "remote_io_pct": remote["io_pct_of_wall"],
                "io_pct_delta": round(remote["io_pct_of_wall"] - local["io_pct_of_wall"], 1),
                "local_cpu_pct_wall": local["cpu_pct_of_wall"],
                "remote_cpu_pct_wall": remote["cpu_pct_of_wall"],
                "retrieve_calls": local["retrieve_calls"],
            }
        )
    return out


def run_ablation(seeds: list[int], backend: str, llm_scale: float) -> dict[str, Any]:
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
    proc_start = time.process_time()
    per_session: list[dict[str, Any]] = []

    task = task_by_id(TASK_ID)
    spec = LOCALITY_ABLATION_PROFILE

    for seed in seeds:
        for retrieve_loc in (LOCALITY_LOCAL, LOCALITY_REMOTE):
            sid = f"{TASK_ID}_s{seed}_retrieve_{retrieve_loc}"
            tok = set_tool_locality(search=LOCALITY_REMOTE, retrieve=retrieve_loc)
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
                    instr_version=3,
                )
                result["retrieve_locality"] = retrieve_loc
                result["seed"] = seed
                result["search_locality"] = LOCALITY_REMOTE
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
        env=_env_info(),
        config={
            "profile": LOCALITY_ABLATION_PROFILE.name,
            "seeds": seeds,
            "mode": "sequential",
            "backend": backend,
            "llm_median_scale": llm_scale,
            "task_ids": [TASK_ID],
            "search_locality": LOCALITY_REMOTE,
            "retrieve_locality_arms": [LOCALITY_LOCAL, LOCALITY_REMOTE],
            "instr_version": 3,
            "total_cpu_basis": "process_time_all_threads",
        },
        total_thread_cpu_ns=total_process_cpu_ns,
        total_wall_ns=wall_end - wall_start,
        os_times=_os_times_delta(os_start, os_end),
        per_session=sorted(per_session, key=lambda s: s["session_id"]),
    )
    return run


def write_report(artifact: dict[str, Any], out_dir: Path) -> Path:
    rows = artifact["session_rows"]
    comparison = artifact["comparison"]
    md = out_dir / f"{STEM}.md"
    lines = [
        validity_banner(artifact["result_validity"]),
        "",
        "# Retrieve-locality ablation (LH-01, local matmul vs mock-remote)",
        "",
        f"Generated: {artifact['generated_utc']}",
        f"Setup digest: `{artifact['setup_ref'].get('setup_digest', 'unknown')}`",
        "",
        "## Question",
        "",
        "Does local retrieve (100k×384 matmul in TOOL_COMPUTE) convert to remote "
        "mock-retrieve I/O wait when only retrieve locality changes?",
        "",
        "## Per-session",
        "",
        "| seed | retrieve | wall (s) | host CPU (ms) | TOOL (ms) | retrieve I/O (s) | "
        "LLM wait (s) | I/O % wall | CPU % wall | retrieve calls |",
        "|------|----------|----------|---------------|-----------|------------------|"
        "-------------|------------|------------|----------------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['seed']} | {r['retrieve_locality']} | {r['session_wall_s']} | "
            f"{r['host_cpu_ms']} | {r['tool_compute_cpu_ms']} | "
            f"{r['remote_retrieve_io_wait_s']} | {r['llm_io_wait_s']} | "
            f"{r['io_pct_of_wall']} | {r['cpu_pct_of_wall']} | {r['retrieve_calls']} |"
        )
    lines.extend(["", "## Paired delta (local → remote)", ""])
    if comparison:
        lines.extend(
            [
                "| seed | matched | Δ host ms | Δ TOOL ms | Δ I/O % wall | retrieve calls |",
                "|------|---------|-----------|-----------|--------------|----------------|",
            ]
        )
        for c in comparison:
            lines.append(
                f"| {c['seed']} | {'yes' if c['matched_pair'] else 'no'} | "
                f"{c['host_cpu_delta_ms']} | {c['tool_compute_delta_ms']} | "
                f"{c['io_pct_delta']} | {c['retrieve_calls']} |"
            )
    else:
        lines.append("_No paired rows._")
    lines.extend(["", "## Interpretation", "", artifact.get("interpretation", ""), ""])
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md


def main() -> None:
    parser = argparse.ArgumentParser(description="LH-01 retrieve locality ablation")
    parser.add_argument("--backend", default="scripted", choices=("scripted", "openai"))
    parser.add_argument("--seeds", default="0,1")
    parser.add_argument("--llm-scale", type=float, default=1.0)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    load_and_validate(strict="--allow-dirty" not in sys.argv)

    run = run_ablation(seeds, args.backend, args.llm_scale)
    per_task = compute_per_task(run)
    per_session_category = run.get("per_session_category") or {}

    rows = [
        _row(per_session_category, run["per_session"], s["session_id"], s["retrieve_locality"])
        for s in run["per_session"]
    ]
    for r, s in zip(rows, run["per_session"]):
        r["seed"] = s.get("seed")

    comparison = _comparison(rows)
    interpretation = (
        "Remote retrieve moves matmul CPU from TOOL_COMPUTE into HTTP_CLIENT I/O wait "
        "(mock round-trip), consistent with the search-locality ablation precedent."
        if comparison and all(c["tool_compute_delta_ms"] < 0 for c in comparison)
        else "Review paired deltas; causal claim requires matched retrieve call counts."
    )
    if args.backend != "openai":
        interpretation = (
            f"Backend: scripted (debug-only). {interpretation}"
        )

    total = run["totals"]["thread_cpu_ns"]
    artifact: dict[str, Any] = {
        "experiment": STEM,
        "result_validity": validity_for_real_agent_backend(args.backend),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "setup_ref": _load_setup_digest(),
        "git": _git_state(),
        "config": {
            "backend": args.backend,
            "seeds": seeds,
            "task_ids": [TASK_ID],
            "search_locality": LOCALITY_REMOTE,
            "retrieve_locality_arms": [LOCALITY_LOCAL, LOCALITY_REMOTE],
            "instr_version": 3,
            "comparison_type": "matched_pair_per_seed",
        },
        "run": run,
        "per_task": per_task,
        "per_task_wall_cpu": compute_per_task_wall_cpu(per_task, run["per_session"]),
        "session_rows": rows,
        "comparison": comparison,
        "interpretation": interpretation,
        "timer_overhead_ns_per_pair": measure_timer_overhead_ns(100_000),
        "reproduce_cmd": (
            "python -m apu_characterization.experiments.retrieve_locality_ablation "
            f"--backend {args.backend} --seeds {','.join(str(s) for s in seeds)}"
        ),
        "invariant": {
            "total_thread_cpu_ns": total,
            "residual_fraction": run.get("residual_fraction", 0),
            "pass": run.get("residual_fraction", 0) < RESIDUAL_LIMIT,
            "limit": RESIDUAL_LIMIT,
        },
    }
    apply_audit_to_artifact(artifact)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"{STEM}.json"
    json_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    md_path = write_report(artifact, OUT_DIR)
    print(f"json: {json_path}")
    print(f"md:   {md_path}")
    print(f"validity: {artifact['result_validity']}")


if __name__ == "__main__":
    main()
