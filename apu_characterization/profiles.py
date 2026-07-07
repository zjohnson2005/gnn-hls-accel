"""Task profiles: distributions over turns, tool mix, payload sizes."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

ToolName = Literal["search", "code_exec", "retrieve", "calculator"]


@dataclass(frozen=True)
class ProfileSpec:
    name: str
    turns_min: int
    turns_max: int
    tool_weights: dict[ToolName, float]
    llm_median_s: float
    llm_sigma: float
    llm_response_kb_min: float
    llm_response_kb_max: float
    tool_result_kb_min: float
    tool_result_kb_max: float
    tool_rate: float  # probability of tool call per turn (except final)


PROFILES: dict[str, ProfileSpec] = {
    "search_heavy": ProfileSpec(
        name="search_heavy",
        turns_min=8,
        turns_max=15,
        tool_weights={"search": 0.80, "code_exec": 0.05, "retrieve": 0.10, "calculator": 0.05},
        llm_median_s=1.8,
        llm_sigma=0.6,
        llm_response_kb_min=0.5,
        llm_response_kb_max=2.0,
        tool_result_kb_min=1.0,
        tool_result_kb_max=20.0,
        tool_rate=0.85,
    ),
    "code_heavy": ProfileSpec(
        name="code_heavy",
        turns_min=4,
        turns_max=8,
        tool_weights={"search": 0.10, "code_exec": 0.70, "retrieve": 0.10, "calculator": 0.10},
        llm_median_s=1.8,
        llm_sigma=0.6,
        llm_response_kb_min=0.5,
        llm_response_kb_max=3.0,
        tool_result_kb_min=2.0,
        tool_result_kb_max=30.0,
        tool_rate=0.75,
    ),
    "rag_heavy": ProfileSpec(
        name="rag_heavy",
        turns_min=5,
        turns_max=10,
        tool_weights={"search": 0.10, "code_exec": 0.05, "retrieve": 0.70, "calculator": 0.15},
        llm_median_s=1.8,
        llm_sigma=0.6,
        llm_response_kb_min=1.0,
        llm_response_kb_max=4.0,
        tool_result_kb_min=50.0,
        tool_result_kb_max=200.0,
        tool_rate=0.80,
    ),
    "reasoning_heavy": ProfileSpec(
        name="reasoning_heavy",
        turns_min=3,
        turns_max=6,
        tool_weights={"search": 0.25, "code_exec": 0.25, "retrieve": 0.25, "calculator": 0.25},
        llm_median_s=4.0,
        llm_sigma=0.6,
        llm_response_kb_min=2.0,
        llm_response_kb_max=8.0,
        tool_result_kb_min=1.0,
        tool_result_kb_max=10.0,
        tool_rate=0.20,
    ),
    "mixed": ProfileSpec(
        name="mixed",
        turns_min=5,
        turns_max=12,
        tool_weights={"search": 0.25, "code_exec": 0.25, "retrieve": 0.25, "calculator": 0.25},
        llm_median_s=1.8,
        llm_sigma=0.6,
        llm_response_kb_min=0.5,
        llm_response_kb_max=4.0,
        tool_result_kb_min=1.0,
        tool_result_kb_max=100.0,
        tool_rate=0.60,
    ),
    # Structural archetypes: turn structure comes from the scripted task, so
    # turns_min/max, tool_weights, and tool_rate are informational here; the
    # payload and latency fields still drive drawn sizes.
    "long_horizon": ProfileSpec(
        name="long_horizon",
        turns_min=10,
        turns_max=15,
        tool_weights={"search": 0.1, "code_exec": 0.0, "retrieve": 0.8, "calculator": 0.1},
        llm_median_s=1.8,
        llm_sigma=0.6,
        llm_response_kb_min=0.5,
        llm_response_kb_max=2.0,
        tool_result_kb_min=5.0,
        tool_result_kb_max=30.0,
        tool_rate=0.75,
    ),
    "fanout": ProfileSpec(
        name="fanout",
        turns_min=2,
        turns_max=2,
        tool_weights={"search": 1.0, "code_exec": 0.0, "retrieve": 0.0, "calculator": 0.0},
        llm_median_s=1.8,
        llm_sigma=0.6,
        llm_response_kb_min=0.5,
        llm_response_kb_max=2.0,
        tool_result_kb_min=1.0,
        tool_result_kb_max=10.0,
        tool_rate=1.0,
    ),
    "chain": ProfileSpec(
        name="chain",
        turns_min=4,
        turns_max=4,
        tool_weights={"search": 0.0, "code_exec": 0.34, "retrieve": 0.33, "calculator": 0.33},
        llm_median_s=1.8,
        llm_sigma=0.6,
        llm_response_kb_min=0.5,
        llm_response_kb_max=2.0,
        tool_result_kb_min=1.0,
        tool_result_kb_max=10.0,
        tool_rate=0.75,
    ),
    "swarm": ProfileSpec(
        name="swarm",
        turns_min=2,
        turns_max=4,
        tool_weights={"search": 0.6, "code_exec": 0.0, "retrieve": 0.4, "calculator": 0.0},
        llm_median_s=1.8,
        llm_sigma=0.6,
        llm_response_kb_min=0.5,
        llm_response_kb_max=2.0,
        tool_result_kb_min=1.0,
        tool_result_kb_max=20.0,
        tool_rate=0.75,
    ),
    "structured_output": ProfileSpec(
        name="structured_output",
        turns_min=7,
        turns_max=7,
        tool_weights={"search": 0.0, "code_exec": 0.0, "retrieve": 1.0, "calculator": 0.0},
        llm_median_s=1.8,
        llm_sigma=0.6,
        llm_response_kb_min=0.5,
        llm_response_kb_max=1.0,
        tool_result_kb_min=5.0,
        tool_result_kb_max=50.0,
        tool_rate=0.3,
    ),
    "api_heavy": ProfileSpec(
        name="api_heavy",
        turns_min=6,
        turns_max=6,
        tool_weights={"search": 0.0, "code_exec": 0.0, "retrieve": 0.0, "calculator": 1.0},
        llm_median_s=1.8,
        llm_sigma=0.6,
        llm_response_kb_min=0.2,
        llm_response_kb_max=1.0,
        tool_result_kb_min=0.5,
        tool_result_kb_max=2.0,
        tool_rate=1.0,
    ),
    # Tool-locality ablation: caps synthetic tool-result padding so multi-tool
    # OpenAI sessions stay under gpt-4o-mini 128k context. Local vs remote
    # search CPU comparison is unchanged (padding is identical across arms).
    "locality_ablation": ProfileSpec(
        name="locality_ablation",
        turns_min=5,
        turns_max=12,
        tool_weights={"search": 0.25, "code_exec": 0.25, "retrieve": 0.25, "calculator": 0.25},
        llm_median_s=1.8,
        llm_sigma=0.6,
        llm_response_kb_min=0.5,
        llm_response_kb_max=2.0,
        tool_result_kb_min=0.25,
        tool_result_kb_max=4.0,
        tool_rate=0.60,
    ),
}


LOCALITY_ABLATION_PROFILE = PROFILES["locality_ablation"]


def sample_turn_count(rng: random.Random, spec: ProfileSpec) -> int:
    return rng.randint(spec.turns_min, spec.turns_max)


def sample_tool(rng: random.Random, spec: ProfileSpec) -> ToolName:
    tools = list(spec.tool_weights.keys())
    weights = [spec.tool_weights[t] for t in tools]
    return rng.choices(tools, weights=weights, k=1)[0]


def sample_payload_kb(rng: random.Random, lo: float, hi: float) -> int:
    if hi <= lo:
        return max(1, int(lo * 1024))
    val = rng.uniform(lo, hi)
    return max(512, int(val * 1024))


def build_scripted_plan(
    rng: random.Random,
    spec: ProfileSpec,
) -> list[dict]:
    """Deterministic per-seed decision sequence for one agent session."""
    n_turns = sample_turn_count(rng, spec)
    plan: list[dict] = []
    for turn in range(n_turns):
        is_last = turn == n_turns - 1
        use_tool = (not is_last) and (rng.random() < spec.tool_rate)
        entry: dict = {
            "turn": turn,
            "finish": is_last or not use_tool,
            "response_bytes": sample_payload_kb(rng, spec.llm_response_kb_min, spec.llm_response_kb_max),
        }
        if use_tool and not is_last:
            entry["tool"] = sample_tool(rng, spec)
            entry["tool_result_bytes"] = sample_payload_kb(
                rng, spec.tool_result_kb_min, spec.tool_result_kb_max
            )
        plan.append(entry)
    return plan
