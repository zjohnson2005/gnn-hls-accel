"""Replication batch: n seeds per configuration, medians and IQR.

Run remote search on Linux after test_resolution PASS (locality_ablation payload, 4 KB tool cap):

  python -m apu_characterization.experiments.replication_batch \\
      --backend openai --profile mixed --seeds 0,1,2,3,4 \\
      --search-locality remote --allow-dirty

Artifacts: out/replication_remote_search.json / .md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..audit import apply_audit_to_artifact, apply_audit_to_replication_batch
from ..artifact_refresh import refresh_replication_batch, write_replication_markdown
from ..setup_validate import load_and_validate
from ..stats import aggregate_replication_runs, batch_attribution_summary
from ..validity import DEBUG_ONLY, PUBLISHABLE
from .real_agent_breakdown import (
    RESIDUAL_LIMIT,
    _env_info,
    _git_state,
    _load_setup_digest,
    _require_langgraph,
    run_real_batch,
)


def _run_one_seed(
    seed: int,
    profile: str,
    backend: str,
    search_locality: str,
    sessions: int,
    llm_scale: float,
    payload_profile: str | None,
) -> dict[str, Any]:
    from ..amenability import compute_category_averages, compute_per_task, compute_per_task_wall_cpu
    from ..behavior import summarize_behavior_buckets
    from ..instr import measure_timer_overhead_ns
    from ..profiles import LOCALITY_ABLATION_PROFILE
    from ..tasks import assign_task
    from ..validity import validity_for_real_agent_backend

    t0 = time.perf_counter()
    run = run_real_batch(
        sessions,
        profile,
        seed,
        backend,
        llm_scale,
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("scripted", "openai"), default="scripted")
    parser.add_argument("--profile", default="mixed")
    parser.add_argument("--seeds", default="0,1,2,3,4")
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--search-locality", default="remote", dest="search_locality")
    parser.add_argument("--payload-profile", default=None, dest="payload_profile")
    parser.add_argument("--llm-scale", type=float, default=0.05, dest="llm_scale")
    parser.add_argument("--out", type=Path, default=Path("apu_characterization/out"))
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument(
        "--refresh-only",
        action="store_true",
        help="Recompute ORCH split, aggregates, and audit from existing JSON (no OpenAI)",
    )
    parser.add_argument(
        "--refresh-json",
        type=Path,
        default=None,
        help="JSON to refresh (default: out/replication_{search_locality}_search.json)",
    )
    args = parser.parse_args()

    if args.refresh_only:
        stem = f"replication_{args.search_locality}_search"
        json_path = args.refresh_json or (args.out / f"{stem}.json")
        if not json_path.is_file():
            raise SystemExit(f"refresh input missing: {json_path}")
        combined = refresh_replication_batch(
            json_path, out_dir=args.out, allow_dirty=args.allow_dirty
        )
        audit = combined.get("audit", {})
        git = combined.get("git") or {}
        print(f"refreshed: {json_path}")
        print(f"git: commit={git.get('commit', '?')[:12]} dirty={git.get('dirty')}")
        print(f"audit pass: {audit.get('pass')}, validity: {combined['result_validity']}")
        print(f"publishable_ok: {audit.get('publishable_ok')}")
        stats = combined.get("_refresh_stats", {})
        print(f"sessions backfilled: {stats.get('sessions_backfilled', 0)}")
        for v in audit.get("violations") or []:
            print(f"  VIOLATION: {v}")
        for w in (audit.get("repro") or {}).get("warnings") or []:
            print(f"  REPRO: {w}")
        if not audit.get("pass"):
            if git.get("dirty") == "yes" and not args.allow_dirty:
                print(
                    "\nHint: commit your changes, then re-run --refresh-only "
                    "(refresh re-stamps git from the current tree)."
                )
            sys.exit(1)
        return

    load_and_validate(strict=not args.allow_dirty)
    _require_langgraph()

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    if len(seeds) < 5 and args.backend == "openai":
        print(f"WARNING: only {len(seeds)} seeds; replication standard is n≥5")

    per_seed = [
        _run_one_seed(
            seed,
            args.profile,
            args.backend,
            args.search_locality,
            args.sessions,
            args.llm_scale,
            args.payload_profile,
        )
        for seed in seeds
    ]

    aggregate = aggregate_replication_runs(per_seed)
    validity = DEBUG_ONLY if args.backend != "openai" else PUBLISHABLE
    stem = f"replication_{args.search_locality}_search"

    combined: dict[str, Any] = {
        "experiment": "replication_batch",
        "result_validity": validity,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "setup_ref": _load_setup_digest(),
        "git": _git_state(),
        "env": _env_info(),
        "config": {
            "profile": args.profile,
            "search_locality": args.search_locality,
            "seeds": seeds,
            "sessions": args.sessions,
            "backend": args.backend,
            "comparison_type": "distribution_over_seeds",
            "allow_dirty": bool(args.allow_dirty),
        },
        "aggregate": aggregate,
        "per_seed_artifacts": per_seed,
    }
    apply_audit_to_replication_batch(combined, allow_dirty=args.allow_dirty)

    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / f"{stem}.json"
    json_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")

    audit = combined.get("audit", {})
    md_path = args.out / f"{stem}.md"
    md_path.write_text(
        write_replication_markdown(
            combined, json_path=json_path, search_locality=args.search_locality
        ),
        encoding="utf-8",
    )

    print(f"json: {json_path}")
    print(f"md:   {md_path}")
    print(f"audit pass: {audit.get('pass')}, validity: {combined['result_validity']}")
    print(f"seeds: {len(seeds)}, TOOL median {aggregate['pooled_tool_compute_pct']['median']:.1f}%")
    if not audit.get("pass"):
        sys.exit(1)


if __name__ == "__main__":
    main()
