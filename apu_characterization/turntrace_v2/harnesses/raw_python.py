"""Raw-Python harness adapter for TurnTrace v2 (first wiring priority)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from apu_characterization.turntrace_v2.derive import RawModelCallEvent
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


class RawPythonHarness:
    """We control every call site — fastest path to correct instrumentation."""

    harness_id = "raw_python"

    def __init__(self, engine: Engine, *, tools: dict[str, ToolFn] | None = None) -> None:
        self.engine = engine
        self.tools = tools or {}

    def run_trajectory(
        self,
        *,
        trajectory_id: str,
        deployment_id: str,
        turns: Sequence[HarnessTurn],
        workload_id: str,
        env: EnvSnapshotRef | None = None,
    ) -> tuple[list[RawModelCallEvent], ReplayBundle]:
        env = env or capture_env_snapshot()
        bundle = ReplayBundle(
            trajectory_id=trajectory_id,
            workload_id=workload_id,
            harness_id=self.harness_id,
            deployment_id=deployment_id,
            meta={},
        )
        events: list[RawModelCallEvent] = []
        history: list[dict[str, str]] = []
        for i, turn in enumerate(turns):
            history = list(turn.messages)
            orch_pre = 1.0
            t0 = time.time()
            result = self.engine.complete(history, max_tokens=64, temperature=0.0, seed=i)
            tool_names: tuple[str, ...] = ()
            tool_calls: list[ToolCall] = []
            tool_results: list[Any] = []
            if turn.tool_name:
                tool_names = (turn.tool_name,)
                tool_calls = [ToolCall(name=turn.tool_name, arguments=dict(turn.tool_args))]
                if turn.tool_name in self.tools:
                    tool_results = [self.tools[turn.tool_name](turn.tool_name, turn.tool_args)]
                else:
                    tool_results = [{"error": "unknown_tool"}]
            orch_post = 1.5
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
                    assembled_context="\n".join(f"{m['role']}: {m['content']}" for m in history),
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
