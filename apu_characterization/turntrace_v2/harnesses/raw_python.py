"""Raw-Python harness adapter for TurnTrace v2 (first wiring priority)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from apu_characterization.turntrace_v2.derive import RawModelCallEvent
from apu_characterization.turntrace_v2.arms import ArmConfig, baseline
from apu_characterization.turntrace_v2.engines import Engine
from apu_characterization.turntrace_v2.replay import (
    EnvSnapshotRef,
    ReplayBundle,
    ToolCall,
    TurnBundle,
)
from apu_characterization.turntrace_v2.workload.env_snapshot import capture_env_snapshot


ToolFn = Callable[[str, dict[str, Any]], Any]


@dataclass
class HarnessTurn:
    messages: list[dict[str, str]]
    tool_name: str | None
    tool_args: dict[str, Any]
    call_site_tag: str = "raw_python"
    fanout_tools: list[tuple[str, dict[str, Any]]] | None = None


class RawPythonHarness:
    """We control every call site — fastest path to correct instrumentation."""

    harness_id = "raw_python"

    def __init__(
        self,
        engine: Engine,
        *,
        tools: dict[str, ToolFn] | None = None,
        arm_config: ArmConfig | None = None,
    ) -> None:
        self.engine = engine
        self.tools = tools or {}
        self.arm_config = arm_config or baseline()

    def run_trajectory(
        self,
        *,
        trajectory_id: str,
        deployment_id: str,
        turns: Sequence[HarnessTurn],
        workload_id: str,
        env: EnvSnapshotRef | None = None,
        pair_id: str = "",
    ) -> tuple[list[RawModelCallEvent], ReplayBundle]:
        env = env or capture_env_snapshot()
        bundle = ReplayBundle(
            trajectory_id=trajectory_id,
            workload_id=workload_id,
            harness_id=self.harness_id,
            deployment_id=deployment_id,
            meta={
                "arm": self.arm_config.arm,
                "interventions_active": list(self.arm_config.interventions_active),
                "pair_id": pair_id,
                "causal_class": self.arm_config.causal_class,
            },
        )
        events: list[RawModelCallEvent] = []
        history: list[dict[str, str]] = []
        for i, turn in enumerate(turns):
            orch_pre_start = time.perf_counter()
            prior_history = history
            history = list(turn.messages)
            append_violation = bool(
                self.arm_config.append_only
                and i > 0
                and history[: len(prior_history)] != prior_history
            )
            assembled_context = "\n".join(
                f"{m['role']}: {m['content']}" for m in history
            )
            orch_pre = max(0.0, (time.perf_counter() - orch_pre_start) * 1000.0)
            t0 = time.time()
            result = self.engine.complete(
                history,
                max_tokens=64,
                temperature=0.0,
                seed=i,
                use_cache=self.arm_config.use_cache,
                reset_cache=i == 0 and self.arm_config.use_cache,
            )
            orch_post_start = time.perf_counter()
            tool_names: tuple[str, ...] = ()
            tool_calls: list[ToolCall] = []
            tool_results: list[Any] = []
            if turn.fanout_tools:
                for name, args in turn.fanout_tools:
                    tool_names += (name,)
                    tool_calls.append(ToolCall(name=name, arguments=dict(args)))
                    tool_results.append(
                        self.tools[name](name, args)
                        if name in self.tools
                        else {"error": "unknown_tool"}
                    )
            elif turn.tool_name:
                tool_names = (turn.tool_name,)
                tool_calls = [ToolCall(name=turn.tool_name, arguments=dict(turn.tool_args))]
                if turn.tool_name in self.tools:
                    tool_results = [self.tools[turn.tool_name](turn.tool_name, turn.tool_args)]
                else:
                    tool_results = [{"error": "unknown_tool"}]
            orch_post = max(0.0, (time.perf_counter() - orch_post_start) * 1000.0)
            accounted = (
                orch_pre
                + result.t_prefill_ms
                + result.t_decode_ms
                + result.t_network_ms
                + orch_post
            )
            events.append(
                RawModelCallEvent(
                    trajectory_id=trajectory_id,
                    turn_index=i,
                    harness_id=self.harness_id,
                    deployment_id=deployment_id,
                    assembled_context=assembled_context,
                    raw_model_output=result.text,
                    tool_names=tool_names,
                    call_site_tag=turn.call_site_tag,
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
                    wall_clock_start=t0,
                    wall_clock_end=t0 + accounted / 1000.0,
                    tokenizer_id=result.tokenizer_id,
                    expected_horizon=len(turns),
                    arm=self.arm_config.arm,
                    interventions_active=self.arm_config.interventions_active,
                    pair_id=pair_id,
                    provider_cached_tokens=result.provider_cached_tokens,
                    extra={
                        "append_discipline_violated": append_violation,
                        "causal_class": self.arm_config.causal_class,
                    },
                )
            )
            bundle.append_turn(
                TurnBundle(
                    turn_index=i,
                    assembled_context=list(history),
                    raw_model_output=result.text,
                    tool_calls=tool_calls,
                    tool_results=tool_results,
                    sampling_params={"temperature": 0.0, "seed": i, "max_tokens": 64},
                    reasoning_mode=result.reasoning_mode,
                    env_snapshot_ref=env,
                    tokenizer_id=result.tokenizer_id,
                )
            )
        return events, bundle
