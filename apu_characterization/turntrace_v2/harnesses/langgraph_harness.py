"""LangGraph harness adapter — exercises graph-node semantic labels."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from apu_characterization.turntrace_v2.derive import RawModelCallEvent
from apu_characterization.turntrace_v2.arms import ArmConfig, baseline
from apu_characterization.turntrace_v2.engines import Engine
from apu_characterization.turntrace_v2.replay import ReplayBundle, ToolCall, TurnBundle
from apu_characterization.turntrace_v2.workload.env_snapshot import capture_env_snapshot

ToolFn = Callable[[str, dict[str, Any]], Any]


@dataclass
class GraphStep:
    """One model call issued from a named graph node."""

    node_name: str
    messages: list[dict[str, str]]
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    fanout_tools: list[tuple[str, dict[str, Any]]] | None = None


class LangGraphHarness:
    """Minimal LangGraph-shaped loop without requiring langgraph at import time.

    When langgraph is installed, ``run_with_langgraph`` can wrap a real StateGraph.
    Edge cases (batched tool-result messages, etc.) are logged to boundary-cases.md
    rather than silently special-cased here.
    """

    harness_id = "langgraph"

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
        steps: Sequence[GraphStep],
        workload_id: str,
        pair_id: str = "",
    ) -> tuple[list[RawModelCallEvent], ReplayBundle]:
        env = capture_env_snapshot()
        bundle = ReplayBundle(
            trajectory_id=trajectory_id,
            workload_id=workload_id,
            harness_id=self.harness_id,
            deployment_id=deployment_id,
            meta={
                "graph": True,
                "arm": self.arm_config.arm,
                "interventions_active": list(self.arm_config.interventions_active),
                "pair_id": pair_id,
                "causal_class": self.arm_config.causal_class,
            },
        )
        events: list[RawModelCallEvent] = []
        prior_messages: list[dict[str, str]] = []
        for i, step in enumerate(steps):
            orch_pre_start = time.perf_counter()
            messages = list(step.messages)
            append_violation = bool(
                self.arm_config.append_only
                and i > 0
                and messages[: len(prior_messages)] != prior_messages
            )
            assembled_context = "\n".join(
                f"{m['role']}: {m['content']}" for m in messages
            )
            orch_pre = max(0.0, (time.perf_counter() - orch_pre_start) * 1000.0)
            t0 = time.time()
            result = self.engine.complete(
                messages,
                max_tokens=64,
                temperature=0.0,
                seed=i,
                use_cache=self.arm_config.use_cache,
                reset_cache=i == 0 and self.arm_config.use_cache,
            )
            orch_post_start = time.perf_counter()
            tool_names: list[str] = []
            tool_calls: list[ToolCall] = []
            tool_results: list[Any] = []
            if step.fanout_tools:
                # One LLM decision → multiple sibling tool calls (fanout_siblings).
                for name, args in step.fanout_tools:
                    tool_names.append(name)
                    tool_calls.append(ToolCall(name=name, arguments=dict(args)))
                    tool_results.append(
                        self.tools[name](name, args) if name in self.tools else {"error": "unknown"}
                    )
            elif step.tool_name:
                tool_names = [step.tool_name]
                args = dict(step.tool_args or {})
                tool_calls = [ToolCall(name=step.tool_name, arguments=args)]
                tool_results = [
                    self.tools[step.tool_name](step.tool_name, args)
                    if step.tool_name in self.tools
                    else {"error": "unknown"}
                ]
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
                    tool_names=tuple(tool_names),
                    graph_node=step.node_name,
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
                    expected_horizon=len(steps),
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
                    assembled_context=list(step.messages),
                    raw_model_output=result.text,
                    tool_calls=tool_calls,
                    tool_results=tool_results,
                    sampling_params={"temperature": 0.0, "seed": i, "max_tokens": 64},
                    reasoning_mode=result.reasoning_mode,
                    env_snapshot_ref=env,
                    tokenizer_id=result.tokenizer_id,
                )
            )
            prior_messages = messages
        return events, bundle
