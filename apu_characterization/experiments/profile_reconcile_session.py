"""Profile one heavy session with normal instrumentation (py-spy wraps this via run_profile_lh01_wsl.sh)."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from apu_characterization.experiments.real_agent_breakdown import (
    RESIDUAL_LIMIT,
    _env_info,
    _git_state,
    _load_setup_digest,
    _require_langgraph,
    build_langchain_tools,
    run_real_session,
)
from apu_characterization.instr import RunAccumulator, install_gc_hooks
from apu_characterization.profiles import LOCALITY_ABLATION_PROFILE
from apu_characterization.tasks import assign_task
from apu_characterization.tools import LOCALITY_REMOTE, reset_tool_locality, set_tool_locality


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-index", type=int, default=0, help="Session index in mixed profile")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--backend", choices=("scripted", "openai"), default="openai")
    parser.add_argument(
        "--allow-synthetic-test",
        action="store_true",
        help="Allow scripted backend (NOT verifiable; instrumentation test only)",
    )
    parser.add_argument("--instr-version", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("apu_characterization/out"))
    args = parser.parse_args()

    _require_langgraph()
    if args.backend == "scripted" and not args.allow_synthetic_test:
        raise SystemExit(
            "Refusing scripted backend for profile runs. Verifiable reconcile profiling "
            "requires --backend openai (see VERIFIABLE_DATA.md). "
            "Pass --allow-synthetic-test only for instrumentation smoke tests."
        )
    if args.backend == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required for openai backend")

    spec = LOCALITY_ABLATION_PROFILE
    install_gc_hooks()
    if args.instr_version >= 2:
        from apu_characterization.harness.thread_hooks import install_thread_hooks

        install_thread_hooks()
    tools = build_langchain_tools()
    acc = RunAccumulator(profile=spec.name, instr_version=args.instr_version)
    task = assign_task("mixed", args.seed, args.task_index)
    sid = "profile_0"
    args.out.mkdir(parents=True, exist_ok=True)

    tok = set_tool_locality(search=LOCALITY_REMOTE)
    try:
        sess = run_real_session(
            acc,
            sid,
            task,
            spec,
            args.seed,
            args.backend,
            0.05,
            tools,
            instr_version=args.instr_version,
        )
    finally:
        reset_tool_locality(tok)

    total = sess["process_cpu_ns"]
    run = acc.to_run_dict(
        env=_env_info(),
        config={"instr_version": args.instr_version, "task_id": task.task_id},
        total_thread_cpu_ns=total,
        total_wall_ns=int(sess["wall_s"] * 1e9),
        os_times={},
        per_session=[sess],
    )
    artifact = {
        "experiment": "profile_reconcile_session",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "setup_ref": _load_setup_digest(),
        "git": _git_state(),
        "task_id": task.task_id,
        "run": run,
        "session": sess,
        "residual_limit": RESIDUAL_LIMIT,
    }
    json_path = args.out / f"profile_{task.task_id.lower()}_s{args.seed}.json"
    json_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"task: {task.task_id}")
    print(f"host_cpu_ms: {sess['process_cpu_ns'] / 1e6:.1f}")
    print(f"reconcile_ms: {sess.get('reconcile_cpu_ns', 0) / 1e6:.1f}")
    print(f"residual_unattributed_ms: {sess.get('residual_unattributed_cpu_ns', 0) / 1e6:.1f}")
    print(f"artifact: {json_path}")


if __name__ == "__main__":
    main()
