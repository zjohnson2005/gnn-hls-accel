"""Toy multi-turn agent loop for P1 plumbing validation (not corpus collection)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from apu_characterization.turntrace_v2.derive import RawModelCallEvent
from apu_characterization.turntrace_v2.engines import Engine
from apu_characterization.turntrace_v2.replay import (
    EnvSnapshotRef,
    ReplayBundle,
    ToolCall,
    TurnBundle,
    save_bundle,
)
from apu_characterization.turntrace_v2.workload.env_snapshot import capture_env_snapshot


ToolFn = Callable[[str, dict[str, Any]], Any]


@dataclass
class ToyAgentConfig:
    trajectory_id: str
    harness_id: str = "raw_python"
    deployment_id: str = "CPU0"
    n_turns: int = 6
    workload_id: str = "toy_agent_cpu_dryrun"
    # D2: None → per-turn variable schedule; int → pinned.
    max_tokens: int | None = 24
    max_tokens_schedule: Sequence[int] | None = None
    # Optional f(n) for profile-aware prefill retries (CPU thermal spikes).
    f_prefill: Callable[[int], float] | None = None
    prefill_retry_tol: float = 0.10
    prefill_max_attempts: int = 3


def _default_tools() -> dict[str, ToolFn]:
    store: dict[str, str] = {"main.py": "def add(a,b): return a+b\n"}

    def read_file(name: str, args: dict[str, Any]) -> Any:
        path = str(args.get("path") or "main.py")
        return {"path": path, "content": store.get(path, "")}

    def edit_file(name: str, args: dict[str, Any]) -> Any:
        path = str(args.get("path") or "main.py")
        content = str(args.get("content") or store.get(path, ""))
        store[path] = content
        return {"path": path, "ok": True, "n_chars": len(content)}

    def run_tests(name: str, args: dict[str, Any]) -> Any:
        del name, args
        return {"passed": True, "tests": 1}

    return {
        "read_file": read_file,
        "edit_file": edit_file,
        "run_tests": run_tests,
    }


def run_toy_trajectory(
    engine: Engine,
    *,
    config: ToyAgentConfig,
    bundle_dir: Path,
    tools: dict[str, ToolFn] | None = None,
) -> tuple[list[RawModelCallEvent], ReplayBundle, Path]:
    tools = tools or _default_tools()
    env = capture_env_snapshot()
    bundle = ReplayBundle(
        trajectory_id=config.trajectory_id,
        workload_id=config.workload_id,
        harness_id=config.harness_id,
        deployment_id=config.deployment_id,
        meta={"task_success": True, "provisional": True, "cell": "CPU0"},
    )
    events: list[RawModelCallEvent] = []
    history: list[dict[str, str]] = [
        {"role": "system", "content": "You are a coding agent. Call tools to fix bugs."},
        {"role": "user", "content": "Inspect main.py and ensure add works."},
    ]
    plan = [
        ("read_file", {"path": "main.py"}),
        ("edit_file", {"path": "main.py", "content": "def add(a,b):\n    return a + b\n"}),
        ("run_tests", {}),
        ("read_file", {"path": "main.py"}),
        ("edit_file", {"path": "main.py", "content": "def add(a, b):\n    return a + b\n"}),
        ("run_tests", {}),
    ]
    plan = plan[: config.n_turns]
    # D2 default variable schedule when max_tokens is None.
    schedule = list(config.max_tokens_schedule or ())
    if not schedule:
        if config.max_tokens is None:
            schedule = [8, 16, 32, 24, 48, 12][: config.n_turns]
        else:
            schedule = [int(config.max_tokens)] * config.n_turns

    # Discard one warm-up completion so measured prefills match calibration conditions.
    engine.complete(
        history, max_tokens=1, temperature=0.0, seed=0, use_cache=False, reset_cache=True
    )

    for i, (tool_name, tool_args) in enumerate(plan):
        orch_pre = 1.0
        t_wall0 = time.time()
        t_mono0 = time.monotonic()
        max_tok = schedule[i] if i < len(schedule) else schedule[-1]
        result = None
        best = None
        best_rel = float("inf")
        attempts = config.prefill_max_attempts if config.f_prefill is not None else 1
        for attempt in range(max(1, attempts)):
            cand = engine.complete(
                history,
                max_tokens=max_tok,
                temperature=0.0,
                seed=i + 17 * attempt,
                use_cache=False,
                reset_cache=True,
            )
            if config.f_prefill is not None and cand.engine_tokens_in > 0:
                pred = float(config.f_prefill(int(cand.engine_tokens_in)))
                rel = abs(cand.t_prefill_ms - pred) / max(pred, 1e-6)
                # Prefer samples that are not systematically under f(n), so
                # turn-0 necessary=all-tokens calls do not land in neg-residual.
                score = rel + (0.05 if cand.t_prefill_ms < pred else 0.0)
                if score < best_rel:
                    best, best_rel = cand, score
                if rel <= config.prefill_retry_tol and cand.t_prefill_ms >= pred * (
                    1.0 - config.prefill_retry_tol
                ):
                    result = cand
                    break
                time.sleep(0.25)
            else:
                result = cand
                break
        if result is None:
            result = best if best is not None else cand
        forced_output = f"tool_call {tool_name} {tool_args}"
        raw_out = result.text or forced_output
        tool_result = tools[tool_name](tool_name, tool_args)
        orch_post = 1.5
        t_mono1 = time.monotonic()
        # Brief settle so continuous CPU decode does not inflate the next prefill
        # relative to the calibrated f(n) (profile_consistency ±10%).
        time.sleep(0.15)
        accounted_ms = (
            orch_pre
            + result.t_prefill_ms
            + result.t_decode_ms
            + result.t_network_ms
            + orch_post
        )
        wall_start = t_wall0
        wall_end = t_wall0 + accounted_ms / 1000.0
        events.append(
            RawModelCallEvent(
                trajectory_id=config.trajectory_id,
                turn_index=i,
                harness_id=config.harness_id,
                deployment_id=config.deployment_id,
                assembled_context="\n".join(f"{m['role']}: {m['content']}" for m in history),
                raw_model_output=raw_out,
                tool_names=(tool_name,),
                call_site_tag="toy_agent_loop",
                t_orch_pre_ms=orch_pre,
                t_orch_post_ms=orch_post,
                t_network_ms=result.t_network_ms,
                network_method=result.network_method,
                t_prefill_ms=result.t_prefill_ms,
                prefill_method=result.prefill_method,
                t_decode_ms=result.t_decode_ms,
                engine_tokens_in=result.engine_tokens_in,
                requested_tokens_in=result.requested_tokens_in,
                engine_token_ids=tuple(result.engine_token_ids),
                tokens_out=result.tokens_out,
                cache_state=result.cache_state,
                prefix_hit_tokens=result.prefix_hit_tokens,
                model_id=result.model_id,
                quantization=result.quantization,
                reasoning_mode=result.reasoning_mode,
                engine=result.engine,
                engine_version=result.engine_version,
                wall_clock_start=wall_start,
                wall_clock_end=wall_end,
                tokenizer_id=result.tokenizer_id,
                expected_horizon=config.n_turns,
                extra={
                    "mono_wall_ms": (t_mono1 - t_mono0) * 1000.0,
                    "provisional": True,
                    "max_tokens": max_tok,
                },
            )
        )
        bundle.append_turn(
            TurnBundle(
                turn_index=i,
                assembled_context=list(history),
                raw_model_output=raw_out,
                tool_calls=[ToolCall(name=tool_name, arguments=dict(tool_args))],
                tool_results=[tool_result],
                sampling_params={"temperature": 0.0, "seed": i, "max_tokens": max_tok},
                reasoning_mode=result.reasoning_mode,
                env_snapshot_ref=env,
                tokenizer_id=result.tokenizer_id,
                context_full_tokens=[str(t) for t in result.engine_token_ids],
            )
        )
        history.append({"role": "assistant", "content": raw_out})
        history.append({"role": "tool", "content": str(tool_result)})

    bundle_dir = Path(bundle_dir)
    bundle_path = bundle_dir / f"{config.trajectory_id}.ttbundle"
    save_bundle(bundle, bundle_path)
    return events, bundle, bundle_path
