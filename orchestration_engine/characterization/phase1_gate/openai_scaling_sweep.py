"""Run real OpenAI scaling anchors at c=100 and c=500 (and full methodology ladder)."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from orchestration_engine.characterization.analyze import analyze_profile, format_markdown_table
from orchestration_engine.characterization.langgraph_react.agent import run_concurrent
from orchestration_engine.characterization.langgraph_react.study import openai_key_configured
from orchestration_engine.characterization.phase1_gate.gate_report import run_gate
from orchestration_engine.characterization.phase1_gate.scaling_regime import (
    build_scaling_regime_report,
    render_scaling_regime_markdown,
)
from orchestration_engine.characterization.trace_io import save_trace

GATE_DIR = Path("orchestration_engine/characterization/out/gate")
DEFAULT_LEVELS = [1, 10, 20, 100, 500]


def _estimate_calls(concurrency: int, steps: int = 10) -> int:
    """Rough LLM calls: agent loop ~ (steps tool rounds + 1 final)."""
    return concurrency * (steps + 1)


def _estimate_minutes(
    concurrency: int,
    *,
    steps: int,
    max_workers: int,
    sec_per_llm_call: float = 2.5,
) -> float:
    calls_per_agent = steps + 1
    serial_agent_s = calls_per_agent * sec_per_llm_call
    return (concurrency / max(1, max_workers)) * serial_agent_s / 60.0


def _rpm_safe_workers(
    requested: int,
    *,
    rpm_limit: int | None = None,
    concurrency: int = 1,
) -> int:
    """Conservative worker cap; global RPM limiter handles request pacing."""
    limit = rpm_limit or int(os.getenv("OE_OPENAI_RPM_LIMIT", "500"))
    # Keep modest parallelism; limiter spaces LLM calls globally.
    cap = max(4, min(requested, limit // 60, concurrency, 12))
    return max(1, cap)


def run_levels(
    levels: list[int],
    *,
    force: bool = False,
    max_workers: int | None = None,
    react_steps: int | None = None,
    task: str | None = None,
    rpm_safe: bool = True,
    repeats: int = 1,
) -> list[Path]:
    if not openai_key_configured():
        raise SystemExit(
            "OPENAI_API_KEY not set. Set a valid key in this shell before running."
        )

    GATE_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    steps = react_steps or int(os.getenv("OE_OPENAI_REACT_STEPS", "10"))
    workers = max_workers or int(os.getenv("OE_OPENAI_MAX_WORKERS", "16"))

    print("OpenAI scaling sweep — TRUE parallel workers enabled.")
    print(f"Levels: {levels}")
    print(f"Parallel workers: {workers}")
    print(f"ReAct steps per agent: {steps}")
    if task:
        print("Using short task prompt (--fast)")

    for conc in levels:
        out = GATE_DIR / f"openai_action_heavy_c{conc}.json"
        if out.is_file() and not force:
            print(f"\nc={conc}: using cached {out.name}")
            saved.append(out)
            continue

        est_calls = _estimate_calls(conc, steps)
        level_workers = workers
        if rpm_safe:
            level_workers = _rpm_safe_workers(workers, concurrency=conc)
            if level_workers < workers:
                rpm = int(os.getenv("OE_OPENAI_RPM_LIMIT", "500"))
                headroom = float(os.getenv("OE_OPENAI_RPM_HEADROOM", "0.8"))
                print(
                    f"  RPM-safe: capping workers {workers} -> {level_workers} "
                    f"(global limiter ~{int(rpm * headroom)} req/min)"
                )
        est_min = _estimate_minutes(conc, steps=steps, max_workers=level_workers)
        print(
            f"\nc={conc}: ~{est_calls * repeats} LLM calls"
            + (f" ({repeats} repeats)" if repeats > 1 else "")
            + f", est. {est_min * repeats:.0f}–{est_min * repeats * 2:.0f} min "
            "(depends on API latency)..."
        )

        level_pcts: list[float] = []
        for r in range(repeats):
            t0 = time.perf_counter()
            last_progress = [-1]

            def _on_agent_done(done: int, total: int, *, _last=last_progress) -> None:
                step = max(1, total // 20)
                if done == total or done - _last[0] >= step:
                    _last[0] = done
                    elapsed = time.perf_counter() - t0
                    print(
                        f"    progress: {done}/{total} agents ({elapsed / 60:.1f} min)",
                        flush=True,
                    )

            try:
                prof = run_concurrent(
                    preset="action_heavy",
                    backend="openai",
                    concurrency=conc,
                    calibrated=False,
                    wall_clock=True,
                    max_workers=level_workers,
                    react_steps_override=react_steps,
                    task=task,
                    on_agent_done=_on_agent_done,
                )
            except KeyboardInterrupt:
                print(f"  interrupted c={conc} rep{r} — saved repeats kept on disk")
                raise
            except Exception as exc:
                print(f"  FAILED c={conc} rep{r}: {exc}")
                continue

            anomaly = int(prof.meta.get("wall_anomaly_agents", "0"))
            if anomaly:
                print(
                    f"  DISCARDED c={conc} rep{r}: {anomaly} agent(s) had a step "
                    f">{os.getenv('OE_MAX_STEP_WALL_S', '300')}s wall gap "
                    "(host slept/hibernated mid-run?) — trace not saved."
                )
                continue

            prof.name = f"langgraph_openai_action_heavy_c{conc}"
            prof.meta["backend"] = "openai"
            prof.meta["sweep"] = "openai_scaling"
            prof.meta["repeat_index"] = str(r)
            if react_steps:
                prof.meta["react_steps_override"] = str(react_steps)
            if task:
                prof.meta["task_prompt"] = task
            prof.meta["parallel_workers"] = str(level_workers)
            if r == 0:
                save_trace(prof, out)
                saved.append(out)
            if repeats > 1:
                rep_path = GATE_DIR / f"openai_action_heavy_c{conc}_rep{r}.json"
                save_trace(prof, rep_path)

            rep = analyze_profile(prof)
            level_pcts.append(rep.orchestration_pct_of_accelerable_cpu)
            elapsed = time.perf_counter() - t0
            tag = f" rep{r}" if repeats > 1 else ""
            print(
                f"  done{tag} in {elapsed/60:.1f} min | orch/accel {rep.orchestration_pct_of_accelerable_cpu:.1f}% | "
                f"ms/agent {prof.meta.get('orch_ms_per_agent', '?')} | "
                f"workers {prof.meta.get('parallel_workers', '?')} | "
                f"-> {out.name}"
            )

        if len(level_pcts) > 1:
            n = len(level_pcts)
            mean = sum(level_pcts) / n
            std = (sum((x - mean) ** 2 for x in level_pcts) / (n - 1)) ** 0.5
            print(f"  c={conc} across {n} repeats: {mean:.1f}% ±{std:.1f}")

    return saved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Real OpenAI scaling anchors (c=100, c=500) — resolves headline regime"
    )
    parser.add_argument(
        "--levels",
        default="100,500",
        help="Comma-separated concurrency levels (default: 100,500)",
    )
    parser.add_argument(
        "--full-ladder",
        action="store_true",
        help="Run 1,10,20,100,500 with --force — required before citing scaling curve in a paper",
    )
    parser.add_argument("--force", action="store_true", help="Ignore cached traces")
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument(
        "--react-steps",
        type=int,
        default=None,
        help="Shorter agent (e.g. 4). Default: 10 or OE_OPENAI_REACT_STEPS.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="4 ReAct steps + 32 workers + short task (~5x faster than default).",
    )
    parser.add_argument(
        "--no-rpm-safe",
        action="store_true",
        help="Do not cap workers to OpenAI RPM (may 429 on c>=500).",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Repeat each level N times for error bars (recommend 10 for c=1, 3 for c>=100).",
    )
    parser.add_argument("--skip-gate", action="store_true", help="Only run traces, skip gate report")
    args = parser.parse_args()

    if args.full_ladder:
        levels = DEFAULT_LEVELS
        force = True
    else:
        levels = [int(x) for x in args.levels.split(",") if x.strip()]
        force = args.force

    max_workers = args.max_workers
    react_steps = args.react_steps
    task = None
    if args.fast:
        max_workers = max_workers or 32
        react_steps = react_steps or 4
        task = "Search once and summarize in one sentence."

    if max_workers is None and os.getenv("OE_OPENAI_MAX_WORKERS"):
        max_workers = int(os.getenv("OE_OPENAI_MAX_WORKERS", "16"))

    run_levels(
        levels,
        force=force,
        max_workers=max_workers,
        react_steps=react_steps,
        task=task,
        rpm_safe=not args.no_rpm_safe,
        repeats=max(1, args.repeats),
    )

    if args.skip_gate:
        return 0

    # Regenerate gate + scaling regime summary
    run_gate(run_extended=False, run_openai=False)
    print("\nGate report updated. See out/gate/gate_report.md section 10.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
